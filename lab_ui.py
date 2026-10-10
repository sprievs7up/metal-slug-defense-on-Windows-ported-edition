"""LAB 界面共用部分：原生素材、文字表（随游戏语言）、按钮按下反馈、原生菜单音效与 BGM、宿主闸门动画。

语言取 app+0x3d64（与原生一致：1 日语，9 繁体中文，10 简体中文，其余显示英语）。
菜单音效经 AppMain::Sound_RequestPlayMenuSE：13 为原生按钮确定音（159 处调用），8 为关闭/返回，
MISSION 菜单 BGM 为 135（SC_MissionMenuInit2 → Sound_RequestPlayBGMEx2）。
"""
import os
from pathlib import Path

W, H = 1280, 720
LANGUAGE_OFFSET = 0x3d64
SE_DECIDE, SE_CLOSE = 13, 8
BGM_MISSION, BGM_STAGE = 135, 103
BGM_MENU = 101                    # SC_MainMenuLoop 状态 0 在闸门结束后请求的主菜单 BGM
WHITE, GOLD, GRAY, DARK = (240, 240, 240, 255), (255, 214, 90, 255), (165, 165, 165, 255), (40, 30, 20, 255)
BLUE, RED = (150, 210, 255, 255), (255, 150, 140, 255)

# 原生素材矩形（图集, (x, y, w, h)），按不透明像素的连通区域量得。
# 顶部标题栏：ConvMenuParts 第 0 项（原生各菜单顶栏，含“METAL SLUG DEFENSE”小字与下沿铆钉条）。
# 原生以 2 倍绘制于 960 基准画面（16:9 时宽 1137.8），在 1280×720 画布上为等比 2.25 倍，宽 1278。
# 第 1 项 (0, 0, 568, 67) 是底部按钮栏的底板，不用作顶栏。
HEADER = ('menuparts.obm', (0, 68, 568, 51))
HEADER_SCALE = 2.25
HEADER_H = round(51 * HEADER_SCALE)                            # 115
PANEL = ('popup.obm', (0, 0, 300, 150))                        # 弹窗底板
BOARD = ('pause_window.obm', (15, 58, 290, 212))               # 暂停窗口米色面板（不含烙印标题）
BRICK = ('pause_menu.obm', (0, 0, 512, 320))                   # 暂停背景砖墙
BUTTONS = {'normal': ('menuparts.obm', (191, 144, 190, 23)),   # 棕
           'light': ('menuparts.obm', (191, 120, 190, 23)),    # 米色
           'on': ('menuparts.obm', (191, 168, 90, 23)),        # 绿
           'off': ('menuparts.obm', (282, 168, 90, 23))}       # 红
ICON_BUTTONS = {'ok': ('menuparts.obm', (813, 170, 60, 48)), 'back': ('menuparts.obm', (935, 170, 60, 48))}  # ConvMenuParts 36/30
# 原生图标按钮（GT_CockpitButtonDraw 0x2003bc）：按下期间先画 ConvMenuParts 79 青色框（锚点 3,3），再画图标，
# 最后画 37 三灯（锚点 −19,−2）；按钮与上述部件按同一倍率绘制。
# 准备界面顶栏按用户确认的比例等比缩小为 1.5 倍（按钮 90×72，青色框 99×81），使按钮与按下光效都位于顶栏深色区内：
# 顶栏原图第 3–40 行为深色区、第 41 行起为铆钉条，2.25 倍后为画布 y 7–92。
ICON_SCALE = 1.5
HEADER_DARK = (round(3 * 2.25), round(41 * 2.25))
ICON_PRESS_FRAME = (('menuparts.obm', (563, 155, 66, 54)), (3, 3))
ICON_PRESS_LAMPS = (('menuparts.obm', (221, 247, 22, 6)), (-19, -2))
# AI 段位文字色（参考 APEX 段位色系）。实际绘制时在深色底板上核对亮度对比，不足 4.5 的只提高文字亮度（色相不变）。
TIER_COLORS = {'ROOKIE': (0x8A, 0x81, 0x78), 'BRONZE': (0xB8, 0x73, 0x33), 'SILVER': (0xC9, 0xCE, 0xD6),
               'GOLD': (0xE8, 0xC0, 0x4A), 'PLATINUM': (0x4F, 0xC3, 0xC9), 'DIAMOND': (0x5B, 0xA8, 0xF5),
               'MASTER': (0xA3, 0x5C, 0xF0), 'PREDATOR': (0xE0, 0x30, 0x2E)}
TAB_ON, TAB_OFF = ('menuparts.obm', (0, 120, 190, 33)), ('menuparts.obm', (0, 154, 190, 33))
ROW_STYLES = {None: TAB_OFF, 'player': TAB_OFF, 'enemy': ('menuparts.obm', (0, 222, 190, 33))}
CELLS = {'player': ('unit.obm', (362, 151, 50, 50)), 'enemy': ('unit.obm', (428, 125, 50, 50)),
         'empty': ('unit.obm', (439, 188, 50, 50))}
ICON_PAGES = {0: 'unit_icon_01.obm', 1: 'unit_icon_02.obm'}

LANGS = {1: 'JP', 9: 'ZT', 10: 'ZS'}
TEXT = {
    'prep_title': ('LAB · 準備', 'LAB · 准备', 'LAB · 準備', 'LAB · SETUP'),
    'start': ('開始戰鬥 →', '开始战斗 →', 'バトル開始 →', 'START →'),
    'player_deck': ('我方牌組', '我方牌组', '自軍デッキ', 'YOUR DECK'),
    'enemy_deck': ('敵方牌組', '敌方牌组', '敵軍デッキ', 'ENEMY DECK'),
    'all_level': ('全部等級', '全部等级', '全レベル', 'ALL LV'),
    'apply': ('套用', '应用', '適用', 'APPLY'),
    'random': ('隨機', '随机', 'ランダム', 'RANDOM'),
    'clear': ('清空', '清空', 'クリア', 'CLEAR'),
    'empty': ('空', '空', '空き', 'EMPTY'),
    'unit_unavailable': ('未啟用', '未启用', '無効', 'N/A'),
    'battle_settings': ('戰鬥設定', '战斗设定', 'バトル設定', 'BATTLE'),
    'player_base': ('我方據點等級', '我方据点等级', '自軍拠点レベル', 'YOUR BASE LV'),
    'enemy_base': ('敵方據點等級', '敌方据点等级', '敵軍拠点レベル', 'ENEMY BASE LV'),
    'max_full': ('MAX（完全控制）', 'MAX（完全控制）', 'MAX（フルコントロール）', 'MAX (FULL CONTROL)'),
    'map': ('地圖', '地图', 'マップ', 'MAP'),
    'world_0': ('地圖 1', '地图 1', 'マップ 1', 'MAP 1'), 'world_1': ('地圖 2', '地图 2', 'マップ 2', 'MAP 2'),
    'world_2': ('地圖 3', '地图 3', 'マップ 3', 'MAP 3'),
    'world_9': ('裏地圖 1', '里地图 1', '裏マップ 1', 'EX MAP 1'),
    'world_10': ('裏地圖 2', '里地图 2', '裏マップ 2', 'EX MAP 2'),
    'world_11': ('裏地圖 3', '里地图 3', '裏マップ 3', 'EX MAP 3'),
    'stage_no': ('{} {}-{}', '{} {}-{}', '{} {}-{}', '{} {}-{}'),
    'base_short': ('據點', '据点', '拠点', 'BASE'),
    'copy_enemy': ('複製敵方', '复制敌方', '敵軍をコピー', 'COPY ENEMY'),
    'copy_player': ('複製我方', '复制我方', '自軍をコピー', 'COPY YOURS'),
    'control': ('控制', '控制', '操作', 'CONTROL'),
    'full_control': ('完全控制（無冷卻・AP 無限）', '完全控制（无冷却 · AP 无限）', 'フルコントロール（CTなし・AP無限）',
                     'FULL CONTROL (NO CD · ∞ AP)'),
    'player_ai': ('我方 AI 自動出兵', '我方 AI 自动出兵', '自軍 AI 自動出撃', 'YOUR AI DEPLOY'),
    'player_ai_short': ('我方 AI', '我方 AI', '自軍 AI', 'YOUR AI'),
    'enemy_ai_short': ('敵方 AI', '敌方 AI', '敵軍 AI', 'ENEMY AI'),
    'player_auto_special': ('我方自動施放絕招', '我方自动释放绝招', '自軍 必殺技自動', 'YOUR AUTO SPECIAL'),
    'enemy_ai': ('敵方 AI 自動出兵', '敌方 AI 自动出兵', '敵軍 AI 自動出撃', 'ENEMY AI DEPLOY'),
    'enemy_auto_special': ('敵方自動施放絕招', '敌方自动释放绝招', '敵軍 必殺技自動', 'ENEMY AUTO SPECIAL'),
    'on': ('開', '开', 'ON', 'ON'), 'off': ('關', '关', 'OFF', 'OFF'),
    'advantage': ('優勢設定', '优势设定', '優位設定', 'ADVANTAGE'),
    'adv_hp': ('生命', '生命', 'HP', 'HP'), 'adv_atk': ('攻擊', '攻击', '攻撃', 'ATK'),
    'adv_player': ('我方', '我方', '自軍', 'YOU'), 'adv_enemy': ('敵方', '敌方', '敵軍', 'ENEMY'),
    'presets': ('預設與履歷', '预设与履历', 'プリセット・履歴', 'PRESETS'),
    'preset': ('預設 {}', '预设 {}', 'プリセット {}', 'PRESET {}'),
    'save': ('儲存', '保存', '保存', 'SAVE'), 'load': ('讀取', '读取', '読込', 'LOAD'),
    'history': ('戰鬥履歷', '战斗履历', '戦闘履歴', 'HISTORY'),
    'saved': ('已儲存至預設 {}', '已保存到预设 {}', 'プリセット {} に保存しました', 'Saved to preset {}'),
    'loaded': ('已讀取預設 {}', '已读取预设 {}', 'プリセット {} を読み込みました', 'Loaded preset {}'),
    'preset_empty': ('預設 {} 為空', '预设 {} 为空', 'プリセット {} は空です', 'Preset {} is empty'),
    'hint': ('點擊格子選擇單位・± 調整等級（Lv1–40，僅用於本場，不寫入存檔）・Esc 關閉',
             '点击格子选择单位 · ± 调整等级（Lv1–40，只用于本场，不写存档）· Esc 关闭',
             'マスをクリックでユニット選択・± でレベル調整（Lv1–40、この戦闘のみ・セーブには書き込みません）・Esc で閉じる',
             'Click a slot to pick a unit · ± level (Lv1–40, this battle only, not saved) · Esc to close'),
    'picker_title': ('選擇單位・{}第 {} 格', '选择单位 · {}第 {} 格', 'ユニット選択・{} {} 番', 'SELECT UNIT · {} SLOT {}'),
    'set_empty': ('設為空槽', '设为空槽', '空きにする', 'SET EMPTY'),
    'tab_all': ('全部', '全部', 'すべて', 'ALL'), 'tab_community': ('社群', '社区', 'コミュニティ', 'COMMUNITY'),
    'f0': ('正規軍', '正规军', '正規軍', 'REGULAR'), 'f1': ('叛軍', '叛军', '反乱軍', 'REBEL'),
    'f2': ('普特曼軍', '普特曼军', 'プトレマイック軍', 'PTOLEMAIC'), 'f3': ('火星人', '火星人', 'マーズピープル', 'MARS'),
    'f4': ('其他', '其他', 'その他', 'OTHER'), 'f5': ('聯動', '联动', 'コラボ', 'COLLAB'),
    'community_mark': ('社群', '社区', 'COM', 'COM'),
    'prev': ('上一頁', '上一页', '前へ', 'PREV'), 'next': ('下一頁', '下一页', '次へ', 'NEXT'),
    'page': ('{} / {}（共 {} 個）', '{} / {}（共 {} 个）', '{} / {}（全 {} 体）', '{} / {} ({} units)'),
    'history_title': ('戰鬥履歷（最近 12 場）', '战斗履历（最近 12 场）', '戦闘履歴（直近 12 戦）', 'HISTORY (LAST 12)'),
    'no_history': ('尚無紀錄', '暂无记录', '記録なし', 'No records'),
    'win_player': ('我方勝', '我方胜', '自軍勝利', 'YOU WIN'), 'win_enemy': ('敵方勝', '敌方胜', '敵軍勝利', 'ENEMY WINS'),
    'aborted': ('中止', '中止', '中断', 'ABORTED'),
    'history_row': ('{}   {}   {:.0f} 秒   {}', '{}   {}   {:.0f} 秒   {}', '{}   {}   {:.0f} 秒   {}',
                    '{}   {}   {:.0f}s   {}'),
    'side_player': ('我方', '我方', '自軍', 'YOUR'), 'side_enemy': ('敵方', '敌方', '敵軍', 'ENEMY'),
    'menu_title': ('LAB 選單', 'LAB 菜单', 'LAB メニュー', 'LAB MENU'),
    'menu_paused': ('戰鬥已暫停', '战斗已暂停', 'バトル一時停止中', 'PAUSED'),
    'restart': ('重新開始', '重新开始', 'リスタート', 'RESTART'),
    'exit_lab': ('返回準備畫面', '返回准备界面', '準備画面へ戻る', 'BACK TO SETUP'),
    'resume': ('繼續', '继续', '続ける', 'RESUME'),
    'fb_busy': ('戰鬥中無法啟動 LAB', '战斗中无法启动 LAB', 'バトル中は LAB を開始できません', 'Cannot start LAB during a battle'),
    'fb_start': ('戰鬥開始・{}', '战斗开始 · {}', 'バトル開始・{}', 'Battle start · {}'),
    'fb_back': ('已返回準備畫面', '已返回准备界面', '準備画面に戻りました', 'Back to setup'),
    'fb_back_menu': ('已返回選單', '已返回菜单', 'メニューに戻りました', 'Back to menu'),
    'fb_failed': ('{} 失敗：{}', '{} 失败：{}', '{} 失敗：{}', '{} failed: {}'),
    'fb_support': ('支援發動', '支援发动', '支援発動', 'Support activated'),
    'fb_full': ('完全控制 {}', '完全控制 {}', 'フルコントロール {}', 'Full control {}'),
    'fb_ai': ('敵方 AI {}・我方 AI {}', '敌方 AI {} · 我方 AI {}', '敵軍 AI {}・自軍 AI {}', 'Enemy AI {} · your AI {}'),
    'fb_no_enemy': ('找不到敵方控制器', '未找到敌方控制器', '敵軍コントローラーが見つかりません', 'Enemy controller not found'),
    'fb_enemy_ap': ('敵方 AP 升級', '敌方 AP 升级', '敵軍 AP レベルアップ', 'Enemy AP level up'),
    'fb_enemy_ap_no': ('敵方 AP 無法升級', '敌方 AP 无法升级', '敵軍 AP はレベルアップできません', 'Enemy AP cannot level up'),
    'fb_enemy_slug': ('敵方合金彈頭出擊', '敌方弹头车出击', '敵軍メタルスラッグ出撃', 'Enemy Metal Slug attack'),
    'fb_enemy_slug_no': ('敵方合金彈頭尚未就緒', '敌方弹头车未就绪', '敵軍メタルスラッグ未準備', 'Enemy Metal Slug not ready'),
    'fb_enemy_special': ('敵方絕招 {} 個', '敌方绝招 {} 个', '敵軍必殺技 {} 体', 'Enemy specials: {}'),
    'fb_enemy_special_none': ('敵方沒有可施放絕招的單位', '敌方无绝招就绪单位', '必殺技が使える敵軍ユニットはいません',
                              'No enemy special ready'),
    'fb_not_playing': ('{} 戰鬥未進行', '{} 战斗未进行', '{} バトル中ではありません', '{} battle not running'),
    'fb_empty_slot': ('{} 空槽位', '{} 空槽位', '{} 空きスロット', '{} empty slot'),
    'fb_unit_limit': ('{} 已達單位數量上限', '{} 已达到单位数量上限', '{} ユニット数の上限です', '{} unit limit reached'),
    'fb_cannot': ('{} 目前無法生產（AP {} / {}）', '{} 当前无法生产（AP {} / {}）', '{} 出撃できません（AP {} / {}）',
                  '{} cannot deploy (AP {} / {})'),
    'fb_deployed': ('{} 敵方出擊', '{} 敌方出击', '{} 敵軍出撃', '{} enemy deployed'),
    'fb_vs_deployed': ('{} 出擊', '{} 出击', '{} 出撃', '{} deployed'),
    'fb_vs_ap': ('{} AP 升級', '{} AP 升级', '{} AP レベルアップ', '{} AP level up'),
    'fb_vs_ap_no': ('{} AP 無法升級', '{} AP 无法升级', '{} AP はレベルアップできません', '{} AP cannot level up'),
    'fb_vs_slug': ('{} 合金彈頭出擊', '{} 弹头车出击', '{} メタルスラッグ出撃', '{} Metal Slug attack'),
    'fb_vs_slug_no': ('{} 合金彈頭尚未就緒', '{} 弹头车未就绪', '{} メタルスラッグ未準備', '{} Metal Slug not ready'),
    'fb_vs_special': ('{} 絕招 {} 個', '{} 绝招 {} 个', '{} 必殺技 {} 体', '{} specials: {}'),
    'fb_vs_special_none': ('{} 沒有可施放絕招的單位', '{} 无绝招就绪单位', '{} 必殺技が使えるユニットはいません',
                           '{} no unit ready for special'),
    'versus': ('雙人對戰', '双人对战', '2P 対戦', '2P VERSUS'),
    'vs_soon': ('區域網對戰與遠端對戰準備中', '局域网对战与远程对战准备中', 'LAN 対戦・オンライン対戦は準備中です', 'LAN and online versus coming soon'),
    'vs_keys': ('{}：{}{} 選擇 · {} AP · {} 出兵 · {} 絕招 · {} 彈頭車', '{}：{}{} 选择 · {} AP · {} 出兵 · {} 绝招 · {} 弹头车',
                '{}：{}{} 選択・{} AP・{} 出撃・{} 必殺技・{} スラッグ', '{}: {}{} select · {} AP · {} deploy · {} special · {} slug'),
    'vs_rules': ('完全控制、AI 與自動絕招關閉 · 滑鼠只能拖動鏡頭', '完全控制、AI 与自动绝招关闭 · 鼠标只能拖动镜头',
                 'フルコントロール・AI・自動必殺技はオフ・マウスはカメラのみ', 'Full control, AI, auto special off · mouse: camera only'),
    'vs_menu_title': ('對戰選單', '对战菜单', '対戦メニュー', 'VERSUS MENU'),
    'menu_music': ('音樂設定', '音乐设置', '音楽設定', 'MUSIC'),
    'menu_effects': ('音效設定', '音效设置', '効果音設定', 'SOUND EFFECTS'),
    'vs_prep_title': ('VERSUS · 準備', 'VERSUS · 准备', 'VERSUS · 準備', 'VERSUS · SETUP'),
    # VS CPU（vs_cpu.py；标题各语言相同，用户 2026-10-11 确认）
    'cpu_prep_title': ('VS CPU', 'VS CPU', 'VS CPU', 'VS CPU'),
    'cpu_you_deck': ('玩家牌組（{}）', '玩家牌组（{}）', 'プレイヤー（{}）', 'YOU ({})'),
    'cpu_cpu_deck': ('CPU 牌組（{}）', 'CPU 牌组（{}）', 'CPU（{}）', 'CPU ({})'),
    'cpu_copy': ('複製對方', '复制对方', '相手をコピー', 'COPY OTHER'),
    'cpu_side': ('玩家位置', '玩家位置', 'プレイヤー', 'YOUR SIDE'),
    'cpu_side_p1': ('P1 · 左', 'P1 · 左', 'P1・左', 'P1 · LEFT'),
    'cpu_side_p2': ('P2 · 右', 'P2 · 右', 'P2・右', 'P2 · RIGHT'),
    'cpu_tier': ('CPU 等級', 'CPU 等级', 'CPU レベル', 'CPU LEVEL'),
    'cpu_rules': ('原版操作介面 · 點擊絕招就緒的單位施放絕招', '原版操作界面 · 点击绝招就绪的单位施放绝招',
                  '通常の操作画面・必殺技が使えるユニットをタップ', 'Standard controls · tap a ready unit for its special'),
    'cpu_win_you': ('玩家勝', '玩家胜', 'プレイヤー勝利', 'YOU WIN'),
    'cpu_win_cpu': ('CPU 勝', 'CPU 胜', 'CPU 勝利', 'CPU WINS'),
    'vs_keys_title': ('按鍵設定', '按键设定', 'キー設定', 'CONTROLS'),
    'vs_help_title': ('操作說明', '操作说明', '操作説明', 'HOW TO PLAY'),
    'vs_side_p1': ('玩家1（P1 · 左）', '玩家1（P1 · 左）', 'プレイヤー1（P1・左）', 'PLAYER 1 (P1 · LEFT)'),
    'vs_side_p2': ('玩家2（P2 · 右）', '玩家2（P2 · 右）', 'プレイヤー2（P2・右）', 'PLAYER 2 (P2 · RIGHT)'),
    # 双人对战中“我方 / 敌方”改称“玩家1 / 玩家2”（用户 2026-10-08 要求；lab_prep.LabPrep.t 以 vs_ 前缀选用）。
    'vs_player_deck': ('玩家1 牌組', '玩家1 牌组', 'プレイヤー1 デッキ', 'PLAYER 1 DECK'),
    'vs_enemy_deck': ('玩家2 牌組', '玩家2 牌组', 'プレイヤー2 デッキ', 'PLAYER 2 DECK'),
    'vs_copy_enemy': ('複製玩家2', '复制玩家2', 'P2 をコピー', 'COPY P2'),
    'vs_copy_player': ('複製玩家1', '复制玩家1', 'P1 をコピー', 'COPY P1'),
    'vs_adv_player': ('玩家1', '玩家1', 'プレイヤー1', 'PLAYER 1'), 'vs_adv_enemy': ('玩家2', '玩家2', 'プレイヤー2', 'PLAYER 2'),
    'vs_side_player': ('玩家1', '玩家1', 'プレイヤー1', 'PLAYER 1 '), 'vs_side_enemy': ('玩家2', '玩家2', 'プレイヤー2', 'PLAYER 2 '),
    'vs_win_player': ('玩家1勝', '玩家1胜', 'P1 勝利', 'P1 WINS'), 'vs_win_enemy': ('玩家2勝', '玩家2胜', 'P2 勝利', 'P2 WINS'),
    'vs_col_action': ('動作', '动作', '操作', 'ACTION'),
    'vs_col_key': ('鍵盤', '键盘', 'キーボード', 'KEYBOARD'),
    'vs_col_pad': ('手把', '手柄', 'コントローラー', 'GAMEPAD'),
    'vs_act_left': ('左選', '左选', '左を選択', 'Select left'),
    'vs_act_right': ('右選', '右选', '右を選択', 'Select right'),
    'vs_act_select': ('選擇單位', '选择单位', 'ユニット選択', 'Select unit'),
    'vs_act_ap': ('AP 升級', 'AP 升级', 'AP レベルアップ', 'AP level up'),
    'vs_act_deploy': ('出兵', '出兵', '出撃', 'Deploy'),
    'vs_act_special': ('全體絕招', '全体绝招', '全員必殺技', 'All specials'),
    'vs_act_slug': ('彈頭車出擊', '弹头车出击', 'メタルスラッグ', 'Metal Slug'),
    'vs_act_menu': ('戰鬥中選單', '战斗中菜单', 'バトルメニュー', 'Battle menu'),
    'vs_act_camera': ('鏡頭', '镜头', 'カメラ', 'Camera'),
    'vs_pad_fixed': ('十字鍵 / 左搖桿', '十字键 / 左摇杆', '十字キー / 左スティック', 'D-pad / left stick'),
    'vs_cam_p1': ('滑鼠拖動戰場 / 右搖桿', '鼠标拖动战场 / 右摇杆', 'マウスドラッグ / 右スティック', 'Mouse drag / right stick'),
    'vs_cam_p2': ('右搖桿', '右摇杆', '右スティック', 'Right stick'),
    'vs_pads': ('手把', '手柄', 'コントローラー', 'GAMEPADS'),
    'vs_pad_none': ('未連接手把（以 XInput 相容手把為準）', '未连接手柄（以 XInput 兼容手柄为准）',
                    'コントローラー未接続（XInput 対応機）', 'No gamepad connected (XInput compatible)'),
    'vs_pad_row': ('手把 {}：{} → {}', '手柄 {}：{} → {}', 'コントローラー {}：{} → {}', 'Gamepad {}: {} → {}'),
    'vs_pad_single': ('單一手把分配給：{}', '单一手柄分配给：{}', '1 台のときの割り当て：{}', 'Single gamepad goes to: {}'),
    'vs_reset': ('恢復預設', '恢复默认', '初期設定に戻す', 'Reset to default'),
    'vs_capture_key': ('請按下 {} 的「{}」鍵（Esc 取消）', '请按下 {} 的“{}”键（Esc 取消）',
                       '{} の「{}」に割り当てるキーを押してください（Esc で取消）', 'Press a key for {} {} (Esc cancels)'),
    'vs_capture_pad': ('請按下 {} 的「{}」手把按鍵（START 或 Esc 取消）', '请按下 {} 的“{}”手柄按键（START 或 Esc 取消）',
                       '{} の「{}」に割り当てるボタンを押してください（START / Esc で取消）',
                       'Press a gamepad button for {} {} (START / Esc cancels)'),
    'vs_bound': ('{} {}：{}', '{} {}：{}', '{} {}：{}', '{} {}: {}'),
    'vs_swapped': ('{} {}：{}（與「{}」互換）', '{} {}：{}（与“{}”互换）', '{} {}：{}（「{}」と入れ替え）',
                   '{} {}: {} (swapped with {})'),
    'vs_banned': ('{} 為保留鍵，無法指定', '{} 为保留键，无法指定', '{} は予約キーのため割り当てできません',
                  '{} is reserved and cannot be assigned'),
    'vs_reset_done': ('已恢復預設按鍵', '已恢复默认按键', '初期設定に戻しました', 'Controls reset to default'),
    'vs_rule_lines': (
        ('摧毀對方據點即獲勝；雙方勝利時都播放 MISSION COMPLETE。',
         'AP 隨時間累積，出兵消耗 AP；升級 AP 可提高上限與累積速度。',
         '左右鍵選擇單位格，出兵鍵出擊選中的單位（冷卻中或 AP 不足時無法出擊）。',
         '絕招只能全體施放：按下絕招鍵時，己方所有絕招就緒的單位同時施放。',
         '彈頭車充能完成後，按彈頭車鍵出擊。',
         '鏡頭由先開始操作的一方控制，直到放開為止；同時開始時 P1 優先。',
         '對戰中完全控制、AI 與自動絕招關閉；滑鼠點擊不會出兵或施放絕招。',
         '兩支手把依連接順序分給 P1、P2；只有一支時可在按鍵設定中指定。',
         '使用 , . / 等鍵前，請先將輸入法切換為英文。'),
        ('摧毁对方据点即获胜；双方胜利时都播放 MISSION COMPLETE。',
         'AP 随时间累积，出兵消耗 AP；升级 AP 可提高上限与累积速度。',
         '左右键选择单位格，出兵键出击选中的单位（冷却中或 AP 不足时无法出击）。',
         '绝招只能全体释放：按下绝招键时，己方所有绝招就绪的单位同时释放。',
         '弹头车充能完成后，按弹头车键出击。',
         '镜头由先开始操作的一方控制，直到松开为止；同时开始时 P1 优先。',
         '对战中完全控制、AI 与自动绝招关闭；鼠标点击不会出兵或释放绝招。',
         '两只手柄按连接顺序分给 P1、P2；只有一只时可在按键设定中指定。',
         '使用 , . / 等键前，请先将输入法切换为英文。'),
        ('相手の拠点を破壊すると勝利です。どちらが勝っても MISSION COMPLETE が表示されます。',
         'AP は時間とともに貯まり、出撃で消費します。AP レベルアップで上限と回復速度が上がります。',
         '左右キーでユニット枠を選び、出撃キーで出撃します（クールダウン中や AP 不足時は不可）。',
         '必殺技は全員同時のみ：必殺技キーで、準備のできた自軍ユニットが一斉に発動します。',
         'メタルスラッグはゲージが満タンになったら出撃キーで出撃できます。',
         'カメラは先に操作を始めた側が離すまで操作します。同時の場合は P1 が優先です。',
         '対戦中はフルコントロール・AI・自動必殺技がオフになり、マウスのクリックでは出撃できません。',
         'コントローラー 2 台は接続順に P1・P2 に割り当て。1 台のときはキー設定で指定できます。',
         ', . / などのキーを使う前に、入力方式を英語に切り替えてください。'),
        ('Destroy the opposing base to win. Either victory shows MISSION COMPLETE.',
         'AP builds up over time and is spent to deploy. AP level up raises the cap and the gain rate.',
         'Left/right select a unit slot; Deploy sends the selected unit (not while cooling down or short of AP).',
         'Specials are all-or-nothing: the Special key fires every ready unit on your side at once.',
         'When the Metal Slug gauge is full, press the Slug key to launch it.',
         'The camera belongs to whoever starts moving it first until they let go; P1 wins a tie.',
         'Full control, AI and auto specials are off in versus; mouse clicks never deploy or fire specials.',
         'Two gamepads go to P1 and P2 in connection order; with one, choose its player under Controls.',
         'Switch your input method to English before using keys such as , . /'),
    ),
    'fb_rejected': ('{} 原生拒絕', '{} 原生拒绝', '{} 出撃不可', '{} rejected'),
    'menu_hint': ('點擊或 ↑/↓ + Enter 選擇・Esc 繼續', '点击或 ↑/↓ + Enter 选择 · Esc 继续',
                  'クリック または ↑/↓ + Enter・Esc で続ける', 'Click or ↑/↓ + Enter · Esc to resume'),
}


def lang(p):
    app = p.app_instance()
    return LANGS.get(p.word(app + LANGUAGE_OFFSET) if app else 0, 'EN')


def T(p, key, *args):
    """界面文字（繁体 / 简体 / 日语 / 英语）。"""
    index = ('ZT', 'ZS', 'JP', 'EN').index(lang(p))
    text = TEXT[key][index]
    return text.format(*args) if args else text


def play_se(p, sound):
    try:
        p.call('_ZN7AppMain23Sound_RequestPlayMenuSEE7SoundID', p.app_instance(), sound)
    except Exception as error:
        p.log('LAB_SE_ERROR', sound, type(error).__name__, str(error))


def current_bgm(p):
    """当前播放的 BGM 编号：Sound_RequestPlayBGM（0x1c677c）写入请求 app+38656+208，
    Sound_PlayBGM（0x1c7364）开始播放时移到 app+38656+212 并清空请求。尚有未处理的请求时取请求值。"""
    app = p.app_instance()
    if not app:
        return 0
    return p.word(app + 38656 + 208) or p.word(app + 38656 + 212)


def play_bgm(p, sound):
    try:
        p.call('_ZN7AppMain23Sound_RequestPlayBGMEx2E7SoundIDi', p.app_instance(), sound, 0)
    except Exception as error:
        p.log('LAB_BGM_ERROR', sound, type(error).__name__, str(error))


def has_hangul(text):
    """含韩文字符（音节、字母、兼容字母）。游戏语言为韩语（app+0x3d64 = 2）时单位名称与区域名为韩文。"""
    return any('\uac00' <= ch <= '\ud7a3' or '\u1100' <= ch <= '\u11ff' or '\u3130' <= ch <= '\u318f'
               for ch in text)


def fonts():
    """font(字号, hangul=False)。界面主字体（微软正黑体等）不含韩文字形，含韩文的字符串改用 Malgun Gothic。"""
    from PIL import ImageFont
    folder = Path(os.environ['SystemRoot']) / 'Fonts'
    path = next((folder / n for n in ('msjhbd.ttc', 'msjh.ttc', 'msyhbd.ttc', 'msyh.ttc', 'msgothic.ttc')
                 if (folder / n).is_file()), None)
    korean = next((folder / n for n in ('malgunbd.ttf', 'malgun.ttf') if (folder / n).is_file()), None)
    cache = {}

    def font(size, hangul=False):
        # 按字号与字体缓存；字体文件只在首次使用时载入。
        key = (size, bool(hangul and korean))
        if key not in cache:
            cache[key] = ImageFont.truetype(str(korean if key[1] else path), size)
        return cache[key]
    return font


class Canvas:
    """一次绘制用的画布：文字自动缩小、按钮（含按下状态）与点击区域登记。"""

    def __init__(self, image, skin, font, pressed):
        from PIL import ImageDraw
        self.image, self.skin, self.font, self.pressed = image, skin, font, pressed
        self.draw = ImageDraw.Draw(image)
        self.hitboxes = []
        self.icons = {}                  # 命令 → (x, y, 图标)，供按下效果叠加

    def face(self, value):
        hangul = has_hangul(value)
        return lambda size: self.font(size, hangul)

    def fit_size(self, value, size, width, minimum=10):
        """超出宽度时先缩小字号（不低于 minimum），仍超出时以“…”截断。"""
        face = self.face(value)
        while size > minimum and face(size).getlength(value) > width:
            size -= 1
        return size

    def text(self, xy, value, size=16, fill=WHITE, anchor='la', stroke=2, width=None):
        face = self.face(value)
        if width is not None:
            size = self.fit_size(value, size, width)
            font = face(size)
            if font.getlength(value) > width:
                while value and font.getlength(value + '…') > width:
                    value = value[:-1]
                value += '…'
        self.draw.text(xy, value, font=face(size), fill=fill, anchor=anchor,
                       stroke_width=stroke, stroke_fill=(0, 0, 0, 255))

    def paste(self, part, xy):
        self.image.alpha_composite(part, (int(xy[0]), int(xy[1])))

    def is_pressed(self, command):
        return self.pressed is not None and self.pressed == command

    def button(self, rect, label, command, size=16, style='normal'):
        """原生 menuparts 按钮；按下时下移 2 像素并压暗，抬起时播放原生确定音（由调用方处理）。"""
        x, y, w, h = rect
        down = self.is_pressed(command)
        part = self.skin.nine(BUTTONS[style], w, h, 6)
        if down:
            part = self.skin.darken(part)
        oy = 2 if down else 0
        self.paste(part, (x, y + oy))
        light = style == 'light'
        self.text((x + w / 2, y + h / 2 + oy), label, size, DARK if light else WHITE, 'mm', 0 if light else 2, w - 8)
        self.hitboxes.append((rect, command))

    def icon_button(self, origin, part_name, command):
        """原生尺寸图标按钮（60×48 × 2.25）。按下效果由 icon_press_image 叠加（青色框与三灯，不压暗、不下移）。"""
        x, y = origin
        w, h = round(60 * ICON_SCALE), round(48 * ICON_SCALE)
        self.paste(self.skin.scaled(ICON_BUTTONS[part_name], w, h), (x, y))
        self.hitboxes.append(((x, y, w, h), command))
        self.icons[command] = (x, y, part_name)

    def panel(self, rect, title=None):
        x, y, w, h = rect
        self.paste(self.skin.nine(PANEL, w, h, 10), (x, y))
        if title:
            self.text((x + 14, y + 20), title, 18, GOLD, 'lm', 2, w - 28)

    def header(self, title):
        """原生顶栏等比放大（不拉伸、不九宫格），水平居中；标题写在“METAL SLUG DEFENSE”小字下方。"""
        w = round(HEADER[1][2] * HEADER_SCALE)
        self.paste(self.skin.scaled(HEADER, w, HEADER_H), ((W - w) // 2, 0))
        self.text((44, 60), title, 30, GOLD, 'lm', 3, 640)


def icon_press_image(skin, background, x, y, part_name):
    """按下状态的原生图标按钮：背景裁切 + 79 青色框 + 图标 + 37 三灯。返回 (图像, 左上角)。"""
    s = ICON_SCALE
    (frame, (fx, fy)), (lamps, (lx, ly)) = ICON_PRESS_FRAME, ICON_PRESS_LAMPS
    left, top = x - round(fx * s), y - round(fy * s)
    fw, fh = round(frame[1][2] * s), round(frame[1][3] * s)
    out = background.crop((left, top, left + fw, top + fh)).copy()
    out.alpha_composite(skin.scaled(frame, fw, fh), (0, 0))
    out.alpha_composite(skin.scaled(ICON_BUTTONS[part_name], round(60 * s), round(48 * s)), (x - left, y - top))
    out.alpha_composite(skin.scaled(lamps, round(lamps[1][2] * s), round(lamps[1][3] * s)),
                        (x - round(lx * s) - left, y - round(ly * s) - top))
    return out, (left, top)


def luminance(rgb):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def readable(color, plate, ratio=4.5):
    """在底板色上达到亮度对比 ratio 的文字色：不足时向白色混合（保持色相方向），返回 RGBA。"""
    base = luminance(plate)
    for step in range(0, 101):
        t = step / 100
        rgb = tuple(round(c + (255 - c) * t) for c in color[:3])
        if (luminance(rgb) + 0.05) / (base + 0.05) >= ratio:
            return rgb + (255,)
    return (255, 255, 255, 255)


class Skin:
    """原生素材（OI 01 20，32 位 RGBA）的加载、九宫格缩放与单位头像。"""

    def __init__(self, lab):
        self.lab = lab
        self.atlases, self.cache, self.icons = {}, {}, None

    def atlas(self, name):
        if name not in self.atlases:
            import struct
            import probe
            from PIL import Image
            loaded = getattr(getattr(self.lab.p, 'community', None), 'assets', {})
            if name in loaded:
                raw = loaded[name]          # 社区内容加载器已读入的图集（含图标页）
            else:
                community = Path(self.lab.root) / 'community_content' / name
                path = community if community.is_file() else Path(probe.RESOURCE_ROOT) / probe.PKG / name
                raw = path.read_bytes()
            w, h = struct.unpack_from('<HH', raw, 4)
            if raw[:4] == b'OI\x01\x20':
                self.atlases[name] = Image.frombytes('RGBA', (w, h), raw[8:8 + w * h * 4])
            elif raw[:3] == b'OI\x00' and raw[3] in (0x18, 0x20) and len(raw) == 8 + w * h * 3:
                # 关卡缩略图等无透明直接色图集（OI 种类 0）：每像素 3 字节 RGB。
                self.atlases[name] = Image.frombytes('RGB', (w, h), raw[8:8 + w * h * 3]).convert('RGBA')
            else:
                raise ValueError(f'{name}：不支持的图集格式 {raw[:4]!r}')
        return self.atlases[name]

    def crop(self, part):
        name, (x, y, w, h) = part
        return self.atlas(name).crop((x, y, x + w, y + h))

    def scaled(self, part, w, h):
        from PIL import Image
        key = ('scaled', part, int(w), int(h))
        if key not in self.cache:
            self.cache[key] = self.crop(part).resize((int(w), int(h)), Image.NEAREST)
        return self.cache[key]

    def darken(self, image, cache=True):
        """压暗（按下状态）。cache 只用于长期保存在 self.cache 中的素材图（以对象 id 为键）。"""
        key = ('dark', id(image))
        if cache and key in self.cache:
            return self.cache[key]
        from PIL import ImageEnhance
        rgb = ImageEnhance.Brightness(image).enhance(0.7)
        rgb.putalpha(image.split()[3])
        if cache:
            self.cache[key] = rgb
        return rgb

    def nine(self, part, w, h, corner):
        """九宫格缩放：四角保持原像素，边与中心以最近邻拉伸。"""
        from PIL import Image
        w, h = int(w), int(h)
        key = ('nine', part, w, h, corner)
        if key in self.cache:
            return self.cache[key]
        src = self.crop(part)
        sw, sh = src.size
        c = min(corner, sw // 2 - 1, sh // 2 - 1, w // 2, h // 2)
        out = Image.new('RGBA', (w, h))
        for sx0, sx1, dx0, dx1 in ((0, c, 0, c), (c, sw - c, c, w - c), (sw - c, sw, w - c, w)):
            for sy0, sy1, dy0, dy1 in ((0, c, 0, c), (c, sh - c, c, h - c), (sh - c, sh, h - c, h)):
                if dx1 > dx0 and dy1 > dy0:
                    out.alpha_composite(src.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.NEAREST),
                                        (dx0, dy0))
        self.cache[key] = out
        return out

    def tiled(self, part, w, h, scale=2, dim=0.55):
        """砖墙等背景按整数倍放大后平铺，并压暗。"""
        from PIL import Image, ImageEnhance
        key = ('tiled', part, w, h, scale, dim)
        if key not in self.cache:
            tile = self.crop(part)
            tile = tile.resize((tile.width * scale, tile.height * scale), Image.NEAREST)
            out = Image.new('RGBA', (w, h), (0, 0, 0, 255))
            for y in range(0, h, tile.height):
                for x in range(0, w, tile.width):
                    out.alpha_composite(tile, (x, y))
            out = ImageEnhance.Brightness(out).enhance(dim)
            self.cache[key] = out
        return self.cache[key]

    def icon_rects(self):
        """UnitID → (图集, 矩形)。原版：菜单表（320 行 × 20 字节，+10 头像序号）→ ConvUnitIcon（16 字节：
        x,y,w,h,锚点 x,y,0,页）；社区单位：注册表 icon.rect（页 1）。"""
        if self.icons is None:
            import struct
            p = self.lab.p
            menu = (p.word(0x101652d0) + 0x101652b4 + 0x818) & 0xffffffff
            conv = p.symbols['ConvUnitIcon']
            icons = {}
            for row in range(320):
                uid = p.word(menu + row * 20)
                index = struct.unpack('<h', p.read(menu + row * 20 + 10, 2))[0]
                if uid and 0 <= index < 340:
                    x, y, w, h, _, _, _, page = struct.unpack('<8h', p.read(conv + index * 16, 16))
                    if w > 0 and h > 0:
                        icons[uid] = (ICON_PAGES.get(page, ICON_PAGES[1]), (x, y, w, h))
            community = getattr(p, 'community', None)
            for unit in (community.units if community is not None else []):
                icon = unit.get('icon')
                if icon:
                    # 页 2 起为社区图标页图集（icon.atlas）。
                    icons[unit['id']] = (icon.get('atlas') or ICON_PAGES[icon.get('page', 1)], tuple(icon['rect']))
            self.icons = icons
        return self.icons

    def icon(self, uid, scale):
        """单位头像按与编组格相同的倍率最近邻缩放（原生头像按 50×50 格设计）。"""
        from PIL import Image
        entry = self.icon_rects().get(uid)
        if entry is None:
            return None
        key = ('icon', uid, round(scale, 3))
        if key not in self.cache:
            name, rect = entry
            src = self.atlas(name).crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
            if src.getbbox() is None:
                self.cache[key] = None
            else:
                self.cache[key] = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))),
                                             Image.NEAREST)
        return self.cache[key]


class Shutter:
    """原生闸门（与 AppMain::SetShutterClose / SetShutterOpen 相同的任务，0x2137b8 / 0x213804）：
    ShutterActionDataInit → CTaskSystem2D::AllDelete(app+0x3830, 5) → 清空 app+0x3820 的 4 个任务槽 →
    createMenuTask(app, app+0x3820, 动作表, 4)；不调用其末尾的 ChangeNT（17/18），场景状态保持不变。
    LAB 每帧调用 CTaskSystem2D::Caller(app+0x3830, 5) 推进任务（GT_Shutter 经 ActionSub2D 按动作表移动并播放
    原生闸门音效），随后 GraphicsOpt::drawStack(app+124) 立即提交，使闸门画在宿主界面之上。
    结束以 IsShutterActionEnd 判定；开闸结束后删除任务。"""

    def __init__(self, lab):
        self.lab = lab
        self.state = 'open'          # open / closing / closed / opening
        self.on_closed = None

    def tables(self):
        p = self.lab.p
        close = p.word((0x102137ea & ~3) + 24) + 0x102137f0          # SetShutterClose 的 pc 相对动作表
        opened = p.word((0x10213836 & ~3) + 28) + 0x1021383c + 224   # SetShutterOpen：同表 +224
        return close, opened

    def create(self, table):
        p = self.lab.p
        app = p.app_instance()
        p.write(app + 0xc200 + 28, bytes((0,)))
        p.call('_Z21ShutterActionDataInitv')
        p.call('_ZN13CTaskSystem2D9AllDeleteEi', app + 0x3830, 5)
        for i in range(4):
            p.put(app + 0x3820 + 4 * i, 0)
        p.call('_ZN7AppMain14createMenuTaskEPP17GENERAL_TASK_BASEPNS_10_MENU_TASKEi', app, app + 0x3820, table, 4)

    def delete(self):
        p = self.lab.p
        app = p.app_instance()
        p.call('_ZN13CTaskSystem2D9AllDeleteEi', app + 0x3830, 5)
        for i in range(4):
            p.put(app + 0x3820 + 4 * i, 0)
        p.write(app + 0xc200 + 28, bytes((1,)))
        # 与原生 SC_ShutterOpen 完成步骤一致：解除闭合标记，恢复普通界面的输入判定。
        p.write(app + 0xc200 + 29, bytes((0,)))

    def close(self, on_closed=None):
        self.create(self.tables()[0])
        self.state, self.on_closed = 'closing', on_closed

    def open(self):
        """从合拢状态开闸（原生战斗结束闸门合拢后，或宿主关闸后）。"""
        self.create(self.tables()[1])
        self.state = 'opening'

    def release(self):
        """原生场景（SC_BattleInit 的 SetShutterOpen）接管闸门：LAB 停止推进，任务交由原生处理。"""
        self.state, self.on_closed = 'open', None

    def set_closed(self):
        pass

    def update_and_draw(self, skin=None):
        if self.state == 'open':
            return
        p = self.lab.p
        app = p.app_instance()
        p.call('_ZN13CTaskSystem2D6CallerEi', app + 0x3830, 5)
        p.call('_ZN11GraphicsOpt9drawStackEv', p.word(app + 124))
        if self.state not in ('closing', 'opening'):
            return
        # 原生 SC_ShutterOpen 或后继场景初始化可先释放任务并清空四个槽。
        # IsShutterActionEnd 对空槽返回 0；已释放的任务需按完成处理，避免准备界面永久阻断返回输入。
        released = not any(p.word(app + 0x3820 + 4 * i) for i in range(4))
        ended = released or p.call('_ZN7AppMain18IsShutterActionEndEv', app)
        if ended:
            if released:
                self.lab.record('shutter_native_release', state=self.state)
            if self.state == 'closing':
                self.state = 'closed'
                callback, self.on_closed = self.on_closed, None
                if callback:
                    callback()
            else:
                self.delete()
                self.state = 'open'

    def close_resources(self):
        pass
