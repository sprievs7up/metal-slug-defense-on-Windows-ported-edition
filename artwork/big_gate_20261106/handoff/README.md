# 大门头像构图素材（2026-11-06，第 335 节 R6）

供用户制作大门的头像。修筑者 `s1xlv.big_gate_builder`（UnitID 1099）与大门本体 `s1xlv.big_gate`（1100，内部单位）共用同一头像。由 `../make_icon_handoff.py` 导出，全部为 1:1 像素（头像与选单位格在游戏中按同一倍率绘制），4 倍、8 倍图为最近邻放大的预览。

## 预留的头像格

- 位置：`community_content/unit_icon_02.obm` (692, 770)，40 × 40，锚点 [−5, −5]，即选单位格的内框（格内 x、y 5–44）。
- 现用：用户构图 `unit_cell_player_green_50x50 拷贝.png`（R7，2026-11-06）；R6 时为 Metal Slug Attack 头像图集 `unit_icon_02.obme` 中大门（pict 468）的原格（占位，`../source/msa_icon_big_gate_604_758.png`）。

## 替换方法

1. 在 `unit_cell_player_green_50x50.png`（原生我方绿格）上画好头像，另存为本目录 `unit_cell_player_green_50x50 拷贝.png`（50 × 50；文件名为生成脚本的 `USER_ICON`）。
2. 运行 `E:\anaconda3\python.exe -I artwork/big_gate_20261106/build_big_gate.py`：取格内 x、y 5–44 中与绿格不同的像素写入预留格，其余透明（同机动兵、虫穴、Fall Climber 头像的做法）。
3. 该文件不存在时，生成脚本保留现用的占位头像。构图需要越出内框时，预留格须相应加大（钢铁哨兵的头像向上越出 6 像素，见参照图）。

## 文件

| 文件 | 内容 |
| --- | --- |
| `big_gate_rest_182x192.png` | 建成后的大门静止画面（透明底，两爪、漩涡、环体），素材像素 1:1 |
| `big_gate_rest_2x_ground.png` | 同上，深色底 2 倍预览；红线为地面（两爪底边） |
| `big_gate_icon_current_40x40.png`、`..._8x.png` | 现用头像（R7 起为用户构图） |
| `big_gate_icon_current_in_player_green_cell_50x50.png`、`..._8x.png` | 现用头像放在我方绿格中的样子；8 倍图的白框为格子外沿、黄框为内框 |
| `big_gate_icon_current_in_enemy_red_cell_50x50.png`、`..._8x.png` | 同上，敌方红格 |
| `unit_cell_player_green_50x50.png`、`unit_cell_enemy_red_50x50.png`、`unit_cell_empty_50x50.png` | 原生选单位格（`unit.obm` (362,151)、(428,125)、(439,188)） |
| `ref_icon_iron_sentinel_in_cell_4x.png`、`ref_icon_iron_death_worm_in_cell_4x.png`、`ref_icon_fall_climber_in_cell_4x.png` | 大型单位头像参照 |
| `ref_icon_native_133_in_cell_4x.png`、`..._162_...`、`..._2_...` | 原版头像构图参照：特種兵（機動）133、沖天火箭彈兵 162、普通兵 2 |

- 大门整体宽约 182，放进 40 × 40 内框需缩小到约 1/4.5。
