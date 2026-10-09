"""Launch the Windows release with historical Event support."""
from pathlib import Path
import json,sys,shutil,argparse
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import portable_launcher
import probe,player
from event_trial import EventTrial,recover_transaction,HEADER
config=json.loads((ROOT/'event_trial_config.json').read_text(encoding='utf-8'))
source=(ROOT/config['source_pack']).resolve()
probe.APK=source/'game_data/original.apk'
probe.RESOURCE_ROOT=source/'game_data/assets'
probe.DATA_ROOT=source/'game_data'
OriginalProbe=probe.Probe
class TrialProbe(OriginalProbe):
    def path(self,s):
        path=super().path(s)
        if path.name=='event_otakara_ui_hud.obm':                 # 战斗拾取物计数的 1.39 布局图集（第 85 节）
            return ROOT/'historical_events/assets'/path.name
        if hasattr(self,'event_trial') and self.event_trial.native_map.active:
            selected=ROOT/'historical_events/assets'/self.event_trial.selected/path.name
            if path.name.startswith('stage_thumbnail_') and selected.is_file():return selected
            override=ROOT/'historical_events/assets'/path.name
            if path.name.startswith('stage_thumbnail_') and override.is_file():return override
        return path
    def initialize(self):
        from community_campaign import recover
        recover(self.saves)
        recover_transaction(self.saves)
        seed=source/'game_data/seed_community.json'
        community=self.saves/'community_progress.json'
        if not community.exists():shutil.copyfile(seed,community)
        super().initialize()
        from world_level_rules import WorldLevelRules
        self.world_level_rules=WorldLevelRules(self)
        self.event_trial=EventTrial(self,ROOT)
        from community_campaign import CommunityCampaign
        self.campaign=CommunityCampaign(self,self.event_trial)
        from online_session import OnlineClient,fingerprint
        import hashlib
        self.online=OnlineClient(fingerprint(self.community.manifest,self.community.campaign_catalog,
                                            hashlib.sha256(self.uc.library_path.read_bytes()).hexdigest()))
        from audio_options import AudioOptions
        self.audio_options=AudioOptions(self)
    def step_frame(self):
        super().step_frame()
        self.event_trial.update()
        self.campaign.update()
        self.audio_options.update()
    def back(self):
        trial=self.event_trial;app=self.app_instance();scene=self.word(app+0x22bc)
        if trial.transition_action is not None:return False
        campaign=self.campaign
        if campaign.opened:
            if campaign.area is not None:campaign.area=None
            elif campaign.world is not None:campaign.world=None
            else:
                campaign.opened=False
                if campaign.active:
                    campaign.clear_music();trial.leave(True);campaign.active=False;campaign.clear_runtime()
            campaign.page=0
            return True
        if trial.overlay:trial.command('close');return True
        if trial.browser.active and trial.browser.back():return True
        if trial.native_selector.active:trial.native_selector.back();return True
        if trial.selected and scene==67 and not trial.active_battle:trial.leave_to_menu();return True
        if trial.native_map.active and not self.word(HEADER+84) and not trial.active_battle and scene==34 and self.word(app+0x22dc) in (4,7,9):
            trial.native_map.back();return True
        if trial.is_native_shop_context():trial.close_native_shop();return True
        return super().back()
    def java_call(self,method,a,idx):
        if method and method[1]=='getFontWidthJava' and hasattr(self,'event_trial'):
            ref=self.word(a[3]+4) if (idx-114)%3==1 else a[4]
            size=self.word(a[3]) if (idx-114)%3==1 else a[3]
            text=self.objects.get(ref)
            new=self.event_trial.browser.measure(text,max(size,1)) if isinstance(text,str) else None
            if new is not None:
                self.objects[ref]=new
                try:return super().java_call(method,a,idx)
                finally:self.objects[ref]=text
        return super().java_call(method,a,idx)
    def draw_text(self,a,idx):
        # 浏览页：主菜单按钮文字仅在光栅化期间替换，随后恢复原字符串对象。
        restore=self.event_trial.browser.rename(a) if hasattr(self,'event_trial') else []
        try:return super().draw_text(a,idx)
        finally:
            for item,text in restore:self.objects[item]=text
    def touch_event(self,action,x,y):
        if self.campaign.touch(action,x,y):return
        if self.event_trial.touch(action,x,y):return
        super().touch_event(action,x,y)
    def close(self):
        if hasattr(self,'online'):self.online.close()
        if hasattr(self,'campaign'):self.campaign.close()
        if hasattr(self,'event_trial'):self.event_trial.close()
        super().close()
player.Probe=TrialProbe
import lab_runtime
lab_runtime.install()
lab_runtime.install_platform()
def create_player(self_test=False,audio_mode=None,fullscreen=None):
    player.TITLE='MSD WINDOWS S1XLV · 1.47.3'
    session=player.Player(self_test=self_test,audio_mode=audio_mode,fullscreen=fullscreen)
    session.guest_root=ROOT/('ui_test_guest' if self_test else config['profile'])
    session.status_file=ROOT/('ui_test_status.json' if self_test else 'event_trial_status.json')
    session.log_name='ui_test.log' if self_test else 'event_trial_player.log'
    if self_test:session.self_test_input=False
    return session
if __name__=='__main__':
    try:
        parser=argparse.ArgumentParser(description='MSD WINDOWS S1XLV 1.47.3')
        parser.add_argument('--self-test',action='store_true')
        parser.add_argument('--mute',action='store_true')
        parser.add_argument('--windowed',action='store_true')
        parser.add_argument('--fullscreen',action='store_true')
        args=parser.parse_args()
        session=create_player(args.self_test,fullscreen=False if args.windowed else (True if args.fullscreen else None))
        session.mute_requested=args.mute
        sys.exit(session.run())
    except Exception:
        import traceback,ctypes
        error=traceback.format_exc();(ROOT/'event_trial_error.log').write_text(error,encoding='utf-8')
        if '--self-test' not in sys.argv:ctypes.windll.user32.MessageBoxW(None,'游戏启动失败。错误记录：'+str(ROOT/'event_trial_error.log'),'MSD WINDOWS S1XLV',0x10)
        sys.exit(1)
