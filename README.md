# grandma2-toolkit

通过 Telnet 读取 grandMA2 onPC 的 Show、编排 Cue 和执行器，并在 MA3D 中调整灯位和相机。**MCP** 让 Agent 调用控台工具，**ma2-control Skill** 告诉 Agent 如何选灯、组织命令并核对回读结果，**CLI** 适合在终端或脚本中取得相同的 JSON 结果。

[快速安装](#快速开始) · [Telnet 与登录](#telnet-与登录) · [第一次只读查询](#第一次只读查询) · [Skill 功能](#skill) · [MCP 工具](#mcp) · [CLI](#cli) · [配置](#配置) · [npm 包](https://www.npmjs.com/package/@rasteaks/grandma2-toolkit)

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

## Telnet 与登录

以下菜单和端口以 **grandMA2 3.9** 官方手册为准。本工具识别的运行时为 grandMA2 onPC 和 MA3D。Telnet 会以明文传输登录信息，请在受信任的灯光控制网络内使用。

1. **在 onPC 开启命令登录。** 打开当前 Show，进入 **Setup → Console → Global Settings → Telnet**，选择 **Login Enabled**。记下 onPC 控制网卡的 IP。官方默认命令端口为 TCP `30000`，`30001` 用于只读 System Monitor。工具默认会探测两个候选端口，并在成功登录后用运行时路径识别应用。只连接标准 onPC 时可以设 `MA2_PORTS=30000`。[MA Lighting · Telnet Remote](https://help.malighting.com/grandMA2/en/help/key_remote_control_telnet.html)
2. **准备当前 Show 的用户。** 请有 Admin 权限的操作员在 **Setup → Console → User & Profiles Setup** 中选择或新建专用用户，设置密码、User Profile 和 Rights。用户名与密码均区分大小写。每个用户有自己的 Programmer，共用 Profile 的用户会共享视图及视图按钮。需要独立整理视图时，为自动化用户分配单独的 Profile。[MA Lighting · 用户与 Profile](https://help.malighting.com/grandMA2/en/help/key_single_multi_systems_create.html) · [Telnet 登录说明](https://help.malighting.com/grandMA2/en/help/key_remote_control_telnet.html)
3. **把凭据交给工具进程。** 同机连接用 `127.0.0.1`，跨机连接将 `MA2_HOST` 设为 onPC 的控制网 IP。在运行 MCP 或 CLI 的进程环境中设置 `MA2_USER` 和 `MA2_PASSWORD`。工具自动发送登录命令并核对登录回显。以下为 Windows PowerShell 的远程 onPC 示例，在提示框中输入 Show 用户名与密码：

```powershell
$env:MA2_HOST = '<ONPC_IP>'
$env:MA2_PORTS = '30000'
$env:MA2_ALLOW_WRITE = '0'
$credential = Get-Credential -Message '输入当前 grandMA2 Show 的用户名和密码'
$env:MA2_USER = $credential.UserName
$env:MA2_PASSWORD = $credential.GetNetworkCredential().Password
Test-NetConnection -ComputerName $env:MA2_HOST -Port 30000
```

将 `<ONPC_IP>` 换成现场地址。上述变量适用于从该终端启动的进程；使用桌面客户端时，请通过客户端的服务环境传入这些值。真实密码仅在本地输入，配置示例和聊天记录中使用占位符。

**登录时注意三点：**

- **确认登录结果。** `TcpTestSucceeded: True` 只确认端口可达。直接用 Telnet 客户端排查时，欢迎信息可能显示 Guest，请在该客户端输入原生命令 `Login "<SHOW_USER>" "<SHOW_PASSWORD>"`，收到 `Logged in as User '…'` 再继续。使用 MCP 或 CLI 时由工具自动登录。工具要求非空密码，用户名和密码中均不支持双引号、反斜杠、分号或控制字符。出现认证失败时，先核对 Show、账号大小写及服务进程收到的环境变量。[MA Lighting · Telnet Remote](https://help.malighting.com/grandMA2/en/help/key_remote_control_telnet.html)
- **按任务分配权限。** Playback 用户可以回放；Program 用户可以进行多数编程操作，配接仅限 Patch Only。用户 Profile 的 World 也会限制可见灯具和属性。`MA2_ALLOW_WRITE=1` 只开启工具侧写入，操作仍受控台用户权限约束。进入 Fixture Setup / Schedule 可能锁住其他操作员的编辑入口，修改前请协调。[MA Lighting · 用户权限](https://help.malighting.com/grandMA2/en/help/key_single_multi_systems_create.html) · [Fixture Setup 的 Telnet 限制](https://help.malighting.com/grandMA2/en/help/key_remote_control_telnet.html)
- **先用只读调用验收。** 在 MCP 调用 `ma2_status`，传入 `{"target":"onpc"}`；使用源码 CLI 时运行 `uv run grandma2 --target onpc status`。能读到预期的 `show`、`runtime`、`port` 和 `network_status`，才确认已登录正确的运行时。若 TCP 已连通但工具仍失败，再检查是否接到了监视端口，以及账号能否执行工具读取身份所用的 Lua 命令。

## 第一次只读查询

1. **确认 Show。** 调用 `ma2_connections`。当 `endpoints.onpc.connected` 为 `true` 时，从 `endpoints.onpc.show` 读取当前 Show 名称。工具会根据运行时路径识别 onPC 与 MA3D。要确认共享会话，还需检查两端的网络状态。
2. **查看一个对象。** 例如，调用 `ma2_list` 查询第二屏的视图按钮。只传对象表达式，工具会补上 `List`，并在 `reply` 中返回控台原文。

```json
{"target": "onpc", "object": "ViewButton 2.1 Thru 2.10 /screen=2"}
```

## Skill

`ma2-control` 将下列操作组织成工作流程。编程与原生对象导入使用已授权的 `ma2_execute`，需要导入的文件应已位于目标运行时对应的目录中。

| 工作流程 | 当前支持的操作 |
| --- | --- |
| 连接与范围确认 | 识别 onPC / MA3D，读取 Show 与会话状态，确认目标端、可修改的页和对象 |
| 灯库、配接与安装 | 区分灯库文件与当前 Show 灯型，按模式核对通道占用和实例，在 EditSetup 导入灯型或灯层，提交后从 LiveSetup 回读灯号、DMX 地址和安装变换 |
| 选灯与布局 | 按顺序选择整灯或像素子实例，保存 Group，关联 Layout，保存指定屏幕的 View、绑定并回读 ViewButton |
| 预设、效果与选区 | 查询或导入 Preset、Effect、MAtricks，处理镜像、连续分块、选区复位及通过 Macro 打乱选灯顺序 |
| Cue、执行器与回放 | 检查 Sequence、Cue 时序及分配关系，导入序列、绑定推杆、设置启停行为，按指定执行器预览 Cue、调整电平和停止回放 |
| 场景与相机 | 查询 Root 场景树，修改灯具安装位置和旋转，复制、命名、调整 Camera 的位置、旋转和视场，回读修改前后的参数 |
| 备份、比对与视觉验收 | 保存 Show 备份，导出对象 XML 并比较指纹，记录操作审计，采集并检查 MA3D 画面；动态效果可分时截图，对照机位、回放状态和光束变化 |

安装后可直接描述要核对的灯光对象。例如：

> 使用 ma2-control，只读检查当前 Show 的第二页执行器。列出每根推杆绑定的 Sequence，以及该序列前五条 Cue 的触发方式。

Skill 优先使用已配置的 MCP。走本地 CLI 时，可将 `MA2_TOOLKIT_ROOT` 指向工具包源码根目录。[Skill 入口](.agents/skills/ma2-control/SKILL.md) · [配接、编组与推杆速查](.agents/skills/ma2-control/references/telnet-workflows.md) · [场景与播放命令](.agents/skills/ma2-control/references/commands.md)

## MCP

| 工具 | 用途 | 可核对的结果 |
| --- | --- | --- |
| `ma2_connections` | 同时探测 onPC 与 MA3D | 各端的连接状态、运行时和 Show |
| `ma2_status` | 检查指定端点 | 当前 Show 和网络状态 |
| `ma2_list` | 读取灯型、Cue 范围、MAtricks 或 ViewButton | 原生 `List` 回显 |
| `ma2_execute` | 在指定 Show 中顺序执行原生命令或 Lua，每批最多 100 行，每行最多 480 个 UTF-8 字节 | 每条命令的回显和审计记录 |
| `ma2_export` | 在本机导出原生 XML | 原生路径 `native_file`、留存副本 `file` 和内容指纹 `fingerprint` |
| `ma2_backup` | 在本机保存并备份 onPC Show | 新备份文件和 SHA256 |
| `ma3d_transform` | 修改指定 Root 场景对象或 Camera 的 XYZ、三轴旋转，或相机 FOV | 修改前后的对象回读 |
| `ma3d_capture` | 截取 Windows 本机可见的 MA3D 窗口 | PNG 截图，供核对机位和灯光画面 |

**只读查询范围。** `ma2_list` 支持 Page、Executor、Sequence（含 Cue 范围）、Effect、Preset、Camera、Group、View、ViewButton、Layout、Fixture、Channel、Root、UserProfile、MAtricks、Macro、Screen、Layer 和 FixtureType，也可读取 `LiveSetup.FixtureTypes`、`LiveSetup.Layers` 和 `NetworkInfo`。可按编号、范围或子节点查询，ViewButton 支持指定屏幕。远程查询和编程使用 Telnet；`ma2_export` 和 `ma2_backup` 需要工具运行在端点本机，通过回环地址连接并读取原生文件。

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
