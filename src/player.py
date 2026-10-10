"""Interactive Windows host for the statically recompiled MSD x64 core."""
from pathlib import Path
import sys, os, time, threading, queue, json, ctypes, traceback, hashlib

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
RUNTIME_PACKAGES=Path(sys.executable).resolve().parent/'packages'
sys.path.insert(0,str(RUNTIME_PACKAGES if RUNTIME_PACKAGES.is_dir() else ROOT.parent/'windows_probe/deps'))
import glfw
from probe import Probe, ProbeCancelled
from window_layout import game_point, fit_rect, WIDTH, HEIGHT
from app_icon import WindowIcon, set_app_user_model_id

from branding import load as load_branding
TITLE=load_branding(ROOT)['application_name']

class Player:
    def __init__(self, self_test=False, audio_mode=None, fullscreen=None):
        self.self_test=self_test
        self.self_test_end_frame=215
        self.audio_mode=audio_mode or ('capture' if self_test else 'output')
        self.mute_requested=False
        self.audio_status={}
        self.stop=threading.Event()
        self.events=queue.Queue()
        self.ready=False
        self.error=None
        self.done=False
        self.frames=0
        self.fps=0.0
        self.last_present=time.perf_counter()
        self.pressed=False
        self.last_motion=None
        self.last_mouse=(0.0,0.0)
        self.minimized=False
        self.capture_requested=False
        self.saved=False
        self.status_write_failures=0
        self.status_write_error=None
        self.guest_root=ROOT/('ui_test_guest' if self_test else 'play_save')
        self.status_file=ROOT/('ui_test_status.json' if self_test else 'player_status.json')
        self.log_name='ui_test.log' if self_test else 'player.log'
        self.window=None
        self.app_icon=None
        self.probe=None
        self.worker=None
        self.mutex=None
        self.settings_path=ROOT/'window_settings.json'
        self.fullscreen=True
        if fullscreen is None and not self_test and self.settings_path.is_file():
            try:self.fullscreen=bool(json.loads(self.settings_path.read_text(encoding='utf-8'))['fullscreen'])
            except (ValueError,KeyError,OSError):pass
        elif fullscreen is not None:self.fullscreen=bool(fullscreen)
        self.window_rect=None
        self.window_drag=None
        self.last_key_event=None
        self.last_unit_result=None
        self.key_sequence=0

    def acquire_instance(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        kernel.CreateMutexW.restype=ctypes.c_void_p
        self.kernel=kernel
        key=hashlib.sha256(str(self.guest_root).encode()).hexdigest()[:20]
        self.mutex=kernel.CreateMutexW(None,False,'Local\\MSD_Windows_Trial_'+key)
        if not self.mutex:raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error()==183:
            ctypes.windll.user32.MessageBoxW(None,'游戏窗口已经运行，请使用已有窗口。',TITLE,0x40)
            return False
        return True

    def progress(self,values):
        if values and values[0]=='SAVE_COMMITTED':self.saved=True

    def coordinates(self,x,y,clamp=False):
        w,h=glfw.get_window_size(self.window)
        return game_point(x,y,w,h,clamp)

    def monitor_rect(self):
        monitors=glfw.get_monitors()
        monitor=glfw.get_primary_monitor()
        if self.window:
            x,y=glfw.get_window_pos(self.window);w,h=glfw.get_window_size(self.window)
            def overlap(candidate):
                mx,my=glfw.get_monitor_pos(candidate);mode=glfw.get_video_mode(candidate)
                return max(0,min(x+w,mx+mode.size.width)-max(x,mx))*max(0,min(y+h,my+mode.size.height)-max(y,my))
            monitor=max(monitors,key=overlap)
        x,y=glfw.get_monitor_pos(monitor);mode=glfw.get_video_mode(monitor)
        return x,y,mode.size.width,mode.size.height

    def toggle_fullscreen(self):
        self.focus(self.window,False)
        self.window_drag=None
        if self.fullscreen:
            x,y,w,h=self.window_rect
        else:
            self.window_rect=(*glfw.get_window_pos(self.window),*glfw.get_window_size(self.window))
            x,y,w,h=self.monitor_rect()
        # A monitor-less window leaves the desktop resolution unchanged.
        glfw.set_window_monitor(self.window,None,x,y,w,h,glfw.DONT_CARE)
        self.fullscreen=not self.fullscreen
        self.framebuffer_size=glfw.get_framebuffer_size(self.window)
        if not self.self_test:
            self.settings_path.write_text(json.dumps({'fullscreen':self.fullscreen}),encoding='utf-8')

    def screen_cursor(self):
        class Point(ctypes.Structure):_fields_=[('x',ctypes.c_long),('y',ctypes.c_long)]
        point=Point();ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return point.x,point.y

    def mouse_button(self,window,button,action,mods):
        if button!=glfw.MOUSE_BUTTON_LEFT:return
        if action==glfw.PRESS and mods&glfw.MOD_ALT and not self.fullscreen:
            self.window_drag=(*self.screen_cursor(),*glfw.get_window_pos(window));return
        if action==glfw.RELEASE and self.window_drag is not None:
            self.window_drag=None;return
        point=self.coordinates(*glfw.get_cursor_pos(window),clamp=self.pressed)
        if point is None:return
        x,y=point
        self.last_mouse=(x,y)
        if action==glfw.PRESS:
            if not self.ready or time.perf_counter()-self.last_present>1.5:return
            self.pressed=True;self.events.put((1,x,y))
        elif action==glfw.RELEASE and self.pressed:
            self.pressed=False;self.last_motion=None;self.events.put((3,x,y))

    def cursor(self,window,x,y):
        if self.window_drag is not None:
            sx,sy,wx,wy=self.window_drag;cx,cy=self.screen_cursor()
            glfw.set_window_pos(window,wx+cx-sx,wy+cy-sy);return
        point=self.coordinates(x,y,clamp=self.pressed)
        if point is None:return
        self.last_mouse=point
        if self.pressed:self.last_motion=self.last_mouse

    def poll_input(self):
        '''窗口线程每轮事件循环调用一次（手柄等需在主线程轮询的输入）；默认无操作。'''

    def focus(self,window,focused):
        if not focused:self.window_drag=None
        if not focused and self.pressed:
            self.pressed=False;self.last_motion=None;self.events.put((3,*self.last_mouse))

    def key(self,window,key,scan,action,mods):
        if action!=glfw.PRESS:return
        if key==glfw.KEY_F11 or (key==glfw.KEY_ENTER and mods&glfw.MOD_ALT):
            self.toggle_fullscreen();return
        slot=9 if key==glfw.KEY_0 else key-glfw.KEY_1 if glfw.KEY_1<=key<=glfw.KEY_9 else None
        if slot is None:slot=9 if key==glfw.KEY_KP_0 else key-glfw.KEY_KP_1 if glfw.KEY_KP_1<=key<=glfw.KEY_KP_9 else None
        if slot is not None:
            self.key_sequence+=1
            blocked_mods=mods&(glfw.MOD_SHIFT|glfw.MOD_CONTROL|glfw.MOD_ALT|glfw.MOD_SUPER)
            queued=self.ready and time.perf_counter()-self.last_present<1.5 and not blocked_mods
            self.last_key_event={'sequence':self.key_sequence,'key':key,'scan':scan,'mods':mods,
                                 'slot':slot+1,'queued':bool(queued)}
            if queued:self.events.put(('unit',slot))
        battle_action={glfw.KEY_SPACE:'special_all',glfw.KEY_GRAVE_ACCENT:'upgrade_ap',
                       glfw.KEY_MINUS:'slug_attack',glfw.KEY_EQUAL:'deploy_all'}.get(key)
        if battle_action:
            self.key_sequence+=1
            blocked_mods=mods&(glfw.MOD_SHIFT|glfw.MOD_CONTROL|glfw.MOD_ALT|glfw.MOD_SUPER)
            queued=self.ready and time.perf_counter()-self.last_present<1.5 and not blocked_mods
            self.last_key_event={'sequence':self.key_sequence,'key':key,'scan':scan,'mods':mods,
                                 'action':battle_action,'queued':bool(queued)}
            if queued:self.events.put(('battle',battle_action))
        if action==glfw.PRESS and key==glfw.KEY_F12:self.capture_requested=True
        if action==glfw.PRESS and key==glfw.KEY_F9:self.mute_requested=True
        if action==glfw.PRESS and key==glfw.KEY_F6 and self.ready:
            self.events.put(('content_menu','worlds'))
        if key==glfw.KEY_ESCAPE and self.ready and not mods&(glfw.MOD_SHIFT|glfw.MOD_CONTROL|glfw.MOD_ALT|glfw.MOD_SUPER):
            self.events.put(('back',))

    def game_thread(self):
        p=None;pacer=None
        try:
            p=Probe(guest_root=self.guest_root,log_name=self.log_name,
                    window_handle=self.hwnd,window_size=(WIDTH,HEIGHT),
                    stop_event=self.stop,on_progress=self.progress,
                    audio_mode=self.audio_mode,audio_capture=ROOT/'ui_test_audio.wav')
            self.probe=p
            p.render_surface_size=self.framebuffer_size
            assert not any(n == 'unicorn' or n.startswith('unicorn.') for n in sys.modules), 'Unexpected ARM engine dependency'
            p.initialize()
            from frame_pacer import FramePacer
            pacer=FramePacer(30)
            sample_time=time.perf_counter();sample_frames=0
            while not self.stop.is_set():
                if self.minimized and self.ready:
                    self.stop.wait(0.05);continue
                began=time.perf_counter()
                if hasattr(p,'graphics'):p.graphics.resize(*self.framebuffer_size)
                if hasattr(p,'audio_bridge'):
                    if self.mute_requested:
                        self.mute_requested=False
                        p.audio_bridge.set_muted(not p.audio_bridge.muted)
                    self.audio_status=p.audio_bridge.stats()
                if self.ready:
                    try:event=self.events.get_nowait()
                    except queue.Empty:event=None
                    if event:
                        if event[0]=='unit':
                            p.log('WINDOW_UNIT_REQUEST',event[1]+1,p.frame)
                            p.activate_unit_slot(event[1])
                            self.last_unit_result=dict(p.last_unit_result)
                        elif event[0]=='battle':
                            p.log('WINDOW_BATTLE_REQUEST',event[1],p.frame)
                            self.last_unit_result=p.battle_key_action(event[1])
                        elif event[0]=='content_menu':
                            if event[1]=='worlds' and hasattr(p,'campaign'):p.campaign.open()
                        elif event[0]=='back':
                            p.log('WINDOW_BACK_REQUEST',p.frame)
                            p.back()
                        else:
                            p.touch_event(*event)
                            p.log('WINDOW_TOUCH',*event)
                    elif self.pressed and self.last_motion is not None:
                        motion=self.last_motion;self.last_motion=None
                        p.touch_event(5,*motion)
                p.step_frame()
                self.frames=p.frame
                if p.frame==140:
                    # 标题截图属于诊断输出：窗口最小化（帧缓冲 0×0）等情形下跳过，不中止运行。
                    try:p.graphics.capture(ROOT/('ui_test_title.png' if self.self_test else 'player_title.png'))
                    except Exception as error:p.log('WINDOW_TITLE_CAPTURE_SKIPPED',type(error).__name__,str(error))
                    self.ready=True;p.log('WINDOW_READY',self.hwnd)
                if self.capture_requested:
                    self.capture_requested=False
                    folder=ROOT/'screenshots';folder.mkdir(exist_ok=True)
                    p.graphics.capture(folder/(time.strftime('%Y%m%d_%H%M%S')+'.png'))
                if self.self_test and p.frame==self.self_test_end_frame:
                    p.graphics.capture(ROOT/'ui_test_menu.png')
                    p.log('WINDOW_SELF_TEST_COMPLETE',self.hwnd)
                    self.done=True;break
                # 会话驱动本帧没有画面时（回放暂停之外的等待、联机等待对方）不交换缓冲区，窗口保持上一帧（lab_runtime）。
                if getattr(p,'frame_drawn',True):p.graphics.present()
                self.last_present=time.perf_counter()
                sample_frames+=1
                if self.last_present-sample_time>=1:
                    self.fps=sample_frames/(self.last_present-sample_time)
                    sample_frames=0;sample_time=self.last_present
                pacer.wait()
        except ProbeCancelled:
            if p:p.log('WINDOW_CLOSED_BY_USER')
        except Exception:
            self.error=traceback.format_exc()
            (ROOT/'player_error.log').write_text(self.error,encoding='utf-8')
            if p:
                p.log('WINDOW_ERROR',self.error)
                if hasattr(p,'graphics'):
                    try:p.graphics.capture(ROOT/'player_error_frame.png')
                    except Exception:pass
        finally:
            if pacer:pacer.close()
            try:
                if p:p.close()
            except Exception:
                self.error=self.error or traceback.format_exc()
            finally:
                if p and hasattr(p,'audio_bridge'):self.audio_status=p.audio_bridge.stats()
                self.done=True

    def write_status(self,state):
        data={'pid':os.getpid(),'hwnd':self.hwnd,'state':state,'frames':self.frames,
              'ready':self.ready,'fps':round(self.fps,2),'save_root':str(self.guest_root),
              'self_test':self.self_test,'save_committed':self.saved,'error':self.error}
        data['audio']=self.audio_status
        data['fullscreen']=self.fullscreen
        data['borderless']=True
        data['framebuffer_size']=self.framebuffer_size
        data['game_viewport']=fit_rect(*self.framebuffer_size)
        data['last_key_event']=self.last_key_event
        data['last_unit_result']=self.last_unit_result
        data['status_write_failures']=self.status_write_failures
        data['status_write_error']=self.status_write_error
        if self.probe and hasattr(self.probe.uc,'library_path'):
            data['native_core']=str(self.probe.uc.library_path)
        tmp=self.status_file.with_name(self.status_file.name+f'.{os.getpid()}.tmp')
        try:
            tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(tmp,self.status_file)
        except OSError as error:
            # 状态报告属于诊断输出；文件锁冲突保留已有报告，由下一周期再次写入。
            self.status_write_failures+=1
            self.status_write_error=str(error)
            try:tmp.unlink(missing_ok=True)
            except OSError:pass
            return False
        return True

    def run(self):
        set_app_user_model_id()
        if not self.acquire_instance():return 0
        if not glfw.init():raise RuntimeError('GLFW could not initialize a Windows window')
        try:
            glfw.window_hint(glfw.CLIENT_API,glfw.NO_API)
            glfw.window_hint(glfw.RESIZABLE,glfw.FALSE)
            glfw.window_hint(glfw.DECORATED,glfw.FALSE)
            glfw.window_hint(glfw.VISIBLE,glfw.FALSE if self.self_test else glfw.TRUE)
            glfw.window_hint(glfw.SCALE_TO_MONITOR,glfw.FALSE)
            mx,my,mw,mh=self.monitor_rect()
            ww,wh=min(WIDTH,mw),min(HEIGHT,mh)
            self.window_rect=(mx+(mw-ww)//2,my+(mh-wh)//2,ww,wh)
            x,y,w,h=(mx,my,mw,mh) if self.fullscreen else self.window_rect
            self.window=glfw.create_window(w,h,TITLE,None,None)
            if not self.window:raise RuntimeError('Could not create the game window')
            glfw.set_window_pos(self.window,x,y)
            self.hwnd=glfw.get_win32_window(self.window)
            self.app_icon=WindowIcon(self.hwnd,ROOT)
            self.framebuffer_size=glfw.get_framebuffer_size(self.window)
            glfw.set_mouse_button_callback(self.window,self.mouse_button)
            glfw.set_cursor_pos_callback(self.window,self.cursor)
            glfw.set_window_focus_callback(self.window,self.focus)
            glfw.set_window_iconify_callback(self.window,lambda w,icon:self.__setattr__('minimized',bool(icon)))
            glfw.set_key_callback(self.window,self.key)
            glfw.set_framebuffer_size_callback(self.window,lambda w,x,y:self.__setattr__('framebuffer_size',(x,y)))
            glfw.set_window_content_scale_callback(self.window,lambda w,x,y:self.app_icon.refresh())
            if not self.self_test:glfw.show_window(self.window)
            self.write_status('loading')
            self.worker=threading.Thread(target=self.game_thread,name='MSD game runtime')
            self.worker.start()
            last_status=0;test_press=None;test_released=False;test_mute_phase=0
            while not glfw.window_should_close(self.window) and not self.done:
                glfw.wait_events_timeout(0.02)
                self.poll_input()
                now=time.perf_counter()
                if self.self_test and self.ready and getattr(self,'self_test_input',True):
                    # Exercise the same input queue used by GLFW's real mouse callbacks.
                    if test_press is None:
                        self.events.put((1,480.0,540.0));test_press=self.frames
                    elif not test_released and self.frames>=test_press+2:
                        self.events.put((3,480.0,540.0));test_released=True
                    if test_mute_phase==0 and self.frames>=170:
                        self.key(self.window,glfw.KEY_F9,0,glfw.PRESS,0);test_mute_phase=1
                    elif test_mute_phase==1 and self.frames>=190:
                        self.key(self.window,glfw.KEY_F9,0,glfw.PRESS,0);test_mute_phase=2
                if now-last_status>0.5:
                    loading=not self.ready or now-self.last_present>1.5
                    self.write_status('loading' if loading else 'running')
                    last_status=now
            self.stop.set()
            if self.window:glfw.hide_window(self.window)
            while self.worker.is_alive():
                glfw.poll_events();self.worker.join(0.05)
            self.write_status('error' if self.error else 'closed')
            if self.error and not self.self_test:
                ctypes.windll.user32.MessageBoxW(None,'游戏运行已停止。已提交的存档仍保留。\n\n错误记录：'+str(ROOT/'player_error.log'),TITLE,0x10)
            return 1 if self.error else 0
        finally:
            # 所有退出路径均等待渲染线程结束，再释放其使用的窗口与图形上下文。
            self.stop.set()
            if self.worker and self.worker.is_alive():
                if self.window:glfw.hide_window(self.window)
                while self.worker.is_alive():
                    glfw.poll_events();self.worker.join(0.05)
            if self.app_icon:self.app_icon.close()
            if self.window:glfw.destroy_window(self.window)
            glfw.terminate()
            if self.mutex:
                self.kernel.CloseHandle.argtypes=[ctypes.c_void_p]
                self.kernel.CloseHandle(self.mutex)

if __name__=='__main__':
    try:sys.exit(Player('--self-test' in sys.argv,audio_mode='silent' if '--mute' in sys.argv else None,
                        fullscreen=False if '--windowed' in sys.argv else True if '--fullscreen' in sys.argv else None).run())
    except Exception:
        error=traceback.format_exc();(ROOT/'player_error.log').write_text(error,encoding='utf-8')
        if '--self-test' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None,'游戏窗口启动失败。错误记录：\n'+str(ROOT/'player_error.log'),TITLE,0x10)
        if sys.stderr:sys.stderr.write(error)
        sys.exit(1)
