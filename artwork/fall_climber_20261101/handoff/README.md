# Fall Climber 头像构图素材（2026-11-01）

供用户制作 Fall Climber（`s1xlv.fall_climber`，UnitID 1091；第二形态 1092 为内部单位，共用同一头像）的头像。由 `../make_icon_handoff.py` 导出，全部为 1:1 像素（头像与选单位格在游戏中按同一倍率绘制），2 倍、4 倍、8 倍图为最近邻放大的预览。

## 机体素材（游戏中的静止姿势）

| 文件 | 内容 |
| --- | --- |
| `fall_climber_form1_rest_317x196.png` | 第一形态整机（透明底，317×196），部件与层次同游戏（核心 r115，第 313 节 R7）；原画朝左，左手为前方的手 |
| `fall_climber_form2_rest_319x183.png` | 第二形态整机（破损部件，头壳换为玻璃罩，机体比第一形态高 16） |
| `fall_climber_form1_rest_2x_walkline.png`、`fall_climber_form2_rest_2x_walkline.png` | 同上，深色底 2 倍预览；红线为行走线（两手底边所在行；第一形态为第 54 行、第二形态为第 55 行，单位原点在第 158 / 160 列） |
| `layers_form1/`、`layers_form2/` | 各层分开的图（文件名前的号码为绘制次序，由后到前：左手、左前臂、左肘护盖、左上臂、右侧同、髋、爪、机体、背枪、头壳 / 玻璃罩、引擎）；`layers.json` 为各层在整机图中的左上角与尺寸，可按需改摆姿势 |

- 不含引擎蒸汽（间歇动画）与攻击、绝招的效果。
- 原作素材：精灵表 `F:\egg\MS7\DS _ DSi - Metal Slug 7 - Enemies - Fall Climber.png`、整机图 `F:\egg\MS7\Fallmecha.webp`（用户提供）。
- 整机宽约 317，放进 40×40 内框需缩小到约 1/8（原版头像为 1:1 像素画，现用头像缩小后把透明度取整为全透明或全不透明）。

## 现用头像与格子

| 文件 | 内容 |
| --- | --- |
| `fall_climber_icon_current_40x36.png` | 现用头像（R9 起为用户构图 `unit_cell_player_green_50x50 fig.png` 中与绿格不同的像素，透明底 40×36），`unit_icon_02.obm` (550,770)，锚点 [−5, −9]；R3–R8 为代理制作的 45×41 |
| `fall_climber_icon_current_8x.png` | 同上，深色底 8 倍预览 |
| `fall_climber_icon_current_in_player_green_cell_50x50.png`、`..._8x.png` | 现用头像放在我方绿格中的样子（左上角在格内 (5,9)）；8 倍图的白框为格子外沿、黄框为内框，四边各多画 8 像素以显示越出格子的部分 |
| `fall_climber_icon_current_in_enemy_red_cell_50x50.png`、`..._8x.png` | 同上，敌方红格 |
| `unit_cell_player_green_50x50.png` | 原生选单位格（我方绿格，`unit.obm` (362,151)） |
| `unit_cell_enemy_red_50x50.png` | 原生选单位格（敌方红格，`unit.obm` (428,125)） |
| `unit_cell_empty_50x50.png` | 原生空格（`unit.obm` (439,188)） |
| `ref_icon_iron_sentinel_in_cell_4x.png` | 大型单位头像参照：钢铁哨兵 1062（46×46，格内 (5,−1)，向上越出内框） |
| `ref_icon_iron_death_worm_in_cell_4x.png` | 钢铁死亡蠕虫 1077（40×40，恰好填满内框） |
| `ref_icon_native_133_in_cell_4x.png`、`..._162_...`、`..._2_...` | 原版头像构图参照：特種兵（機動）133、沖天火箭彈兵 162、普通兵 2 |

## 格子与头像的坐标

- 选单位格 50×50，四边各 5 像素为边框，内框为格内 x、y 5–44（40×40）。原版头像的下沿多止于内框底行（第 44 行）。
- 头像在格内的位置由锚点决定：锚点取负值即头像左上角在格内的坐标。头像可以越出内框（例如钢铁哨兵向上越出 6 像素）。

用户构图已于 2026-11-01 写入（第 313 节 R9）；修改时替换 `unit_cell_player_green_50x50 fig.png` 后重新运行 `../build_fall_climber.py`。
