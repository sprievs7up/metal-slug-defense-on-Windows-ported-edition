# 机动兵头像构图素材（2026-10-31）

供用户修改机动兵（`s1xlv.rebel_bomb_bike`，UnitID 1088）的头像。由 `../make_icon_handoff.py` 导出，全部为 1:1 像素（头像与选单位格在游戏中按同一倍率绘制），8 倍、4 倍图为最近邻放大的预览。

| 文件 | 内容 |
| --- | --- |
| `rebel_bomb_bike_icon_current_46x43.png` | 现用头像（透明底，46×43；平骑帧水平翻转为朝右，底边对齐），`unit_icon_02.obm` (502,770) |
| `rebel_bomb_bike_icon_current_8x.png` | 同上，深色底 8 倍预览 |
| `rebel_bomb_bike_icon_current_in_player_green_cell_50x50.png`、`..._8x.png` | 现用头像放在我方绿格中的样子（左上角在格内 (5,2)）；8 倍图的白框为格子外沿、黄框为内框，四边各多画 8 像素以显示越出格子的部分 |
| `rebel_bomb_bike_icon_current_in_enemy_red_cell_50x50.png`、`..._8x.png` | 同上，敌方红格 |
| `unit_cell_player_green_50x50.png` | 原生选单位格（我方绿格，`unit.obm` (362,151)） |
| `unit_cell_enemy_red_50x50.png` | 原生选单位格（敌方红格，`unit.obm` (428,125)） |
| `unit_cell_empty_50x50.png` | 原生空格（`unit.obm` (439,188)） |
| `ref_icon_native_133_in_cell_4x.png` | 原版头像构图参照：特種兵（機動）133（46×41，格内 (5,4)） |
| `ref_icon_native_162_in_cell_4x.png` | 沖天火箭彈兵 162（39×37，格内 (5,8)） |
| `ref_icon_native_2_in_cell_4x.png` | 普通兵 2（42×39，格内 (2,6)） |

## 格子与头像的坐标

- 选单位格 50×50，四边各 5 像素为边框，内框为格内 x、y 5–44（40×40）。原版头像的下沿多止于内框底行（第 44 行）。
- 头像在格内的位置由锚点决定：锚点取负值即头像左上角在格内的坐标（现用 [−5, −2] 为 (5,2)）。头像可以越出内框。
- 现用头像的不透明范围在格内为 x 5–50、y 4–44：车头与前轮压在右侧边框上，最右 1 列越出格子。

把构图结果给我即可（例如画好的 50×50 格子图，或头像图加上它在格内的左上角坐标），我写入 `unit_icon_02.obm` 并更新头像设定。
