"""《合金弹头7》（NDS）音效序列的读取与渲染（R5）：F:\\egg\\MS7\\mslug7_sdat_extract（用户提供，VGMTrans / Tinke 由 ms7ds.sdat 转出）的
sequence/<区段>/ 中，音效为 .mid 序列，按同目录 BANK_nnn.sf2 的音色播放 samples 中的采样。本文件只读该目录（2026-11-01 R5，由 verification/ms7_m4_units_20261031 移入，供 build_fall_climber.py 渲染音效）。
- read_mid：标准 MIDI 文件 → [(秒, 事件)]（音符开 / 关、音色、控制器、弯音、速度）。
- read_sf2：SoundFont 2 → 预设 (bank, program) → [区]（键 / 力度范围、采样、根音、微调、衰减、声相、循环、音量包络），采样为 16 位 PCM。
- render：按序列与音色合成（线性插值变调；音量包络为延迟 / 起音 / 保持 / 衰减 / 延音 / 释音；CC7 音量、CC10 声相、CC11 表情；弯音范围 ±2 半音，
  序列有 RPN 0 时按其值）。输出采样率可选。用法：E:/anaconda3/python.exe -I ds_sseq.py <区段目录> <序列名> <输出 wav>（16 kHz 立体声）"""
import math
import struct
import sys
import wave
from pathlib import Path

import numpy as np


def _vlq(b, i):
    v = 0
    while True:
        c = b[i]
        i += 1
        v = (v << 7) | (c & 0x7f)
        if not c & 0x80:
            return v, i


def read_mid(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'MThd'
    fmt, ntr, div = struct.unpack('>HHH', b[8:14])
    i, tracks = 14, []
    for _ in range(ntr):
        assert b[i:i + 4] == b'MTrk'
        n = struct.unpack('>I', b[i + 4:i + 8])[0]
        tracks.append(b[i + 8:i + 8 + n])
        i += 8 + n
    events = []                                   # (tick, 序号, 事件)
    seq = 0
    for tb in tracks:
        j, t, run = 0, 0, None
        while j < len(tb):
            d, j = _vlq(tb, j)
            t += d
            st = tb[j]
            if st == 0xff:
                kind, ln = tb[j + 1], None
                ln, j2 = _vlq(tb, j + 2)
                data = tb[j2:j2 + ln]
                j = j2 + ln
                if kind == 0x51:
                    events.append((t, seq, ('tempo', int.from_bytes(data, 'big'))))
                elif kind == 0x2f:
                    events.append((t, seq, ('end',)))
                seq += 1
                continue
            if st in (0xf0, 0xf7):
                ln, j2 = _vlq(tb, j + 1)
                j = j2 + ln
                continue
            if st & 0x80:
                run = st
                j += 1
            st = run
            hi, ch = st & 0xf0, st & 0x0f
            if hi in (0xc0, 0xd0):
                a = tb[j]
                j += 1
                if hi == 0xc0:
                    events.append((t, seq, ('program', ch, a)))
            else:
                a, c = tb[j], tb[j + 1]
                j += 2
                if hi == 0x90 and c > 0:
                    events.append((t, seq, ('on', ch, a, c)))
                elif hi in (0x80, 0x90):
                    events.append((t, seq, ('off', ch, a)))
                elif hi == 0xb0:
                    events.append((t, seq, ('cc', ch, a, c)))
                elif hi == 0xe0:
                    events.append((t, seq, ('bend', ch, (c << 7 | a) - 8192)))
            seq += 1
    events.sort(key=lambda e: (e[0], e[1]))
    out, tempo, last_t, sec = [], 500000, 0, 0.0
    for t, _, ev in events:
        sec += (t - last_t) * tempo / 1e6 / div
        last_t = t
        if ev[0] == 'tempo':
            tempo = ev[1]
        out.append((sec, ev))
    return out


def _chunks(b, i, end):
    while i < end:
        cid, n = b[i:i + 4], struct.unpack('<I', b[i + 4:i + 8])[0]
        yield cid, i + 8, n
        i += 8 + n + (n & 1)


def read_sf2(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'RIFF' and b[8:12] == b'sfbk'
    lists = {}
    for cid, i, n in _chunks(b, 12, len(b)):
        if cid == b'LIST':
            lists[b[i:i + 4]] = (i + 4, i + n)
    sdta = {cid: (i, n) for cid, i, n in _chunks(b, *lists[b'sdta'])}
    smpl = np.frombuffer(b, '<i2', sdta[b'smpl'][1] // 2, sdta[b'smpl'][0]).astype(np.float32) / 32768
    p = {cid: b[i:i + n] for cid, i, n in _chunks(b, *lists[b'pdta'])}

    def rec(name, fmt):
        size = struct.calcsize(fmt)
        return [struct.unpack_from(fmt, p[name], k) for k in range(0, len(p[name]), size)]
    phdr, pbag, pgen = rec(b'phdr', '<20sHHHIII'), rec(b'pbag', '<HH'), rec(b'pgen', '<HH')
    inst, ibag, igen = rec(b'inst', '<20sH'), rec(b'ibag', '<HH'), rec(b'igen', '<HH')
    shdr = rec(b'shdr', '<20sIIIIIBbHH')

    def zones(bags, gens, a, z):
        out = []
        for k in range(a, z):
            g = {}
            for gi in range(bags[k][0], bags[k + 1][0]):
                op, amt = gens[gi]
                g[op] = amt
            out.append(g)
        return out
    s16 = lambda v: v - 65536 if v >= 32768 else v   # noqa: E731
    presets = {}
    for pi in range(len(phdr) - 1):
        name, prog, bank, bag0 = phdr[pi][:4]
        pz = zones(pbag, pgen, bag0, phdr[pi + 1][3])
        glob_p = pz[0] if pz and 41 not in pz[0] else {}
        regions = []
        for z in pz:
            if 41 not in z:
                continue
            ii = z[41]
            iz = zones(ibag, igen, inst[ii][1], inst[ii + 1][1])
            glob_i = iz[0] if iz and 53 not in iz[0] else {}
            for zz in iz:
                if 53 not in zz:
                    continue
                g = dict(glob_i)
                g.update(zz)
                for op, amt in list(glob_p.items()) + list(z.items()):   # 预设层的生成器为增量
                    if op in (41, 43, 44):
                        continue
                    g[op] = s16(g.get(op, 0)) + s16(amt) if op not in (43, 44) else g.get(op)
                kr = zz.get(43, z.get(43, 0x7f00))
                vr = zz.get(44, z.get(44, 0x7f00))
                sh = shdr[zz[53]]
                regions.append({'key': (kr & 0xff, kr >> 8), 'vel': (vr & 0xff, vr >> 8), 'gen': {k: s16(v) for k, v in g.items()},
                                'sample': sh})
        presets[(bank, prog)] = regions
    return presets, smpl


def _tc(v, default):
    return 2 ** ((v if v is not None else default) / 1200.0)


def render(mid, sf2, rate=48000, tail=2.0):
    events = read_mid(mid)
    presets, smpl = read_sf2(sf2)
    dur = max(t for t, _ in events) + tail
    out = np.zeros((int(dur * rate) + 1, 2), np.float32)
    ch_state = {c: {'prog': 0, 'vol': 100, 'pan': 64, 'expr': 127, 'bend': 0, 'range': 2, 'mod': 0} for c in range(16)}
    notes = []                                    # 进行中的音符
    rpn = {}
    for t, ev in events:
        if ev[0] == 'program':
            ch_state[ev[1]]['prog'] = ev[2]
        elif ev[0] == 'cc':
            ch, cc, v = ev[1], ev[2], ev[3]
            if cc == 7:
                ch_state[ch]['vol'] = v
            elif cc == 10:
                ch_state[ch]['pan'] = v
            elif cc == 11:
                ch_state[ch]['expr'] = v
            elif cc == 1:
                ch_state[ch]['mod'] = v
            elif cc in (100, 101):
                rpn[(ch, cc)] = v
            elif cc == 6 and rpn.get((ch, 100)) == 0 and rpn.get((ch, 101)) == 0:
                ch_state[ch]['range'] = v
        elif ev[0] == 'bend':
            ch_state[ev[1]]['bend'] = ev[2]
            for n in notes:
                if n['ch'] == ev[1]:
                    n['bends'].append((t, ev[2] / 8192 * ch_state[ev[1]]['range']))
        elif ev[0] == 'on':
            ch, key, vel = ev[1], ev[2], ev[3]
            st = ch_state[ch]
            regs = presets.get((0, st['prog'])) or presets.get((128 if ch == 9 else 0, st['prog'])) or []
            for r in regs:
                if r['key'][0] <= key <= r['key'][1] and r['vel'][0] <= vel <= r['vel'][1]:
                    notes.append({'ch': ch, 'key': key, 'vel': vel, 'start': t, 'end': None, 'r': r, 'st': dict(st),
                                  'bends': [(t, st['bend'] / 8192 * st['range'])]})
        elif ev[0] == 'off':
            for n in notes:
                if n['ch'] == ev[1] and n['key'] == ev[2] and n['end'] is None:
                    n['end'] = t
    for n in notes:
        r, g = n['r'], n['r']['gen']
        name, s0, s1, l0, l1, srate, root, corr = r['sample'][:8]
        ork = g.get(58, -1)                       # 根音覆盖（−1 为用采样自身的原音高）
        root = ork if ork >= 0 else (root if root <= 127 else 60)
        data = smpl[s0:s1]
        loop = g.get(54, 0) & 1
        ls, le = l0 - s0, l1 - s0
        tune = (n['key'] - root) * g.get(56, 100) / 100 + g.get(51, 0) + g.get(52, 0) / 100 + corr / 100
        att = 10 ** (-0.4 * g.get(48, 0) / 200)   # 初始衰减（cB，按 FluidSynth 的 0.4 系数）
        st = n['st']
        gain = att * (n['vel'] / 127) ** 2 * (st['vol'] / 127) ** 2 * (st['expr'] / 127) ** 2
        pan = max(-1.0, min(1.0, (st['pan'] - 64) / 63 + g.get(17, 0) / 500))
        lg, rg = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        delay, attack = _tc(g.get(33), -12000), _tc(g.get(34), -12000)
        hold, decay = _tc(g.get(35), -12000), _tc(g.get(36), -12000)
        sustain = 10 ** (-max(0, g.get(37, 0)) / 200)
        release = _tc(g.get(38), -12000)
        end = n['end'] if n['end'] is not None else dur - tail
        i0 = int(n['start'] * rate)
        nframes = int((end - n['start'] + release + 0.01) * rate)
        tt = np.arange(nframes) / rate
        # 变调（含弯音，分段常数）
        semis = np.full(nframes, tune, np.float64)
        for bt, bs in n['bends']:
            k = int((bt - n['start']) * rate)
            if k < nframes:
                semis[max(0, k):] = tune + bs
        # 颤音：CC1（SoundFont 缺省调制器，满值 50 音分）加生成器 6，频率生成器 24（8.176 Hz 起的绝对音分）、延迟生成器 23
        vib = st['mod'] / 127 * 50 + g.get(6, 0)
        if vib:
            vf = 8.176 * 2 ** (g.get(24, 0) / 1200)
            vd = _tc(g.get(23), -12000)
            semis += np.where(tt >= vd, vib / 100 * np.sin(2 * np.pi * vf * (tt - vd)), 0.0)
        step = srate / rate * 2 ** (semis / 12)
        pos = np.concatenate([[0.0], np.cumsum(step)[:-1]])
        if loop and le > ls + 1:
            over = pos >= le
            pos[over] = ls + np.mod(pos[over] - ls, le - ls)
        valid = pos < len(data) - 1
        k = np.floor(pos[valid]).astype(np.int64)
        fr = (pos[valid] - k).astype(np.float32)
        sig = np.zeros(nframes, np.float32)
        sig[valid] = data[k] * (1 - fr) + data[k + 1] * fr
        env = np.ones(nframes, np.float32)
        a0, a1 = delay, delay + attack
        env[tt < a0] = 0
        m = (tt >= a0) & (tt < a1)
        env[m] = (tt[m] - a0) / max(attack, 1e-6)
        d0 = a1 + hold
        m = tt >= d0
        env[m] = sustain + (1 - sustain) * np.exp(-(tt[m] - d0) / max(decay, 1e-6) * 5)
        rel = end - n['start']
        m = tt >= rel
        if m.any():
            lvl = env[np.argmax(m)]
            env[m] = lvl * np.exp(-(tt[m] - rel) / max(release, 1e-6) * 5)
        sig *= env * gain
        j1 = min(len(out), i0 + nframes)
        out[i0:j1, 0] += sig[:j1 - i0] * lg
        out[i0:j1, 1] += sig[:j1 - i0] * rg
    nz = np.nonzero(np.abs(out).max(axis=1) > 1e-4)[0]
    if len(nz):
        out = out[:nz[-1] + 1]
    return out, notes


def write_wav(path, data, rate):
    pcm = (np.clip(data, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def render_native(mid, sf2, peak_db=-1.0):
    """48 kHz 合成后以多相低通滤波降到游戏原生的 16 kHz 立体声，峰值归一到 peak_db（同 MSXX 转出的 WAV 接近满幅）。"""
    from scipy.signal import resample_poly
    data, notes = render(mid, sf2, 48000)
    out = resample_poly(data, 1, 3, axis=0).astype(np.float32)
    pk = float(np.abs(out).max())
    if pk > 0:
        out *= 10 ** (peak_db / 20) / pk
    return out, notes


if __name__ == '__main__':
    d, name, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    sf2 = next(d.glob('BANK_*.sf2'))
    data, notes = render_native(d / (name + '.mid'), sf2)
    write_wav(out, data, 16000)
    print(name, f'{len(data) / 16000:.2f} s', 'notes', [(round(n['start'], 3), n['key'], n['vel'], n['r']['sample'][0].split(bytes(1))[0].decode()) for n in notes][:12])
