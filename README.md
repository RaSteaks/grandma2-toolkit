# grandma2-toolkit

通过 Telnet 读取 grandMA2 onPC 的 Show、编排 Cue 和执行器，并在 MA3D 中调整灯位和相机。**MCP** 让 Agent 调用控台工具，**ma2-control Skill** 告诉 Agent 如何选灯、组织命令并核对回读结果，**CLI** 适合在终端或脚本中取得相同的 JSON 结果。

[快速安装](#快速开始) · [第一次只读查询](#第一次只读查询) · [MCP 工具](#mcp) · [CLI](#cli) · [配置](#配置) · [npm 包](https://www.npmjs.com/package/@rasteaks/grandma2-toolkit)

## 快速开始

**想让 Agent 帮你安装？** 在目标项目目录打开 Codex 或 Claude Code，展开对应提示词，复制整段发送。两种方式都需要 Node.js（含 npx）和 [uv](https://docs.astral.sh/uv/)。安装和发现工具时无需控台密码。

<details>
<summary><strong>Codex</strong> · 复制安装提示词</summary>

```text
请在当前项目中安装 ma2-control Skill，并为 Codex 注册 grandma2-toolkit MCP。
先检查 node、npx、uv 和 codex 是否可用，缺少哪一项就指出来。已有相同配置时复用。

1. 在项目根目录执行：
   npx --yes skills add RaSteaks/grandma2-toolkit --skill ma2-control --agent codex -y
2. 注册 MCP 到 Codex 用户配置：
   codex mcp add grandma2-toolkit -- npx --yes @rasteaks/grandma2-toolkit
3. 检查 .agents/skills/ma2-control/SKILL.md，再运行 codex mcp get grandma2-toolkit。
   确认启动命令和参数正确。若当前会话已加载服务，列出它提供的工具。
   若需打开新会话才能发现工具，请明确说明。

本次只安装和验证。保持默认只读，跳过控台登录和 Show 操作。
```

</details>

<details>
<summary><strong>Claude Code</strong> · 复制安装提示词</summary>

```text
请在当前项目中安装 ma2-control Skill，并为 Claude Code 注册 grandma2-toolkit MCP。
先检查 node、npx、uv 和 claude 是否可用，缺少哪一项就指出来。已有相同配置时复用。

1. 在项目根目录执行：
   npx --yes skills add RaSteaks/grandma2-toolkit --skill ma2-control --agent claude-code -y
2. 以 local 作用域注册 stdio 服务，仅供我在当前项目使用：
   claude mcp add --transport stdio --scope local grandma2-toolkit -- npx --yes @rasteaks/grandma2-toolkit
3. 检查 .claude/skills/ma2-control/SKILL.md，再运行 claude mcp get grandma2-toolkit。
   核对服务状态。若当前会话已加载服务，列出它提供的工具。
   若需打开新会话才能发现工具，请明确说明。

本次只安装和验证。保持默认只读，跳过控台登录和 Show 操作。
```

Claude Code 的 `local` 配置只对当前用户的当前项目生效。[Claude Code MCP 作用域说明](https://code.claude.com/docs/en/mcp#mcp-installation-scopes)

</details>

**只需启动 MCP？** 在任意目录运行以下命令。首次确认安装后，uv 会按包内的 `uv.lock` 准备 Python 环境，服务随后通过标准输入输出（stdio）等待客户端请求。

```sh
npx @rasteaks/grandma2-toolkit
```

<details>
<summary>其他 MCP 客户端 · JSON 配置与源码启动</summary>

支持 `mcpServers` 的客户端可直接使用以下配置。确保客户端的 `PATH` 能找到 npx 和 uv。

```json
{
  "mcpServers": {
    "grandma2-toolkit": {
      "command": "npx",
      "args": ["--yes", "@rasteaks/grandma2-toolkit"]
    }
  }
}
```

从源码启动时，在仓库根目录执行 `uv run --locked grandma2-mcp`。使用 uv 配置模板时，将 `<REPO_DIR>` 换成仓库绝对路径，`<OUTPUT_DIR>` 换成保存备份和截图的绝对路径。省略 `MA2_OUTPUT_DIR` 即使用默认目录。[npx 配置](examples/mcp.npx.json) · [uv 配置](examples/mcp.json)

</details>

## 第一次只读查询

1. **连接控台。** 在 onPC 或 MA3D 启用 Telnet，通过 MCP 服务进程的环境变量提供 `MA2_PASSWORD`。控台位于另一台机器时，设置 `MA2_HOST` 为其地址。Telnet 使用明文传输，请在受信任的控制网络内使用。
2. **确认 Show。** 调用 `ma2_connections`。当 `endpoints.onpc.connected` 为 `true` 时，从 `endpoints.onpc.show` 读取当前 Show 名称。工具会根据运行时路径识别 onPC 与 MA3D。要确认共享会话，还需检查两端的网络状态。
3. **查看一个对象。** 例如，调用 `ma2_list` 查询第二屏的视图按钮。只传对象表达式，工具会补上 `List`，并在 `reply` 中返回控台原文。

```json
{"target": "onpc", "object": "ViewButton 2.1 Thru 2.10 /screen=2"}
```

### Skill

安装 Skill 后，可以直接在对话中描述要核对的灯光对象。例如：

> 使用 ma2-control，只读检查当前 Show 的第二页执行器。列出每根推杆绑定的 Sequence，以及该序列前五条 Cue 的触发方式。

Skill 优先使用已配置的 MCP。走本地 CLI 时，可将 `MA2_TOOLKIT_ROOT` 指向工具包源码根目录。[Skill 入口](.agents/skills/ma2-control/SKILL.md) · [配接、编组与推杆速查](.agents/skills/ma2-control/references/telnet-workflows.md) · [场景与播放命令](.agents/skills/ma2-control/references/commands.md)

## MCP

| 工具 | 用途 | 可核对的结果 |
| --- | --- | --- |
| `ma2_connections` | 同时探测 onPC 与 MA3D | 各端的连接状态、运行时和 Show |
| `ma2_status` | 检查指定端点 | 当前 Show 和网络状态 |
| `ma2_list` | 读取灯型、Cue 范围、MAtricks 或 ViewButton | 原生 `List` 回显 |
| `ma2_execute` | 在指定 Show 中顺序执行命令 | 每条命令的回显和审计记录 |
| `ma2_export` | 在本机导出原生 XML | 原生路径 `native_file`、留存副本 `file` 和内容指纹 `fingerprint` |
| `ma2_backup` | 在本机保存并备份 onPC Show | 新备份文件和 SHA256 |
| `ma3d_transform` | 调整灯具安装位置、朝向或相机 | 修改前后的对象回读 |
| `ma3d_capture` | 截取 Windows 本机可见的 MA3D 窗口 | PNG 截图，供核对机位和灯光画面 |

**写入与回读。** 写入前设置 `MA2_ALLOW_WRITE=1`，并传入与当前 Show 完全匹配的 `expected_show`。批次遇错即停，此前的命令可能已经生效。超时后先回读对象。依赖 `EditSetup` 当前目录的命令应放在同一批次，因为每次工具调用都会新建连接。

**安装角与灯光画面。** `ma3d_transform` 操作机身或相机。Cue 中的灯头方向由 Pan/Tilt 控制。共享会话中的几何变更可能同步至 onPC。截图需要可见且未最小化的 MA3D 窗口，请结合截图中的机位、播放状态和实际光束判断效果。

## CLI

在仓库根目录安装依赖，并在当前 PowerShell 会话中输入 Telnet 凭据。CLI 默认操作 onPC，返回 JSON。

```powershell
uv sync --locked
$credential = Get-Credential -Message 'MA2 Telnet 登录'
$env:MA2_USER = $credential.UserName
$env:MA2_PASSWORD = $credential.GetNetworkCredential().Password
uv run grandma2 connections
```

```powershell
uv run grandma2 list 'LiveSetup.FixtureTypes'
uv run grandma2 list 'MAtricks 1 Thru 10'
uv run grandma2 --target ma3d list 'Camera 50'
```

<details>
<summary>导出效果、备份 Show 和调整相机</summary>

将 Show 名称、相机编号和坐标换成现场已核对的值。`--target` 放在子命令前。位置单位为米，旋转为度，相机 FOV 为弧度。

```powershell
uv run grandma2 export 'Effect 1 Thru 10'
uv run grandma2 capture --window-title 'MA 3D'

$env:MA2_ALLOW_WRITE = '1'
uv run grandma2 backup --expect-show '<SHOW_NAME>'
uv run grandma2 --target ma3d transform 'Camera 50' --expect-show '<SHOW_NAME>' --values '{"z":12.8,"rx":-2}'
uv run grandma2 execute --expect-show '<SHOW_NAME>' --commands-file examples/commands.readback.json
```

</details>

## 配置

环境变量需传给实际运行 MCP 或 CLI 的进程。桌面客户端可能使用独立于终端的环境。

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `MA2_HOST` | `127.0.0.1` | 控台或可视化主机地址 |
| `MA2_PORTS` | `30000,30001` | 探测的 Telnet 端口 |
| `MA2_USER` | `administrator` | Telnet 登录用户 |
| `MA2_PASSWORD` | 无 | 连接设备时必填 |
| `MA2_ALLOW_WRITE` | `0` | 设为 `1` 后，允许对匹配的 Show 执行写入命令，包括 Lua |
| `MA2_TIMEOUT` | `15` | 响应超时秒数，可设为 1–120 |
| `MA2_OUTPUT_DIR` | 依启动方式而定 | 审计日志、备份、XML 和截图的保存目录 |

npx 默认保存到用户主目录的 `.grandma2-toolkit/.data`，源码默认保存到仓库的 `.data`。使用 wheel 安装时建议显式设置输出目录。

## 开发

```sh
uv sync --locked --group dev
uv run ruff check .
uv run pytest
uv run pytest tests/npx_smoke.py
uv build
```



---

本项目由个人独立开发，是面向 MA Lighting 产品的非官方工具。
许可证为 [AGPL-3.0](LICENSE)。
