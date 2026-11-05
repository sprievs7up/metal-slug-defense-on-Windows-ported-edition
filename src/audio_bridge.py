"""OpenSL ES PCM buffer-queue adapter for the original ARM mixer.

Guest buffers are copied synchronously on Enqueue. The ARM callback is invoked
only by pump(), between top-level guest calls on the owning emulation thread.
No waveOut thread is allowed to enter Unicorn or retain a guest memory pointer.
"""
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import struct
import threading
import wave
from audio_output import WaveOutError


@dataclass
class Stream:
    object: int
    rate: int
    channels: int
    capacity: int
    queue: deque = field(default_factory=deque)
    interfaces: dict = field(default_factory=dict)
    callback: tuple | None = None
    state: int = 1
    index: int = 0
    generated_bytes: int = 0
    callbacks: int = 0
    volume_mb: int = 0
    mute: bool = False
    destroyed: bool = False
    sink: object = None
    capture: object = None
    error: str | None = None
    mode: str = 'silent'
    last_frame: int = 0
    capture_seconds: float = 0.0

    @property
    def bytes_per_second(self):
        return self.rate * self.channels * 2


class OpenSLAudio:
    def __init__(self, probe, mode='silent', capture_path=None):
        if mode not in ('silent', 'capture', 'output'):
            raise ValueError('Unknown audio mode: ' + mode)
        self.p = probe
        self.mode = mode
        self.capture_path = Path(capture_path) if capture_path else None
        self.owner_thread = threading.get_ident()
        self.objects = {}
        self.interfaces = {}
        self.streams = {}
        self.created_streams = 0
        self.retired_streams = deque(maxlen=16)
        self.retired_totals = {'streams': 0, 'callbacks': 0, 'generated_bytes': 0,
                               'failed_streams': 0, 'output_submitted_bytes': 0,
                               'output_completed_bytes': 0, 'output_discarded_bytes': 0,
                               'output_errors': 0}
        self.muted = False
        self.mute_changes = 0
        self.held = False
        self.closed = False
        self.error = None
        self.lead_seconds = 0.080
        self.callback_limit = 32

    def object(self, kind):
        table = self.p.alloc(16 * 4)
        for index in range(16):
            self.p.put(table + index * 4, self.p.thunk(f'sl_object_{index}'))
        obj = self.p.alloc(4)
        self.p.put(obj, table)
        self.objects[obj] = {'kind': kind, 'interfaces': {}, 'realized': False,
                             'allocations': [table, obj]}
        return obj

    def _interface(self, obj, kind):
        owner = self.objects[obj]
        if kind not in owner['interfaces']:
            table = self.p.alloc(16 * 4)
            for index in range(16):
                self.p.put(table + index * 4, self.p.thunk(f'sl_{kind}_{index}'))
            pointer = self.p.alloc(4)
            self.p.put(pointer, table)
            owner['interfaces'][kind] = pointer
            owner['allocations'].extend((table, pointer))
            self.interfaces[pointer] = (obj, kind)
            if obj in self.streams:
                self.streams[obj].interfaces[kind] = pointer
        return owner['interfaces'][kind]

    def _create_player(self, source):
        locator, fmt = struct.unpack('<II', self.p.read(source, 8))
        locator_kind, capacity = struct.unpack('<II', self.p.read(locator, 8))
        kind, channels, rate_milli, bits, container, mask, byte_order = struct.unpack('<7I', self.p.read(fmt, 28))
        if (locator_kind != 0x800007BD or kind != 2 or channels not in (1, 2)
                or bits != 16 or container != 16 or byte_order != 2 or rate_milli % 1000
                or rate_milli // 1000 not in (16000,22050,44100,48000) or not 1 <= capacity <= 64):
            raise RuntimeError(f'Unsupported OpenSL PCM source: locator={locator_kind:x}, format={(kind,channels,rate_milli,bits,container,mask,byte_order)}, capacity={capacity}')
        obj = self.object('player')
        stream = Stream(obj, rate_milli // 1000, channels, capacity, mode=self.mode,
                        last_frame=self.p.frame)
        self.streams[obj] = stream
        self.created_streams += 1
        self.p.log('AUDIO_FORMAT', stream.rate, channels, bits, 'little-endian', 'queue', capacity)
        if self.mode == 'output':
            try:
                from audio_output import WaveOut
                stream.sink = WaveOut(stream.rate, channels, bits)
                stream.sink.pause(True)
            except (OSError, RuntimeError) as error:
                self._failed(stream, error)
        elif self.mode == 'capture':
            if not self.capture_path:
                raise ValueError('Capture mode requires a local WAV path')
            path = self.capture_path
            if self.created_streams > 1:
                path = path.with_name(path.stem + f'_{self.created_streams}' + path.suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            stream.capture = wave.open(str(path), 'wb')
            stream.capture.setnchannels(channels)
            stream.capture.setsampwidth(2)
            stream.capture.setframerate(stream.rate)
        return obj

    def _failed(self, stream, error):
        stream.error = self.error = str(error)
        stream.mode = 'unavailable'
        self.p.log('AUDIO_UNAVAILABLE', str(error))
        if stream.sink is not None:
            try:
                stream.sink.close()
            except Exception as close_error:
                self.p.log('AUDIO_CLOSE_ERROR', str(close_error))
            stream.sink = None

    def _stream(self, pointer, kind):
        obj, actual = self.interfaces[pointer]
        if actual != kind:
            raise RuntimeError('OpenSL interface type mismatch')
        return self.streams[obj]

    def _backend(self, stream, method, *args):
        try:
            return getattr(stream.sink, method)(*args)
        except (OSError, WaveOutError) as error:
            self._failed(stream, error)
            return None

    def _tick(self, stream):
        current = self.p.frame
        if stream.state == 3:
            stream.capture_seconds += max(0, current - stream.last_frame) * max(1, getattr(self.p, 'frame_interval', 33)) / 1000
        stream.last_frame = current

    def _put_short(self, address, value):
        self.p.write(address, struct.pack('<H', value & 0xFFFF))

    def dispatch(self, name, args):
        _, kind, method = name.split('_')
        method = int(method)
        if kind == 'object':
            obj = args[0]
            if method == 6:
                self._destroy_object(obj)
                return 0
            if obj not in self.objects:
                return 1
            if method == 0:
                self.objects[obj]['realized'] = True
                return 0
            if method == 1:
                return 0
            if method == 2:
                self.p.put(args[1], 2 if self.objects[obj]['realized'] else 1)
                return 0
            if method == 3:
                iid = self.p.slids.get(args[1])
                interface = {'SL_IID_ENGINE': 'engine', 'SL_IID_ANDROIDSIMPLEBUFFERQUEUE': 'queue',
                             'SL_IID_VOLUME': 'volume', 'SL_IID_PLAYBACKRATE': 'rate', 'SL_IID_PLAY': 'play'}.get(iid)
                if interface is None:
                    raise RuntimeError(f'Unknown OpenSL interface: {args[1]:x}')
                self.p.put(args[2], self._interface(obj, interface))
                return 0
        if kind == 'engine' and method in (2, 7):
            obj = self._create_player(args[2]) if method == 2 else self.object('mix')
            self.p.put(args[1], obj)
            return 0
        if kind in ('play', 'queue', 'volume', 'rate'):
            if args[0] not in self.interfaces:
                return 1
            stream = self._stream(args[0], kind)
            if stream.destroyed:
                return 1
        if kind == 'play':
            if method == 0:
                if args[1] not in (1, 2, 3):
                    return 2
                self._tick(stream)
                stream.state = args[1]
                if stream.sink:
                    self._backend(stream, 'pause', stream.state != 3 or self.held)
                return 0
            if method == 1:
                self.p.put(args[1], stream.state)
                return 0
            if method == 3:
                self.p.put(args[1], int(stream.generated_bytes * 1000 / stream.bytes_per_second))
                return 0
            if method in (4, 5, 7, 8, 10):
                return 0
        if kind == 'queue':
            if method == 0:
                size = args[2]
                if not size or size > stream.bytes_per_second or size % (stream.channels * 2):
                    return 2
                if len(stream.queue) >= stream.capacity:
                    return 7
                # The game reuses a four-block ring. Never expose its pointer to WinMM.
                stream.queue.append(self.p.read(args[1], size))
                return 0
            if method == 1:
                stream.queue.clear()
                stream.index = 0
                if stream.sink:
                    self._backend(stream, 'clear')
                return 0
            if method == 2:
                self.p.put(args[1], len(stream.queue))
                self.p.put(args[1] + 4, stream.index)
                return 0
            if method == 3:
                stream.callback = (args[1], args[2]) if args[1] else None
                return 0
        if kind == 'volume':
            if method == 0:
                value = (args[1] + 0x80000000) % 0x100000000 - 0x80000000
                if not -9600 <= value <= 0:
                    return 2
                stream.volume_mb = value
                self._update_volume(stream)
                return 0
            if method == 1:
                self._put_short(args[1], stream.volume_mb)
                return 0
            if method == 2:
                self._put_short(args[1], 0)
                return 0
            if method == 3:
                stream.mute = bool(args[1])
                self._update_volume(stream)
                return 0
            if method == 4:
                self.p.put(args[1], int(stream.mute))
                return 0
            if method in (5, 7):
                return 0
            if method in (6, 8):
                if method == 8:self._put_short(args[1], 0)
                else:self.p.put(args[1], 0)
                return 0
        if kind == 'rate':
            if method == 0:
                return 0 if args[1] == 1000 else 12
            if method == 2:
                return 0
            if method == 1:
                self._put_short(args[1], 1000)
                return 0
        raise RuntimeError(f'Unimplemented OpenSL method {name}')

    def _update_volume(self, stream):
        if stream.sink:
            self._backend(stream, 'set_volume', 0.0 if self.muted or stream.mute else 10 ** (stream.volume_mb / 2000))

    def set_muted(self, muted):
        if self.muted != bool(muted):self.mute_changes += 1
        self.muted = bool(muted)
        for stream in self.streams.values():
            if stream.destroyed:
                continue
            if stream.sink:
                self._backend(stream, 'clear')
            self._update_volume(stream)

    def hold(self, held):
        """Pause output without discarding it (local versus pause menu, versus_session).

        Render-only paused frames restore the guest mixer and these streams afterwards, so pumping
        during them would submit the same blocks every frame. While held, pump() does nothing and
        each WaveOut device is paused with its queued audio kept; release resumes from that point."""
        held = bool(held)
        if held == self.held:
            return
        self.held = held
        for stream in self.streams.values():
            if stream.destroyed:
                continue
            if not held:
                stream.last_frame = self.p.frame        # held frames do not count as capture time
            if stream.sink:
                self._backend(stream, 'pause', held or stream.state != 3)

    def pump(self):
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError('Game audio callbacks must run on the game thread')
        if self.held:
            return
        for stream in list(self.streams.values()):
            self._tick(stream)
            if stream.destroyed or stream.state != 3 or stream.mode in ('silent', 'unavailable'):
                continue
            try:
                if stream.sink:
                    self._backend(stream, 'poll')
                    if stream.mode == 'unavailable':continue
                # Capture follows game frame time; hardware follows queued wall-clock audio.
                target = stream.capture_seconds
                for _ in range(self.callback_limit):
                    if not stream.queue:
                        break
                    if stream.sink and stream.sink.queued_seconds >= self.lead_seconds:
                        break
                    if stream.capture and stream.generated_bytes / stream.bytes_per_second >= target:
                        break
                    block = stream.queue[0]
                    if stream.sink and not self._backend(stream, 'submit', block):
                        break
                    if stream.capture:
                        stream.capture.writeframesraw(block)
                    stream.queue.popleft()
                    stream.generated_bytes += len(block)
                    stream.index = (stream.index + 1) & 0xFFFFFFFF
                    if stream.callback:
                        address, context = stream.callback
                        stream.callbacks += 1
                        # Tiny mixer calls otherwise pay a per-call watchdog-thread cost.
                        # A finite compiled-block budget preserves a hard stop boundary.
                        self.p.call(address, stream.interfaces['queue'], context,
                                    count=2_000_000, timeout=0)
            except OSError as error:
                self._failed(stream, error)

    def _close_stream(self, stream):
        if stream.destroyed:
            return
        stream.destroyed = True
        stream.callback = None
        stream.queue.clear()
        if stream.capture:
            stream.capture.close()
        if stream.sink:
            self._backend(stream, 'close')

    def _stream_stats(self, stream):
        return {'rate': stream.rate, 'channels': stream.channels, 'bits': 16, 'mode': stream.mode,
                'state': stream.state, 'queued_guest_buffers': len(stream.queue), 'callbacks': stream.callbacks,
                'generated_bytes': stream.generated_bytes,
                'generated_seconds': stream.generated_bytes / stream.bytes_per_second,
                'error': stream.error, 'output': stream.sink.stats() if stream.sink else None}

    def _destroy_object(self, obj):
        owner = self.objects.pop(obj, None)
        if owner is None:
            return
        stream = self.streams.pop(obj, None)
        if stream is not None:
            self._close_stream(stream)
            summary = self._stream_stats(stream)
            self.retired_streams.append(summary)
            self.retired_totals['streams'] += 1
            self.retired_totals['callbacks'] += stream.callbacks
            self.retired_totals['generated_bytes'] += stream.generated_bytes
            self.retired_totals['failed_streams'] += int(stream.error is not None)
            output = summary['output'] or {}
            for key in ('submitted_bytes', 'completed_bytes', 'discarded_bytes', 'errors'):
                self.retired_totals['output_' + key] += output.get(key, 0)
            stream.interfaces.clear()
        for pointer in owner['interfaces'].values():
            self.interfaces.pop(pointer, None)
        for pointer in reversed(owner['allocations']):
            self.p.free(pointer)

    def stats(self):
        return {'requested_mode': self.mode, 'muted': self.muted, 'mute_changes': self.mute_changes, 'held': self.held,
                'error': self.error,
                'streams': [self._stream_stats(s) for s in self.streams.values()],
                'created_streams': self.created_streams,
                'retired_streams': list(self.retired_streams),
                'retired_totals': dict(self.retired_totals)}

    def close(self):
        if not self.closed:
            for stream in self.streams.values():
                self._close_stream(stream)
            self.closed = True
