import argparse
import sys
from urllib.error import HTTPError, URLError

from looper_cli import CLI_VERSION, DEFAULT_PER_PAGE, PB_BASE_URL, PRODUCT_NAME
from looper_cli.device import (
    DeviceSession,
    calibration_set_mode,
    calibration_status,
    calibration_upload,
    calibration_restore,
    camera_fps,
    dds_set,
    dds_show,
    deep_flow_set,
    deep_flow_show,
    device_versions_show,
    fetch_logs,
    insightfull_pause,
    insightfull_start,
    insightfull_stop,
    monitor_status,
    network_set,
    network_show,
    print_current_status,
    reboot_device,
    ros_domain_id_set,
    ros_domain_id_show,
    ros_topic_set,
    ros_topic_show,
    system_recovery,
    system_info_show,
    system_sync_time,
    system_time_show,
    time_sync_set_enabled,
    time_sync_status,
)
from looper_cli.errors import CommandNotImplementedError, LooperCliError
from looper_cli.ota import print_release_list, run_ota_upgrade
from looper_cli.output import log


class CliHelpFormatter(argparse.RawDescriptionHelpFormatter):
    pass


def _help_text(description: str, examples: list[str] | None = None) -> dict:
    kwargs: dict = {
        "description": description,
        "formatter_class": CliHelpFormatter,
    }
    if examples:
        kwargs["epilog"] = "Examples:\n  " + "\n  ".join(examples)
    return kwargs


def _resolve_help_parser(
    parser: argparse.ArgumentParser, topics: list[str]
) -> argparse.ArgumentParser:
    current = parser
    for topic in topics:
        subparsers_action = next(
            (
                action
                for action in current._actions
                if isinstance(action, argparse._SubParsersAction)
            ),
            None,
        )
        if not subparsers_action:
            raise LooperCliError(
                f"Unknown help topic: {' '.join(topics)}"
            )
        next_parser = subparsers_action.choices.get(topic)
        if not next_parser:
            raise LooperCliError(
                f"Unknown help topic: {' '.join(topics)}"
            )
        current = next_parser
    return current


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


def command_calibration_restore(args) -> int:
    return calibration_restore(args, DeviceSession(args.device_base_url))


def command_camera_fps(args) -> int:
    return camera_fps(args, DeviceSession(args.device_base_url))


def command_deep_flow_show(args) -> int:
    return deep_flow_show(args, DeviceSession(args.device_base_url))


def command_deep_flow_enable(args) -> int:
    return deep_flow_set(args, DeviceSession(args.device_base_url), enabled=True)


def command_deep_flow_disable(args) -> int:
    return deep_flow_set(args, DeviceSession(args.device_base_url), enabled=False)


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


def command_ros_domain_id_show(args) -> int:
    return ros_domain_id_show(args, DeviceSession(args.device_base_url))


def command_ros_domain_id_set(args) -> int:
    return ros_domain_id_set(args, DeviceSession(args.device_base_url))


def command_ros_topic_show(args) -> int:
    return ros_topic_show(args, DeviceSession(args.device_base_url))


def command_ros_topic_set(args) -> int:
    return ros_topic_set(args, DeviceSession(args.device_base_url))


def command_monitor_status(args) -> int:
    return monitor_status(args, DeviceSession(args.device_base_url))


def command_device_versions(args) -> int:
    return device_versions_show(args, DeviceSession(args.device_base_url))


def command_system_time_show(args) -> int:
    return system_time_show(args, DeviceSession(args.device_base_url))


def command_system_info_show(args) -> int:
    return system_info_show(args, DeviceSession(args.device_base_url))


def command_system_sync_time(args) -> int:
    return system_sync_time(args, DeviceSession(args.device_base_url))


def command_time_sync_status(args) -> int:
    return time_sync_status(args, DeviceSession(args.device_base_url))


def command_time_sync_enable(args) -> int:
    return time_sync_set_enabled(args, DeviceSession(args.device_base_url), enabled=True)


def command_time_sync_disable(args) -> int:
    return time_sync_set_enabled(args, DeviceSession(args.device_base_url), enabled=False)


def command_system_recovery(args) -> int:
    return system_recovery(args, DeviceSession(args.device_base_url))


def command_insight_start(args) -> int:
    return insightfull_start(args, DeviceSession(args.device_base_url))


def command_insight_pause(args) -> int:
    return insightfull_pause(args, DeviceSession(args.device_base_url))


def command_insight_stop(args) -> int:
    return insightfull_stop(args, DeviceSession(args.device_base_url))


def help_command(args) -> int:
    parser = build_parser()
    if args.topic:
        _resolve_help_parser(parser, args.topic).print_help()
    else:
        parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Official command-line utility for device management, OTA release discovery, "
            "and Ota Updates on LooperRobotics Insight Series devices."
        ),
        epilog=(
            "Examples:\n"
            "  python3 looper_cli.py current\n"
            "  python3 looper_cli.py ota list\n"
            "  python3 looper_cli.py ota upgrade --latest -y\n"
            "  python3 looper_cli.py network set --segment 20 -y\n"
            "  python3 looper_cli.py help ota upgrade\n"
            "  python3 looper_cli.py system info --json"
        ),
        formatter_class=CliHelpFormatter,
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
        "help",
        help="Show general or command-specific help",
        **_help_text(
            "Show general help, top-level command help, or nested subcommand help.",
            [
                "python3 looper_cli.py help",
                "python3 looper_cli.py help ota",
                "python3 looper_cli.py help ota upgrade",
                "python3 looper_cli.py help network set",
            ],
        ),
    )
    help_parser.add_argument(
        "topic",
        nargs="*",
        choices=[
            "help",
            "current",
            "list",
            "upgrade",
            "device",
            "current",
            "versions",
            "ota",
            "list",
            "upgrade",
            "network",
            "show",
            "set",
            "dds",
            "show",
            "set",
            "cyclonedds",
            "fastrtps",
            "monitor",
            "status",
            "system",
            "reboot",
            "recovery",
            "info",
            "calibration",
            "status",
            "enable",
            "disable",
            "upload",
            "restore",
            "camera",
            "fps",
            "deep-flow",
            "enable",
            "disable",
            "logs",
            "fetch",
            "time",
            "show",
            "sync",
            "insight",
            "start",
            "pause",
            "stop",
            "ros",
            "domain-id",
            "topic",
            "set",
            "node-name",
            "camera-namespace",
            "camera-name",
            "looper",
            "control",
            "insight-start",
            "insight-pause",
            "insight-stop",
            "restore",
            "shallow",
            "deep",
            "recovery",
        ],
        help="Optional command path, for example: ota upgrade, network set, restore deep",
    )
    help_parser.set_defaults(func=help_command)

    current_parser = subparsers.add_parser(
        "current",
        help="Show the detected device endpoint and current firmware version",
        **_help_text(
            "Detect a reachable device endpoint and print the current firmware version.",
            [
                "python3 looper_cli.py current",
                "python3 looper_cli.py --device-base-url http://169.254.10.1 current",
            ],
        ),
    )
    current_parser.set_defaults(func=command_current)

    list_parser = subparsers.add_parser(
        "list",
        help="List published OTA releases for Insight Series devices",
        **_help_text(
            "List published OTA releases from the configured PocketBase OTA service.",
            [
                "python3 looper_cli.py list",
                "python3 looper_cli.py --per-page 20 list",
            ],
        ),
    )
    list_parser.set_defaults(func=command_list)

    upgrade_parser = subparsers.add_parser(
        "upgrade",
        help="Download, upload, and start an OTA Ota Update",
        **_help_text(
            "Upgrade the device to a specific published release or to the latest release.",
            [
                "python3 looper_cli.py upgrade --latest",
                "python3 looper_cli.py upgrade --version 1.2.3 -y",
                "python3 looper_cli.py upgrade --latest --watch-seconds 1200 -y",
            ],
        ),
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
        "device",
        help="Device inspection and identity commands",
        **_help_text(
            "Inspect the connected device and query device identity or version details.",
            [
                "python3 looper_cli.py device current",
                "python3 looper_cli.py device versions",
            ],
        ),
    )
    device_subparsers = device_parser.add_subparsers(
        dest="device_command", required=True
    )
    device_current = device_subparsers.add_parser(
        "current",
        help="Show the detected device endpoint and current firmware version",
        **_help_text(
            "Detect a reachable device endpoint and show the current firmware version.",
            ["python3 looper_cli.py device current"],
        ),
    )
    device_current.set_defaults(func=command_current)
    device_versions = device_subparsers.add_parser(
        "versions",
        help="Show softwareVersion and firewareVersion from the web dashboard API",
        **_help_text(
            "Show the dashboard-oriented software and firmware version fields.",
            ["python3 looper_cli.py device versions"],
        ),
    )
    device_versions.set_defaults(func=command_device_versions)

    network_parser = subparsers.add_parser(
        "network",
        help="Network configuration commands",
        **_help_text(
            "Show or update device IP configuration.",
            [
                "python3 looper_cli.py network show",
                "python3 looper_cli.py network set --segment 20 -y",
                "python3 looper_cli.py network set --master-ip 169.254.20.1 --slave-ip 169.254.20.2 -y",
            ],
        ),
    )
    network_subparsers = network_parser.add_subparsers(
        dest="network_command", required=True
    )
    network_show_parser = network_subparsers.add_parser(
        "show",
        help="Show current IP configuration",
        **_help_text(
            "Display the current device IP configuration.",
            ["python3 looper_cli.py network show"],
        ),
    )
    network_show_parser.set_defaults(func=command_network_show)
    network_set_parser = network_subparsers.add_parser(
        "set",
        help="Update IP configuration",
        **_help_text(
            "Update the device IP configuration using a segment shortcut or explicit IPs.",
            [
                "python3 looper_cli.py network set --segment 20 -y",
                "python3 looper_cli.py network set --master-ip 169.254.20.1 --slave-ip 169.254.20.2 -y",
            ],
        ),
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

    dds_parser = subparsers.add_parser(
        "dds",
        help="DDS configuration commands",
        **_help_text(
            "Show or update the DDS implementation used by the device.",
            [
                "python3 looper_cli.py dds show",
                "python3 looper_cli.py dds set cyclonedds -y",
            ],
        ),
    )
    dds_subparsers = dds_parser.add_subparsers(dest="dds_command", required=True)
    dds_show_parser = dds_subparsers.add_parser(
        "show",
        help="Show the current DDS implementation",
        **_help_text(
            "Display the DDS implementation currently configured on the device.",
            ["python3 looper_cli.py dds show"],
        ),
    )
    dds_show_parser.set_defaults(func=command_dds_show)
    dds_set_parser = dds_subparsers.add_parser(
        "set",
        help="Update the DDS implementation",
        **_help_text(
            "Switch the device DDS implementation.",
            [
                "python3 looper_cli.py dds set cyclonedds -y",
                "python3 looper_cli.py dds set fastrtps -y",
            ],
        ),
    )
    dds_set_parser.add_argument(
        "type", choices=["cyclonedds", "fastrtps"], help="Target DDS implementation"
    )
    dds_set_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    dds_set_parser.set_defaults(func=command_dds_set)

    monitor_parser = subparsers.add_parser(
        "monitor",
        help="System monitor and health commands",
        **_help_text(
            "Display a summarized device health view including CPU, memory, temperature, uptime, and IP.",
            [
                "python3 looper_cli.py monitor status",
                "python3 looper_cli.py monitor status --json",
            ],
        ),
    )
    monitor_subparsers = monitor_parser.add_subparsers(
        dest="monitor_command", required=True
    )
    monitor_status_parser = monitor_subparsers.add_parser(
        "status",
        help="Show CPU, memory, temperature, uptime, and IP summary",
        **_help_text(
            "Show a summarized system health view or print the raw JSON payload.",
            [
                "python3 looper_cli.py monitor status",
                "python3 looper_cli.py monitor status --json",
            ],
        ),
    )
    monitor_status_parser.add_argument(
        "--json", action="store_true", help="Print the raw monitor payload as JSON"
    )
    monitor_status_parser.set_defaults(func=command_monitor_status)

    ota_parser = subparsers.add_parser(
        "ota",
        help="OTA release and update commands",
        **_help_text(
            "OTA-specific command group. `list` and `upgrade` are also available as top-level shortcuts.",
            [
                "python3 looper_cli.py ota list",
                "python3 looper_cli.py ota upgrade --latest -y",
                "python3 looper_cli.py ota upgrade --version 1.2.3 --watch-seconds 1200",
            ],
        ),
    )
    ota_subparsers = ota_parser.add_subparsers(dest="ota_command", required=True)
    ota_list = ota_subparsers.add_parser(
        "list",
        help="List published OTA releases",
        **_help_text(
            "List published OTA releases from the configured OTA service.",
            ["python3 looper_cli.py ota list"],
        ),
    )
    ota_list.set_defaults(func=command_list)
    ota_upgrade = ota_subparsers.add_parser(
        "upgrade",
        help="Download, upload, and start an OTA Ota Update",
        **_help_text(
            "Upgrade the device to the latest release or a specified version.",
            [
                "python3 looper_cli.py ota upgrade --latest -y",
                "python3 looper_cli.py ota upgrade --version 1.2.3 --watch-seconds 1200 -y",
            ],
        ),
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

    system_parser = subparsers.add_parser(
        "system",
        help="System lifecycle commands",
        **_help_text(
            "Device lifecycle operations such as reboot, recovery, and system info.",
            [
                "python3 looper_cli.py system reboot -y",
                "python3 looper_cli.py system recovery shallow -y",
                "python3 looper_cli.py system info --json",
            ],
        ),
    )
    system_subparsers = system_parser.add_subparsers(
        dest="system_command", required=True
    )
    reboot_parser = system_subparsers.add_parser(
        "reboot",
        help="Reboot the device",
        **_help_text(
            "Reboot the target device.",
            ["python3 looper_cli.py system reboot -y"],
        ),
    )
    reboot_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    reboot_parser.set_defaults(func=command_reboot)
    recovery_parser = system_subparsers.add_parser(
        "recovery",
        help="Restore the system to the initial state of the current version or wipe software completely",
        **_help_text(
            "Run restore-to-factory recovery. Shallow keeps the current version; deep wipes software.",
            [
                "python3 looper_cli.py system recovery shallow -y",
                "python3 looper_cli.py system recovery deep -y",
            ],
        ),
    )
    recovery_parser.add_argument(
        "mode",
        choices=["shallow", "deep"],
        help="Recovery mode: shallow restores the current version state, deep deletes software and requires OTA again",
    )
    recovery_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    recovery_parser.add_argument(
        "--watch-seconds",
        type=int,
        default=6000,
        help="Seconds to keep streaming device-side recovery logs after the request starts",
    )
    recovery_parser.set_defaults(func=command_system_recovery)
    system_info_parser = system_subparsers.add_parser(
        "info",
        help="Show device system information",
        **_help_text(
            "Show device system information or print the raw JSON payload.",
            [
                "python3 looper_cli.py system info",
                "python3 looper_cli.py system info --json",
            ],
        ),
    )
    system_info_parser.add_argument(
        "--json", action="store_true", help="Print the raw system info payload as JSON"
    )
    system_info_parser.set_defaults(func=command_system_info_show)

    time_parser = subparsers.add_parser(
        "time",
        help="Device time commands",
        **_help_text(
            "Show the device time or synchronize the device clock with the local host.",
            [
                "python3 looper_cli.py time show",
                "python3 looper_cli.py time status",
                "python3 looper_cli.py time enable -y",
                "python3 looper_cli.py time disable -y",
                "python3 looper_cli.py time sync -y",
                "python3 looper_cli.py time sync --samples 30 --interval-ms 50 -y",
            ],
        ),
    )
    time_subparsers = time_parser.add_subparsers(dest="time_command", required=True)
    time_show_parser = time_subparsers.add_parser(
        "show",
        help="Show current device system time",
        **_help_text(
            "Show the device system time.",
            [
                "python3 looper_cli.py time show",
                "python3 looper_cli.py time show --json",
            ],
        ),
    )
    time_show_parser.add_argument(
        "--json", action="store_true", help="Print the raw time payload as JSON"
    )
    time_show_parser.set_defaults(func=command_system_time_show)
    time_status_parser = time_subparsers.add_parser(
        "status",
        help="Show NTP time synchronization status",
        **_help_text(
            "Show the same sync and enable status used by the Web Time Sync page.",
            [
                "python3 looper_cli.py time status",
                "python3 looper_cli.py time status --json",
            ],
        ),
    )
    time_status_parser.add_argument(
        "--json", action="store_true", help="Print the raw time sync payload as JSON"
    )
    time_status_parser.set_defaults(func=command_time_sync_status)
    time_enable_parser = time_subparsers.add_parser(
        "enable",
        help="Enable NTP time synchronization",
        **_help_text(
            "Enable the device NTP synchronization switch used by the Web Time Sync page.",
            ["python3 looper_cli.py time enable -y"],
        ),
    )
    time_enable_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    time_enable_parser.set_defaults(func=command_time_sync_enable)
    time_disable_parser = time_subparsers.add_parser(
        "disable",
        help="Disable NTP time synchronization",
        **_help_text(
            "Disable the device NTP synchronization switch used by the Web Time Sync page.",
            ["python3 looper_cli.py time disable -y"],
        ),
    )
    time_disable_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    time_disable_parser.set_defaults(func=command_time_sync_disable)
    time_sync_parser = time_subparsers.add_parser(
        "sync",
        help="Synchronize the device clock with the local host",
        **_help_text(
            "Synchronize device time using repeated RTT samples to estimate offset.",
            [
                "python3 looper_cli.py time sync -y",
                "python3 looper_cli.py time sync --samples 30 --interval-ms 50 -y",
            ],
        ),
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
    insight_parser = subparsers.add_parser(
        "insight",
        help="Insightfull control commands",
        **_help_text(
            "Start, pause, or stop Insightfull on the device.",
            [
                "python3 looper_cli.py insight start",
                "python3 looper_cli.py insight pause",
                "python3 looper_cli.py insight stop",
            ],
        ),
    )
    insight_subparsers = insight_parser.add_subparsers(
        dest="insight_command", required=True
    )
    insight_start_parser = insight_subparsers.add_parser(
        "start",
        help="Start insightfull",
        **_help_text("Start Insightfull.", ["python3 looper_cli.py insight start"]),
    )
    insight_start_parser.set_defaults(func=command_insight_start)
    insight_pause_parser = insight_subparsers.add_parser(
        "pause",
        help="Pause insightfull",
        **_help_text("Pause Insightfull.", ["python3 looper_cli.py insight pause"]),
    )
    insight_pause_parser.set_defaults(func=command_insight_pause)
    insight_stop_parser = insight_subparsers.add_parser(
        "stop",
        help="Stop insightfull",
        **_help_text(
            "Stop Insightfull. Falls back to pause endpoints on older firmware.",
            ["python3 looper_cli.py insight stop"],
        ),
    )
    insight_stop_parser.set_defaults(func=command_insight_stop)
    looper_parser = subparsers.add_parser(
        "looper",
        help="Looper control commands",
        **_help_text(
            "Looper-oriented aliases that mirror the Web Looper Control page.",
            [
                "python3 looper_cli.py looper reboot -y",
                "python3 looper_cli.py looper control reboot -y",
                "python3 looper_cli.py looper control insight-start",
            ],
        ),
    )
    looper_subparsers = looper_parser.add_subparsers(
        dest="looper_command", required=True
    )
    looper_reboot_parser = looper_subparsers.add_parser(
        "reboot",
        help="Reboot the Looper device",
        **_help_text(
            "Reboot the device through the Looper-oriented alias.",
            ["python3 looper_cli.py looper reboot -y"],
        ),
    )
    looper_reboot_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    looper_reboot_parser.set_defaults(func=command_reboot)
    looper_control_parser = looper_subparsers.add_parser(
        "control",
        help="Aliases that mirror the Web Looper Control page",
        **_help_text(
            "Control aliases that match the action layout of the Web Looper Control page.",
            [
                "python3 looper_cli.py looper control reboot -y",
                "python3 looper_cli.py looper control insight-start",
            ],
        ),
    )
    looper_control_subparsers = looper_control_parser.add_subparsers(
        dest="looper_control_command", required=True
    )
    looper_control_reboot_parser = looper_control_subparsers.add_parser(
        "reboot", help="Reboot the Looper device"
    )
    looper_control_reboot_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    looper_control_reboot_parser.set_defaults(func=command_reboot)
    looper_control_start_parser = looper_control_subparsers.add_parser(
        "insight-start", help="Start Insightfull"
    )
    looper_control_start_parser.set_defaults(func=command_insight_start)
    looper_control_pause_parser = looper_control_subparsers.add_parser(
        "insight-pause", help="Pause Insightfull"
    )
    looper_control_pause_parser.set_defaults(func=command_insight_pause)
    looper_control_stop_parser = looper_control_subparsers.add_parser(
        "insight-stop", help="Stop Insightfull"
    )
    looper_control_stop_parser.set_defaults(func=command_insight_stop)
    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore-to-factory commands from the Web system page",
        **_help_text(
            "Restore the current version state or wipe software completely.",
            [
                "python3 looper_cli.py restore shallow -y",
                "python3 looper_cli.py restore deep -y",
            ],
        ),
    )
    restore_subparsers = restore_parser.add_subparsers(
        dest="restore_command", required=True
    )
    restore_shallow_parser = restore_subparsers.add_parser(
        "shallow",
        help="Restore the initial state of the current version",
        **_help_text(
            "Restore the initial state of the currently installed version.",
            ["python3 looper_cli.py restore shallow -y"],
        ),
    )
    restore_shallow_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    restore_shallow_parser.add_argument(
        "--watch-seconds",
        type=int,
        default=6000,
        help="Seconds to keep streaming device-side recovery logs after the request starts",
    )
    restore_shallow_parser.set_defaults(
        func=command_system_recovery, mode="shallow"
    )
    restore_deep_parser = restore_subparsers.add_parser(
        "deep",
        help="Delete all software and require OTA upgrade again",
        **_help_text(
            "Delete software and require OTA installation again.",
            ["python3 looper_cli.py restore deep -y"],
        ),
    )
    restore_deep_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    restore_deep_parser.add_argument(
        "--watch-seconds",
        type=int,
        default=6000,
        help="Seconds to keep streaming device-side recovery logs after the request starts",
    )
    restore_deep_parser.set_defaults(func=command_system_recovery, mode="deep")
    recovery_alias_parser = subparsers.add_parser(
        "recovery",
        help="Alias of restore-to-factory commands",
        **_help_text(
            "Alias of `restore` for users who prefer the recovery naming.",
            [
                "python3 looper_cli.py recovery shallow -y",
                "python3 looper_cli.py recovery deep -y",
            ],
        ),
    )
    recovery_alias_subparsers = recovery_alias_parser.add_subparsers(
        dest="recovery_command", required=True
    )
    recovery_shallow_parser = recovery_alias_subparsers.add_parser(
        "shallow",
        help="Restore the initial state of the current version",
        **_help_text(
            "Alias of `restore shallow`.",
            ["python3 looper_cli.py recovery shallow -y"],
        ),
    )
    recovery_shallow_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    recovery_shallow_parser.add_argument(
        "--watch-seconds",
        type=int,
        default=6000,
        help="Seconds to keep streaming device-side recovery logs after the request starts",
    )
    recovery_shallow_parser.set_defaults(
        func=command_system_recovery, mode="shallow"
    )
    recovery_deep_parser = recovery_alias_subparsers.add_parser(
        "deep",
        help="Delete all software and require OTA upgrade again",
        **_help_text(
            "Alias of `restore deep`.",
            ["python3 looper_cli.py recovery deep -y"],
        ),
    )
    recovery_deep_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    recovery_deep_parser.add_argument(
        "--watch-seconds",
        type=int,
        default=6000,
        help="Seconds to keep streaming device-side recovery logs after the request starts",
    )
    recovery_deep_parser.set_defaults(func=command_system_recovery, mode="deep")
    calibration_parser = subparsers.add_parser(
        "calibration",
        help="Calibration mode and parameter commands",
        **_help_text(
            "Inspect calibration mode, toggle it, or upload calibration parameters.",
            [
                "python3 looper_cli.py calibration status",
                "python3 looper_cli.py calibration enable -y",
                "python3 looper_cli.py calibration upload calibration.json",
            ],
        ),
    )
    calibration_subparsers = calibration_parser.add_subparsers(
        dest="calibration_command", required=True
    )
    calibration_status_parser = calibration_subparsers.add_parser(
        "status",
        help="Show calibration mode status",
        **_help_text(
            "Show whether calibration mode is currently enabled.",
            ["python3 looper_cli.py calibration status"],
        ),
    )
    calibration_status_parser.set_defaults(func=command_calibration_status)
    calibration_enable_parser = calibration_subparsers.add_parser(
        "enable",
        help="Enable calibration mode",
        **_help_text(
            "Enable calibration mode on the device.",
            ["python3 looper_cli.py calibration enable -y"],
        ),
    )
    calibration_enable_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    calibration_enable_parser.set_defaults(func=command_calibration_enable)
    calibration_disable_parser = calibration_subparsers.add_parser(
        "disable",
        help="Disable calibration mode",
        **_help_text(
            "Disable calibration mode on the device.",
            ["python3 looper_cli.py calibration disable -y"],
        ),
    )
    calibration_disable_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    calibration_disable_parser.set_defaults(func=command_calibration_disable)
    calibration_restore_parser = calibration_subparsers.add_parser(
        "restore",
        help="Restore calibration backup files",
        **_help_text(
            "Restore backed-up calibration files from the device.",
            ["python3 looper_cli.py calibration restore -y"],
        ),
    )
    calibration_restore_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    calibration_restore_parser.set_defaults(func=command_calibration_restore)
    calibration_upload_parser = calibration_subparsers.add_parser(
        "upload",
        help="Upload calibration parameters to the device",
        **_help_text(
            "Upload a calibration parameter file to the device.",
            [
                "python3 looper_cli.py calibration upload calibration.json",
                "python3 looper_cli.py calibration upload calibration.json --endpoint /api/calibration/upload",
                "python3 looper_cli.py calibration upload calibration.json --endpoint /api/upload",
            ],
        ),
    )
    calibration_upload_parser.add_argument(
        "file", help="Path to the calibration parameter file"
    )
    calibration_upload_parser.add_argument(
        "--endpoint",
        help="Optional explicit device API path for calibration upload, for example /api/calibration/upload",
    )
    calibration_upload_parser.set_defaults(func=command_calibration_upload)

    camera_parser = subparsers.add_parser(
        "camera",
        help="Camera configuration commands",
        **_help_text(
            "Inspect or update camera FPS configuration.",
            [
                "python3 looper_cli.py camera fps",
                "python3 looper_cli.py camera fps --fps 30 -y",
            ],
        ),
    )
    camera_subparsers = camera_parser.add_subparsers(
        dest="camera_command", required=True
    )
    camera_fps_parser = camera_subparsers.add_parser(
        "fps",
        help="View or set the camera frame rate",
        **_help_text(
            "Get or set the camera FPS.",
            [
                "python3 looper_cli.py camera fps",
                "python3 looper_cli.py camera fps --fps 30 -y",
            ],
        ),
    )
    camera_fps_parser.add_argument(
        "--fps",
        choices=["20", "30", "60"],
        help="Optional target FPS value: 20, 30, or 60",
    )
    camera_fps_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the raw camera FPS JSON response",
    )
    camera_fps_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    camera_fps_parser.set_defaults(func=command_camera_fps)

    deep_flow_parser = subparsers.add_parser(
        "deep-flow",
        help="Deep flow switch commands",
        **_help_text(
            "Inspect or toggle the deep flow (depth estimation) switch shown on the Web Looper Control page.",
            [
                "python3 looper_cli.py deep-flow show",
                "python3 looper_cli.py deep-flow enable -y",
                "python3 looper_cli.py deep-flow disable -y",
            ],
        ),
    )
    deep_flow_subparsers = deep_flow_parser.add_subparsers(
        dest="deep_flow_command", required=True
    )
    deep_flow_show_parser = deep_flow_subparsers.add_parser(
        "show",
        help="Show the current deep flow switch state",
        **_help_text(
            "Show whether the deep flow switch is currently enabled.",
            [
                "python3 looper_cli.py deep-flow show",
                "python3 looper_cli.py deep-flow show --json",
            ],
        ),
    )
    deep_flow_show_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the raw deep flow JSON response",
    )
    deep_flow_show_parser.set_defaults(func=command_deep_flow_show)
    deep_flow_enable_parser = deep_flow_subparsers.add_parser(
        "enable",
        help="Enable the deep flow switch",
        **_help_text(
            "Enable deep flow on the device; the camera service restarts to apply the change.",
            ["python3 looper_cli.py deep-flow enable -y"],
        ),
    )
    deep_flow_enable_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    deep_flow_enable_parser.set_defaults(func=command_deep_flow_enable)
    deep_flow_disable_parser = deep_flow_subparsers.add_parser(
        "disable",
        help="Disable the deep flow switch",
        **_help_text(
            "Disable deep flow on the device; the camera service restarts to apply the change.",
            ["python3 looper_cli.py deep-flow disable -y"],
        ),
    )
    deep_flow_disable_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    deep_flow_disable_parser.set_defaults(func=command_deep_flow_disable)

    ros_parser = subparsers.add_parser(
        "ros",
        help="ROS configuration commands",
        **_help_text(
            "Show or update ROS configuration values, including ROS domain ID and camera ROS topic naming.",
            [
                "python3 looper_cli.py ros domain-id show",
                "python3 looper_cli.py ros domain-id set --ros-domain-id 1 -y",
                "python3 looper_cli.py ros topic show",
                "python3 looper_cli.py ros topic set --node-name insight_full --camera-namespace camera --camera-name camera -y",
            ],
        ),
    )
    ros_subparsers = ros_parser.add_subparsers(dest="ros_command", required=True)

    ros_domain_id_parser = ros_subparsers.add_parser(
        "domain-id",
        help="Show or update the ROS_DOMAIN_ID setting",
        **_help_text(
            "Show or update the ROS_DOMAIN_ID file setting.",
            [
                "python3 looper_cli.py ros domain-id show",
                "python3 looper_cli.py ros domain-id set --ros-domain-id 1 -y",
            ],
        ),
    )
    ros_domain_id_subparsers = ros_domain_id_parser.add_subparsers(
        dest="ros_domain_id_command", required=True
    )
    ros_domain_id_show_parser = ros_domain_id_subparsers.add_parser(
        "show",
        help="Show the current ROS domain ID",
        **_help_text(
            "Show the ROS_DOMAIN_ID currently configured on the device.",
            ["python3 looper_cli.py ros domain-id show"],
        ),
    )
    ros_domain_id_show_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the raw ROS domain ID JSON response",
    )
    ros_domain_id_show_parser.set_defaults(func=command_ros_domain_id_show)

    ros_domain_id_set_parser = ros_domain_id_subparsers.add_parser(
        "set",
        help="Update the ROS domain ID",
        **_help_text(
            "Update the ROS_DOMAIN_ID setting on the device.",
            ["python3 looper_cli.py ros domain-id set --ros-domain-id 1 -y"],
        ),
    )
    ros_domain_id_set_parser.add_argument(
        "--ros-domain-id",
        required=True,
        help="ROS_DOMAIN_ID value to write to the device",
    )
    ros_domain_id_set_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    ros_domain_id_set_parser.set_defaults(func=command_ros_domain_id_set)

    ros_topic_parser = ros_subparsers.add_parser(
        "topic",
        help="ROS topic camera naming configuration commands",
        **_help_text(
            "Show or update the ROS camera topic name configuration.",
            [
                "python3 looper_cli.py ros topic show",
                "python3 looper_cli.py ros topic set --node-name insight_full --camera-namespace camera --camera-name camera -y",
            ],
        ),
    )
    ros_topic_subparsers = ros_topic_parser.add_subparsers(
        dest="ros_topic_command", required=True
    )
    ros_topic_show_parser = ros_topic_subparsers.add_parser(
        "show",
        help="Show the current ROS topic camera config",
        **_help_text(
            "Show the ROS camera topic configuration stored on the device.",
            ["python3 looper_cli.py ros topic show"],
        ),
    )
    ros_topic_show_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the raw ROS topic config JSON response",
    )
    ros_topic_show_parser.set_defaults(func=command_ros_topic_show)

    ros_topic_set_parser = ros_topic_subparsers.add_parser(
        "set",
        help="Update the ROS topic camera name configuration",
        **_help_text(
            "Update the ROS camera topic name configuration on the device.",
            [
                "python3 looper_cli.py ros topic set --node-name insight_full --camera-namespace camera --camera-name camera -y",
            ],
        ),
    )
    ros_topic_set_parser.add_argument(
        "--node-name",
        required=True,
        help="ROS node name for the camera topic, e.g. insight_full",
    )
    ros_topic_set_parser.add_argument(
        "--camera-namespace",
        required=True,
        help="ROS namespace for the camera, e.g. camera",
    )
    ros_topic_set_parser.add_argument(
        "--camera-name",
        required=True,
        help="ROS camera name, e.g. camera",
    )
    ros_topic_set_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    ros_topic_set_parser.set_defaults(func=command_ros_topic_set)

    logs_parser = subparsers.add_parser(
        "logs",
        help="System log retrieval commands",
        **_help_text(
            "Fetch logs from the device, or fall back to a diagnostic snapshot when a log endpoint is unavailable.",
            [
                "python3 looper_cli.py logs fetch",
                "python3 looper_cli.py logs fetch --output device_logs.zip",
                "python3 looper_cli.py logs fetch --endpoint /api/system-logs/download",
            ],
        ),
    )
    logs_subparsers = logs_parser.add_subparsers(dest="logs_command", required=True)
    logs_fetch_parser = logs_subparsers.add_parser(
        "fetch",
        help="Fetch system logs from the device",
        **_help_text(
            "Fetch system logs or a diagnostic snapshot from the device.",
            [
                "python3 looper_cli.py logs fetch",
                "python3 looper_cli.py logs fetch --output device_logs.zip",
            ],
        ),
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
