# grandMA2 Telnet 命令速查

命令示例来自 grandMA2 onPC 3.3.4.3 的操作回显。下列编号用于说明语法，文件名可替换。先在当前 Show 核对对象、目标池位和选灯范围。

## 登录与只读查询

工具从环境读取凭据并发送 `Login "<user>" "<password>"`。以 `Logged in as User '…'` 确认登录。`ma2_connections` 通过 `gma.show.getvar('PATH')` 识别 onPC / MA3D；`ma2_status` 返回 `SHOWFILE` 和 `gma.network.getstatus()` 的结果。Telnet 端口和 `[Fixture]>` 提示符本身不足以确定应用身份。

下列命令可在写入关闭时使用。传给 `ma2_list` 或 CLI `list` 时省略开头的 `List `。

| 要查看什么 | 原生命令示例 | 从回显中核对 |
|---|---|---|
| Show 的灯型与灯层 | `List LiveSetup.FixtureTypes`、`List LiveSetup.Layers` | 找到已提交的节点。再从已识别的 Root 地址列子项，如该 Show 的 `List Root 10.3.*` 和 `List Root 10.4.*` |
| 单灯配接与安装 | `List Root 10.4.2.1`、`List Root 10.6.3.3` | 按 FixId 匹配灯层记录与 3D 模型，分别读实例地址、机身 XYZ 和 Rot.X/Y/Z |
| Group 与 Layout | `List Group 1 Thru 10`、`List Layout 1` | 池位、名称；精确成员与选灯顺序用 Group XML 核对 |
| 第二屏 | `List Screen 2.*`、`List ViewButton 2.1 Thru 2.10 /screen=2` | 查屏幕上的控件、按钮实际绑定的 View 或 Macro |
| MAtricks 与 Macro | `List MAtricks 1 Thru 10`、`List Macro 9` | 核对空位和系统 Reset 所在格；配方字段见原生导出 |
| Preset 与 Effect | `List Preset 2.1 Thru 2.20`、`List Effect 1 Thru 10` | 按池类型和编号核对对象 |
| 执行器与 Cue | `List Executor 2.1 Thru 2.15`、`List Sequence 401 Cue 1 Thru 5` | 核对绑定的序列和 Cue 的编号、Trig、TrigTime。小数 Cue 也可查询 |

## 灯库、配接与 EditSetup

运行时 `PATH/library` 下的 `.xml`、`.xmlp` 是可导入的灯库。按厂商、型号、模式定位文件；同一型号可有不同 footprint 和实例数。历史盘点读取了库文件，其中有单文件包含多个 FixtureType 的情况。`List LiveSetup.FixtureTypes` 查询的是当前 Show 内的节点。两种查询回答不同的问题。

在获准修改配接时，使用 `ma2_execute`，目标为 `onpc`。上下文相关的命令要在同一批次执行，每次工具调用都会新建连接。以下是记录中的操作阶段，按现场对象选择需要的步骤。

| 阶段 | 原生命令示例 | 核对点 |
|---|---|---|
| 打开编辑树 | `ChangeDest EditSetup`，再 `List` | 确认提示符为 `EditSetup >`，取得 FixtureTypes、Layers 的实际子项编号 |
| 导入灯型 | `Import "glp@impression_x4_bar_20@single_pixel.xmlp" At FixtureType 3 /nc`，再 `List FixtureType 3` | 确认目标池位可用、导入数量、Mode、DMXFootprint 和 Instances |
| 导入灯层 | 在该例中 `ChangeDest 4` 进入 Layers，随后 `Import "stage_layer" At 2 /nc` | 文件须已在端点的 `fixture_layers` 内；目标数字相对于当前目录。通过 `List 2.*` 核对灯号和实例 |
| 提交与复核 | `ChangeDest / /nc`，再从 LiveSetup 的 Root 地址 `List` | 离开 EditSetup 会提交编辑；比较已提交的灯号、灯型、各实例 DMX 地址和安装变换，按任务要求保存 Show |

`/nc` 会跳过确认。导入的整层可能包含多台灯，核对目标和 XML 的覆盖范围后再执行。远程 Telnet 的文件名由端点解析；`ma2_export` 和 `ma2_backup` 需要可在本机读取的运行时目录。

## 选灯、分组与分屏视图

- **按顺序录组。** 从已清理、可用于编程的选区开始。例如 `Fixture 505.16 + 505.17 + 505.22 + 505.23`，然后 `Store Group 25 "Center Pixels" /nc`。Group 保存实例及先后顺序。需要从 Layout 点选像素时，Layout 里应当有对应的子实例。
- **核对主模块和像素。** X4 Bar 20 方案使用 Single pixel 模式，把整灯的 Tilt、Zoom 与逐像素的 DIM、颜色分开。登录记录中该模式回读为 88 通道、21 个实例。按当前模式核对主模块和像素的实际编号，再按物理顺序录组。六边形渐变的亮度、相位和角度是设计建议，现场验证需逐边试灯。
- **布局与召回。** `Assign Group 1 At Layout 1` 将组放入布局。`Select Layout 1` 选中布局。`Store View 55 "Stage" /screen=2 /nc` 保存第二屏，`Assign View 55 At ViewButton 2.1 /screen=2` 绑定按钮。用上表的 Screen 和 ViewButton 查询分别核对屏幕内容和召回入口。

## MAtricks、预设、效果与推杆

| 目的 | 原生命令示例 | 使用要点 |
|---|---|---|
| 选区配方 | `Import "paired" At MAtricks 10 /nc`、`MAtricksReset` | XML 位于端点的 `matricks`；记录中池位 1 为系统 Reset。Wings 从选区首尾配对，Block X=2 取连续两个成员，结果取决于 Group 顺序 |
| 随机选灯 | `Assign Macro 1.9.1 /cmd="ShuffleSelection"` | 先建立所需 Macro 与行。该命令把洗牌操作写入宏，实际调用会改变当前选灯顺序 |
| 导入编程对象 | `Import "positions" At Preset 2.1 /nc`、`Import "wave" At Effect 1 /nc`、`Import "segment" At Sequence 401 /nc` | 先核对文件和目的范围。该版本的 Preset、Sequence 默认在 `importexport`，Effect 在 `effects`。多对象文件会占用后续池位 |
| 执行器绑定 | `Assign Sequence 501 Thru 515 At Executor 2.1 Thru 2.15`、`Assign Master At Executor 2.1 Thru 2.15` | 核对目标页、槽位和绑定数量。需要推起启动、拉下停止时用 `Assign Executor 2.1 /AutoStart=On /AutoStop=On /Restart=First` |
| 保存与验收 | `Export Sequence 501 "segment_check"`、`SaveShow /nc` | 对照 Cue 数据和 Executor 绑定。通过本机工具优先使用 `ma2_export` 和 `ma2_backup`，分别等待完整 XML 与新 Show 文件 |

MA 会按对象类型选择原生导出目录。预览、停止执行器和调整 MA3D 相机的命令见[场景与播放参考](commands.md)。[MA Lighting 的 Export 关键词说明](https://help.malighting.com/grandMA2/en/help/key_keyword_export.html)

## 只读抽查与 DMX 采样

这些入口由源码版提供。先用 `ma2_status` 核对目标，保持 `MA2_ALLOW_WRITE=0`。只读巡检使用 Telnet 返回的数据，原始回显保存在工具侧的审计目录。

| 入口 | 输入示例 | 如何判断结果 |
|---|---|---|
| `ma2_probe` / CLI `probe` | `{"objects":["TimecodeSlot 1","Timer 1","Form 1","World 1"]}` | 省略 objects 默认抽查 41 项。自选 1–64 个表达式均须符合 ma2_list 语法。acknowledged 表示收到命令回显，empty 表示指定范围为空，rejected 表示明确拒绝。超时或断线后终止；审计保留已完成项 |
| `ma2_read_dmx` / CLI `read-dmx` | `{"universe":1,"address":449,"count":64}` | Universe 1–256、地址 1–512，单次最多 64 个连续通道，限同一 Universe。返回控制台读值；验收物理输出和光束需另外观察 |
| `ma2_playback` / CLI `playback` | 在允许改变输出的 Show 中，指定 executor、action、expected_show。goto 另传 cue 字符串（可含小数），level 另传 level（整数 0–100） | go / back / pause / off 操作该执行器，goto 跳 Cue，level 设置电平。按页.推杆定位，目标为 onPC；命令已确认并不证明灯光效果 |

在 onPC 3.3.4.3 的一次只读抽查中，默认 41 项有 34 项收到普通回显，7 项明确报告抽查范围为空。定向查询取得了 Cue 时序、分屏按钮、灯具类型、灯层、计时器、时间码槽和效果波形等对象行。Layer、ButtonPage、FaderPage 和 NetworkInfo 在当时的上下文返回根目录内容，读取灯层可用 LiveSetup.Layers，再列已确认的 Root 子地址。无效 Root 子地址返回拒绝，其后的有效查询可继续。

DMX 实测覆盖同一 Universe 的首地址和末端 64 个通道，以及另一 Universe 和 256.512 的边界地址。当次样本均为零。回放的六种动作在模拟端验证了命令与权限控制，现场测试仅做查询和采样。
