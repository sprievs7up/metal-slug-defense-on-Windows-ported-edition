"""局域网联机大厅、房间与常规联机对战流程（N6a，docs/netcode/N6A_REGULAR_NETPLAY_2026-10-10.md）。

入口：主菜单“對戰” → VERSUS 页“局域网”卡片。用户决定（Rollback 任务书第 7 节 R7、R8）：
- 大厅复用原版 Wi-Fi VERSUS 菜单（场景 66/67）：头像、留言与 DECK 保持原生；“朋友對戰 / 排名配對”改为“建立房間 / 加入房間”；
  Google Play 图标、VERSUS REQUEST、1 對 1 / 2 對 2 切换、RANKING（N6c 历史记录）与 ACHIEVEMENT 隐藏并停用（drawConv 替换表）。
- 玩家名称：原版取自 Google Play；本移植版由玩家输入，保存在当前存档目录（netplay_profile），写入原生 GameCenter 显示名称后由原生名牌显示。
- 名片战绩为本地联机战绩（netplay_profile），分數 / 排名显示为 “-”（不计 RP）。
- 房间：房主在局域网应答发现并显示本机地址与房间码（N6b 观战使用）；加入方列出局域网房间，也可按 IP 直连。
  连接后比较内容清单（不同即拒绝并列出差异），双方确认“準備”后以编队承诺—揭示交换存档的当前编队与发展进度。
- 开战：先显示原生对手画面（WiFiDeck 场景 73：对手名片与编队，开战前一刻公开），原生转入 SC_BattleStart（105）时改由
  LAB 联机流程开战（netplay_regular.RegularBattle）。战斗在游戏窗口中经会话驱动接口运行；Esc 打开不暂停的菜单（音乐、音效、投降）。
- 结束（含断线、分歧、投降、对方离开）后回到大厅的房间；再战需双方再次确认。回放自动保存（N5.5）；分歧报告保存在用户目录。
- 远程（N6b，docs/netcode/N6B_REMOTE_DIRECT_2026-10-10.md；R9）：VERSUS 页“远程”卡片进入同一大厅。不经任何服务器，
  房主建房后显示房间码与对手可填写的地址（路由器 UPnP 取得的公网 IPv4、本机 IPv6、局域网地址），对手输入“地址 + 房间码”直连；
  房主核对房间码。IPv4 与 IPv6 双栈；房主端口可更改（保存在存档目录的 netplay_profile.json）；远程默认自动输入延迟。
"""
import json
import os
import random
import re
import struct
import time
from collections import deque
from pathlib import Path

from lab_ui import (W, H, WHITE, GOLD, GRAY, BLUE, RED, DARK, PANEL, SE_DECIDE, SE_CLOSE, Canvas, Skin, fonts, lang, play_se)

WIFI_INIT, WIFI_LOOP, WIFI_DECK_INIT, WIFI_DECK_LOOP, BATTLE_START = 66, 67, 73, 74, 105
MENU_SCENES = (66, 67, 68)                       # 68 SC_WiFiMenuEnd：点 DECK 进入编队页、按 BACK 离开大厅时各经过一帧
DECK_SCENES = (54, 55, 56, 57)                   # Wi-Fi 菜单 DECK 按钮进入的原生编队页（返回经 56 → 66）
POPUP_SCENES = (119, 120, 121, 122)              # 原生弹窗（头像、留言选择，首次进入的说明等）
SCALE, MARGIN = 1.125, 88.9                      # 原生参考坐标 → 1280×720 逻辑坐标


def native_rect(x, y, w, h, ax=0, ay=0, scale=2):
    """原生 2 倍绘制的图块（参考坐标、像素尺寸、锚点）在逻辑画布上的矩形。"""
    return ((x - ax + MARGIN) * SCALE, (y - ay) * SCALE, w * scale * SCALE, h * scale * SCALE)


FRIEND_RECT = native_rect(194, 322, 120, 23)
RANKED_RECT = native_rect(524, 322, 120, 23)
NAME_RECT = native_rect(410, 122, 147, 19)
BLOCKED_RECTS = (native_rect(706, 184, 21, 19, 10, 9),       # 1 對 1 / 2 對 2 切换
                 native_rect(-48, 122, 30, 20),              # Google Play
                 native_rect(92, 226, 64, 69, 34, 54),       # VERSUS REQUEST
                 native_rect(264, 532, 60, 48),              # RANKING（N6c 历史记录）
                 native_rect(576, 532, 60, 48))              # ACHIEVEMENT
VS_TABLE, VS_MAGIC = 0x1ffeb000 + 0xb40, 0x47505356          # drawConv 替换表（lab_hooks.cpp 第 22 版：16 项、转换项通配）
HIDDEN = ((0x1031d010, 0), (0x10307202, 0), (0x10307212, 0), (0x1031d040, 0), (0x1031d030, 0), (0, 226.0))
GAMECENTER_NAME = 0x380c                          # CGameCenter 显示名称（64 字节，getUserDisplayName）
OPPONENT = 0xc081                                 # app 偏移：对手数据（_SEND_MESSAGE +1 起，GetPlayerInfo 复制；WiFiDeck 场景读取）
POOL_FILE = 'netplay_pool.json'
ADDRESS_CHARS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.:[]-'   # IPv4、IPv6、域名
CODE_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
CGNAT = ('100.64.0.0/10',)
PRIVATE4 = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16', '127.0.0.0/8')

TEXT = {
    'host': ('建立房間', '建立房间', '部屋を作る', 'CREATE ROOM'),
    'join': ('加入房間', '加入房间', '部屋に入る', 'JOIN ROOM'),
    'name_title': ('玩家名稱', '玩家名称', 'プレイヤー名', 'PLAYER NAME'),
    'name_hint': ('對戰時顯示給對手的名稱（最多 16 個字，保存在目前的存檔）。', '对战时显示给对手的名称（最多 16 个字，保存在当前存档）。',
                  '対戦相手に表示される名前（16 文字まで・現在のセーブに保存）。', 'Shown to your opponent (up to 16 characters, saved in this save).'),
    'name_first': ('開始聯機前請先設定玩家名稱。', '开始联机前请先设定玩家名称。', 'オンライン対戦の前に名前を設定してください。',
                   'Set your player name before playing online.'),
    'ok': ('確定', '确定', 'OK', 'OK'), 'cancel': ('取消', '取消', 'キャンセル', 'CANCEL'),
    'host_wait': ('等待對手加入…', '等待对手加入…', '対戦相手を待っています…', 'Waiting for an opponent…'),
    'room_code': ('房間碼 {}', '房间码 {}', '部屋コード {}', 'Room code {}'),
    'address': ('本機位址（對手可按 IP 連接）：', '本机地址（对手可按 IP 连接）：', 'このPCのアドレス（IP 接続用）：',
                'This PC (for connecting by IP):'),
    'firewall': ('首次建立房間時 Windows 防火牆可能詢問是否允許網路存取，請同時勾選「私人網路」與「公用網路」。',
                 '首次建立房间时 Windows 防火墙可能询问是否允许网络访问，请同时勾选“专用网络”和“公用网络”。',
                 '初回は Windows ファイアウォールの確認が出ます。「プライベート」と「パブリック」の両方を許可してください。',
                 'Windows Firewall may ask for network access the first time: allow both Private and Public networks.'),
    'port_busy': ('連接埠 {} 已被占用，改用 {}。', '端口 {} 已被占用，改用 {}。', 'ポート {} は使用中のため {} を使います。',
                  'Port {} is in use; using {}.'),
    'searching': ('正在搜尋區域網路中的房間…', '正在搜索局域网中的房间…', 'LAN の部屋を探しています…', 'Searching the LAN for rooms…'),
    'no_rooms': ('找不到房間。也可以輸入對方的 IP 位址直接連接。', '找不到房间。也可以输入对方的 IP 地址直接连接。',
                 '部屋が見つかりません。相手の IP アドレスで直接接続することもできます。', 'No rooms found. You can also connect by IP address.'),
    'by_ip': ('輸入位址', '输入地址', 'アドレス入力', 'ENTER ADDRESS'),
    'ip_title': ('輸入位址與房間碼', '输入地址与房间码', 'アドレスと部屋コードを入力', 'ENTER ADDRESS AND ROOM CODE'),
    'ip_hint': ('例：203.0.113.5:47631、[2001:db8::5]:47631（未寫連接埠時為 47631）。Tab 切換欄位。',
                '例：203.0.113.5:47631、[2001:db8::5]:47631（未写端口时为 47631）。Tab 切换栏位。',
                '例：203.0.113.5:47631、[2001:db8::5]:47631（ポート省略時 47631）。Tab で欄を切り替え。',
                'e.g. 203.0.113.5:47631 or [2001:db8::5]:47631 (port 47631 if omitted). Tab switches fields.'),
    'ip_bad': ('位址格式不正確。', '地址格式不正确。', 'アドレスの形式が正しくありません。', 'Invalid address.'),
    'field_address': ('房主位址', '房主地址', 'ホストのアドレス', 'Host address'),
    'field_code': ('房間碼', '房间码', '部屋コード', 'Room code'),
    'code_bad': ('房間碼為 6 個字元。', '房间码为 6 个字符。', '部屋コードは 6 文字です。', 'The room code has 6 characters.'),
    'host_tell': ('把下面其中一個位址與房間碼告訴對手：', '把下面其中一个地址与房间码告诉对手：',
                  '下のアドレスのどれかと部屋コードを相手に伝えてください：', 'Give your opponent one of these addresses and the room code:'),
    'addr_public': ('公網 IPv4（路由器已開放連接埠）', '公网 IPv4（路由器已开放端口）', 'グローバル IPv4（ルーターでポート開放済み）',
                    'Public IPv4 (port opened on the router)'),
    'addr_ipv6': ('IPv6', 'IPv6', 'IPv6', 'IPv6'),
    'addr_lan': ('區域網路 / 虛擬區域網路', '局域网 / 虚拟局域网', 'LAN / 仮想 LAN', 'LAN / virtual LAN'),
    'upnp_trying': ('正在請求路由器開放連接埠（UPnP）…', '正在请求路由器开放端口（UPnP）…', 'ルーターにポート開放を要求しています（UPnP）…',
                    'Asking the router to open the port (UPnP)…'),
    'upnp_failed': ('路由器沒有自動開放連接埠（UPnP 不可用）。對手在其他網路時：請在路由器上把 UDP {} 轉發到本機，並把路由器狀態頁顯示的 WAN（外網）IP 告訴對手；'
                    '或使用 IPv6、虛擬區域網路，或改由對手建立房間。',
                    '路由器没有自动开放端口（UPnP 不可用）。对手在其他网络时：请在路由器上把 UDP {} 转发到本机，并把路由器状态页显示的 WAN（外网）IP 告诉对手；'
                    '或使用 IPv6、虚拟局域网，或改由对手建立房间。',
                    'ルーターがポートを開放しませんでした（UPnP 不可）。別ネットワークの相手とは：ルーターで UDP {} をこの PC に転送し、'
                    '状態ページの WAN IP を伝えてください。IPv6、仮想 LAN、相手が部屋を作る方法もあります。',
                    'The router did not open the port (UPnP unavailable). For players on other networks: forward UDP {} to this PC on your '
                    'router and give the opponent the WAN IP shown on the router\'s status page; or use IPv6, a virtual LAN, or let the opponent create the room.'),
    'upnp_cgnat': ('路由器的外網位址 {} 屬於電信業者的內部網路（CGNAT），其他網路的玩家無法直接連接本機。請使用 IPv6、虛擬區域網路，或改由對手建立房間。',
                   '路由器的外网地址 {} 属于运营商的内部网络（CGNAT），其他网络的玩家无法直接连接本机。请使用 IPv6、虚拟局域网，或改由对手建立房间。',
                   'ルーターの外側アドレス {} は通信事業者の内部ネットワーク（CGNAT）のため、他のネットワークから直接接続できません。'
                   'IPv6、仮想 LAN、または相手が部屋を作る方法を使ってください。',
                   'The router\'s outside address {} is inside your provider\'s network (CGNAT), so players on other networks cannot reach '
                   'this PC directly. Use IPv6, a virtual LAN, or let the opponent create the room.'),
    'upnp_private': ('路由器的外網位址 {} 是內部位址（前面還有一台路由器）。請在上一層路由器把 UDP {} 轉發到本機的路由器。',
                     '路由器的外网地址 {} 是内部地址（前面还有一台路由器）。请在上一层路由器把 UDP {} 转发到本机的路由器。',
                     'ルーターの外側アドレス {} は内部アドレスです（さらに上位のルーターがあります）。上位ルーターで UDP {} を転送してください。',
                     'The router\'s outside address {} is a private address (there is another router in front). Forward UDP {} on that router.'),
    'no_ipv6': ('本機沒有可用的 IPv6 位址。', '本机没有可用的 IPv6 地址。', 'この PC には使える IPv6 アドレスがありません。',
                'This PC has no usable IPv6 address.'),
    'port_label': ('連接埠 {}', '端口 {}', 'ポート {}', 'Port {}'),
    'change_port': ('更改連接埠', '更改端口', 'ポート変更', 'CHANGE PORT'),
    'port_title': ('房主連接埠', '房主端口', 'ホストのポート', 'HOST PORT'),
    'port_hint': ('1024–65535。在路由器上手動轉發連接埠時，請填寫相同的連接埠。', '1024–65535。在路由器上手动转发端口时，请填写相同的端口。',
                  '1024–65535。ルーターで手動転送する場合は同じポートにしてください。',
                  '1024–65535. If you forward a port on your router, use the same port here.'),
    'port_bad': ('連接埠須為 1024–65535。', '端口须为 1024–65535。', 'ポートは 1024–65535 です。', 'The port must be 1024–65535.'),
    'resolving': ('正在解析位址…', '正在解析地址…', 'アドレスを解決しています…', 'Resolving the address…'),
    'fail_timeout': ('對方沒有回應。請確認位址、連接埠與房間碼；房主須能被其他網路連接（路由器開放連接埠、IPv6 或虛擬區域網路），雙方都須允許本遊戲通過 Windows 防火牆。',
                     '对方没有回应。请确认地址、端口与房间码；房主须能被其他网络连接（路由器开放端口、IPv6 或虚拟局域网），双方都须允许本游戏通过 Windows 防火墙。',
                     '応答がありません。アドレス・ポート・部屋コードを確認してください。ホストは他のネットワークから接続できる必要があります'
                     '（ポート開放、IPv6、仮想 LAN）。双方で Windows ファイアウォールを許可してください。',
                     'No answer. Check the address, port and room code. The host must be reachable from other networks (open port, IPv6 or a '
                     'virtual LAN), and both players must allow the game through Windows Firewall.'),
    'connect_failed': ('無法連接', '无法连接', '接続できません', 'Could not connect'),
    'fail_wrong_code': ('房間碼不正確。', '房间码不正确。', '部屋コードが正しくありません。', 'Wrong room code.'),
    'fail_resolve': ('無法解析這個位址。', '无法解析这个地址。', 'このアドレスを解決できません。', 'The address could not be resolved.'),
    'delay_frames': ('{} 幀', '{} 帧', '{} フレーム', '{} frames'),
    'delay_auto': ('自動（依網路延遲 2–6 幀）', '自动（按网络延迟 2–6 帧）', '自動（通信遅延に応じ 2–6 フレーム）', 'auto (2–6 frames by latency)'),
    'connecting': ('連接中…', '连接中…', '接続中…', 'Connecting…'),
    'checking': ('比較雙方的遊戲內容…', '比较双方的游戏内容…', 'ゲーム内容を確認しています…', 'Comparing game content…'),
    'busy': ('對戰中', '对战中', '対戦中', 'IN MATCH'), 'open': ('可加入', '可加入', '参加可', 'OPEN'),
    'content_diff': ('內容不同', '内容不同', '内容が異なる', 'DIFFERENT CONTENT'),
    'version_diff': ('版本不同', '版本不同', 'バージョン違い', 'DIFFERENT VERSION'),
    'room_title': ('房間 {}', '房间 {}', '部屋 {}', 'ROOM {}'),
    'ready': ('準備', '准备', '準備OK', 'READY'), 'rematch': ('再戰', '再战', '再戦', 'REMATCH'),
    'leave': ('離開房間', '离开房间', '部屋を出る', 'LEAVE ROOM'),
    'state_ready': ('已準備', '已准备', '準備OK', 'READY'), 'state_wait': ('準備中', '准备中', '準備中', 'NOT READY'),
    'state_empty': ('等待加入', '等待加入', '参加待ち', 'WAITING'),
    'deck_hidden': ('編隊在開戰前一刻公開', '编队在开战前一刻公开', '編成は対戦直前に公開', 'Deck revealed at battle start'),
    'your_deck': ('使用目前的編隊與發展進度', '使用当前的编队与发展进度', '現在の編成と育成状況で対戦', 'Uses your current deck and upgrades'),
    'room_info': ('地圖：從官方 Wi-Fi 對戰地圖池（{} 張）隨機・輸入延遲 {}', '地图：从官方 Wi-Fi 对战地图池（{} 张）随机·输入延迟 {}',
                  'マップ：公式 Wi-Fi 対戦マップ（{} 種）からランダム・入力遅延 {}',
                  'Map: random from the official Wi-Fi pool ({}) · input delay {}'),
    'win': ('勝利', '胜利', '勝利', 'WIN'), 'lose': ('敗北', '败北', '敗北', 'LOSE'), 'draw': ('平手', '平局', '引き分け', 'DRAW'),
    'last_result': ('上一局：{}', '上一局：{}', '前回：{}', 'Last round: {}'),
    'peer_left': ('對手已離開房間。', '对手已离开房间。', '相手が部屋を出ました。', 'The opponent left the room.'),
    'disconnected': ('與對手的連線中斷。', '与对手的连接中断。', '相手との接続が切れました。', 'Connection to the opponent was lost.'),
    'desync': ('雙方的對戰狀態不一致，本局結束。已保存分歧報告。', '双方的对战状态不一致，本局结束。已保存分歧报告。',
               '対戦状態が一致しなくなったため終了しました。報告を保存しました。', 'The match went out of sync and ended. A report was saved.'),
    'rejected': ('無法與對手對戰：', '无法与对手对战：', '対戦できません：', 'Cannot play this opponent:'),
    'menu_title': ('對戰選單', '对战菜单', '対戦メニュー', 'VERSUS MENU'),          # 与本地双人对战菜单相同
    'menu_music': ('音樂', '音乐', 'BGM', 'MUSIC'), 'menu_effects': ('音效', '音效', '効果音', 'SOUND'),
    'surrender': ('投降', '投降', '降参', 'SURRENDER'), 'resume': ('返回對戰', '返回对战', '戻る', 'RESUME'),
    'on': ('開', '开', 'ON', 'ON'), 'off': ('關', '关', 'OFF', 'OFF'),
    'peer_surrender': ('對手投降。', '对手投降。', '相手が降参しました。', 'The opponent surrendered.'),
    'you_surrender': ('你已投降。', '你已投降。', '降参しました。', 'You surrendered.'),
    'wait_peer': ('等待對手…', '等待对手…', '相手を待っています…', 'Waiting for the opponent…'),
    'interrupted': ('連線不穩定…', '连接不稳定…', '接続が不安定です…', 'Connection unstable…'),
    'close': ('關閉', '关闭', '閉じる', 'CLOSE'),
    'intro': ('建立房間或加入房間即可與其他玩家對戰。\n\n同一網路中的房間會自動列出；\n遠程對戰時輸入房主的位址與房間碼直接連接。\n使用目前的編隊與發展進度，不計排名分數。',
              '建立房间或加入房间即可与其他玩家对战。\n\n同一网络中的房间会自动列出；\n远程对战时输入房主的地址与房间码直接连接。\n使用当前的编队与发展进度，不计排名分数。',
              '部屋を作るか部屋に入って対戦します。\n\n同じネットワークの部屋は自動で表示されます。\nリモート対戦ではホストのアドレスと部屋コードで直接接続します。\n現在の編成と育成状況で対戦し、ランクポイントは計算しません。',
              'Create a room or join one to play.\n\nRooms on your network are listed automatically;\nfor remote play, enter the host address and room code.\nYour current deck and upgrades are used; no rank points.'),
}


def upnp_state(mapping):
    """路由器端口映射结果的分类：ok（外网地址为公网 IPv4）、cgnat（运营商级 NAT 的 100.64.0.0/10）、private（外网地址为内部地址：
    前面还有一台路由器）、failed（UPnP 不可用或失败）。"""
    import ipaddress
    if not mapping.get('ok'):
        return 'failed'
    try:
        address = ipaddress.IPv4Address(str(mapping.get('external_ip') or ''))
    except ValueError:
        return 'failed'
    if address in ipaddress.ip_network('0.0.0.0/8'):              # 路由器尚未取得外网地址
        return 'failed'
    if any(address in ipaddress.ip_network(n) for n in CGNAT):
        return 'cgnat'
    if any(address in ipaddress.ip_network(n) for n in PRIVATE4):
        return 'private'
    return 'ok'


def wrap(text, width):
    """按字符数折行（中日文约 46 字、英文约 80 字一行）；英文在空格处折行。"""
    lines = []
    for paragraph in str(text).split('\n'):
        while len(paragraph) > width:
            cut = paragraph.rfind(' ', 0, width + 1) if ' ' in paragraph[:width + 1] and paragraph.isascii() else -1
            cut = cut if cut > width // 2 else width
            lines.append(paragraph[:cut].rstrip())
            paragraph = paragraph[cut:].lstrip()
        lines.append(paragraph)
    return lines


def tr(p, key, *args):
    index = ('ZT', 'ZS', 'JP', 'EN').index(lang(p))
    text = TEXT[key][index]
    return text.format(*args) if args else text


def replace_last_numbers(text, values):
    """把字符串中最后 len(values) 个整数依次换为 values（原生“戰績（1對1）：%d勝%d敗”的胜负数，各语言格式相同的位置）。"""
    spans = [m.span() for m in re.finditer(r'\d+', text)][-len(values):]
    if len(spans) < len(values):
        return text
    for (start, end), value in sorted(zip(spans, values), reverse=True):
        text = text[:start] + str(value) + text[end:]
    return text


def inside(rect, x, y):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


def load_pool(root):
    data = json.loads((Path(root) / POOL_FILE).read_text(encoding='utf-8'))
    return [int(s) for s in data['stages']]


def desync_dir():
    configured = os.environ.get('MSD_DESYNC_DIR')
    if configured:
        return Path(configured)
    local = os.environ.get('LOCALAPPDATA')
    return Path(local) / 'MSD_WINDOWS_S1XLV' / 'netplay' / 'desync' if local else Path(__file__).resolve().parent / 'desync'


class TextField:
    def __init__(self, value='', limit=16, allowed=None, upper=False):
        self.value, self.limit, self.allowed, self.upper = value, limit, allowed, upper

    def type(self, text):
        for ch in text:
            if self.upper:
                ch = ch.upper()
            if len(self.value) >= self.limit:
                break
            if ch.isprintable() and (self.allowed is None or ch in self.allowed):
                self.value += ch

    def backspace(self):
        self.value = self.value[:-1]


# ---------- 房间（网络与对局协议） ----------
class Room:
    """一名对手的房间：房主（Listener + 局域网应答）或加入方（Connector）；连接后由 netplay_match.Match 处理握手、编队与再战。"""

    def __init__(self, lobby, role):
        import netplay_net as nn
        self.lobby, self.p, self.role = lobby, lobby.p, role
        self.nn = nn
        self.code = ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
        self.endpoint = self.listener = self.connector = self.responder = self.link = self.match = None
        self.port_note = None
        self.state = 'idle'               # waiting、connecting、checking、room、locked、vs、battle、closed
        self.reason = None
        self.differences = None
        self.result = None                # 上一局结果（本方视角）
        self.local_ready = False
        self.history = []
        self.peer_delta = {}              # 连接后各轮对方战绩的变化（双方按同一结果判定，对方结果为本方的相反）
        self.upnp = None                  # 远程房主：路由器端口映射（后台线程）的结果，state 为 trying / ok / failed / cgnat / private
        self.upnp_closed = False
        self.join_code = None
        self.pending = None               # 加入方：后台解析地址的结果

    # 房主
    def open_host(self, port=None):
        nn = self.nn
        bind = os.environ.get('MSD_NETPLAY_BIND', '0.0.0.0')
        ipv6 = os.environ.get('MSD_NETPLAY_BIND6') or None
        port = int(os.environ.get('MSD_NETPLAY_PORT') or port or nn.GAME_PORT)
        try:
            self.endpoint = nn.Endpoint((bind, port), ipv6=ipv6)
        except OSError:
            self.endpoint = nn.Endpoint((bind, 0), ipv6=ipv6)
            self.port_note = (port, self.endpoint.address[1])
        self.listener = nn.Listener(self.endpoint, self.lobby.link_info(), code=self.code)
        if self.lobby.kind == 'remote' and os.environ.get('MSD_NETPLAY_NO_UPNP') != '1':
            self.start_upnp()
        discovery = int(os.environ.get('MSD_NETPLAY_DISCOVERY_PORT', nn.DISCOVERY_PORT))
        if os.environ.get('MSD_NETPLAY_NO_LAN') != '1':
            try:
                self.responder = nn.LanResponder(self.room_info, bind=(bind, discovery))
            except OSError as error:
                self.p.log('NETPLAY_LAN_RESPONDER_ERROR', str(error))
        self.state = 'waiting'

    def start_upnp(self):
        """后台线程请求路由器把对战端口转发到本机（UPnP），取得路由器的外网地址；不阻塞游戏线程。房间先关闭时随即删除映射。"""
        import threading
        port = self.endpoint.address[1]
        self.upnp = {'state': 'trying'}

        def work():
            import upnp_igd
            kwargs = {}
            target = os.environ.get('MSD_UPNP_TARGET')       # 测试：模拟路由器的 SSDP 地址
            if target:
                host, _, tport = target.rpartition(':')
                kwargs.update(target=(host, int(tport)), bind=(os.environ.get('MSD_UPNP_BIND', '127.0.0.1'), 0), timeout=1.5)
            try:
                mapping = upnp_igd.open_port(port, 'MSD WINDOWS S1XLV', **kwargs)
            except Exception as error:
                mapping = {'ok': False, 'error': f'{type(error).__name__}: {error}'}
            result = dict(mapping, state=upnp_state(mapping))
            if self.upnp_closed and mapping.get('ok'):
                upnp_igd.close_port(mapping)
            self.upnp = result
        threading.Thread(target=work, name='MSD UPnP', daemon=True).start()

    def close_upnp(self):
        self.upnp_closed = True
        mapping = self.upnp or {}
        if mapping.get('ok'):
            import threading
            import upnp_igd
            threading.Thread(target=upnp_igd.close_port, args=(dict(mapping),), name='MSD UPnP close', daemon=True).start()

    def address_rows(self):
        """房主窗口列出的地址：(种类, 文字)。种类 public（UPnP 取得的公网 IPv4）、ipv6（全局 IPv6）、lan（局域网 IPv4 与 ULA）。"""
        nn = self.nn
        rows = []
        upnp = self.upnp or {}
        if self.endpoint is None:
            return rows
        if upnp.get('state') == 'ok':
            rows.append(('public', nn.format_address((upnp['external_ip'], int(upnp.get('external_port') or self.endpoint.address[1])))))
        for ip, port in self.endpoint.candidates():
            kind = ('ipv6' if nn.ipv6_kind(ip) == 'global' else 'lan') if ':' in ip else 'lan'
            rows.append((kind, nn.format_address((ip, port))))
        order = {'public': 0, 'ipv6': 1, 'lan': 2}
        return sorted(rows, key=lambda row: order[row[0]])

    def room_info(self):
        info = dict(self.lobby.link_info(), port=self.endpoint.address[1], code=self.code,
                    state='open' if self.link is None else 'busy')
        return info

    # 加入方
    def open_join(self, candidates, code=None):
        nn = self.nn
        bind = os.environ.get('MSD_NETPLAY_BIND', '0.0.0.0')
        self.endpoint = nn.Endpoint((bind, 0), ipv6=os.environ.get('MSD_NETPLAY_BIND6') or None)
        self.connector = nn.Connector(self.endpoint, candidates, dict(self.lobby.link_info(), code=code), timeout=12.0)
        self.state = 'connecting'

    def resolve(self, text, code):
        """加入方按地址文字连接：IP 字面量立即连接；域名在后台线程解析（不阻塞游戏线程），由 service() 接着连接。"""
        import threading
        self.join_code = code
        self.state = 'resolving'

        def work():
            try:
                found = self.nn.resolve_addresses(text, self.nn.GAME_PORT)
            except (ValueError, OSError):
                found = []
            self.pending = found
        threading.Thread(target=work, name='MSD resolve', daemon=True).start()

    def addresses(self):
        return [text for _, text in self.address_rows()]

    def service(self):
        """每帧（大厅与开战前）：网络收发与状态推进。对战中由会话驱动直接处理。"""
        if self.responder is not None:
            self.responder.service()
        if self.state == 'resolving' and self.pending is not None:
            found, self.pending = self.pending, None
            if found:
                self.open_join(found, self.join_code)
            else:
                self.state, self.reason = 'closed', 'resolve'
        elif self.state == 'waiting':
            self.listener.service()
            if self.listener.link is not None:
                self.attach(self.listener.link)
        elif self.state == 'connecting':
            self.connector.service()
            if self.connector.state == 'connected':
                self.attach(self.connector.link)
            elif self.connector.state in ('failed', 'rejected'):
                self.state, self.reason = 'closed', self.connector.reason or self.connector.state
        elif self.match is not None and self.state not in ('closed', 'battle'):
            self.match.poll()
            self.follow_match()

    def attach(self, link):
        import netplay_match as nm
        lobby = self.lobby
        self.link = link
        manifest = lobby.manifest()
        community = getattr(self.p, 'community', None)
        known = {u['key'] for u in community.units if not u.get('internal_only')} if community is not None else None
        self.match = nm.Match(link, 'host' if self.role == 'host' else 'client', manifest, name=lobby.profile['name'],
                              delay=lobby.delay, pool=lobby.pool, version=lobby.version, known_keys=known,
                              profile=lobby.card(), mode='regular')
        self.match.start()
        self.peer_delta = {}
        self.state = 'checking'
        self.p.log('NETPLAY_CONNECTED', self.role, link.remote)

    def follow_match(self):
        m = self.match
        if m.state in ('rejected',):
            self.state, self.reason, self.differences = 'closed', m.reason, m.differences
        elif m.state in ('left', 'disconnected'):
            self.peer_gone(m.state)
        elif m.state == 'decks' and self.state in ('checking', 'room'):
            self.state = 'room'
        elif m.state == 'locked' and self.state == 'room':
            self.state = 'locked'

    def peer_gone(self, how):
        """对手离开或断线：房主重新开放房间（同一房间码），加入方回到大厅。"""
        self.reason = 'peer_left' if how == 'left' else 'disconnected'
        self.close_link()
        self.local_ready = False
        if self.role == 'host':
            self.listener = self.nn.Listener(self.endpoint, self.lobby.link_info(), code=self.code)
            self.state = 'waiting'
        else:
            self.state = 'closed'

    def ready(self):
        """本方确认：结果后先请求再战（进入下一轮），编队状态下锁定本方编队与发展进度（承诺）。"""
        import netplay_profile
        m = self.match
        if m is None or self.local_ready:
            return
        if m.state == 'result':
            m.request_rematch()
            self.local_ready = True
            return
        if m.state == 'decks':
            development = netplay_profile.development(self.p)
            m.lock_deck(development['deck'], development['status'])
            self.local_ready = True

    def maybe_lock_after_rematch(self):
        """再战已被双方接受（进入下一轮的编队状态）而本方已按过再战：锁定编队。"""
        import netplay_profile
        m = self.match
        if m is not None and m.state == 'decks' and self.local_ready and m.commit is None:
            development = netplay_profile.development(self.p)
            m.lock_deck(development['deck'], development['status'])

    def peer_profile(self):
        return ((self.match.peer or {}).get('profile') if self.match else None) or {}

    def peer_card(self):
        """房间窗口显示的对方名片：连接时的名片加上此后各轮的结果。"""
        card = dict(self.peer_profile())
        record = dict(card.get('record') or {})
        for key, value in self.peer_delta.items():
            record[key] = record.get(key, 0) + value
        card['record'] = record
        return card

    def count_round(self, outcome):
        key = {'win': 'losses', 'loss': 'wins', 'draw': 'draws'}.get(outcome)
        if key:
            self.peer_delta[key] = self.peer_delta.get(key, 0) + 1

    def peer_ready(self):
        m = self.match
        if m is None:
            return False
        return m.peer_commit is not None or (m.state == 'result' and m.peer_rematch is not None)

    def close_link(self):
        if self.link is not None:
            try:
                if self.match is not None and self.match.state not in ('left', 'disconnected', 'leaving'):
                    self.match.leave('leave', wait=0.5)
                self.link.leave('leave')
            except Exception:
                pass
        self.link = self.match = None

    def close(self):
        self.close_link()
        self.close_upnp()
        for item in (self.responder, self.endpoint):
            if item is not None:
                try:
                    item.close()
                except Exception:
                    pass
        self.responder = self.endpoint = None
        self.state = 'closed'


# ---------- 对战（会话驱动） ----------
class RegularDriver:
    """常规联机一轮对战的会话驱动（lab_runtime 的 session_driver）。开战前（原生对手画面、战斗初始化）每显示帧推进一帧；
    第 0 帧与对方同步后由 RegularBattle 逐帧推进；结束后保存回放、交换结果并经 LAB 闸门回到大厅。"""

    def __init__(self, lobby, room, m):
        import netplay_regular
        self.lobby, self.room, self.p, self.lab = lobby, room, lobby.p, lobby.lab
        self.m = dict(m)
        self.session = netplay_regular.RegularBattle(self.p, m['side'], m['seed'], delay=m['delay'])
        self.session.on_present = self.present
        self.phase = 'waiting_scene'          # waiting_scene → starting → sync → battle → closing
        self.finished = False
        self.end = None
        self.notice = None
        self.wait_since = None
        self.menu = NetMenu(self)
        self.desync_report = None
        self.replay = None
        self.surrender_queued = False

    # 原生 SC_BattleStart（105）之前由大厅调用：以本场设定开战
    def start_battle(self):
        session, lab = self.session, self.lab
        m = self.m
        config = session.match_config(m['stage'], m['p1_deck'], m['p2_deck'], m.get('p1_status'), m.get('p2_status'))
        lab.netplay_mode = 'regular'
        session.config = dict(config)
        lab.config_override = dict(config)
        session.saved_lab_config = dict(lab.config)
        lab.config.update(config)
        session.saved_support = (lab.player_support, lab.enemy_support)
        lab.player_support = lab.enemy_support = 0
        # LAB 的开关（完全控制、双方 AI 与自动绝招）属于本机设定，联机期间一律关闭（双方模拟相同），结束后还原。
        import lab as labmod
        self.saved_switches = {name: getattr(lab, name) for name in labmod.SWITCHES}
        for name in labmod.SWITCHES:
            setattr(lab, name, 0 if name.endswith('_support') else False)
        session.mode.enter(reseed=False)
        lab.start_hook = session.mode.reseed
        lab.versus = False
        lab.return_scene = WIFI_INIT
        lab.start()
        self.phase = 'starting'

    def drive(self):
        p, lab, session = self.p, self.lab, self.session
        try:
            if self.phase in ('waiting_scene', 'starting'):
                if self.phase == 'starting' and lab.active and session.ready():
                    self.begin()
                    return False
                if self.phase == 'starting' and not lab.active and p.frame - getattr(self, 'start_frame', p.frame) > 600:
                    return self.abort('not_started')
                self.start_frame = getattr(self, 'start_frame', p.frame)
                p.step_frame()
                return True
            if self.phase == 'sync':
                return self.sync()
            if self.phase == 'battle':
                return self.battle()
            if self.phase == 'closing':
                return self.closing()
            p.step_frame()
            return True
        except Exception as error:
            import traceback
            from probe import ProbeCancelled
            if isinstance(error, ProbeCancelled):
                raise
            p.log('NETPLAY_DRIVER_ERROR', traceback.format_exc())
            self.notice = f'{type(error).__name__}: {error}'
            return self.abort('error')

    def begin(self):
        session, match = self.session, self.room.match
        checksum0 = session.begin()
        match.send_ready(checksum0, session.battle_frame0, session.deck_digests)
        self.phase, self.wait_since = 'sync', time.perf_counter()

    def sync(self):
        match = self.room.match
        state = match.poll()
        if state == 'battle':
            self.session.transport = self.room.link
            self.phase = 'battle'
            self.p.log('NETPLAY_BATTLE_BEGIN', self.m['round'], self.m['stage'], self.m['seed'])
            return False
        if state != 'locked' or time.perf_counter() - self.wait_since > 60:
            if state == 'rejected' and 'frame0_mismatch' in str(match.reason):
                self.exchange_desync(frame0=True)
                self.end = 'desync'
            else:
                self.end = 'not_started' if state == 'locked' else ('peer_left' if state == 'left' else str(state))
            return self.finish_round()
        time.sleep(0.002)
        return False

    def surrender_end(self):
        """已确认的投降（输入位 SURRENDER，双方按同一帧判定）：本方 surrender、对方 peer_surrender、同一帧双方 draw_surrender。
        战斗已在更早的已确认帧结束时不计。"""
        session = self.session
        sur = session.surrender
        if sur is None or (session.finished_frame is not None and session.finished_frame <= sur[0]):
            return None
        side = self.m['side']
        mine, theirs = sur[1][side], sur[1][1 - side]
        return 'draw_surrender' if mine and theirs else 'surrender' if mine else 'peer_surrender'

    def battle(self):
        session, room = self.session, self.room
        match, link = room.match, room.link
        if self.menu.surrendered and not self.surrender_queued:
            session.actions.add('surrender')
            self.surrender_queued = True
        session.tick()
        match.poll()
        surrender = self.surrender_end()
        if surrender is not None:
            self.end = surrender
        elif session.desync is not None or match.peer_desync is not None:
            self.exchange_desync()
            self.end = 'desync'
        elif session.finished_frame is not None and session.confirmed >= session.finished_frame + 30:
            self.end = 'finished'
        elif link.state == 'disconnected':
            self.end = 'disconnected'
        elif link.state == 'closed' or match.state in ('left', 'disconnected'):
            self.end = 'peer_left'
        if self.end is not None:
            return self.finish_round()
        return True

    def present(self):
        """实际显示的帧（RegularBattle.lab_update 之后）：连接状态与 Esc 菜单。"""
        self.menu.draw()
        link = self.room.link
        if link is not None and self.phase == 'battle':
            self.lobby.draw_hud(link)

    def exchange_desync(self, frame0=False):
        import netplay_desync as nd
        match, session = self.room.match, self.session
        try:
            notice = {'kind': 'frame0', 'frame': 0, 'by': 'local'} if frame0 else session.desync_notice(match.peer_desync)
            payload = session.desync_payload(notice, match.peer_desync)
            match.send_desync(notice, payload)
            deadline = time.perf_counter() + 15
            while match.peer_desync_data is None and room_alive(self.room) and time.perf_counter() < deadline:
                match.poll()
                time.sleep(0.005)
            notes = [{'zh': d.get('zh'), 'en': d.get('en')} for d in match.differences or []] if frame0 else None
            report = nd.safe_report(payload, match.peer_desync_data, session.local_side, match.round, notes=notes)
            folder = desync_dir()
            folder.mkdir(parents=True, exist_ok=True)
            self.desync_report = str(nd.save(report, folder))
            self.p.log('NETPLAY_DESYNC_REPORT', self.desync_report)
        except Exception as error:
            self.p.log('NETPLAY_DESYNC_REPORT_ERROR', type(error).__name__, str(error))

    def outcome(self):
        """本方视角的结果：win / loss / draw；未打完的轮按结束原因判定（投降一方负）。"""
        side = self.m['side']
        if self.end == 'surrender':
            return 'loss'
        if self.end == 'peer_surrender':
            return 'win'
        if self.end == 'draw_surrender':
            return 'draw'
        if self.end != 'finished':
            return None
        hp = self.session.events_end.get(self.session.finished_frame)
        hp = hp if isinstance(hp, list) else self.session.base_hp()
        if hp[0] is None or hp[1] is None:
            return None
        mine, theirs = hp[side], hp[1 - side]
        if mine > 0 >= theirs:
            return 'win'
        if theirs > 0 >= mine:
            return 'loss'
        return 'draw'

    def finish_round(self):
        """本轮结束：保存回放与战绩，结束会话，向对方发送结果（或投降），经闸门回到大厅。"""
        import netplay_profile
        import netplay_replay
        session, room, lab = self.session, self.room, self.lab
        match = room.match
        names = [self.lobby.profile['name'], room.peer_profile().get('name', '?')]
        if self.m['side'] == 1:
            names.reverse()
        if session.input_log:
            try:
                replay = netplay_replay.build(session, 'netplay', self.lobby.manifest(), self.m, names=names, end=self.end,
                                              version=self.lobby.version)
                self.replay = str(netplay_replay.save(replay))
            except Exception as error:
                self.p.log('NETPLAY_REPLAY_ERROR', type(error).__name__, str(error))
        outcome = self.outcome()
        room.count_round(outcome)
        try:
            self.lobby.profile = netplay_profile.record_result(self.p, outcome)
        except OSError as error:
            self.p.log('NETPLAY_RECORD_ERROR', str(error))
        if match is not None and room_alive(room):
            if match.state in ('battle', 'locked'):
                match.send_result({'confirmed': session.confirmed, 'finished_frame': session.finished_frame, 'reason': self.end,
                                   'checksums': {str(f): list(v) for f, v in sorted(session.checksum_log.items())}})
        if self.phase in ('sync', 'battle'):
            session.end()
        room.result = {'end': self.end, 'outcome': outcome, 'replay': self.replay, 'desync': self.desync_report,
                       'round': self.m['round']}
        room.local_ready = False
        room.state = 'room' if room_alive(room) else 'closed'
        self.p.log('NETPLAY_ROUND_END', self.m['round'], self.end, outcome, self.replay)
        self.phase = 'closing'
        self.menu.set_open(False)
        if lab.active:
            lab.finish('netplay_' + str(self.end), reopen_prep=False)
        return True

    def closing(self):
        """闸门合拢、离开战斗、回到 Wi-Fi 菜单之后交还游戏循环；期间继续处理网络（结果送达）。"""
        p, lab, room = self.p, self.lab, self.room
        if room.match is not None and room_alive(room):
            room.match.poll()
        p.step_frame()
        if not lab.active and lab.finishing is None:
            self.restore_switches()
            self.finished = True
            self.lobby.round_closed(self)
        return True

    def restore_switches(self):
        saved, self.saved_switches = getattr(self, 'saved_switches', None), None
        for name, value in (saved or {}).items():
            setattr(self.lab, name, value)

    def abort(self, reason):
        self.end = self.end or reason
        self.p.log('NETPLAY_DRIVER_ABORT', reason, self.notice)
        try:
            if self.phase in ('sync', 'battle'):
                self.session.end()
            else:
                self.session.mode.exit()
                if self.lab.start_hook == self.session.mode.reseed:
                    self.lab.start_hook = None
                self.lab.netplay_mode = None
        finally:
            self.phase = 'closing'
            if self.lab.active:
                self.lab.finish('netplay_' + reason, reopen_prep=False)
        return True


def room_alive(room):
    return room.link is not None and room.link.state in ('connected', 'interrupted')


class NetMenu:
    """对战中 Esc 菜单（R4：联机不暂停）：音乐、音效、投降、返回对战。宿主绘制，不改变模拟。"""

    ROWS = ('menu_music', 'menu_effects', 'surrender', 'resume')

    def __init__(self, driver):
        self.driver, self.p = driver, driver.p
        self.open = False
        self.surrendered = False
        self.overlay = None
        self.rects = []
        self.revision = 0
        self.confirm = False

    def set_open(self, value):
        if value != self.open:
            self.open = value
            self.confirm = False
            self.revision += 1
            play_se(self.p, SE_DECIDE if value else SE_CLOSE)

    def audio(self, offset):
        app = self.p.app_instance()
        return bool(self.p.word(app + offset))

    def select(self, row):
        p = self.p
        if row in ('menu_music', 'menu_effects'):
            offset = 0x3d5c if row == 'menu_music' else 0x3d60
            app = p.app_instance()
            p.put(app + offset, 0 if p.word(app + offset) else 1)   # 回滚时保持当前值（RegularBattle.ui_capture）
            play_se(p, SE_DECIDE)
        elif row == 'surrender':
            if not self.confirm:
                self.confirm = True
            else:
                self.surrendered = True
                self.set_open(False)
        else:
            self.set_open(False)
        self.revision += 1

    def touch(self, action, x, y):
        if not self.open:
            return False
        if action == 3:
            for rect, row in self.rects:
                if inside(rect, x, y):
                    self.select(row)
                    return True
            if not inside((440, 160, 400, 400), x, y):
                self.set_open(False)
        return True

    def draw(self):
        if not self.open:
            return
        from PIL import Image
        p = self.p
        if self.overlay is None:
            from trial_overlay import SurfaceOverlay
            self.overlay = SurfaceOverlay(p.graphics)
        key = ('netmenu', self.revision, lang(p), self.audio(0x3d5c), self.audio(0x3d60))
        if self.overlay.cached != key:
            image = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
            skin = self.driver.lobby.skin
            c = Canvas(image, skin, self.driver.lobby.font(), None)
            c.panel((0, 0, 400, 400), tr(p, 'menu_title'))
            self.rects = []
            for i, row in enumerate(self.ROWS):
                label = tr(p, row)
                if row in ('menu_music', 'menu_effects'):
                    label += '：' + tr(p, 'on' if self.audio(0x3d5c if row == 'menu_music' else 0x3d60) else 'off')
                if row == 'surrender' and self.confirm:
                    label = tr(p, 'surrender') + ' ?'
                rect = (40, 70 + i * 76, 320, 56)
                c.button(rect, label, row, 20, 'off' if row == 'surrender' else 'normal')
                self.rects.append(((440 + rect[0], 160 + rect[1], rect[2], rect[3]), row))
            self.image = image
        self.overlay.draw_image(self.image, key, (440, 160, 400, 400))

    def close(self):
        if self.overlay is not None:
            self.overlay.close()
            self.overlay = None


# ---------- 大厅 ----------
class NetplayLobby:
    def __init__(self, probe, lab, root):
        self.p, self.lab, self.root = probe, lab, Path(root)
        self.state = 'closed'             # closed、entering、menu、vs、battle
        self.kind = None
        self.window = None                # {'kind': ..., ...}
        self.room = None
        self.commands = deque()           # 窗口线程放入的文字与按键（游戏线程处理）
        self.skin = Skin(lab)
        self._font = None
        self.overlay = self.press_overlay = self.hud_overlay = None
        self.revision = 0
        self.rects = []
        self.pressed = None
        self.profile = None
        self.delay = int(os.environ.get('MSD_NETPLAY_DELAY', '2'))
        self.pool = None
        self.version = ''
        self._manifest = None
        self.messages = []                # 原生留言文字（大厅文字批次中取得，按留言号）
        self.driver = None
        self.since = 0
        self.shutter_closing = False
        self.vs_fixed = False
        self.error = None
        self.base_scene = None            # 最近一个非弹窗场景（判断原生弹窗下面是 Wi-Fi 菜单还是编队页）

    # ---------- 公共 ----------
    def font(self):
        if self._font is None:
            self._font = fonts()
        return self._font

    def active(self):
        return self.state != 'closed'

    def manifest(self):
        if self._manifest is None:
            import content_manifest
            self._manifest = content_manifest.build(self.p)
        return self._manifest

    def link_info(self):
        import content_manifest
        return {'name': self.profile['name'] if self.profile else '', 'version': self.version,
                'digest': content_manifest.digest(self.manifest())[:16], 'mode': 'regular'}

    def card(self):
        """本方名片（发给对手）：名称、头像、留言号与文字、本地战绩。"""
        p = self.p
        app = p.app_instance()
        message = p.call('_ZN7AppMain22GetWiFiMessageSaveDataEv', app) & 0xff
        avatar = p.call('_ZN7AppMain23GetWiFiMyAvatarSaveDataEv', app) & 0xff
        card = {'name': self.profile['name'], 'avatar': avatar, 'message': message, 'record': dict(self.profile['record'])}
        if 0 <= message < len(self.messages):
            card['message_text'] = self.messages[message]
        return card

    def open(self, kind='lan'):
        """VERSUS 页“局域网”卡片：原生闸门合拢后进入 Wi-Fi VERSUS 菜单。"""
        import branding
        import netplay_profile
        if self.state != 'closed':
            return
        p = self.p
        self.kind = kind
        # 输入延迟：局域网 2 帧；远程自动（0：按网络延迟 2–6 帧，双方取较大值，R9）。环境变量供测试。
        self.delay = int(os.environ['MSD_NETPLAY_DELAY']) if os.environ.get('MSD_NETPLAY_DELAY') else (0 if kind == 'remote' else 2)
        self.profile = netplay_profile.load(p)
        self.pool = load_pool(self.root)
        self.version = branding.load(self.root)['display_version']
        self._manifest = None
        self.state, self.since = 'entering', p.frame
        self.base_scene = None
        self.shutter_closing = True
        p.call('_ZN7AppMain15SetShutterCloseEv', p.app_instance())
        p.log('NETPLAY_LOBBY_OPEN', kind)

    def scene(self):
        app = self.p.app_instance()
        return self.p.word(app + 0x22bc), self.p.word(app + 0x22dc)

    def set_window(self, window):
        self.window = window
        self.pressed = None
        self.revision += 1

    def menu_shown(self, scene):
        """Wi-Fi 菜单在画面上：菜单场景本身，或菜单之上的原生弹窗（编队页之上的弹窗如 SORT 不算）。"""
        return scene in MENU_SCENES or (scene in POPUP_SCENES and self.base_scene in MENU_SCENES)

    # ---------- 每帧（原生 step 之前） ----------
    def prepare_frame(self):
        if self.state == 'closed':
            return
        p = self.p
        try:
            self.process_commands()
            scene, state = self.scene()
            if scene not in POPUP_SCENES:
                self.base_scene = scene
            app = p.app_instance()
            if self.state == 'entering':
                if self.shutter_closing and p.frame - self.since > 2 and p.call('_ZN7AppMain14IsShutterCloseEv', app):
                    self.shutter_closing = False
                    p.call('_ZN7AppMain12SceneEndFuncEi', app, scene)
                    p.call('_ZN7AppMain11ChangeExeSTEi', app, WIFI_INIT)
                elif not self.shutter_closing and scene == WIFI_LOOP:
                    self.state = 'menu'
                    self.stable = 0
                elif p.frame - self.since > 300:
                    self.close('enter_timeout')
                    return
            if self.state == 'menu':
                # 菜单稳定（无原生弹窗）15 帧后：尚无名称时打开名称窗口；名称修改后重建原生名牌与文字批次。
                self.stable = self.stable + 1 if (scene, state) == (WIFI_LOOP, 1) else 0
                if self.stable >= 15 and self.window is None and not self.profile['name'] and not getattr(self, 'name_prompted', False):
                    self.name_prompted = True
                    self.open_name(first=True)
                if self.stable >= 2 and getattr(self, 'pending_restart', False):
                    self.pending_restart = False
                    self.restart_menu()
            if self.state in ('menu', 'vs'):
                if self.room is not None:
                    self.room.service()
                self.follow_room()
            if self.state == 'vs':
                self.vs_frame(scene)
            if self.state == 'menu' and scene not in MENU_SCENES + DECK_SCENES + POPUP_SCENES and not self.lab.active:
                if self.room is None:
                    self.close('left_menu')
                    return
            # 菜单上的原生弹窗（换头像、留言、首次说明等）期间背景仍是 Wi-Fi 菜单，隐藏表保持有效；编队页期间不写。
            self.write_menu(self.menu_shown(scene) and self.state == 'menu')
            if scene in MENU_SCENES:
                self.write_name()
        except Exception as error:
            import traceback
            from probe import ProbeCancelled
            if isinstance(error, ProbeCancelled):
                raise
            self.error = f'{type(error).__name__}: {error}'
            p.log('NETPLAY_LOBBY_ERROR', traceback.format_exc())

    def write_menu(self, enable):
        """原生 Wi-Fi 菜单的隐藏图块（drawConv 替换表）。"""
        p = self.p
        if not enable:
            if p.word(VS_TABLE) == VS_MAGIC and getattr(self, 'table_written', False):
                p.put(VS_TABLE, 0)
                self.table_written = False
            return
        if getattr(self, 'table_written', False) and p.word(VS_TABLE) == VS_MAGIC:
            return
        for i, (conv, y) in enumerate(HIDDEN):
            e = VS_TABLE + 0x10 + i * 32
            p.put(e, conv)
            p.put(e + 4, 0)
            p.put(e + 8, 0)
            p.write(e + 12, struct.pack('<f', y) if y else bytes(4))
            p.write(e + 16, bytes(16))
        p.put(VS_TABLE + 4, len(HIDDEN))
        p.put(VS_TABLE, VS_MAGIC)
        self.table_written = True

    def write_name(self):
        p = self.p
        name = (self.profile or {}).get('name') or ''
        app = p.app_instance()
        gc = p.call('_ZN7AppMain21getGameCenterInstanceEv', app)
        if gc:
            raw = name.encode('utf-8')[:63]
            if p.read(gc + GAMECENTER_NAME, len(raw) + 1) != raw + b'\x00':
                p.write(gc + GAMECENTER_NAME, raw + bytes(64 - len(raw)))

    def rename_strings(self, a):
        """原生 Wi-Fi 菜单文字批次（按钮、名称、战绩、分数、OK、留言…）：改按钮文字，战绩数字改为本地联机战绩，分数 / 排名为 “-”。"""
        if self.state == 'closed' or not self.menu_shown(self.scene()[0]):
            return
        p = self.p
        try:
            cursor = (a[3] + 4 + 7) & ~7
            cursor += 8
            refs = [p.word(cursor + 4 * i) for i in range(6)]
            items = p.objects[refs[5]]['items']
            texts = [p.objects.get(item) for item in items]
            for item, text in zip(items, texts):
                if isinstance(text, str) and 'Google Play' in text:
                    p.objects[item] = tr(p, 'intro')          # 原版首次进入的 Google Play 说明 → 局域网对战说明
            if len(texts) < 7 or not all(isinstance(t, str) for t in texts[:6]) or texts[5] != 'OK':
                return
            p.objects[items[0]] = tr(p, 'host')
            p.objects[items[1]] = tr(p, 'join')
            record = (self.profile or {}).get('record') or {}
            p.objects[items[3]] = replace_last_numbers(texts[3], (record.get('wins', 0), record.get('losses', 0)))
            p.objects[items[4]] = re.sub(r'\d+', '-', texts[4], count=1)
            self.messages = [t for t in texts[6:] if isinstance(t, str)]
        except Exception as error:
            p.log('NETPLAY_RENAME_ERROR', type(error).__name__, str(error))

    # ---------- 窗口线程指令 ----------
    def wants_keys(self):
        return self.state != 'closed' and self.window is not None and self.scene()[0] in MENU_SCENES + DECK_SCENES

    def wants_text(self):
        return self.wants_keys() and self.window.get('field') is not None

    def process_commands(self):
        while self.commands:
            command = self.commands.popleft()
            if command[0] == 'text':
                field = (self.window or {}).get('field')
                if field is not None:
                    field.type(command[1])
                    self.revision += 1
            elif command[0] == 'key':
                self.key(command[1])
            elif command[0] == 'battle_menu':
                if self.driver is not None and self.driver.phase == 'battle':
                    self.driver.menu.set_open(not self.driver.menu.open)

    def key(self, name):
        window = self.window
        if window is None:
            return
        field = window.get('field')
        if name == 'backspace' and field is not None:
            field.backspace()
            self.revision += 1
        elif name == 'tab' and window.get('fields'):
            self.focus(1 - window['focus'])
        elif name == 'enter' and window.get('fields') and window['focus'] == 0:
            self.focus(1)
        elif name == 'enter':
            default = window.get('default')
            if default:
                self.command(default)
        elif name == 'escape':
            cancel = window.get('cancel')
            if cancel:
                self.command(cancel)

    # ---------- 触点 ----------
    def touch(self, action, x, y):
        """返回 True 表示已处理（不送入原生）。"""
        if self.state == 'closed':
            return False
        if self.driver is not None and self.lab.active:
            if self.driver.menu.touch(action, x, y):
                return True
            return False                                  # 对战中的触点交给 RegularBattle（lab_runtime）
        scene = self.scene()[0]
        if self.state == 'entering' or self.state == 'vs':
            return True
        if self.window is not None:
            if action == 1:
                self.pressed = next((cmd for rect, cmd in self.rects if inside(rect, x, y)), None)
                self.revision += 1
            elif action == 3:
                command = next((cmd for rect, cmd in self.rects if inside(rect, x, y)), None)
                pressed, self.pressed = self.pressed, None
                self.revision += 1
                if command is not None and command == pressed:
                    self.command(command)
            return True
        if scene not in MENU_SCENES:
            return False
        if action == 1:
            if inside(FRIEND_RECT, x, y):
                self.pressed = 'host'
            elif inside(RANKED_RECT, x, y):
                self.pressed = 'join'
            elif inside(NAME_RECT, x, y):
                self.pressed = 'name'
            elif any(inside(r, x, y) for r in BLOCKED_RECTS):
                self.pressed = 'blocked'
            else:
                return False
            return True
        if self.pressed is None:
            return False
        if action == 3:
            pressed, self.pressed = self.pressed, None
            target = {'host': FRIEND_RECT, 'join': RANKED_RECT, 'name': NAME_RECT}.get(pressed)
            if target is not None and inside(target, x, y):
                self.command(pressed)
        return True

    def back(self):
        """Esc / 原生 Back：窗口打开时关闭窗口；对战中打开或关闭 Esc 菜单。"""
        if self.state == 'closed':
            return False
        if self.driver is not None and self.lab.active:
            if self.driver.phase == 'battle':
                self.driver.menu.set_open(not self.driver.menu.open)
            return True
        if self.window is not None:
            self.key('escape')
            return True
        return self.state in ('entering', 'vs')

    # ---------- 命令 ----------
    def command(self, name):
        p = self.p
        window = self.window or {}
        if name in ('host', 'join') and not self.profile['name']:
            self.open_name(first=True)
            return
        if name == 'name':
            play_se(p, SE_DECIDE)
            self.open_name()
        elif name == 'name_ok':
            import netplay_profile
            value = netplay_profile.clean_name(window['field'].value)
            if not value:
                play_se(p, SE_CLOSE)
                return
            self.profile['name'] = value
            netplay_profile.save(p, self.profile)
            play_se(p, SE_DECIDE)
            self.set_window(None)
            self.pending_restart = True                   # 原生名牌与文字批次在菜单初始化时重建（菜单稳定后）
        elif name == 'name_cancel':
            play_se(p, SE_CLOSE)
            self.set_window(None)
        elif name == 'host':
            play_se(p, SE_DECIDE)
            self.open_host()
        elif name == 'join':
            play_se(p, SE_DECIDE)
            if self.kind == 'remote':
                self.open_direct('direct_cancel')
            else:
                self.open_join()
        elif name.startswith('room:'):
            room = self.scanned.get(name[5:])
            if room is not None:
                play_se(p, SE_DECIDE)
                self.connect([tuple(room['address'])], room.get('code'))
        elif name == 'by_ip':
            play_se(p, SE_DECIDE)
            self.stop_scan()
            self.open_direct('join')
        elif name.startswith('focus:'):
            self.focus(int(name[6:]))
        elif name == 'direct_ok':
            import netplay_net as nn
            import netplay_profile
            fields = window['fields']
            text, code = fields[0].value.strip(), fields[1].value.strip().upper()
            try:
                nn.split_address(text, nn.GAME_PORT)
                valid = True
            except (ValueError, TypeError):
                valid = False
            if not valid or len(code) != 6:
                play_se(p, SE_CLOSE)
                window['error'] = tr(p, 'ip_bad' if not valid else 'code_bad')
                self.focus(0 if not valid else 1)
                return
            self.profile['last_address'] = text
            try:
                netplay_profile.save(p, self.profile)
            except OSError as error:
                p.log('NETPLAY_PROFILE_SAVE_ERROR', str(error))
            play_se(p, SE_DECIDE)
            self.stop_scan()
            self.room = Room(self, 'client')
            self.room.resolve(text, code)
            self.set_window({'kind': 'connecting', 'cancel': 'leave_room'})
        elif name == 'direct_cancel':
            play_se(p, SE_CLOSE)
            self.set_window(None)
        elif name == 'port':
            play_se(p, SE_DECIDE)
            port = self.room.endpoint.address[1] if self.room is not None and self.room.endpoint else 47631
            self.set_window({'kind': 'port', 'field': TextField(str(port), 5, '0123456789'), 'default': 'port_ok',
                             'cancel': 'port_cancel'})
        elif name == 'port_ok':
            import netplay_profile
            value = window['field'].value
            port = int(value) if value.isdigit() else 0
            if not 1024 <= port < 65536:
                play_se(p, SE_CLOSE)
                window['error'] = tr(p, 'port_bad')
                self.revision += 1
                return
            play_se(p, SE_DECIDE)
            self.profile['port'] = port
            try:
                netplay_profile.save(p, self.profile)
            except OSError as error:
                p.log('NETPLAY_PROFILE_SAVE_ERROR', str(error))
            if self.room is not None:
                self.room.close()
                self.room = None
            self.open_host()
        elif name == 'port_cancel':
            play_se(p, SE_CLOSE)
            self.set_window({'kind': 'host', 'cancel': 'leave_room'})
        elif name == 'join_cancel':
            play_se(p, SE_CLOSE)
            self.stop_scan()
            self.set_window(None)
        elif name == 'ready':
            if self.room is not None:
                play_se(p, SE_DECIDE)
                self.room.ready()
                self.revision += 1
        elif name == 'leave_room':
            play_se(p, SE_CLOSE)
            self.leave_room()
        elif name == 'message_ok':
            play_se(p, SE_CLOSE)
            self.set_window(window.get('next'))

    def open_host(self):
        p = self.p
        self.room = Room(self, 'host')
        try:
            self.room.open_host(self.profile.get('port') or None)
        except OSError as error:
            self.room = None
            self.message(tr(p, 'disconnected'), [str(error)])
            return
        self.set_window({'kind': 'host', 'cancel': 'leave_room'})

    def open_direct(self, cancel):
        """按地址加入：房主地址（IPv4、[IPv6]、域名，可带 :端口）与 6 位房间码两个输入栏（Tab、Enter 或点击切换）。"""
        fields = [TextField((self.profile or {}).get('last_address', ''), 64, ADDRESS_CHARS),
                  TextField('', 6, CODE_CHARS, upper=True)]
        focus = 1 if fields[0].value else 0
        self.set_window({'kind': 'direct', 'fields': fields, 'focus': focus, 'field': fields[focus], 'default': 'direct_ok',
                         'cancel': cancel})

    def focus(self, index):
        window = self.window or {}
        if window.get('fields') and index in (0, 1):
            window['focus'], window['field'] = index, window['fields'][index]
            self.revision += 1

    def open_name(self, first=False):
        self.set_window({'kind': 'name', 'field': TextField(self.profile['name'], 16), 'first': first,
                         'default': 'name_ok', 'cancel': 'name_cancel'})

    def open_join(self):
        import netplay_net as nn
        self.stop_scan()
        targets = None
        configured = os.environ.get('MSD_NETPLAY_SCAN')
        if configured:
            targets = [nn.parse_address(t, nn.DISCOVERY_PORT) for t in configured.split(',')]
        try:
            self.scanner = nn.LanScanner(targets, bind=(os.environ.get('MSD_NETPLAY_BIND', '0.0.0.0'), 0))
        except OSError as error:
            self.scanner = None
            self.p.log('NETPLAY_SCAN_ERROR', str(error))
        self.scanned = {}
        self.set_window({'kind': 'join', 'cancel': 'join_cancel'})

    def stop_scan(self):
        scanner = getattr(self, 'scanner', None)
        if scanner is not None:
            scanner.close()
        self.scanner = None

    def connect(self, candidates, code=None):
        self.stop_scan()
        self.room = Room(self, 'client')
        self.room.open_join(candidates, code)
        self.set_window({'kind': 'connecting', 'cancel': 'leave_room'})

    def leave_room(self):
        if self.room is not None:
            self.room.close()
        self.room = None
        self.set_window(None)

    def message(self, title, lines, next_window=None):
        self.set_window({'kind': 'message', 'title': title, 'lines': list(lines), 'default': 'message_ok',
                         'cancel': 'message_ok', 'next': next_window})

    def restart_menu(self):
        """重新进入 Wi-Fi 菜单（名称修改后原生名牌与文字批次重建）。"""
        p = self.p
        scene, _ = self.scene()
        if scene in MENU_SCENES:
            app = p.app_instance()
            p.call('_ZN7AppMain12SceneEndFuncEi', app, scene)
            p.call('_ZN7AppMain11ChangeExeSTEi', app, WIFI_INIT)

    # ---------- 房间状态 ----------
    def follow_room(self):
        p, room = self.p, self.room
        window = self.window or {}
        kind = window.get('kind')
        scanner = getattr(self, 'scanner', None)
        if scanner is not None and kind == 'join':
            scanner.service()
            rooms = {f"{r['address'][0]}:{r['address'][1]}": r for r in scanner.rooms.values()
                     if time.perf_counter() - r.get('seen', 0) < 3.0}
            if rooms.keys() != self.scanned.keys():
                self.scanned = rooms
                self.revision += 1
        if room is None:
            return
        if room.state == 'closed':
            reason, differences = room.reason, room.differences
            self.leave_room()
            if differences:
                import content_manifest
                lines = content_manifest.report(differences, 'zh' if lang(p) in ('ZT', 'ZS', 'JP') else 'en', 8).split('\n')
                self.message(tr(p, 'rejected'), lines)
            elif reason in ('peer_left', 'disconnected'):
                self.message(tr(p, reason), [])
            elif reason:
                import netplay_net as nn
                key = {'timeout': 'fail_timeout', 'wrong_code': 'fail_wrong_code', 'resolve': 'fail_resolve'}.get(reason)
                text = tr(p, key) if key else nn.connect_failure_text(reason, 'zh' if lang(p) != 'EN' else 'en')
                self.message(tr(p, 'connect_failed'), wrap(text, 46 if lang(p) != 'EN' else 80))
            return
        if room.state == 'waiting' and kind not in ('host', 'message'):
            if room.reason in ('peer_left', 'disconnected'):
                self.message(tr(p, room.reason), [], {'kind': 'host', 'cancel': 'leave_room'})
                room.reason = None
            else:
                self.set_window({'kind': 'host', 'cancel': 'leave_room'})
        elif room.state in ('checking',) and kind != 'connecting':
            self.set_window({'kind': 'connecting', 'cancel': 'leave_room'})
        elif room.state == 'room' and kind not in ('room', 'message'):
            self.set_window({'kind': 'room', 'cancel': 'leave_room'})
        elif room.state == 'room' and room.match is not None and room.match.state == 'decks':
            room.maybe_lock_after_rematch()
        if room.state == 'locked' and self.state == 'menu':
            self.begin_versus()
        key = (room.state, room.local_ready, room.peer_ready(), room.match.state if room.match else None,
               (room.upnp or {}).get('state'))
        if key != getattr(self, 'room_key', None):
            self.room_key = key
            self.revision += 1

    # ---------- 开战：原生对手画面 → 战斗 ----------
    def begin_versus(self):
        """双方编队已揭示：写入原生对手数据，闸门合拢后进入 WiFiDeck 场景（对手名片与编队）。"""
        p, room = self.p, self.room
        m = room.match.match
        self.set_window(None)
        self.write_opponent(m)
        self.driver = RegularDriver(self, room, m)
        p.session_driver = self.driver
        self.state, self.since, self.vs_fixed = 'vs', p.frame, False
        self.vs_phase = 'closing'
        room.state = 'vs'
        p.call('_ZN7AppMain15SetShutterCloseEv', p.app_instance())
        p.log('NETPLAY_VERSUS', m['round'], m['stage'])

    def write_opponent(self, m):
        """对手数据（_SEND_MESSAGE +1 起，app+0xc081）：编队（UID 低 10 位 | 等级 << 10，社区单位以同阵营原版单位代写，
        供原生阵营奖励显示）、名称 +0x14、勝場 +0x3c、留言 +0x3e、头像 +0x3f。"""
        p, lab = self.p, self.lab
        app = p.app_instance()
        side = m['side']
        deck = lab.resolve_deck(m['p2_deck'] if side == 0 else m['p1_deck'])
        self.opponent_deck = deck
        lab.write_enemy_deck([None if e is None else (e[0] if e[0] < 400 else lab.stand_in(e[0]), e[1]) for e in deck])
        profile = self.room.peer_card()
        base = app + OPPONENT
        name = (profile.get('name') or '').encode('utf-8')[:0x2f]
        p.write(base + 0x14, name + bytes(0x30 - len(name)))
        p.put(base + 0x34, 0)                                  # 分數（不计 RP）
        p.put(base + 0x38, 0)                                  # 排名（0：显示 “-”）
        wins = int((profile.get('record') or {}).get('wins', 0)) & 0xffff
        p.write(base + 0x3c, struct.pack('<H', wins))
        p.write(base + 0x3e, bytes((int(profile.get('message', 0)) & 0xff, int(profile.get('avatar', 0)) & 0xff)))

    def vs_frame(self, scene):
        p = self.p
        app = p.app_instance()
        if self.vs_phase == 'closing':
            if p.frame - self.since > 2 and p.call('_ZN7AppMain14IsShutterCloseEv', app):
                p.call('_ZN7AppMain12SceneEndFuncEi', app, scene)
                p.call('_ZN7AppMain11ChangeExeSTEi', app, WIFI_DECK_INIT)
                self.vs_phase = 'deck'
        elif self.vs_phase == 'deck':
            if scene == WIFI_DECK_LOOP and not self.vs_fixed:
                self.vs_fixed = True
                for slot, entry in enumerate(self.opponent_deck):   # 社区单位以完整 UnitID 显示（原生对手数据只能写 10 位）
                    if entry is not None and entry[0] >= 400:
                        p.call('_ZN7AppMain15SetWiFiDeckUnitEii', app, slot, entry[0])
            if scene == BATTLE_START:
                self.vs_phase = 'battle'
                self.state = 'battle'
                self.driver.start_battle()                   # 取代原生 SC_BattleStart（本帧原生 step 之前）
        if self.room is not None and not room_alive(self.room) and self.vs_phase != 'battle':
            pass                                              # 对手在对手画面期间离开：开战后由第 0 帧同步超时结束

    def round_closed(self, driver):
        """一轮结束、已回到 Wi-Fi 菜单：显示房间与结果。"""
        self.driver = None
        self.state = 'menu'
        room = self.room
        if room is not None and room.state == 'room':
            self.set_window({'kind': 'room', 'cancel': 'leave_room'})
        elif room is not None and room.state == 'closed':
            self.follow_room()
        self.revision += 1

    # ---------- 绘制 ----------
    def draw(self):
        if self.state == 'closed':
            return
        p = self.p
        scene = self.scene()[0]
        try:
            if self.window is not None and scene in MENU_SCENES + DECK_SCENES and self.state == 'menu':
                self.draw_window()
            elif self.window is None and self.pressed in ('host', 'join', 'name') and scene in MENU_SCENES:
                self.draw_press()
        except Exception as error:
            import traceback
            p.log('NETPLAY_LOBBY_DRAW_ERROR', traceback.format_exc())

    def draw_press(self):
        from PIL import Image
        rect = {'host': FRIEND_RECT, 'join': RANKED_RECT, 'name': NAME_RECT}[self.pressed]
        if self.press_overlay is None:
            from trial_overlay import SurfaceOverlay
            self.press_overlay = SurfaceOverlay(self.p.graphics)
        key = ('press', self.pressed)
        if self.press_overlay.cached != key:
            self.press_image = Image.new('RGBA', (8, 8), (120, 220, 255, 90))
        self.press_overlay.draw_image(self.press_image, key, tuple(int(v) for v in rect))

    def draw_window(self):
        from PIL import Image
        p = self.p
        if self.overlay is None:
            from trial_overlay import SurfaceOverlay
            self.overlay = SurfaceOverlay(p.graphics)
        key = ('lobby', self.revision, lang(p))
        if self.overlay.cached != key:
            image = Image.new('RGBA', (W, H), (0, 0, 0, 120))
            c = Canvas(image, self.skin, self.font(), self.pressed)
            self.render(c)
            self.rects = c.hitboxes
            self.window_image = image
        self.overlay.draw_image(self.window_image, key, (0, 0, W, H))

    def draw_hud(self, link):
        """对战中右上角的连接状态（往返延迟；不稳定时提示）。"""
        from PIL import Image
        p = self.p
        status = link.status()
        rtt = status.get('srtt_ms')
        text = ('Ping %d ms' % rtt) if rtt is not None else 'Ping -'
        if link.state == 'interrupted':
            text = tr(p, 'interrupted')
        if self.hud_overlay is None:
            from trial_overlay import SurfaceOverlay
            self.hud_overlay = SurfaceOverlay(p.graphics)
        key = ('hud', text, lang(p))
        if self.hud_overlay.cached != key:
            image = Image.new('RGBA', (220, 30), (0, 0, 0, 0))
            c = Canvas(image, self.skin, self.font(), None)
            c.text((216, 15), text, 16, RED if link.state == 'interrupted' else WHITE, 'rm', 2, 214)
            self.hud_image = image
        self.hud_overlay.draw_image(self.hud_image, key, (1050, 96, 220, 30))

    def render(self, c):
        p = self.p
        window = self.window
        kind = window['kind']
        if kind == 'name':
            self.render_field(c, tr(p, 'name_title'), [tr(p, 'name_first')] if window.get('first') else [],
                              tr(p, 'name_hint'), window['field'], 'name_ok', 'name_cancel', window.get('error'))
        elif kind == 'direct':
            self.render_direct(c)
        elif kind == 'port':
            self.render_field(c, tr(p, 'port_title'), [], tr(p, 'port_hint'), window['field'], 'port_ok', 'port_cancel',
                              window.get('error'))
        elif kind == 'host':
            self.render_host(c)
        elif kind == 'join':
            self.render_join(c)
        elif kind == 'connecting':
            x, y, w, h = 290, 230, 700, 260
            c.panel((x, y, w, h), tr(p, 'host') if self.room and self.room.role == 'host' else tr(p, 'join'))
            text = (tr(p, 'checking') if self.room and self.room.state == 'checking' else
                    tr(p, 'resolving') if self.room and self.room.state == 'resolving' else tr(p, 'connecting'))
            c.text((x + w / 2, y + 110), text, 22, WHITE, 'mm', 2, w - 40)
            c.button((x + (w - 260) / 2, y + h - 80, 260, 52), tr(p, 'cancel'), 'leave_room', 20)
        elif kind == 'message':
            x, y, w, h = 240, 200, 800, 320
            c.panel((x, y, w, h), window['title'])
            for i, line in enumerate(window['lines'][:7]):
                c.text((x + 30, y + 64 + i * 30), line, 17, WHITE, 'la', 2, w - 60)
            c.button((x + (w - 260) / 2, y + h - 76, 260, 52), tr(p, 'ok'), 'message_ok', 20)
        elif kind == 'room':
            self.render_room(c)

    def render_field(self, c, title, notes, hint, field, ok, cancel, error=None):
        p = self.p
        x, y, w, h = 240, 200, 800, 330
        c.panel((x, y, w, h), title)
        line = y + 60
        for note in notes:
            c.text((x + 30, line), note, 18, GOLD, 'la', 2, w - 60)
            line += 32
        c.text((x + 30, line), hint, 16, GRAY, 'la', 2, w - 60)
        box = (x + 30, line + 36, w - 60, 56)
        c.draw.rectangle(box[:2] + (box[0] + box[2], box[1] + box[3]), fill=(10, 30, 32, 230), outline=(140, 220, 230, 255), width=2)
        caret = '_' if (self.p.frame // 15) % 2 == 0 else ' '
        c.text((box[0] + 16, box[1] + box[3] / 2), field.value + caret, 24, WHITE, 'lm', 2, box[2] - 32)
        if error:
            c.text((x + 30, box[1] + box[3] + 12), error, 16, RED, 'la', 2, w - 60)
        c.button((x + w / 2 - 280, y + h - 76, 260, 52), tr(p, 'ok'), ok, 20)
        c.button((x + w / 2 + 20, y + h - 76, 260, 52), tr(p, 'cancel'), cancel, 20)

    def render_host(self, c):
        p, room = self.p, self.room
        remote = self.kind == 'remote'
        x, y, w, h = (130, 108, 1020, 504) if remote else (200, 150, 880, 420)
        c.panel((x, y, w, h), tr(p, 'host'))
        c.text((x + w / 2, y + 62), tr(p, 'host_wait'), 22, WHITE, 'mm', 2, w - 40)
        c.text((x + w / 2, y + 106), tr(p, 'room_code', room.code), 30, GOLD, 'mm', 3, w - 40)
        c.text((x + 30, y + 146), tr(p, 'host_tell') if remote else tr(p, 'address'), 17, BLUE, 'la', 2, w - 60)
        rows = room.address_rows()
        if not remote:
            rows = [row for row in rows if row[0] == 'lan']
        line = y + 174
        for kind, text in rows[:5]:
            if remote:
                c.text((x + 50, line), tr(p, 'addr_' + kind), 15, GOLD if kind == 'public' else GRAY, 'la', 2, 300)
                c.text((x + 360, line - 2), text, 20, WHITE, 'la', 2, w - 390)
            else:
                c.text((x + 50, line - 2), text, 20, WHITE, 'la', 2, w - 80)
            line += 28
        notes = []
        if remote:
            upnp = room.upnp or {}
            state = upnp.get('state')
            port = room.endpoint.address[1] if room.endpoint else 0
            if state == 'trying':
                notes.append((tr(p, 'upnp_trying'), GRAY))
            elif state == 'cgnat':
                notes.append((tr(p, 'upnp_cgnat', upnp.get('external_ip')), GOLD))
            elif state == 'private':
                notes.append((tr(p, 'upnp_private', upnp.get('external_ip'), port), GOLD))
            elif state == 'failed':
                notes.append((tr(p, 'upnp_failed', port), GOLD))
            if not any(kind == 'ipv6' for kind, _ in rows):
                notes.append((tr(p, 'no_ipv6'), GRAY))
        if room.port_note:
            notes.append((tr(p, 'port_busy', *room.port_note), GOLD))
        notes.append((tr(p, 'firewall'), GRAY))
        line = max(line + 8, y + (330 if remote else 300))
        for text, color in notes:
            for part in wrap(text, 64 if lang(p) != 'EN' else 125):
                if line > y + h - 84:
                    break
                c.text((x + 30, line), part, 14, color, 'la', 2, w - 60)
                line += 20
        if remote:
            port = room.endpoint.address[1] if room.endpoint else 0
            c.text((x + 30, y + h - 40), tr(p, 'port_label', port), 17, WHITE, 'lm', 2, 200)
            c.button((x + 190, y + h - 66, 220, 50), tr(p, 'change_port'), 'port', 18)
            c.button((x + w - 290, y + h - 66, 260, 50), tr(p, 'cancel'), 'leave_room', 20)
        else:
            c.button((x + (w - 260) / 2, y + h - 64, 260, 50), tr(p, 'cancel'), 'leave_room', 20)

    def render_direct(self, c):
        p, window = self.p, self.window
        x, y, w, h = 200, 150, 880, 420
        c.panel((x, y, w, h), tr(p, 'ip_title'))
        labels = (tr(p, 'field_address'), tr(p, 'field_code'))
        widths = (w - 60, 260)
        for i, field in enumerate(window['fields']):
            top = y + 58 + i * 108
            c.text((x + 30, top), labels[i], 17, BLUE, 'la', 2, w - 60)
            box = (x + 30, top + 28, widths[i], 54)
            active = window['focus'] == i
            c.draw.rectangle(box[:2] + (box[0] + box[2], box[1] + box[3]), fill=(10, 30, 32, 230),
                             outline=(140, 220, 230, 255) if active else (70, 100, 104, 255), width=3 if active else 2)
            c.text((box[0] + 16, box[1] + box[3] / 2), field.value + ('_' if active else ''), 24, WHITE, 'lm', 2, box[2] - 32)
            c.hitboxes.append((box, f'focus:{i}'))
        c.text((x + 30, y + 286), tr(p, 'ip_hint'), 15, GRAY, 'la', 2, w - 60)
        if window.get('error'):
            c.text((x + 30, y + 312), window['error'], 16, RED, 'la', 2, w - 60)
        c.button((x + w / 2 - 280, y + h - 76, 260, 52), tr(p, 'ok'), 'direct_ok', 20)
        c.button((x + w / 2 + 20, y + h - 76, 260, 52), tr(p, 'cancel'), window['cancel'], 20)

    def render_join(self, c):
        p = self.p
        x, y, w, h = 160, 130, 960, 460
        c.panel((x, y, w, h), tr(p, 'join'))
        import content_manifest
        digest = content_manifest.digest(self.manifest())[:16]
        rows = sorted(self.scanned.items(), key=lambda kv: (kv[1].get('state') != 'open', kv[1].get('name', '')))
        if not rows:
            c.text((x + w / 2, y + 120), tr(p, 'searching'), 20, WHITE, 'mm', 2, w - 40)
            c.text((x + w / 2, y + 170), tr(p, 'no_rooms'), 16, GRAY, 'mm', 2, w - 40)
        for i, (address, room) in enumerate(rows[:5]):
            top = y + 60 + i * 62
            joinable = room.get('state') == 'open' and room.get('protocol') == self_protocol()
            state = (tr(p, 'busy') if room.get('state') != 'open' else
                     tr(p, 'version_diff') if room.get('protocol') != self_protocol() or room.get('version') != self.version else
                     tr(p, 'content_diff') if room.get('digest') != digest else tr(p, 'open'))
            label = f"{room.get('name') or '?'}   {address}   {tr(p, 'room_code', room.get('code', '-'))}"
            if joinable:
                c.button((x + 24, top, w - 220, 52), label, 'room:' + address, 18, 'light')
            else:
                c.draw.rectangle((x + 24, top, x + w - 196, top + 52), fill=(40, 40, 40, 200))
                c.text((x + 40, top + 26), label, 18, GRAY, 'lm', 2, w - 250)
            c.text((x + w - 30, top + 26), state, 16, GOLD if joinable else GRAY, 'rm', 2, 160)
        c.button((x + 40, y + h - 70, 260, 52), tr(p, 'by_ip'), 'by_ip', 20)
        c.button((x + w - 300, y + h - 70, 260, 52), tr(p, 'cancel'), 'join_cancel', 20)

    def render_room(self, c):
        p, room = self.p, self.room
        x, y, w, h = 110, 120, 1060, 470
        c.panel((x, y, w, h), tr(p, 'room_title', room.code if room.role == 'host' else ''))
        me = self.card()
        peer = room.peer_card()
        cards = [(me, room.local_ready, True), (peer, room.peer_ready(), False)]
        if room.role == 'client':
            cards.reverse()                                   # 左 P1（房主）、右 P2（加入方），与对战画面一致
        for i, (card, ready, own) in enumerate(cards):
            cx = x + 30 + i * (w // 2)
            cw = w // 2 - 60
            c.draw.rectangle((cx, y + 60, cx + cw, y + 300), fill=(16, 40, 44, 220), outline=(120, 200, 210, 255), width=2)
            c.text((cx + 16, y + 84), ('P1' if i == 0 else 'P2') + '  ' + (card.get('name') or '-'), 22, GOLD, 'lm', 2, cw - 32)
            record = card.get('record') or {}
            c.text((cx + 16, y + 120), f"{record.get('wins', 0)} {tr(p, 'win')} / {record.get('losses', 0)} {tr(p, 'lose')}",
                   17, WHITE, 'lm', 2, cw - 32)
            message = card.get('message')
            text = card.get('message_text') or (self.messages[message] if isinstance(message, int)
                                                and 0 <= message < len(self.messages) else None)
            if text:
                c.text((cx + 16, y + 152), '「' + text + '」', 17, BLUE, 'lm', 2, cw - 32)
            c.text((cx + 16, y + 190), tr(p, 'your_deck') if own else tr(p, 'deck_hidden'), 15, GRAY, 'lm', 2, cw - 32)
            if own:
                self.render_deck(c, cx + 16, y + 214)
            status = tr(p, 'state_ready') if ready else tr(p, 'state_wait')
            c.text((cx + cw - 16, y + 84), status, 18, (120, 255, 140, 255) if ready else GRAY, 'rm', 2, 140)
        delay = tr(p, 'delay_frames', self.delay) if self.delay > 0 else tr(p, 'delay_auto')
        c.text((x + w / 2, y + 330), tr(p, 'room_info', len(self.pool or ()), delay), 15, GRAY, 'mm', 2, w - 40)
        result = room.result
        if result:
            label = tr(p, {'win': 'win', 'loss': 'lose', 'draw': 'draw'}.get(result.get('outcome'), 'draw')) \
                if result.get('outcome') else {'desync': tr(p, 'desync'), 'peer_left': tr(p, 'peer_left'),
                                              'disconnected': tr(p, 'disconnected')}.get(result.get('end'), str(result.get('end')))
            if result.get('end') in ('peer_surrender', 'surrender'):
                label += '（' + tr(p, result['end'] if result['end'] == 'peer_surrender' else 'you_surrender').rstrip('。.') + '）'
            c.text((x + w / 2, y + 362), tr(p, 'last_result', label), 18, GOLD, 'mm', 2, w - 40)
        ready_label = tr(p, 'rematch') if room.match is not None and room.match.state == 'result' else tr(p, 'ready')
        if room.local_ready:
            c.draw.rectangle((x + w / 2 - 300, y + h - 76, x + w / 2 - 20, y + h - 24), fill=(40, 60, 40, 200))
            c.text((x + w / 2 - 160, y + h - 50), tr(p, 'wait_peer'), 18, WHITE, 'mm', 2, 270)
        else:
            c.button((x + w / 2 - 300, y + h - 76, 280, 52), ready_label, 'ready', 20, 'on')
        c.button((x + w / 2 + 20, y + h - 76, 280, 52), tr(p, 'leave'), 'leave_room', 20, 'off')

    def render_deck(self, c, x, y):
        import netplay_profile
        deck = getattr(self, 'deck_cache', None)
        if deck is None or self.p.frame - getattr(self, 'deck_cache_frame', 0) > 60:
            self.deck_cache = deck = netplay_profile.current_deck(self.p)
            self.deck_cache_frame = self.p.frame
        lab = self.lab
        for slot, entry in enumerate(deck):
            if entry is None:
                continue
            uid = lab.community_uid(entry[0]) if isinstance(entry[0], str) else entry[0]
            icon = self.skin.icon(uid, 0.9) if uid is not None else None
            if icon is not None:
                c.paste(icon, (x + slot * 46, y))

    def close(self, reason):
        self.p.log('NETPLAY_LOBBY_CLOSE', reason)
        self.stop_scan()
        if self.room is not None:
            self.room.close()
        self.room = None
        self.window = None
        self.write_menu(False)
        self.state = 'closed'

    def shutdown(self):
        self.close('shutdown')
        for overlay in (self.overlay, self.press_overlay, self.hud_overlay):
            if overlay is not None:
                overlay.close()
        self.overlay = self.press_overlay = self.hud_overlay = None


def self_protocol():
    import netplay_net
    return netplay_net.PROTOCOL
