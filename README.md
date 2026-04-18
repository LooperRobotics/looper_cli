# LooperRobotics Insight Series OTA CLI

## Overview

`ota_cli.py` is a command-line utility for managing over-the-air firmware updates on LooperRobotics Insight Series cameras.

The tool is intended for environments where the device web interface is unavailable or where a scripted, repeatable OTA workflow is preferred.

Core capabilities:

- Detect the currently reachable Insight device endpoint
- Query the current firmware version from the device
- List published OTA releases from the LooperRobotics OTA service
- Upgrade to a specified firmware release or to the latest published release
- Stream upload progress and device-side OTA logs during execution

## Script Locations

Local machine:

- `/home/dm/ota_cli.py`
- `/home/dm/looper_scripts/ota_cli.py`

Remote machine:

- `/home/jetson/looper_scripts/ota_cli.py`

## Device Addressing

The CLI supports both legacy and current Insight network configurations.

Legacy addressing, typically used before Insight `v1.2.2`:

- `http://192.168.137.100`
- `http://looperrobotics.net`

Current addressing, typically used for Insight `v1.2.2` and later:

- `http://169.254.10.1`
- `http://looper.local`

If `--device-base-url` is not supplied, the CLI automatically probes known endpoints and selects the first reachable device.

## Command Reference

Show overall help:

```bash
python3 ota_cli.py help
```

Show the CLI version:

```bash
python3 ota_cli.py --version
```

Show the detected device endpoint and current firmware version:

```bash
python3 ota_cli.py current
```

List published OTA releases:

```bash
python3 ota_cli.py list
```

Upgrade to a specific firmware version:

```bash
python3 ota_cli.py upgrade --version 1.2.3
```

Upgrade to the latest published release:

```bash
python3 ota_cli.py upgrade --latest
```

Show command-specific help:

```bash
python3 ota_cli.py help current
python3 ota_cli.py help list
python3 ota_cli.py help upgrade
```

Useful options:

```bash
python3 ota_cli.py --version
python3 ota_cli.py list --device-base-url http://169.254.10.1
python3 ota_cli.py upgrade --version 1.2.3 -y
python3 ota_cli.py upgrade --version 1.2.3 --watch-seconds 1200
```

Remote-machine examples:

```bash
python3 /home/jetson/looper_scripts/ota_cli.py current
python3 /home/jetson/looper_scripts/ota_cli.py list
python3 /home/jetson/looper_scripts/ota_cli.py upgrade --version 1.2.3
```

## Operational Flow

For `list` and `upgrade`, the CLI performs the following steps:

1. Resolve the reachable Insight device endpoint
2. Query the device version endpoint
3. Retrieve OTA release metadata from `https://looper-robotics.com/pb`
4. For upgrades, download release assets from the OTA service
5. Upload firmware payloads to the device in `4 MB` chunks
6. Trigger the OTA start endpoint on the device
7. Stream device-side OTA logs over WebSocket

## Release Notes Display Format

The `list` command presents each OTA release as a structured block with the following fields:

- `Version`
- `Release Date`
- `Files`
- `Channel`
- `Record ID`
- `Notes`

The `Notes` field is rendered in wrapped multi-line form so that the full published release notes remain visible in terminal output without being truncated.

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

## Operational Guidance

- Ensure stable power during the full OTA process
- Do not disconnect the device network link while upload or flashing is in progress
- Be aware that some firmware releases may change the device IP address or hostname after upgrade
- Some installation stages may continue in the background after visible OTA logs become quiet
- Prefer running `current` or `list` before initiating an upgrade

## Troubleshooting

If the CLI takes longer than expected to respond:

- Verify the host has network connectivity to the device
- Use `python3 ota_cli.py current` to confirm which endpoint is reachable
- If necessary, specify the endpoint explicitly with `--device-base-url`
- Confirm the device is not already busy with another OTA task
