# grandma2-toolkit

通过 **MCP、CLI 和 Agent Skill** 控制 grandMA2 onPC 与 MA3D。

- **双端连接**：自动识别 onPC / MA3D，查询 Show、灯具和播放对象。
- **场景与编程**：执行命令，调整灯具位置、安装方向和相机。
- **备份与验收**：导出 XML、备份 Show、保存 MA3D 截图和操作记录。

## 快速开始

准备 **Python 3.11+、[uv](https://docs.astral.sh/uv/)**，启动 onPC / MA3D 并启用 Telnet。在仓库目录运行：

```powershell
uv sync --locked

$credential = Get-Credential -UserName administrator -Message 'MA2 Telnet 登录'
$env:MA2_USER = $credential.UserName
$env:MA2_PASSWORD = $credential.GetNetworkCredential().Password

uv run grandma2 connections
```

默认连接 `127.0.0.1`，探测 `30000 / 30001`，按运行时身份区分两端。**默认只读。**

## 使用方式

### MCP

将 [examples/mcp.json](examples/mcp.json) 中的配置加入 MCP 客户端，修改仓库路径，并为服务进程提供 `MA2_PASSWORD`。也可使用以下启动命令：

```powershell
uv run --locked --directory G:/GitHub/grandma2-toolkit grandma2-mcp
```

<details>
<summary>查看 8 个 MCP 工具</summary>

| 工具 | 功能 |
|---|---|
| `ma2_connections` | 同时连接 onPC 与 MA3D |
| `ma2_status` | 读取 Show、运行时和网络状态 |
| `ma2_list` | 查询对象及编号范围 |
| `ma2_execute` | 批量执行命令，遇错停止 |
| `ma2_export` | 导出原生 XML 并计算内容指纹 |
| `ma2_backup` | 保存、备份 Show 并计算 SHA256 |
| `ma3d_transform` | 调整灯具安装位置、朝向或相机 |
| `ma3d_capture` | 保存 MA3D 窗口截图并返回图片 |

</details>

### Skill

入口：[ma2-control / SKILL.md](.agents/skills/ma2-control/SKILL.md)。支持项目 Skill 的客户端可直接发现，也可让 Agent 读取该文件。

> 使用 $ma2-control 同时连接 onPC 和 MA3D，只读检查当前 Show 与 Page 3。

> 使用 $ma2-control，保留 Page 3 编程，先备份，再调整指定地面灯的安装方向并截图验收。

### CLI

```powershell
# 查询、导出与截图
uv run grandma2 list 'Executor 3.1 Thru 3.8'
uv run grandma2 --target ma3d list 'Camera 50'
uv run grandma2 export 'Page 3'
uv run grandma2 capture --window-title 'MA 3D'

# 开启写入；将 Show 名称和对象编号替换为现场实际值
$env:MA2_ALLOW_WRITE = '1'
uv run grandma2 backup --expect-show codex
uv run grandma2 --target ma3d transform 'Camera 50' --expect-show codex --values '{"z":12.8,"rx":-2}'
uv run grandma2 execute --expect-show codex --commands-file examples/commands.readback.json
```

`--target` 放在子命令前，默认 `onpc`。位置单位为米、旋转为度、相机 FOV 为弧度。
更多命令见 [命令参考](.agents/skills/ma2-control/references/commands.md)。

## 配置

通过进程环境变量配置，无内置密码。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MA2_HOST` | `127.0.0.1` | 目标主机 |
| `MA2_PORTS` | `30000,30001` | 候选 Telnet 端口 |
| `MA2_USER` | `administrator` | 登录用户 |
| `MA2_PASSWORD` | — | 必填 |
| `MA2_ALLOW_WRITE` | `0` | 设为 `1` 启用写入 |
| `MA2_TIMEOUT` | `15` | 响应超时，单位秒 |
| `MA2_OUTPUT_DIR` | 仓库 `.data` | 日志、备份、导出和截图目录；安装 wheel 后建议显式设置 |

MCP 客户端不一定继承终端环境变量，请确认密码已传给服务进程。

## 使用须知

- **写入需匹配 Show**：开启写入后仍需提供 `expected_show`。批次失败不会回滚，超时后应先查询状态再决定是否重试。
- **区分场景与编程**：安装朝向不是 Cue 的 Pan/Tilt；MA3D 场景修改可能同步到 onPC。两端同名 Show 不代表已加入同一会话。
- **本机能力**：文件导出、备份仅支持本机运行时；截图需要 Windows 上可见、未最小化的 MA3D 窗口，效果仍需查看图片确认。
- **控制网络**：Telnet 明文传输，仅用于受信任网络。通用命令接口可执行 Lua、删除等操作，写入开关不是权限沙箱。

## 开发

```powershell
uv sync --locked --group dev
uv run pytest
uv run ruff check .
uv build
```

测试使用模拟 Telnet 与 MCP 子进程，不修改真实 Show。

---

[AGPL-3.0](LICENSE) · 非 MA Lighting 官方项目
