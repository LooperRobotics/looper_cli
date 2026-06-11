# LooperRobotics Insight Series CLI

## Overview

`looper_cli.py` is the official command-line utility for managing LooperRobotics Insight Series devices.

It can be used for device inspection, OTA upgrades, and common maintenance tasks when the Web management page is unavailable, when scripted execution is needed, or when device operations should be repeatable.

Current capability coverage:

- Device address auto-discovery and current firmware version inspection
- Web-dashboard-aligned `softwareVersion` and `firewareVersion` inspection
- OTA release listing and OTA upgrade
- Network configuration read and update
- DDS configuration read and update
- System monitor, system info, and device time inspection
- Device time synchronization with the local machine
- Looper reboot and Insightfull start, pause, stop
- Restore-to-factory shallow and deep recovery
- Calibration mode status, switching, calibration parameter upload, and calibration backup restore
- Camera FPS configuration inspection and update
- Deep flow (depth estimation) switch inspection and toggling
- System log retrieval, with diagnostic snapshot fallback when the log API is unavailable

## Version Commit Mapping

Versions `1.2.3` and earlier correspond to commit: `d5efdabb2088c735a3592ab7a29e274e2e039a8c`

Versions `1.2.4` through `1.2.5` correspond to commit:`5930bb25a6d7f2902c6e89fe80f62007195a16f4`

## Repository Layout

- `looper_cli.py`: CLI entry script
- `looper_cli/`: command parsing, device operations, OTA, HTTP, output, and error handling modules
- `README.md`: English documentation
- `README_cn.md`: Chinese documentation

## Quick Start

Show top-level help:

```bash
python3 looper_cli.py --help
python3 looper_cli.py help
```

Show help for a command or subcommand:

```bash
python3 looper_cli.py help ota
python3 looper_cli.py help ota upgrade
python3 looper_cli.py help network set
python3 looper_cli.py help restore
```

Show version:

```bash
python3 looper_cli.py --version
```

## Device Address Rules

The CLI supports both legacy and current Insight network configurations.

Legacy addresses commonly seen before Insight `v1.2.2`:

- `http://192.168.137.100`
- `http://looperrobotics.net`

Current addresses commonly seen on Insight `v1.2.2` and later:

- `http://169.254.10.1`
- `http://looper.local`

If `--device-base-url` is not provided explicitly, the CLI automatically probes these known addresses and uses the first reachable device address.

Examples:

```bash
python3 looper_cli.py current
python3 looper_cli.py --device-base-url http://169.254.10.1 current
```

## Command Overview

Top-level shortcuts:

```bash
# View version information
python3 looper_cli.py current
# List existing OTA upgrade packages
python3 looper_cli.py list
# Upgrade to the latest released version
python3 looper_cli.py upgrade --latest
# Upgrade to a specified version
python3 looper_cli.py upgrade --version 1.2.3
```

Grouped commands:

```bash
python3 looper_cli.py ota list
python3 looper_cli.py ota upgrade --latest

# View device network information
python3 looper_cli.py network show
# Set IP addresses to segment 20 (master 169.254.20.1, slave 169.254.20.2)
python3 looper_cli.py network set --segment 20
# Explicitly set master and slave IP addresses
python3 looper_cli.py network set --master-ip 169.254.20.1 --slave-ip 169.254.20.2

# View the device DDS mode
python3 looper_cli.py dds show
# Set the device DDS mode to cyclonedds
python3 looper_cli.py dds set cyclonedds
# Set the device DDS mode to fastrtps
python3 looper_cli.py dds set fastrtps

# View device monitoring information, including CPU and memory usage
python3 looper_cli.py monitor status
# Display as JSON
python3 looper_cli.py monitor status --json

# Reboot the system
python3 looper_cli.py system reboot
# Shallow factory recovery: restore to the initial state of the current version
python3 looper_cli.py system recovery shallow
# Deep factory recovery: delete all software; OTA upgrade is required again
python3 looper_cli.py system recovery deep
# View device information, temperature, and runtime information
python3 looper_cli.py system info

# View device time information
python3 looper_cli.py time show
# View NTP time synchronization status
python3 looper_cli.py time status
# Enable or disable NTP time synchronization
python3 looper_cli.py time enable
python3 looper_cli.py time disable
# Synchronize device time, Time synchronization must be enabled first
python3 looper_cli.py time sync

# Start software
python3 looper_cli.py insight start
# Stop software
python3 looper_cli.py insight stop

# View current calibration mode status
python3 looper_cli.py calibration status
# Enable calibration mode
python3 looper_cli.py calibration enable
# Disable calibration mode
python3 looper_cli.py calibration disable
# Upload calibration file
python3 looper_cli.py calibration upload calibration.json
# Upload calibration file to custom endpoint (e.g., /api/upload)
python3 looper_cli.py calibration upload calibration.json --endpoint /api/upload
# Restore calibration files from backups
python3 looper_cli.py calibration restore

# View current camera FPS setting
python3 looper_cli.py camera fps
# Set camera FPS to 30
python3 looper_cli.py camera fps --fps 30 -y
# Set camera FPS to 60
python3 looper_cli.py camera fps --fps 60 -y
# Display camera FPS as JSON
python3 looper_cli.py camera fps --json

# View current deep flow switch state
python3 looper_cli.py deep-flow show
# Enable deep flow
python3 looper_cli.py deep-flow enable -y
# Disable deep flow
python3 looper_cli.py deep-flow disable -y
# Display deep flow state as JSON
python3 looper_cli.py deep-flow show --json

# View all monitored device status information
python3 looper_cli.py logs fetch
# Write device status information to a file
python3 looper_cli.py logs fetch --output device_logs.zip

# show ros domain id
python3 looper_cli.py ros domain-id show
# set ros domain id
python3 looper_cli.py ros domain-id set --ros-domain-id 1 -y

# show ros topic name
python3 looper_cli.py ros topic show
# set ros topic name
python3 looper_cli.py ros topic set --node-name insight_full --camera-namespace camera --camera-name camera -y

```

## OTA Workflow

When OTA-related commands are executed, the CLI currently works as follows:

1. Parse and probe reachable device addresses
2. Query the current device version
3. Fetch OTA release information from `https://looper-robotics.com/pb`
4. Download the firmware and signature files for the target version
5. Upload firmware in `4 MB` chunks
6. Call the device OTA start API
7. Continuously stream device-side OTA logs through WebSocket

## Behavioral Notes

`list` and `ota list`

- Equivalent commands
- Display version, release date, file count, channel, record ID, and release notes
- Wrap long release notes for terminal readability

`upgrade` and `ota upgrade`

- Equivalent commands
- Require either `--version <x.y.z>` or `--latest`
- Support `--watch-seconds` to continue tracking device-side logs after the upgrade starts

`device versions`

- Reads the same version information source as the Web frontend
- Shows `softwareVersion` and `firewareVersion`

`network set`

- Supports `--segment <n>` and also explicit `--master-ip` plus `--slave-ip`
- For example, `--segment 20` derives `169.254.20.1` and `169.254.20.2`

`dds set`

- Currently supports `cyclonedds` and `fastrtps`

`monitor status`

- Aggregates CPU, memory, temperature, uptime, IP, and related information
- Includes the same time sync status used by the Web Time Sync page
- `--json` outputs the raw data

`time status`, `time enable`, and `time disable`

- Mirror the Web Time Sync page
- Read and write `/api/time-sync-setting`
- `time status --json` outputs the raw response payload

`system recovery`, `restore`, and `recovery`

- Point to the same restore-to-factory behavior
- `shallow` restores the initial state of the current version
- `deep` deletes software and requires OTA again afterward

`insight stop`

- Calls the stop backend first and falls back to pause endpoints for older firmware
- `looper control insight-stop` is an alias entry for the same action

`calibration upload`

- Used to upload calibration parameter files
- If a firmware uses a custom upload API, specify it explicitly with `--endpoint`
- Common endpoints include `/api/calibration/upload`, `/api/calibration/params`, and `/api/upload`

`calibration restore`

- Restores backup calibration files from the device
- Looks for `.bak` files and copies them back to their original names
- Useful for recovering previous calibration settings

`camera fps`

- Query or configure the camera frame rate
- Supports 20, 30, and 60 FPS values
- Returns the current FPS setting when called without `--fps`
- Setting a new FPS value reboots the device to apply the change

`deep-flow show`, `deep-flow enable`, and `deep-flow disable`

- Mirror the deep flow switch on the Web Looper Control page
- `show` reports the current state; `--json` outputs the raw response payload
- `enable` and `disable` write `/api/deep-flow` and restart the camera service to apply the change

`logs fetch`

- Attempts known log download APIs first
- Falls back to a diagnostic snapshot if the device has no available log archive API
- Supports `--output` to specify the save path

## API Coverage

The current CLI covers these confirmed device-local APIs:

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
- `/api/upload` (multipart form file upload with backup support)
- `/api/restore` (restore backup files)
- `/api/camera-fps` (GET/POST camera FPS configuration)
- `/api/deep-flow` (GET/POST deep flow switch configuration)

## Troubleshooting

- First confirm that the current host can access the device network
- Run `python3 looper_cli.py current` to confirm which address auto-discovery selected
- Use `--device-base-url` to explicitly specify the device address when auto-discovery is not suitable
- Confirm that the device is not currently occupied by another OTA task
- Keep power and network stable during OTA upload and installation

## Download CLI Through Device API

The backend provides a CLI download API. You can pull the full CLI package directly from the device:

```bash
curl -L http://<device-host>/api/looper-cli/download -o looper_cli.tar.gz
tar -xzf looper_cli.tar.gz
python3 looper_cli/looper_cli.py --help
```

To inspect download information first:

```bash
curl http://<device-host>/api/looper-cli
```
