# LooperRobotics Insight 系列 OTA CLI

## 概述

`ota_cli.py` 是一款用于管理 LooperRobotics Insight 系列相机 OTA 固件升级的命令行工具。

当设备 Web 管理页面不可用，或希望使用可重复、可脚本化的升级流程时，可以使用该工具完成 OTA 查询与升级。

主要能力：

- 自动探测当前可访问的 Insight 设备地址
- 查询设备当前固件版本
- 获取 LooperRobotics OTA 服务上已发布的升级版本
- 升级到指定版本，或升级到最新发布版本
- 在升级过程中输出上传进度与设备侧 OTA 日志

## 脚本位置

本地机器：

- `/home/dm/ota_cli.py`
- `/home/dm/looper_scripts/ota_cli.py`

远程机器：

- `/home/jetson/looper_scripts/ota_cli.py`

## 设备地址规则

该工具同时兼容旧版与新版 Insight 网络配置。

通常在 Insight `v1.2.2` 之前使用的旧地址：

- `http://192.168.137.100`
- `http://looperrobotics.net`

通常在 Insight `v1.2.2` 及之后使用的新地址：

- `http://169.254.10.1`
- `http://looper.local`

如果未显式指定 `--device-base-url`，CLI 会自动探测这些已知地址，并选择当前可访问的设备地址。

## 命令说明

查看整体帮助：

```bash
python3 ota_cli.py help
```

查看 CLI 版本：

```bash
python3 ota_cli.py --version
```

查看当前设备地址和当前固件版本：

```bash
python3 ota_cli.py current
```

查看已发布 OTA 版本：

```bash
python3 ota_cli.py list
```

升级到指定固件版本：

```bash
python3 ota_cli.py upgrade --version 1.2.3
```

升级到最新发布版本：

```bash
python3 ota_cli.py upgrade --latest
```

查看子命令帮助：

```bash
python3 ota_cli.py help current
python3 ota_cli.py help list
python3 ota_cli.py help upgrade
```

常用示例：

```bash
python3 ota_cli.py --version
python3 ota_cli.py list --device-base-url http://169.254.10.1
python3 ota_cli.py upgrade --version 1.2.3 -y
python3 ota_cli.py upgrade --version 1.2.3 --watch-seconds 1200
```

远程机器示例：

```bash
python3 /home/jetson/looper_scripts/ota_cli.py current
python3 /home/jetson/looper_scripts/ota_cli.py list
python3 /home/jetson/looper_scripts/ota_cli.py upgrade --version 1.2.3
```

## 工作流程

执行 `list` 或 `upgrade` 时，CLI 主要执行以下步骤：

1. 解析并探测当前可访问的 Insight 设备地址
2. 查询设备版本接口
3. 从 `https://looper-robotics.com/pb` 获取 OTA 发布信息
4. 在升级时下载对应发布版本的固件文件与签名文件
5. 以 `4 MB` 分块方式将固件上传到设备
6. 调用设备 OTA 启动接口
7. 通过 WebSocket 持续输出设备侧 OTA 日志

## Release Notes 显示格式

`list` 命令会以结构化方式显示每个 OTA 发布版本，包含以下字段：

- `Version`
- `Release Date`
- `Files`
- `Channel`
- `Record ID`
- `Notes`

其中 `Notes` 会完整显示，并自动换行，避免在终端中被截断。

示例：

```text
Release [1]
Version     : 1.2.3
Release Date: 2026-04-17
Files       : 6
Channel     : release
Record ID   : ugwj5d7wcsg4ysn
Notes       : 1. Integrated a Log Rotation mechanism...
              2. Optimized VIO logic...
```

## 使用建议

- OTA 全过程应保证供电稳定
- 上传和刷写过程中不要断开设备网络连接
- 某些版本升级后，设备 IP 地址或主机名可能发生变化
- 某些安装阶段即使前台日志变少，后台仍可能继续执行
- 建议在正式升级前先运行 `current` 或 `list`

## 故障排查

如果 CLI 响应比预期慢，可以依次检查：

- 当前主机是否能访问设备网络
- 使用 `python3 ota_cli.py current` 确认当前命中的设备地址
- 必要时使用 `--device-base-url` 显式指定地址
- 确认设备当前没有被其他 OTA 任务占用
