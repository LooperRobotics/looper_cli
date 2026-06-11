# LooperRobotics Insight 系列 CLI

## 概述

`looper_cli.py` 是用于管理 LooperRobotics Insight 系列设备的官方命令行工具。

当 Web 管理页面不可用、需要脚本化执行、或者希望把设备运维流程做成可重复操作时，可以使用它来完成设备检查、OTA 升级和常见维护任务。

当前已覆盖的能力：

- 自动探测设备地址并查看当前固件版本
- 查看与 Web 仪表盘同源的 `softwareVersion` 和 `firewareVersion`
- 查看已发布 OTA 版本并执行 OTA 升级
- 查看和修改网络配置
- 查看和修改 DDS 配置
- 查看系统监控、系统信息、设备时间
- 将设备时间同步到本机时间
- 控制 Looper 重启、Insightfull 启动/暂停/停止
- 执行 restore-to-factory 的 shallow 和 deep 恢复
- 查看/切换校准模式、上传校准参数和校准备份恢复
- 摄像头帧率配置的查询和更新
- 深度流（深度估计）开关的查询和切换
- 获取系统日志，或在无日志接口时回退到诊断快照



## 版本commit对应信息

1.2.3版本及以前的版本对应commit：`d5efdabb2088c735a3592ab7a29e274e2e039a8c`

1.2.4-1.2.5版本对应commit：`5930bb25a6d7f2902c6e89fe80f62007195a16f4`





## 目录结构

- `looper_cli.py`：CLI 入口脚本
- `looper_cli/`：命令解析、设备操作、OTA、HTTP、输出和错误处理模块
- `README.md`：英文文档
- `README_cn.md`：中文文档

## 快速开始

查看整体帮助：

```bash
python3 looper_cli.py --help
python3 looper_cli.py help
```

查看某个命令或子命令的帮助：

```bash
python3 looper_cli.py help ota
python3 looper_cli.py help ota upgrade
python3 looper_cli.py help network set
python3 looper_cli.py help restore
```

查看版本：

```bash
python3 looper_cli.py --version
```

## 设备地址规则

CLI 同时兼容旧版和新版 Insight 网络配置。

通常在 Insight `v1.2.2` 之前常见的旧地址：

- `http://192.168.137.100`
- `http://looperrobotics.net`

通常在 Insight `v1.2.2` 及之后常见的新地址：

- `http://169.254.10.1`
- `http://looper.local`

如果没有显式传入 `--device-base-url`，CLI 会自动探测这些已知地址，并优先使用第一个可访问的设备地址。

示例：

```bash
python3 looper_cli.py current
python3 looper_cli.py --device-base-url http://169.254.10.1 current
```

## 命令总览

顶层快捷命令：

```bash
# 查看版本信息
python3 looper_cli.py current
# 列出已有的ota升级包列表
python3 looper_cli.py list
# 升级到最新发布的版本
python3 looper_cli.py upgrade --latest
# 升级到指定版本号的版本
python3 looper_cli.py upgrade --version 1.2.3
```

分组命令：

```bash
python3 looper_cli.py ota list
python3 looper_cli.py ota upgrade --latest

# 查看设备网络信息
python3 looper_cli.py network show
# 设置ip为20网段（主机169.254.20.1，从机169.254.20.2）
python3 looper_cli.py network set --segment 20
# 指定设置主从机ip
python3 looper_cli.py network set --master-ip 169.254.20.1 --slave-ip 169.254.20.2

# 查看设备的dds模式
python3 looper_cli.py dds show
# 设置设备的dds模式为cyclonedds模式
python3 looper_cli.py dds set cyclonedds
# 设置设备的dds模式为fastrtps模式
python3 looper_cli.py dds set fastrtps


# 查看设备监控的信息，包含cpu内存使用率
python3 looper_cli.py monitor status
# 以json形式显示
python3 looper_cli.py monitor status --json

# 系统重启
python3 looper_cli.py system reboot
# 浅恢复出厂，恢复到当前版本初始状态
python3 looper_cli.py system recovery shallow
# 深恢复出厂，删除所有软件，需要重新进行ota升级
python3 looper_cli.py system recovery deep
# 查看设备信息，温度与设备运行信息
python3 looper_cli.py system info

# 查看设备信息
python3 looper_cli.py time show
# 查看 NTP 时间同步状态
python3 looper_cli.py time status
# 开启或关闭 NTP 时间同步
python3 looper_cli.py time enable
python3 looper_cli.py time disable
# 进行设备时间同步,需先使能时间同步功能
python3 looper_cli.py time sync

# 启动软件
python3 looper_cli.py insight start
# 关闭软件
python3 looper_cli.py insight stop

# 查看当前标定模式状态
python3 looper_cli.py calibration status
# 使能标定模式
python3 looper_cli.py calibration enable
# 关闭标定模式
python3 looper_cli.py calibration disable
# 上传标定文件
python3 looper_cli.py calibration upload calibration.json
# 上传标定文件到自定义端点（例如 /api/upload）
python3 looper_cli.py calibration upload calibration.json --endpoint /api/upload
# 从备份恢复标定文件
python3 looper_cli.py calibration restore

# 查看当前摄像头帧率设置
python3 looper_cli.py camera fps
# 设置摄像头帧率为 30
python3 looper_cli.py camera fps --fps 30 -y
# 设置摄像头帧率为 60
python3 looper_cli.py camera fps --fps 60 -y
# 以 JSON 格式显示摄像头帧率
python3 looper_cli.py camera fps --json

# 查看当前深度流开关状态
python3 looper_cli.py deep-flow show
# 开启深度流
python3 looper_cli.py deep-flow enable -y
# 关闭深度流
python3 looper_cli.py deep-flow disable -y
# 以 JSON 格式显示深度流状态
python3 looper_cli.py deep-flow show --json

# 查看设备所有监控的状态信息
python3 looper_cli.py logs fetch
# 将设备状态信息输入到文件
python3 looper_cli.py logs fetch --output device_logs.zip

# 查看ros domain id
python3 looper_cli.py ros domain-id show
# 设置ros domain id
python3 looper_cli.py ros domain-id set --ros-domain-id 1 -y

# 查看ros topic name
python3 looper_cli.py ros topic show
# 设置ros topic name
python3 looper_cli.py ros topic set --node-name insight_full --camera-namespace camera --camera-name camera -y

```



## OTA 工作流程

执行 OTA 相关命令时，CLI 当前会按以下流程工作：

1. 解析并探测可访问的设备地址
2. 查询设备当前版本
3. 从 `https://looper-robotics.com/pb` 获取 OTA 发布信息
4. 下载目标版本对应的固件与签名文件
5. 以 `4 MB` 分块方式上传固件
6. 调用设备 OTA 启动接口
7. 通过 WebSocket 持续输出设备侧 OTA 日志

## 行为说明

`list` 和 `ota list`

- 两者等价
- 会显示版本号、发布日期、文件数、通道、记录 ID 和发布说明
- 长发布说明会自动换行，方便终端阅读

`upgrade` 和 `ota upgrade`

- 两者等价
- 必须二选一传入 `--version <x.y.z>` 或 `--latest`
- 可通过 `--watch-seconds` 控制启动升级后继续跟踪设备侧日志的时长

`device versions`

- 读取与 Web 前端一致的版本信息来源
- 显示 `softwareVersion` 和 `firewareVersion`

`network set`

- 支持 `--segment <n>`，也支持显式传入 `--master-ip` 与 `--slave-ip`
- 例如 `--segment 20` 会推导为 `169.254.20.1` 和 `169.254.20.2`

`dds set`

- 目前支持 `cyclonedds` 和 `fastrtps`

`monitor status`

- 汇总 CPU、内存、温度、运行时长和 IP 等信息
- 包含与 Web Time Sync 页面相同的时间同步状态
- `--json` 会输出原始数据

`time status`、`time enable` 和 `time disable`

- 对齐 Web Time Sync 页面
- 读取和写入 `/api/time-sync-setting`
- `time status --json` 会输出原始响应数据

`system recovery`、`restore`、`recovery`

- 指向同一套 restore-to-factory 行为
- `shallow` 表示恢复到当前版本的初始状态
- `deep` 表示删除软件，之后需要重新 OTA

`insight stop`

- 优先调用 stop 后端接口，并兼容旧固件上的 pause 接口
- `looper control insight-stop` 是同一个动作的别名入口

`calibration upload`

- 用于上传校准参数文件
- 若某个固件使用自定义上传接口，可通过 `--endpoint` 显式指定

`calibration restore`

- 从设备恢复校准参数备份文件
- 查找 `.bak` 文件并将其复制回原始文件名
- 用于恢复之前的校准设置

`camera fps`

- 查询或配置摄像头帧率
- 支持 20、30 和 60 FPS 三个值
- 不带 `--fps` 参数调用时返回当前帧率设置
- 设置新的帧率值会重启设备以使配置生效

`deep-flow show`、`deep-flow enable` 与 `deep-flow disable`

- 对应 Web 端 Looper 控制页面上的深度流开关
- `show` 查看当前状态，`--json` 输出原始响应数据
- `enable` 与 `disable` 写入 `/api/deep-flow` 并重启相机服务以使配置生效

`logs fetch`

- 会优先尝试已知的日志下载接口
- 如果设备没有可用日志归档接口，会回退到诊断快照
- 支持 `--output` 指定保存路径

## 已覆盖的设备 API

当前 CLI 已覆盖这些确认可用的设备本地接口：

- `/api/version`
- `/api/reboot`
- `/api/insight-start`
- `/api/insight-stop`
- `/api/insight-pause`
- `/api/system/recovery`
- `/api/mode`
- `/api/ip-config`
- `/api/dds-type`
- `/api/system-time`
- `/api/cpu-monitor`
- `/api/memory-monitor`
- `/api/system-info`
- `/api/time-sync-setting`
- `/api/time-sync/ping`
- `/api/set-time-v2`
- `/api/ota/upload`
- `/api/ota/start`
- `/api/ota/ws`
- `/api/upload` (支持备份现有文件的多部分表单文件上传)
- `/api/restore` (恢复备份文件)
- `/api/camera-fps` (GET/POST 摄像头帧率配置)
- `/api/deep-flow` (GET/POST 深度流开关配置)

## 故障排查

- 先确认当前主机可以访问设备所在网络
- 运行 `python3 looper_cli.py current`，确认自动探测命中了哪个地址
- 自动探测不合适时，使用 `--device-base-url` 显式指定设备地址
- 确认设备当前没有被其他 OTA 任务占用
- OTA 上传和安装过程中保持供电和网络稳定

## 通过设备接口下载 CLI

后端提供了 CLI 下载接口，可以直接从设备拉取完整 CLI 包：

```bash
curl -L http://<device-host>/api/looper-cli/download -o looper_cli.tar.gz
tar -xzf looper_cli.tar.gz
python3 looper_cli/looper_cli.py --help
```

如果想先查看下载信息：

```bash
curl http://<device-host>/api/looper-cli
```
