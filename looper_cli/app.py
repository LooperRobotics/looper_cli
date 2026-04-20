import argparse
import sys
from urllib.error import HTTPError, URLError

from looper_cli import CLI_VERSION, DEFAULT_PER_PAGE, PB_BASE_URL, PRODUCT_NAME
from looper_cli.device import (
    DeviceSession,
    calibration_set_mode,
    calibration_status,
    calibration_upload,
    dds_set,
    dds_show,
    fetch_logs,
    monitor_status,
    network_set,
    network_show,
    print_current_status,
    reboot_device,
    system_info_show,
    system_sync_time,
    system_time_show,
)
from looper_cli.errors import CommandNotImplementedError, LooperCliError
from looper_cli.ota import print_release_list, run_ota_upgrade
from looper_cli.output import log


def command_current(args) -> int:
    return print_current_status(DeviceSession(args.device_base_url))


def command_list(args) -> int:
    return print_release_list(args, DeviceSession(args.device_base_url))


def command_upgrade(args) -> int:
    return run_ota_upgrade(args, DeviceSession(args.device_base_url))


def command_reboot(args) -> int:
    return reboot_device(args, DeviceSession(args.device_base_url))


def command_calibration_status(args) -> int:
    return calibration_status(args, DeviceSession(args.device_base_url))


def command_calibration_enable(args) -> int:
    return calibration_set_mode(args, DeviceSession(args.device_base_url), enabled=True)


def command_calibration_disable(args) -> int:
    return calibration_set_mode(
        args, DeviceSession(args.device_base_url), enabled=False
    )


def command_calibration_upload(args) -> int:
    return calibration_upload(args, DeviceSession(args.device_base_url))


def command_logs_fetch(args) -> int:
    return fetch_logs(args, DeviceSession(args.device_base_url))


def command_network_show(args) -> int:
    return network_show(args, DeviceSession(args.device_base_url))


def command_network_set(args) -> int:
    return network_set(args, DeviceSession(args.device_base_url))


def command_dds_show(args) -> int:
    return dds_show(args, DeviceSession(args.device_base_url))


def command_dds_set(args) -> int:
    return dds_set(args, DeviceSession(args.device_base_url))


def command_monitor_status(args) -> int:
    return monitor_status(args, DeviceSession(args.device_base_url))


def command_system_time_show(args) -> int:
    return system_time_show(args, DeviceSession(args.device_base_url))


def command_system_info_show(args) -> int:
    return system_info_show(args, DeviceSession(args.device_base_url))


def command_system_sync_time(args) -> int:
    return system_sync_time(args, DeviceSession(args.device_base_url))


def help_command(args) -> int:
    parser = build_parser()
    if args.topic:
        subparsers_action = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        subparser = subparsers_action.choices.get(args.topic)
        if not subparser:
            raise LooperCliError(f"Unknown help topic: {args.topic}")
        subparser.print_help()
    else:
        parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Official command-line utility for device management, OTA release discovery, "
            "and firmware updates on LooperRobotics Insight Series devices."
        )
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PRODUCT_NAME} {CLI_VERSION}",
        help="Show the CLI version and exit",
    )
    parser.add_argument(
        "--pb-base-url", default=PB_BASE_URL, help="PocketBase base URL"
    )
    parser.add_argument(
        "--device-base-url",
        default=None,
        help="Target device base URL; if omitted, the CLI auto-detects a reachable Looper device endpoint",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=DEFAULT_PER_PAGE,
        help="Maximum number of OTA release records to fetch",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    help_parser = subparsers.add_parser(
        "help", help="Show general or command-specific help"
    )
    help_parser.add_argument(
        "topic",
        nargs="?",
        choices=[
            "help",
            "current",
            "list",
            "upgrade",
            "device",
            "ota",
            "network",
            "dds",
            "monitor",
            "system",
            "calibration",
            "logs",
            "time",
        ],
    )
    help_parser.set_defaults(func=help_command)

    current_parser = subparsers.add_parser(
        "current", help="Show the detected device endpoint and current firmware version"
    )
    current_parser.set_defaults(func=command_current)

    list_parser = subparsers.add_parser(
        "list", help="List published OTA releases for Insight Series devices"
    )
    list_parser.set_defaults(func=command_list)

    upgrade_parser = subparsers.add_parser(
        "upgrade", help="Download, upload, and start an OTA firmware update"
    )
    upgrade_target_group = upgrade_parser.add_mutually_exclusive_group(required=True)
    upgrade_target_group.add_argument(
        "--version", help="Target firmware version, for example 1.2.3"
    )
    upgrade_target_group.add_argument(
        "--latest", action="store_true", help="Upgrade to the latest published release"
    )
    upgrade_parser.add_argument(
        "--watch-seconds",
        type=int,
        default=600,
        help="Seconds to keep streaming device-side OTA logs after the update starts",
    )
    upgrade_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    upgrade_parser.set_defaults(func=command_upgrade)

    device_parser = subparsers.add_parser(
        "device", help="Device inspection and identity commands"
    )
    device_subparsers = device_parser.add_subparsers(
        dest="device_command", required=True
    )
    device_current = device_subparsers.add_parser(
        "current", help="Show the detected device endpoint and current firmware version"
    )
    device_current.set_defaults(func=command_current)

    network_parser = subparsers.add_parser(
        "network", help="Network configuration commands"
    )
    network_subparsers = network_parser.add_subparsers(
        dest="network_command", required=True
    )
    network_show_parser = network_subparsers.add_parser(
        "show", help="Show current IP configuration"
    )
    network_show_parser.set_defaults(func=command_network_show)
    network_set_parser = network_subparsers.add_parser(
        "set", help="Update IP configuration"
    )
    network_group = network_set_parser.add_mutually_exclusive_group(required=True)
    network_group.add_argument(
        "--segment",
        help="Set network segment n and derive 169.254.n.1 / 169.254.n.2",
    )
    network_group.add_argument(
        "--master-ip",
        help="Explicit master IP; requires --slave-ip",
    )
    network_set_parser.add_argument(
        "--slave-ip",
        help="Explicit slave IP; required with --master-ip",
    )
    network_set_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    network_set_parser.set_defaults(func=command_network_set)

    dds_parser = subparsers.add_parser("dds", help="DDS configuration commands")
    dds_subparsers = dds_parser.add_subparsers(dest="dds_command", required=True)
    dds_show_parser = dds_subparsers.add_parser(
        "show", help="Show the current DDS implementation"
    )
    dds_show_parser.set_defaults(func=command_dds_show)
    dds_set_parser = dds_subparsers.add_parser(
        "set", help="Update the DDS implementation"
    )
    dds_set_parser.add_argument(
        "type", choices=["cyclonedds", "fastrtps"], help="Target DDS implementation"
    )
    dds_set_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    dds_set_parser.set_defaults(func=command_dds_set)

    monitor_parser = subparsers.add_parser(
        "monitor", help="System monitor and health commands"
    )
    monitor_subparsers = monitor_parser.add_subparsers(
        dest="monitor_command", required=True
    )
    monitor_status_parser = monitor_subparsers.add_parser(
        "status", help="Show CPU, memory, temperature, uptime, and IP summary"
    )
    monitor_status_parser.add_argument(
        "--json", action="store_true", help="Print the raw monitor payload as JSON"
    )
    monitor_status_parser.set_defaults(func=command_monitor_status)

    ota_parser = subparsers.add_parser("ota", help="OTA release and update commands")
    ota_subparsers = ota_parser.add_subparsers(dest="ota_command", required=True)
    ota_list = ota_subparsers.add_parser("list", help="List published OTA releases")
    ota_list.set_defaults(func=command_list)
    ota_upgrade = ota_subparsers.add_parser(
        "upgrade", help="Download, upload, and start an OTA firmware update"
    )
    ota_group = ota_upgrade.add_mutually_exclusive_group(required=True)
    ota_group.add_argument(
        "--version", help="Target firmware version, for example 1.2.3"
    )
    ota_group.add_argument(
        "--latest", action="store_true", help="Upgrade to the latest published release"
    )
    ota_upgrade.add_argument(
        "--watch-seconds",
        type=int,
        default=600,
        help="Seconds to keep streaming device-side OTA logs after the update starts",
    )
    ota_upgrade.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    ota_upgrade.set_defaults(func=command_upgrade)

    system_parser = subparsers.add_parser("system", help="System lifecycle commands")
    system_subparsers = system_parser.add_subparsers(
        dest="system_command", required=True
    )
    reboot_parser = system_subparsers.add_parser("reboot", help="Reboot the device")
    reboot_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    reboot_parser.set_defaults(func=command_reboot)
    system_info_parser = system_subparsers.add_parser(
        "info", help="Show device system information"
    )
    system_info_parser.add_argument(
        "--json", action="store_true", help="Print the raw system info payload as JSON"
    )
    system_info_parser.set_defaults(func=command_system_info_show)

    time_parser = subparsers.add_parser("time", help="Device time commands")
    time_subparsers = time_parser.add_subparsers(dest="time_command", required=True)
    time_show_parser = time_subparsers.add_parser(
        "show", help="Show current device system time"
    )
    time_show_parser.add_argument(
        "--json", action="store_true", help="Print the raw time payload as JSON"
    )
    time_show_parser.set_defaults(func=command_system_time_show)
    time_sync_parser = time_subparsers.add_parser(
        "sync", help="Synchronize the device clock with the local host"
    )
    time_sync_parser.add_argument(
        "--samples", type=int, default=20, help="Number of RTT samples to collect"
    )
    time_sync_parser.add_argument(
        "--interval-ms",
        type=int,
        default=30,
        help="Delay in milliseconds between RTT samples",
    )
    time_sync_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    time_sync_parser.set_defaults(func=command_system_sync_time)

    calibration_parser = subparsers.add_parser(
        "calibration", help="Calibration mode and parameter commands"
    )
    calibration_subparsers = calibration_parser.add_subparsers(
        dest="calibration_command", required=True
    )
    calibration_status_parser = calibration_subparsers.add_parser(
        "status", help="Show calibration mode status"
    )
    calibration_status_parser.set_defaults(func=command_calibration_status)
    calibration_enable_parser = calibration_subparsers.add_parser(
        "enable", help="Enable calibration mode"
    )
    calibration_enable_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    calibration_enable_parser.set_defaults(func=command_calibration_enable)
    calibration_disable_parser = calibration_subparsers.add_parser(
        "disable", help="Disable calibration mode"
    )
    calibration_disable_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    calibration_disable_parser.set_defaults(func=command_calibration_disable)
    calibration_upload_parser = calibration_subparsers.add_parser(
        "upload", help="Upload calibration parameters to the device"
    )
    calibration_upload_parser.add_argument(
        "file", help="Path to the calibration parameter file"
    )
    calibration_upload_parser.add_argument(
        "--endpoint",
        help="Optional explicit device API path for calibration upload, for example /api/calibration/upload",
    )
    calibration_upload_parser.set_defaults(func=command_calibration_upload)

    logs_parser = subparsers.add_parser("logs", help="System log retrieval commands")
    logs_subparsers = logs_parser.add_subparsers(dest="logs_command", required=True)
    logs_fetch_parser = logs_subparsers.add_parser(
        "fetch", help="Fetch system logs from the device"
    )
    logs_fetch_parser.add_argument(
        "--output", help="Optional destination file path for the downloaded logs"
    )
    logs_fetch_parser.add_argument(
        "--endpoint",
        help="Optional explicit device API path for log download, for example /api/system-logs/download",
    )
    logs_fetch_parser.set_defaults(func=command_logs_fetch)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        log("Interrupted")
        return 130
    except CommandNotImplementedError as exc:
        log(f"NOT IMPLEMENTED: {exc}")
        return 2
    except LooperCliError as exc:
        log(f"ERROR: {exc}")
        return 1
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        log(f"HTTP ERROR {exc.code}: {body or exc.reason}")
        return 1
    except URLError as exc:
        log(f"NETWORK ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
