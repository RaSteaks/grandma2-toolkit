# grandma2-toolkit

通过 Telnet 查询和编程 grandMA2 onPC，并在 MA3D 中调整灯位、相机和检查画面。

| 入口 | 用途 | 安装方式 |
|---|---|---|
| MCP 服务 | 为客户端提供 8 个工具，可读取 Show、执行编程命令、导出 XML、备份和截图 | 从 npm 启动，见[快速开始](#快速开始) |
| `ma2-control` Skill | 指导 Agent 选择工具、组织配接和编组命令，并用回读或截图核对结果 | 在使用它的项目中安装，见 [Skill](#skill) |
| CLI | 在终端或脚本中调用同一套操作，读取 JSON 结果 | 从源码安装，见 [CLI](#cli) |

## 快速开始

准备 Node.js（含 npx）和 [uv](https://docs.astral.sh/uv/)，在任意目录运行：

```sh
npx @rasteaks/grandma2-toolkit
```

首次运行时确认 npx 的安装提示，uv 会按包内的 `uv.lock` 准备 Python 环境。服务启动后通过标准输入输出（stdio）等待 MCP 请求。

使用 Codex CLI 时，运行一次以下命令注册服务。之后 Codex 会按需启动 MCP：

```sh
codex mcp add grandma2-toolkit -- npx --yes @rasteaks/grandma2-toolkit
```

使用支持 `mcpServers` 的客户端时，将以下配置加入客户端。后台启动使用 `--yes` 自动确认安装。

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

确保客户端能从 `PATH` 找到 npx 和 uv。启动后可直接列出工具。要连接控台，请启用 onPC 或 MA3D 的 Telnet，并通过客户端的服务进程环境提供 `MA2_PASSWORD`。默认只读，连接地址为 `127.0.0.1`，候选端口为 `30000`、`30001`。远程控台用 `MA2_HOST` 指定地址。调用 `ma2_connections`，查看 `endpoints.onpc.connected` 和 `endpoints.onpc.show` 确认编程端和当前 Show。

## 使用方式

### MCP

客户端可直接使用 [npx 配置示例](examples/mcp.npx.json)。npx 入口默认将审计记录、导出和备份保存在用户主目录的 `.grandma2-toolkit/.data`，可通过 `MA2_OUTPUT_DIR` 指定其他目录。

从源码运行 MCP 时，可在仓库根目录执行 `uv run --locked grandma2-mcp`。使用 [uv 配置示例](examples/mcp.json) 时，将 `<REPO_DIR>` 换成本机仓库的绝对路径，`<OUTPUT_DIR>` 换成保存审计记录、备份和截图的绝对路径。删除 `MA2_OUTPUT_DIR` 配置项即可使用默认目录。

<details>
<summary>查看 8 个 MCP 工具</summary>

| 工具 | 功能 |
|---|---|
| `ma2_connections` | 同时连接 onPC 与 MA3D |
| `ma2_status` | 读取 Show、运行时和网络状态 |
| `ma2_list` | 查询灯型、灯层子项、Cue 范围、MAtricks 和指定屏幕的 ViewButton 等对象 |
| `ma2_execute` | 批量执行命令，遇错停止 |
| `ma2_export` | 导出原生 XML 并计算内容指纹 |
| `ma2_backup` | 保存、备份 Show 并计算 SHA256 |
| `ma3d_transform` | 调整灯具安装位置、朝向或相机 |
| `ma3d_capture` | 保存 MA3D 窗口截图并返回图片 |

</details>

在 MCP 客户端调用 `ma2_list` 时，`object` 只填写对象表达式。以下参数查询第二屏视图按钮的实际绑定，返回的 `reply` 保留控台原文：

```json
{"target": "onpc", "object": "ViewButton 2.1 Thru 2.10 /screen=2"}
```

### Skill

在希望使用 Skill 的**目标项目根目录**运行：

```sh
npx --yes skills add RaSteaks/grandma2-toolkit --skill ma2-control --agent codex -y
```

安装后可在项目的 `.agents/skills/ma2-control/SKILL.md` 查看入口。在 Codex 中用 `$ma2-control` 调用它。要实际查询或操作控台，先按快速开始配置 MCP；使用本地 CLI 时，也可以将 `MA2_TOOLKIT_ROOT` 指向已克隆的工具包根目录。在本仓库工作时可直接使用[随仓库提供的 Skill](.agents/skills/ma2-control/SKILL.md)。

> 使用 $ma2-control，只读检查当前 Show 第二页的执行器，列出每根推杆绑定的 Sequence 和前五条 Cue 的触发方式。

> 使用 $ma2-control，保留 Page 3 编程，先备份，再调整指定地面灯的安装方向并截图验收。

### CLI

CLI 示例使用仓库源码。在仓库根目录安装依赖，并给当前 PowerShell 会话设置 Telnet 凭据：

```powershell
uv sync --locked
$credential = Get-Credential -Message 'MA2 Telnet 登录'
$env:MA2_USER = $credential.UserName
$env:MA2_PASSWORD = $credential.GetNetworkCredential().Password
uv run grandma2 connections
```

```powershell
# 查看当前 Show 已提交的灯型节点和 MAtricks 池位
uv run grandma2 list 'LiveSetup.FixtureTypes'
uv run grandma2 list 'MAtricks 1 Thru 10'

# 查看 MA3D 相机，在本机导出效果或截图
uv run grandma2 --target ma3d list 'Camera 50'
uv run grandma2 export 'Effect 1 Thru 10'
uv run grandma2 capture --window-title 'MA 3D'

# 开启写入；将 Show 名称和对象编号替换为现场实际值
$env:MA2_ALLOW_WRITE = '1'
uv run grandma2 backup --expect-show '<SHOW_NAME>'
uv run grandma2 --target ma3d transform 'Camera 50' --expect-show '<SHOW_NAME>' --values '{"z":12.8,"rx":-2}'
uv run grandma2 execute --expect-show '<SHOW_NAME>' --commands-file examples/commands.readback.json
```

`--target` 放在子命令前，默认 `onpc`。位置单位为米、旋转为度、相机 FOV 为弧度。

进入 `EditSetup` 修改配接时，把依赖当前目录的命令放在同一次 `execute` 调用中。每次调用都会建立新连接。提交后从 `LiveSetup` 回读灯号、灯型和实例地址。配接、像素编组与推杆绑定的完整示例见 [Telnet 操作速查](.agents/skills/ma2-control/references/telnet-workflows.md)。相机、安装角和播放示例见 [场景与播放命令](.agents/skills/ma2-control/references/commands.md)。

在 onPC 本机导出对象时，工具按对象类型到 `effects`、`matricks` 或 `macros` 等原生目录读取 XML。`native_file` 指向原生文件，`file` 指向本次操作留存的副本，`fingerprint` 可用于比较两次导出的对象内容。

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
| `MA2_OUTPUT_DIR` | 源码启动为仓库 `.data`；npx 启动为用户主目录下的 `.grandma2-toolkit/.data` | 日志、备份、导出和截图目录；安装 wheel 后建议显式设置 |

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

修改 npx 入口后运行 `uv run pytest tests/npx_smoke.py`，通过本地 npm 压缩包验证安装、stdio 握手和工具发现。

### 发布到 npm

首次启用时，在 npm 包设置的 **Trusted Publisher** 中选择 **GitHub Actions**。GitHub 用户填 `RaSteaks`，仓库填 `grandma2-toolkit`，工作流文件名填 `publish-npm.yml`，Environment 留空，并允许直接执行 `npm publish`。发布任务通过 OIDC 获取短期凭据。[npm 配置说明](https://docs.npmjs.com/trusted-publishers/)

1. 更新 `package.json` 和 `pyproject.toml` 的版本，运行 `uv lock`，将版本改动推送到 GitHub。
2. 在该提交上发布正式 GitHub Release。标签使用 `v<版本号>`，例如版本 `0.1.1` 对应 `v0.1.1`。预发布版本会跳过发布流程。
3. 在 **Actions → Publish to npm** 查看结果。[发布工作流](.github/workflows/publish-npm.yml) 会先核对标签，运行 Ruff、Python 测试和 npx 安装测试，通过后才将该版本公开发布为 `latest`。可用 `npm view @rasteaks/grandma2-toolkit@latest version` 核对结果。

---
此仓库为个人开发，非官方malighting skill
[AGPL-3.0](LICENSE) 
