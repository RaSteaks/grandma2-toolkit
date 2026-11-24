# 项目方案

grandma2-toolkit 在同一个 Python 包中提供 Telnet 客户端、JSON CLI 与 stdio MCP。
Skill 位于 .agents/skills/ma2-control，调用同一 CLI/MCP，不复制连接逻辑。
npx 入口随包分发 Python 源码和 uv.lock，由 uv 启动同一个 stdio MCP 服务。
保留仓库原有 AGPL-3.0 许可证。全部源文件、文档、示例、测试及本地构建产物保留在本仓库。
README 面向首次使用者，按快速开始、MCP / Skill / CLI、配置和必要限制组织；详细命令留在 Skill 引用文档中。

## 运行约束

- onPC 和 MA3D 都可连接，使用 PATH 识别身份，绝不按端口号猜测。connections 会同时持有两个连接。
- onPC 负责编程；MA3D 默认用于场景安装变换、相机与截图验收。共享会话中的几何修改可能回传 onPC。
- 写入要求 MA2_ALLOW_WRITE=1、expected_show 与每条命令执行前的 SHOWFILE 一致；这不是用户授权或事务回滚机制。
- 通用 execute 可执行有副作用的命令和 Lua，不用于只读查询；只读 list 使用严格对象语法。
- list 支持子节点、Cue 与分屏 ViewButton 查询。需要 EditSetup 上下文的相对命令在同一 execute 批次发送，提交后从 LiveSetup 回读。
- 本机 XML 导出按对象类型定位文件，Effect、MAtricks、Macro 分别使用 effects、matricks、macros。
- 每条命令使用独立 Lua completion marker，超时后不自动重发；文件保存/导出额外等待异步完成。
- 密码只从进程环境读取；不提交 .env、Show、原生 XML 或截图。审计写入 .data，密码脱敏。
- Git 保留源码、Skill、配置示例及 uv.lock；忽略环境、缓存、构建产物和运行证据目录。不要全局忽略 XML/PNG/JSON，以免隐藏测试样本或文档资源。
- 不固定任何用户的 Page、Fixture、Camera、地址映射或场馆布局。先查询后修改。
- 截图保存不等于视觉验收；MA3D 灯具旋转不等于 Cue Pan/Tilt。

## 开发验证

`uv sync --group dev`；`uv run pytest`；`uv run ruff check .`。
测试使用本地模拟 Telnet 与真实 MCP stdio 握手，不自动连接或写入灯光 Show。
需要现场只读验证时设置凭据后运行 `uv run grandma2 connections` 和 `list`。
写入/截图实机测试必须在用户授权范围内进行，不把模拟测试写成实机效果验收。
编辑代码后同步注释、相关使用说明和测试。不要发布、提交或推送，除非用户另行要求。
