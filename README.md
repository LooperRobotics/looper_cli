# LooperRobotics Insight Series CLI

## Overview

`looper_cli.py` is the primary command-line utility for device management on LooperRobotics Insight Series products.

The CLI is designed as an extensible foundation for firmware management and future device operations, including OTA workflows, device lifecycle controls, calibration workflows, parameter management, and log retrieval.

Current implementation status:

- Fully supported: device discovery, firmware version inspection, OTA release listing, OTA firmware upgrade
- Fully supported: calibration mode status, calibration mode enable/disable
- Fully supported: IP configuration read/update, DDS configuration read/update, system monitor status, system time inspection, system time sync
- Best-effort integration: system reboot, calibration parameter upload, system log retrieval

## Repository Layout

- `looper_cli.py`: primary CLI entrypoint
- `looper_cli/`: modular application package
- `README.md`: English documentation
- `README_cn.md`: Chinese documentation

## Architecture

The CLI has been refactored from a single-purpose OTA script into a modular package so that future device commands can be added without continuing to grow a single file.

Current modules:

- `looper_cli.app`: parser setup and command routing
- `looper_cli.device`: device discovery and device-oriented command handlers
- `looper_cli.ota`: OTA release discovery, upload, and update logic
- `looper_cli.http`: shared HTTP request utilities
- `looper_cli.output`: terminal logging and inline progress rendering
- `looper_cli.errors`: shared exception types

## Device Addressing

The CLI supports both legacy and current Insight network configurations.

Legacy addressing, typically used before Insight `v1.2.2`:

- `http://192.168.137.100`
- `http://looperrobotics.net`

Current addressing, typically used for Insight `v1.2.2` and later:

- `http://169.254.10.1`
- `http://looper.local`

If `--device-base-url` is not supplied, the CLI automatically probes known endpoints and selects the first reachable device.

## Command Model

The new command model is grouped by capability domain.

Structured command groups:

```bash
python3 looper_cli.py device current
python3 looper_cli.py ota list
python3 looper_cli.py ota upgrade --latest
python3 looper_cli.py network show
python3 looper_cli.py network set --segment 20
python3 looper_cli.py dds show
python3 looper_cli.py dds set fastrtps
python3 looper_cli.py monitor status
python3 looper_cli.py system reboot
python3 looper_cli.py system info
python3 looper_cli.py time show
python3 looper_cli.py time sync
python3 looper_cli.py calibration status
python3 looper_cli.py calibration enable
python3 looper_cli.py calibration disable
python3 looper_cli.py calibration upload calibration.json
python3 looper_cli.py logs fetch
```

General utility commands:

```bash
python3 looper_cli.py help
python3 looper_cli.py help ota
python3 looper_cli.py --version
```

## OTA Workflow

The OTA implementation currently performs the following steps:

1. Resolve the reachable device endpoint
2. Query the device firmware version
3. Retrieve OTA release metadata from `https://looper-robotics.com/pb`
4. Download release assets and signatures from the OTA service
5. Upload firmware payloads to the device in `4 MB` chunks
6. Trigger the device OTA start endpoint
7. Stream device-side OTA logs over WebSocket

## API Coverage

The current CLI covers these confirmed device-local API capabilities:

- `/api/version`
- `/api/mode`
- `/api/ip-config`
- `/api/dds-type`
- `/api/system-time`
- `/api/cpu-monitor`
- `/api/memory-monitor`
- `/api/system-info`
- `/api/time-sync/ping`
- `/api/set-time-v2`
- `/api/ota/upload`
- `/api/ota/start`
- `/api/ota/ws`

## Release Notes Display Format

The `list` and `ota list` commands present each OTA release as a structured block with the following fields:

- `Version`
- `Release Date`
- `Files`
- `Channel`
- `Record ID`
- `Notes`

The `Notes` field is rendered in wrapped multi-line form so that full published release notes remain visible in terminal output without truncation.

Numbered entries such as `1. 2. 3. 4.` are automatically split into separate readable lines with indentation for better terminal readability.

Example:

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

## Command Behavior Notes

`system reboot`

- Attempts a set of known reboot API patterns on the current device firmware
- Returns a clear error if the running firmware does not expose a supported reboot endpoint

`calibration status`, `calibration enable`, `calibration disable`

- Integrated with the current device calibration mode API at `/api/mode`

`calibration upload`

- Attempts common calibration upload API paths
- Supports `--endpoint` when a device firmware exposes a custom upload path

`logs fetch`

- Attempts known log download API paths first
- If no native log download endpoint is available, it falls back to a diagnostic system snapshot containing version, time, IP configuration, DDS type, calibration mode, CPU, memory, and system information

`network show`, `network set`

- Integrated with `/api/ip-config`
- Supports either `--segment <n>` or explicit `--master-ip` and `--slave-ip`

`dds show`, `dds set`

- Integrated with `/api/dds-type`

`monitor status`

- Aggregates `/api/cpu-monitor`, `/api/memory-monitor`, `/api/system-info`, and `/api/ip-config`

`time show`, `time sync`

- `time show` reads `/api/system-time`
- `time sync` uses `/api/time-sync/ping` and `/api/set-time-v2`

## Examples

Show current device information:

```bash
python3 looper_cli.py device current
```

Show network and DDS configuration:

```bash
python3 looper_cli.py network show
python3 looper_cli.py dds show
```

Update network segment and DDS type:

```bash
python3 looper_cli.py network set --segment 20
python3 looper_cli.py dds set cyclonedds
```

Show live system summary and device time:

```bash
python3 looper_cli.py monitor status
python3 looper_cli.py time show
```

List published firmware releases:

```bash
python3 looper_cli.py ota list
```

Upgrade to a specific release:

```bash
python3 looper_cli.py ota upgrade --version 1.2.3
```

Upgrade to the latest published release without confirmation prompt:

```bash
python3 looper_cli.py ota upgrade --latest -y
```

Force a specific device endpoint:

```bash
python3 looper_cli.py ota list --device-base-url http://169.254.10.1
```

Fetch logs into a file:

```bash
python3 looper_cli.py logs fetch --output insight_snapshot.json
```

Upload calibration parameters through an explicit endpoint:

```bash
python3 looper_cli.py calibration upload calibration.json --endpoint /api/calibration/upload
```

## Operational Guidance

- Ensure stable power during the full OTA process
- Do not disconnect the device network link while upload or flashing is in progress
- Be aware that some firmware releases may change the device IP address or hostname after upgrade
- Some installation stages may continue in the background after visible OTA logs become quiet
- Prefer running `device current` or `ota list` before initiating an upgrade

## Troubleshooting

If the CLI takes longer than expected to respond:

- Verify the host has network connectivity to the device
- Use `python3 looper_cli.py device current` to confirm which endpoint is reachable
- If necessary, specify the endpoint explicitly with `--device-base-url`
- Confirm the device is not already busy with another OTA task

## Execution Location

Run all commands from the `looper_scripts` directory, or invoke them by full path from that directory tree.

Examples:

```bash
cd /home/dm/looper_scripts
python3 looper_cli.py --version
python3 looper_cli.py ota list
```
