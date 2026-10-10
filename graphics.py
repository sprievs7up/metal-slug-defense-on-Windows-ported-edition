"""GLES2 rendering through ANGLE, using a pbuffer or a Win32 game window."""
import ctypes as C
import os
import sys
from pathlib import Path

def max_render_height():
    """display_settings.json 的 max_render_height（0 为按窗口实际分辨率渲染）；MSD_MAX_RENDER_HEIGHT 可覆盖。"""
    value=os.environ.get('MSD_MAX_RENDER_HEIGHT')
    if value is None:
        try:
            import json
            value=json.loads((Path(__file__).resolve().parent/'display_settings.json').read_text(encoding='utf-8')).get('max_render_height',0)
        except (OSError,ValueError,AttributeError):value=0
    try:return max(0,int(value))
    except (TypeError,ValueError):return 0

class Graphics:
    def __init__(self, probe, width=960, height=640):
        self.p=probe; self.logical_size=(width,height)
        self.width,self.height=getattr(probe,'render_surface_size',(width,height))
        self.default_viewport=(0,0,width,height)
        self.default_scissor=(0,0,width,height)
        bundled=Path(sys.executable).resolve().parent/'angle'
        folder=bundled if (bundled/'libEGL.dll').is_file() else Path(__file__).resolve().parent.parent/'zero_progress/runtime/sdk/emulator/lib64/gles_angle'
        self.dll_dir=os.add_dll_directory(str(folder))
        self.egl=C.WinDLL(str(folder/'libEGL.dll'))
        self.gl=C.WinDLL(str(folder/'libGLESv2.dll'))
        self.funcs={}; self.bindings={0x8892:0,0x8893:0,0x8D40:0}; self.strings={}
        def egl(name, ret, args):
            f=getattr(self.egl,name);f.restype=ret;f.argtypes=args;return f
        P,I,U=C.c_void_p,C.c_int,C.c_uint
        from gpu_select import initialize_display
        self.display=initialize_display(self.egl,probe.log)
        major,minor=I(),I()
        if not egl('eglInitialize',U,[P,C.POINTER(I),C.POINTER(I)])(self.display,C.byref(major),C.byref(minor)):
            raise RuntimeError('ANGLE eglInitialize failed')
        from shader_cache import ShaderCache
        self.shader_cache=ShaderCache(self.egl,self.display,probe.log)
        egl('eglBindAPI',U,[U])(0x30A0)
        window=getattr(probe,'window_handle',None)
        attrs=(I*17)(0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,16,0x3033,4 if window else 1,0x3040,4,0x3038,0,0)
        config=P();count=I()
        ok=egl('eglChooseConfig',U,[P,C.POINTER(I),C.POINTER(P),I,C.POINTER(I)])(self.display,attrs,C.byref(config),1,C.byref(count))
        if not ok or not count.value: raise RuntimeError('No GLES2 pbuffer configuration')
        pbattrs=(I*5)(0x3057,self.width,0x3056,self.height,0x3038)
        self.window,self.config=window,config
        self.render_cap=max_render_height();self.fixed=None;self.full=(self.width,self.height)
        if window:self.surface=self.window_surface()
        else:self.surface=egl('eglCreatePbufferSurface',P,[P,P,C.POINTER(I)])(self.display,config,pbattrs)
        if not self.surface:raise RuntimeError('ANGLE could not create the rendering surface')
        ctxattrs=(I*3)(0x3098,2,0x3038)
        self.context=egl('eglCreateContext',P,[P,P,P,C.POINTER(I)])(self.display,config,None,ctxattrs)
        if not egl('eglMakeCurrent',U,[P,P,P,P])(self.display,self.surface,self.surface,self.context): raise RuntimeError('ANGLE context failed')
        egl('eglSwapInterval',U,[P,I])(self.display,0)
        self.swap=egl('eglSwapBuffers',U,[P,P])
        renderer=self.function('glGetString','u',P)(0x1F01)
        probe.log('GLES_RENDERER',C.string_at(renderer).decode())
        self.shader_cache.bind(C.string_at(renderer).decode())
        self.function('glViewport','iiii')(*self.surface_rect(self.default_viewport))
        from native_imports import bind
        bind(probe,self)

    def surface_rect(self, rect):
        from window_layout import fit_rect
        left,top,w,h=fit_rect(self.width,self.height,self.logical_size)
        x,y,rw,rh=rect;lw,lh=self.logical_size
        bottom=self.height-top-h
        x1,y1=left+round(x*w/lw),bottom+round(y*h/lh)
        x2,y2=left+round((x+rw)*w/lw),bottom+round((y+rh)*h/lh)
        return x1,y1,max(0,x2-x1),max(0,y2-y1)

    def fixed_size(self, width, height):
        """内部渲染分辨率上限：窗口高于上限时按上限高度、同宽高比渲染，由 D3D 呈现时放大。"""
        if not self.window or self.render_cap<=0 or height<=self.render_cap:return None
        return max(1,round(width*self.render_cap/height)),self.render_cap

    def window_surface(self):
        I=C.c_int
        self.fixed=self.fixed_size(*self.full)
        attrs=(I*7)(0x3201,1,0x3057,self.fixed[0],0x3056,self.fixed[1],0x3038) if self.fixed else None
        fn=self.egl.eglCreateWindowSurface;fn.restype=C.c_void_p;fn.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p]
        surface=fn(self.display,self.config,self.window,attrs)
        if not surface and self.fixed:
            self.p.log('RENDER_FIXED_SIZE_UNAVAILABLE',*self.fixed);self.fixed=None
            surface=fn(self.display,self.config,self.window,None)
        self.width,self.height=self.fixed or self.full
        if self.fixed:self.p.log('RENDER_FIXED_SIZE',*self.fixed,'window',*self.full)
        return surface

    def resize(self, width, height):
        if width<=0 or height<=0:return
        self.full=(width,height)
        if self.fixed or self.fixed_size(width,height):
            if self.fixed_size(width,height)==self.fixed:return
            P=C.c_void_p
            make=self.egl.eglMakeCurrent;make.argtypes=[P,P,P,P];make.restype=C.c_uint
            destroy=self.egl.eglDestroySurface;destroy.argtypes=[P,P];destroy.restype=C.c_uint
            make(self.display,None,None,None);destroy(self.display,self.surface)
            self.surface=self.window_surface()
            if not self.surface or not make(self.display,self.surface,self.surface,self.context):
                raise RuntimeError('ANGLE could not recreate the rendering surface')
            self.egl.eglSwapInterval(self.display,0)
        elif (width,height)==(self.width,self.height):return
        else:self.width,self.height=width,height
        if not self.bindings[0x8D40]:
            self.function('glViewport','iiii')(*self.surface_rect(self.default_viewport))
            self.function('glScissor','iiii')(*self.surface_rect(self.default_scissor))
        self.p.log('WINDOW_RENDER_SIZE',width,height)

    def clear_bars(self):
        from window_layout import fit_rect
        left,top,w,h=fit_rect(self.width,self.height,self.logical_size)
        if (w,h)==(self.width,self.height) or self.bindings[0x8D40]:return
        scissor=(C.c_int*4)();color=(C.c_float*4)()
        enabled=self.function('glIsEnabled','u',C.c_ubyte)(0x0C11)
        self.function('glGetIntegerv','up')(0x0C10,C.cast(scissor,C.c_void_p))
        self.function('glGetFloatv','up')(0x0C22,C.cast(color,C.c_void_p))
        self.function('glEnable','u')(0x0C11)
        self.function('glClearColor','ffff')(0,0,0,1)
        bottom=self.height-top-h
        for rect in ((0,0,left,self.height),(left+w,0,self.width-left-w,self.height),
                     (left,0,w,bottom),(left,bottom+h,w,top)):
            if rect[2]>0 and rect[3]>0:
                self.function('glScissor','iiii')(*rect)
                self.function('glClear','u')(0x4000)
        self.function('glClearColor','ffff')(*color)
        self.function('glScissor','iiii')(*scissor)
        if not enabled:self.function('glDisable','u')(0x0C11)

    def present(self):
        self.clear_bars()
        if not self.swap(self.display,self.surface):raise RuntimeError('ANGLE could not present the game frame')

    def draw_feedback(self, feedback):
        import time
        if not feedback or not feedback['visible'] or time.perf_counter()>feedback['until']:return
        if self.bindings[0x8D40]:return
        if not hasattr(self,'input_overlay'):
            from input_feedback import FeedbackOverlay
            self.input_overlay=FeedbackOverlay(self)
        self.input_overlay.draw(feedback)

    def close(self):
        if hasattr(self,'input_overlay'):self.input_overlay.close()
        self.shader_cache.save()
        P=C.c_void_p
        for name,args,values in (
            ('eglMakeCurrent',[P,P,P,P],(self.display,None,None,None)),
            ('eglDestroySurface',[P,P],(self.display,self.surface)),
            ('eglDestroyContext',[P,P],(self.display,self.context)),
            ('eglTerminate',[P],(self.display,))):
            fn=getattr(self.egl,name);fn.argtypes=args;fn.restype=C.c_uint;fn(*values)

    def function(self,name,signature='',ret=None):
        key=(name,signature,ret)
        if key not in self.funcs:
            types={'u':C.c_uint,'i':C.c_int,'p':C.c_void_p,'f':C.c_float,'b':C.c_ubyte}
            f=getattr(self.gl,name);f.restype=ret;f.argtypes=[types[c] for c in signature];self.funcs[key]=f
        return self.funcs[key]

    ledger=None   # 联机回滚期间的 GL 对象登记（netplay_state.GLLedger）：推迟删除、回滚时删除被撤销帧中新建的对象

    def call(self,name,args):
        p=self.p
        ledger=self.ledger
        if ledger is not None and name in ledger.hooked and not ledger.busy:return ledger.handle(name,args)
        if name=='glBindFramebuffer':self.bindings[0x8D40]=args[1]
        if name in ('glViewport','glScissor') and not self.bindings[0x8D40]:
            rect=tuple(C.c_int(value).value for value in args[:4])
            if name=='glViewport':self.default_viewport=rect
            else:self.default_scissor=rect
            args=list(self.surface_rect(rect))+list(args[4:])
        if name=='glGetString':
            key=args[0]
            if key not in self.strings:
                q=self.function(name,'u',C.c_void_p)(key)
                self.strings[key]=p.cstr(C.string_at(q).decode() if q else '')
            return self.strings[key]
        if name=='glShaderSource':
            shader,count,ptr,lens=args[:4]
            strings=(C.c_void_p*count)(*[p.host(p.word(ptr+i*4)) for i in range(count)])
            self.function(name,'uipp')(shader,count,C.cast(strings,C.c_void_p),p.host(lens));return 0
        if name=='glBindBuffer':
            self.bindings[args[0]]=args[1]
            if hasattr(p.uc.lib,'msd_set_bound_buffer'):
                fn=p.uc.lib.msd_set_bound_buffer;fn.argtypes=[C.POINTER(type(p.uc.ctx)),C.c_uint32,C.c_uint32]
                fn(C.byref(p.uc.ctx),args[0],args[1])
        if name in ('glVertexAttribPointer','glDrawElements') and hasattr(p.uc.lib,'msd_bound_buffer'):
            target=0x8892 if name=='glVertexAttribPointer' else 0x8893
            fn=p.uc.lib.msd_bound_buffer;fn.argtypes=[C.POINTER(type(p.uc.ctx)),C.c_uint32];fn.restype=C.c_uint32
            self.bindings[target]=fn(C.byref(p.uc.ctx),target)
        sigs={
            'glEnable':'u','glDisable':'u','glBindTexture':'uu','glBlendFunc':'uu','glDepthFunc':'u','glBlendEquation':'u',
            'glScissor':'iiii','glDepthMask':'b','glUseProgram':'u','glFramebufferTexture2D':'uuuui',
            'glClearColor':'ffff','glClear':'u','glReadPixels':'iiiiuup','glBlendColor':'ffff',
            'glCullFace':'u','glHint':'uu','glViewport':'iiii','glUniform4fv':'iip','glUniformMatrix4fv':'iibp',
            'glEnableVertexAttribArray':'u','glDisableVertexAttribArray':'u','glVertexAttribPointer':'uiubip',
            'glDrawArrays':'uii','glActiveTexture':'u','glUniform1i':'ii','glBindBuffer':'uu','glDrawElements':'uiup',
            'glUniform4f':'iffff','glFrontFace':'u','glUniform1f':'if','glUniform3fv':'iip',
            'glGetProgramiv':'uup','glGetProgramInfoLog':'uipp','glCreateShader':'u','glCompileShader':'u',
            'glGetShaderiv':'uup','glGetShaderInfoLog':'uipp','glDeleteShader':'u','glDeleteProgram':'u',
            'glGetAttribLocation':'up','glGetUniformLocation':'up','glCreateProgram':'','glAttachShader':'uu',
            'glLinkProgram':'u','glValidateProgram':'u','glTexImage2D':'uiiiiiuup','glDeleteTextures':'ip',
            'glDeleteFramebuffers':'ip','glTexParameterf':'uuf','glGenTextures':'ip','glGetError':'',
            'glPixelStorei':'ui','glTexSubImage2D':'uiiiiiuup','glCompressedTexImage2D':'uiuiiiip',
            'glCompressedTexSubImage2D':'uiiiiiuip','glCopyTexImage2D':'uiuiiiii','glGenFramebuffers':'ip',
            'glGetIntegerv':'up','glBindFramebuffer':'uu','glCheckFramebufferStatus':'u','glFlush':'',
            'glVertexAttrib4f':'uffff','glVertexAttrib4fv':'up',
        }
        sig=sigs[name]
        returns={'glCreateShader':C.c_uint,'glCreateProgram':C.c_uint,'glGetAttribLocation':C.c_int,
                 'glGetUniformLocation':C.c_int,'glGetError':C.c_uint,'glCheckFramebufferStatus':C.c_uint}
        values=[]
        for i,kind in enumerate(sig):
            n=args[i]
            if kind=='p':
                offset=(name=='glVertexAttribPointer' and self.bindings[0x8892]) or (name=='glDrawElements' and self.bindings[0x8893])
                values.append(n if offset else p.host(n))
            elif kind=='f':values.append(__import__('struct').unpack('<f',__import__('struct').pack('<I',n))[0])
            elif kind=='i':values.append(C.c_int(n).value)
            else:values.append(n)
        result=self.function(name,sig,returns.get(name))(*values)
        return result or 0

    def capture(self,path):
        from PIL import Image
        self.clear_bars()
        pixels=(C.c_ubyte*(self.width*self.height*4))()
        self.function('glFinish')()
        self.function('glReadPixels','iiiiuup')(0,0,self.width,self.height,0x1908,0x1401,C.cast(pixels,C.c_void_p))
        Image.frombytes('RGBA',(self.width,self.height),bytes(pixels)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(path)
