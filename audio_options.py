"""音频选项适配：原生控件、原生混音端口与原生存档。"""
HEADER=0x1ffea000
MAGIC=0x41554431
MUSIC=0x3d5c
EFFECTS=0x3d60
# 语言编号为原生 app+0x3d64（GetStringTitle 核对）：0 英 1 日 2 韩 3 西 4 葡 5 法 7 意 9 繁中 10 俄；6、8 无原生文字。
LABELS={
    0:('MUSIC','SOUND EFFECTS','ON','OFF'),
    1:('音楽設定','効果音設定','ON','OFF'),
    2:('음악 설정','효과음 설정','켜짐','꺼짐'),
    3:('MÚSICA','EFECTOS DE SONIDO','ON','OFF'),
    4:('MÚSICA','EFEITOS SONOROS','ON','OFF'),
    5:('MUSIQUE','EFFETS SONORES','ON','OFF'),
    6:('MUSIK','SOUNDEFFEKTE','AN','AUS'),
    7:('MUSICA','EFFETTI SONORI','ON','OFF'),
    8:('MUSIC','SOUND EFFECTS','ON','OFF'),
    9:('音樂設定','音效設定','開','關'),
    10:('МУЗЫКА','ЗВУКОВЫЕ ЭФФЕКТЫ','ВКЛ','ВЫКЛ'),
}

# 标题 OPTION 合并为一行两个按钮时的短文字（开关状态由原生喇叭图标表示）。语言编号同 LABELS。
TITLE_SHORT={0:('MUSIC','SOUND'),1:('音楽','効果音'),2:('음악','효과음'),3:('MÚSICA','EFECTOS'),4:('MÚSICA','EFEITOS'),
             5:('MUSIQUE','EFFETS'),6:('MUSIK','EFFEKTE'),7:('MUSICA','EFFETTI'),8:('MUSIC','SOUND'),
             9:('音樂','音效'),10:('МУЗЫКА','ЗВУКИ')}

class AudioOptions:
    def __init__(self,p):
        self.p=p;self.mode=None;self.tasks=();self.label_key=None;self.strings={}
        if not hasattr(p.uc.lib,'msd_beta_audio_options_version') or p.uc.lib.msd_beta_audio_options_version()!=1:
            raise RuntimeError('音频设置需要匹配的游戏核心')
        p.uc.lib.msd_enable_beta_audio_options();p.put(HEADER,MAGIC);p.put(HEADER+4,0)
        self.last_values=None;self.last_revision=0
    def values(self):
        app=self.p.app_instance()
        return self.p.word(app+MUSIC),self.p.word(app+EFFECTS)
    def apply_volume(self):
        p=self.p;app=p.app_instance()
        for name in ('Sound_SetVolumeBGM','Sound_SetVolumeSE','Sound_SetVolumeVO','Sound_SetVolumeUI','Sound_SetVolumeANNOUNCE'):
            p.call('_ZN7AppMain'+str(len(name))+name+'Ev',app)
    def context(self):
        p=self.p;app=p.app_instance();scene=p.word(app+0x22bc)
        if scene==28 and p.word(app+0x22dc)==2:return 'menu'
        if scene==113:return 'pause'
        if scene==20:
            task=p.word(app+0x3388)
            if task and p.word(task)==p.symbols['_ZN7AppMain14GT_TitleOptionEP17GENERAL_TASK_BASE']:return 'title'
        return None
    def set_label(self,task,text):
        p=self.p;app=p.app_instance()
        if text not in self.strings:self.strings[text]=p.cstr(text)
        p.call('_ZN9TexString13setStringCharEPKcPiP4Fontb',p.word(app+0x3238),self.strings[text],task+0x1f8,p.word(app+0x60),0)
    def update(self):
        p=self.p;app=p.app_instance();values=self.values();revision=p.word(HEADER+4)
        # 混音端口创建完成后，原生 BGM 比例计算的分母才具备有效值。
        if not p.word(app+0x9a48):return
        if self.last_values is None:
            self.apply_volume();self.last_values=values;self.last_revision=revision
        elif values!=self.last_values or revision!=self.last_revision:
            self.apply_volume()
            p.call('_ZN7AppMain20WriteMainSaveDataExeEv',app)
            if not p.call('_ZN7AppMain18SaveDataWriteCheckEv',app):raise RuntimeError('音频设置存档核验失败')
            self.last_values=values;self.last_revision=revision
            p.log('BETA_AUDIO_OPTIONS',bool(values[0]),bool(values[1]))
        mode=self.context()
        if mode is None:
            if self.mode=='menu' and p.word(app+0x22bc)==28:
                for offset in (0x3390,0x3394):
                    task=p.word(app+offset)
                    # 原生 0x80 控制绘制，0x20 控制点击；退出时同时清除按压及选择状态。
                    p.put(task+0x7c,p.word(task+0x7c)|0xa0)
                    p.call('_ZN7AppMain16ClearSelectPanelEP17GENERAL_TASK_BASEi',app,task,0)
            self.mode=None;self.tasks=();self.label_key=None;return
        if mode=='menu':
            offsets=(0x338c,0x3390,0x3394)
            if self.mode!=mode:
                # 原生选项页逐行入场（SelectCockpitMainMenu：第 10、11 行延迟 5、7 帧，每行 +2）。本调用晚于原生一帧，
                # 音乐、音效两行以语言行（第 11 行，任务 +104 为剩余延迟）当前值 +2、+4 接续。
                language_task=p.word(app+0x338c);remaining=p.word(language_task+104) if language_task else 7
                for index,step in ((12,2),(13,4)):p.call('_ZN7AppMain10SetPanelInEii',app,index,remaining+step)
        elif mode=='pause':offsets=(0x3364,0x3368,0x336c)
        else:offsets=(0x3390,0x3394,0x3398)
        language,music,effects=(p.word(app+offset) for offset in offsets)
        if mode=='menu':
            from probe import u32f
            # 与主菜单原生三行控件的中心位置保持一致。
            for task,y in zip((language,music,effects),(180.0,272.0,364.0)):p.put(task+0x88,u32f(y))
        elif mode=='pause':
            from probe import u32f
            for offset,y in zip(range(0x3364,0x3378,4),(176.0,244.0,312.0,380.0,448.0)):
                p.put(p.word(app+offset)+0x88,u32f(y))
        for task,value in zip((music,effects),values):
            p.put(task+0x7c,p.word(task+0x7c)&~(0xa0 if mode=='menu' else 0x80))
            if mode in ('title','pause'):p.put(task+0x80,(p.word(task+0x80)&~0x18)|(0x08 if value else 0x10))
            else:p.put(task+0x1b4,12 if value else 13)
        lang=p.word(app+0x3d64);key=(mode,lang,values,language,music,effects)
        if self.label_key!=key:
            a,b,on,off=LABELS.get(lang,LABELS[0])
            texts=(a+' : '+(on if values[0] else off),b+' : '+(on if values[1] else off))
            if mode=='title':
                # 通过原生整页重建流程更新标题控件的文字图集及索引。
                table=p.word(p.symbols['strTitleTbl']+lang*4)
                mods=getattr(p,'mod_page',None)
                if mods is not None and mods.extension:
                    # 模组 M4：音乐、音效合并为一行两个按钮（短文字），第 6 个面板改为 MOD 设定。
                    texts=TITLE_SHORT.get(lang,TITLE_SHORT[0])
                    label=mods.title_label('mod',lang)
                    if label not in self.strings:self.strings[label]=p.cstr(label)
                    p.put(table+5*4,self.strings[label])
                for index,text in enumerate(texts,1):
                    if text not in self.strings:self.strings[text]=p.cstr(text)
                    p.put(table+index*4,self.strings[text])
                p.call('_ZN7AppMain19SetTitlePanelStringEv',app)
            elif mode=='pause':
                tex=p.word(app+0x3238);p.call('_ZN9TexString11clearStringEv',tex)
                for index,offset in enumerate(range(0x3364,0x3378,4)):
                    task=p.word(app+offset)
                    if index in (1,2):self.set_label(task,texts[index-1])
                    else:
                        pointer=p.call('_Z14GetStringPauseii',index,0xffffffff)
                        p.call('_ZN9TexString13setStringCharEPKcPiP4Fontb',tex,pointer,task+0x1f8,p.word(app+0x60),0)
            else:
                for task,text in zip((music,effects),texts):self.set_label(task,text)
            self.label_key=key
        self.mode=mode;self.tasks=(language,music,effects)
