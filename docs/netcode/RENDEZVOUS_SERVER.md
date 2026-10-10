# 联机会合服务器部署说明（社区自建，N4）

依据：`docs/netcode/ROLLBACK_NETCODE_TASK_2026-10-09.md` 第 7 节 R3、R4。实现：游戏目录中的 `rendezvous_server.py`（单个文件，只用 Python 标准库）。

## 1. 它做什么，不做什么

- 只在**建立连接时**帮助两名玩家交换地址：房主登记后得到 6 位房间码，加入方用房间码取得房主的公网地址与内网地址，服务器同时把加入方的地址告诉房主；
  之后双方互相发送打洞包，直接连通（UDP 打洞）。
- **不转发任何对战数据**，不提供中继。双方网络都无法打洞（例如都处于对称型 NAT 或运营商级 NAT 之后）时，游戏提示无法连接。
- 不保存任何数据：房间只存在于内存，房主 60 秒没有保活即删除；服务器重启后全部清空。
- 日志只记录登记与加入事件的房间码和来源 IP:端口（运行所需），以及周期统计。

## 2. 运行

需要 Python 3.8 及以上（Windows 可直接用游戏目录里的 `windows_runtime\python.exe`），以及一个对外开放的 **UDP** 端口（默认 47632）。

```bash
python3 rendezvous_server.py --host 0.0.0.0 --port 47632
```

Windows（游戏目录中）：

```bash
windows_runtime\python.exe rendezvous_server.py --host 0.0.0.0 --port 47632
```

或双击 `tools\netplay_check\rendezvous_server.bat`。

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--host` | 0.0.0.0 | 监听地址 |
| `--port` | 47632 | UDP 端口 |
| `--ttl` | 60 | 房主多少秒没有保活即删除房间（游戏每 15 秒保活一次） |
| `--max-rooms` | 5000 | 同时存在的房间上限 |
| `--stats-every` | 300 | 每隔多少秒在日志中输出统计（0 为不输出） |
| `--log` | 无（输出到控制台） | 日志文件 |

## 3. 网络设置

- 云服务器：在安全组 / 防火墙中放行入站 UDP 47632。
- 家用电脑：在路由器上把 UDP 47632 转发到运行服务器的电脑，并在 Windows 防火墙中允许 `python.exe`。
- 只支持 IPv4。
- 公布给玩家的地址写成 `IP或域名:端口`，例如 `msd.example.org:47632`。玩家在游戏中填写同一个地址（可保存多个），房主建房得到房间码，告诉对方即可。

Linux systemd 示例（`/etc/systemd/system/msd-rendezvous.service`）：

```ini
[Unit]
Description=MSD WINDOWS S1XLV rendezvous server
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/msd/rendezvous_server.py --host 0.0.0.0 --port 47632
Restart=always
User=nobody

[Install]
WantedBy=multi-user.target
```

## 4. 限制与防滥用

- 每个来源 IP 每分钟：登记 20 次、加入 120 次、其他请求 240 次；超出时回复 `rate_limited`。
- 单包不超过 1400 字节，格式不符的包直接忽略；内网地址最多 8 个、附带信息最多 512 字节。
- 房间码 6 位，取自 32 个不易混淆的字符（约 10.7 亿种），按密码学随机数生成。
- 服务器不验证游戏版本：版本、内容清单（模组、数值）在双方连通后由游戏自行比对，不一致即拒绝匹配并列出差异。

## 5. 协议（供其他实现参考）

UDP，每包为魔数 `MSDR` + 版本字节 `1` + UTF-8 JSON。详见 `rendezvous_server.py` 文件开头说明：
`register` → `registered{code, secret, public, ttl}`；`keepalive{code, secret}`；`unregister{code, secret}`；
`join{code, private}` → 加入方收到 `joined{host, public, punch}`，房主收到 `peer{peer, punch}`；`whoami` → `you{public}`；
错误为 `error{reason}`（`no_room`、`rate_limited`、`server_full`）。`punch` 为本次打洞令牌，双方的打洞包携带它。
