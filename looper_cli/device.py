import concurrent.futures
import json
from dataclasses import dataclass
import os
import statistics
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from looper_cli import DEFAULT_DEVICE_BASE_URLS, DEVICE_DETECTION_TIMEOUT, PRODUCT_NAME
from looper_cli.device_logs import DeviceLogStreamer
from looper_cli.errors import LooperCliError
from looper_cli.http import (
    DEFAULT_HEADERS,
    build_headers,
    http_get_bytes,
    http_json,
    http_post_bytes,
)
from looper_cli.output import log


CALIBRATION_MODE_ENDPOINT = "/api/mode"
CALIBRATION_UPLOAD_CANDIDATES = [
    "/api/calibration/upload",
    "/api/calibration/params",
    "/api/calibration",
    "/api/calibration-params/upload",
    "/api/upload",
]
RESTORE_ENDPOINT = "/api/restore"
CAMERA_FPS_ENDPOINT = "/api/camera-fps"
DEEP_FLOW_ENDPOINT = "/api/deep-flow"
ROS_DOMAIN_ID_ENDPOINT = "/api/ros-domain-id"
CAMERA_CONFIG_ENDPOINT = "/api/camera-config"
REBOOT_ENDPOINT_CANDIDATES = [
    "/api/reboot",
    "/api/cli-reboot",
    "/api/system/reboot",
    "/api/system-reboot",
]
LOG_DOWNLOAD_CANDIDATES = [
    "/api/system-logs/download",
    "/api/system/logs/download",
    "/api/logs/download",
    "/api/logs/export",
]
IP_CONFIG_ENDPOINT = "/api/ip-config"
DDS_TYPE_ENDPOINT = "/api/dds-type"
SYSTEM_TIME_ENDPOINT = "/api/system-time"
CPU_MONITOR_ENDPOINT = "/api/cpu-monitor"
MEMORY_MONITOR_ENDPOINT = "/api/memory-monitor"
SYSTEM_INFO_ENDPOINT = "/api/system-info"
TIME_SYNC_PING_ENDPOINT = "/api/time-sync/ping"
TIME_SYNC_SETTING_ENDPOINT = "/api/time-sync-setting"
SET_TIME_V2_ENDPOINT = "/api/set-time-v2"
INSIGHT_START_ENDPOINT_CANDIDATES = [
    "/api/insight-start",
    "/api/cli-insight-start",
]
INSIGHT_PAUSE_ENDPOINT_CANDIDATES = [
    "/api/insight-pause",
    "/api/cli-insight-pause",
]
INSIGHT_STOP_ENDPOINT_CANDIDATES = [
    "/api/insight-stop",
    "/api/cli-insight-stop",
    *INSIGHT_PAUSE_ENDPOINT_CANDIDATES,
]
OTA_DEVICE_VERSIONS_ENDPOINT = "/api/ota/device-versions"
SYSTEM_RECOVERY_ENDPOINT = "/api/system/recovery"


def normalize_device_base_url(url: str) -> str:
    return url.rstrip("/")


def get_device_version(device_base_url: str, timeout: float = 5.0) -> Optional[str]:
    try:
        payload = http_json(
            f"{normalize_device_base_url(device_base_url)}/api/version",
            timeout=timeout,
        )
    except (HTTPError, URLError, OSError, TimeoutError):
        return None
    if isinstance(payload, dict):
        return payload.get("version")
    return None


def resolve_device_base_url(configured_url: Optional[str] = None) -> str:
    candidates = []
    if configured_url:
        candidates.append(normalize_device_base_url(configured_url))
    for candidate in DEFAULT_DEVICE_BASE_URLS:
        normalized = normalize_device_base_url(candidate)
        if normalized not in candidates:
            candidates.append(normalized)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates)) as executor:
        future_map = {
            executor.submit(
                get_device_version, candidate, DEVICE_DETECTION_TIMEOUT
            ): candidate
            for candidate in candidates
        }
        for future in concurrent.futures.as_completed(future_map):
            candidate = future_map[future]
            version = future.result()
            if version:
                log(f"Resolved device endpoint: {candidate} (version {version})")
                executor.shutdown(wait=False, cancel_futures=True)
                return candidate

    raise LooperCliError(
        "Unable to reach device version endpoint from any known address: "
        + ", ".join(candidates)
    )


@dataclass
class DeviceSession:
    configured_base_url: Optional[str]
    resolved_base_url: Optional[str] = None
    current_version: Optional[str] = None

    def ensure_resolved(self) -> str:
        if self.resolved_base_url is None:
            self.resolved_base_url = resolve_device_base_url(self.configured_base_url)
        return self.resolved_base_url

    def ensure_version(self) -> Optional[str]:
        if self.current_version is None:
            self.current_version = get_device_version(self.ensure_resolved())
        return self.current_version


def get_ota_device_versions(session: DeviceSession) -> dict:
    payload = _device_json_get(session, OTA_DEVICE_VERSIONS_ENDPOINT)
    if not isinstance(payload, dict):
        raise LooperCliError("Failed to read OTA device versions")
    return {
        "softwareVersion": payload.get("softwareVersion") or "",
        "firewareVersion": payload.get("firewareVersion") or "",
    }


def _display_version(value: object) -> str:
    text = str(value or "").strip()
    return text or "--"


def print_current_status(session: DeviceSession) -> int:
    ota_versions = get_ota_device_versions(session)
    print(PRODUCT_NAME)
    print(f"Device Endpoint : {session.ensure_resolved()}")
    print(f"Current Version : {_display_version(session.ensure_version() or 'unknown')}")
    print(f"softwareVersion: {_display_version(ota_versions.get('softwareVersion'))}")
    print(f"firewareVersion: {_display_version(ota_versions.get('firewareVersion'))}")
    return 0


def device_versions_show(_args, session: DeviceSession) -> int:
    payload = get_ota_device_versions(session)
    _print_key_values(
        "Device Versions",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("softwareVersion", _display_version(payload.get("softwareVersion"))),
            ("firewareVersion", _display_version(payload.get("firewareVersion"))),
        ],
    )
    return 0


def print_json(data) -> None:
    print(json.dumps(data, indent=2))


def _device_url(session: DeviceSession, path: str) -> str:
    return f"{session.ensure_resolved()}{path}"


def _device_json_get(session: DeviceSession, path: str, timeout: float = 10.0):
    return http_json(_device_url(session, path), timeout=timeout)


def _device_json_post(
    session: DeviceSession, path: str, payload: dict, timeout: float = 30.0
):
    data = json.dumps(payload).encode("utf-8")
    return http_json(
        _device_url(session, path),
        method="POST",
        data=data,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )


def _print_key_values(title: str, entries: list[tuple[str, object]]) -> None:
    print(PRODUCT_NAME)
    print(title)
    for key, value in entries:
        print(f"{key:<16}: {value}")


def network_show(_args, session: DeviceSession) -> int:
    payload = _device_json_get(session, IP_CONFIG_ENDPOINT)
    if not isinstance(payload, dict) or not payload.get("success"):
        raise LooperCliError("Failed to read IP configuration")
    data = payload.get("data") or {}
    _print_key_values(
        "Network Configuration",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Master IP", data.get("masterIp", "unknown")),
            ("Slave IP", data.get("slaveIp", "unknown")),
        ],
    )
    return 0


def _segment_to_ips(segment: str) -> tuple[str, str]:
    try:
        segment_value = int(segment)
    except ValueError as exc:
        raise LooperCliError(
            "Network segment must be an integer, for example 10 or 20"
        ) from exc
    if segment_value < 10 or segment_value > 250:
        raise LooperCliError("Network segment must be between 10 and 250")
    return f"169.254.{segment_value}.1", f"169.254.{segment_value}.2"


def network_set(args, session: DeviceSession) -> int:
    if args.segment:
        master_ip, slave_ip = _segment_to_ips(args.segment)
    else:
        master_ip = args.master_ip
        slave_ip = args.slave_ip

    if not master_ip or not slave_ip:
        raise LooperCliError(
            "Provide either --segment <n> or both --master-ip and --slave-ip"
        )

    if not args.yes:
        answer = (
            input(
                f"Apply IP configuration master={master_ip} slave={slave_ip}? [y/N]: "
            )
            .strip()
            .lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1

    payload = _device_json_post(
        session,
        IP_CONFIG_ENDPOINT,
        {"masterIp": master_ip, "slaveIp": slave_ip},
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        message = (
            payload.get("message") if isinstance(payload, dict) else "request failed"
        )
        raise LooperCliError(f"IP configuration update failed: {message}")
    log(payload.get("message") or "IP configuration saved successfully")
    return 0


def dds_show(_args, session: DeviceSession) -> int:
    payload = _device_json_get(session, DDS_TYPE_ENDPOINT)
    if not isinstance(payload, dict) or not payload.get("success"):
        raise LooperCliError("Failed to read DDS type")
    current_dds = (payload.get("data") or {}).get("ddsType", "unknown")
    _print_key_values(
        "DDS Configuration",
        [("Device Endpoint", session.ensure_resolved()), ("DDS Type", current_dds)],
    )
    return 0


def dds_set(args, session: DeviceSession) -> int:
    target = args.type
    if not args.yes:
        answer = (
            input(f"Apply DDS type '{target}'? The device may reboot. [y/N]: ")
            .strip()
            .lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1
    payload = _device_json_post(session, DDS_TYPE_ENDPOINT, {"ddsType": target})
    if not isinstance(payload, dict) or not payload.get("success"):
        message = (
            payload.get("message") if isinstance(payload, dict) else "request failed"
        )
        raise LooperCliError(f"DDS type update failed: {message}")
    log(payload.get("message") or f"DDS type updated to {target}")
    return 0


def ros_domain_id_show(args, session: DeviceSession) -> int:
    payload = _device_json_get(session, ROS_DOMAIN_ID_ENDPOINT)
    if args.json:
        print_json(payload)
        return 0
    if not isinstance(payload, dict) or not payload.get("success"):
        raise LooperCliError("Failed to read ROS domain ID")
    data = payload.get("data") or {}
    _print_key_values(
        "ROS Domain ID",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("ROS Domain ID", data.get("rosDomainId", "unknown")),
        ],
    )
    return 0


def ros_domain_id_set(args, session: DeviceSession) -> int:
    if args.ros_domain_id is None:
        raise LooperCliError("Provide --ros-domain-id value")
    if not args.yes:
        answer = (
            input(f"Set ROS_DOMAIN_ID to {args.ros_domain_id}? [y/N]: ")
            .strip()
            .lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1
    payload = _device_json_post(
        session,
        ROS_DOMAIN_ID_ENDPOINT,
        {"rosDomainId": args.ros_domain_id},
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        message = (
            payload.get("message") if isinstance(payload, dict) else "request failed"
        )
        raise LooperCliError(f"ROS Domain ID update failed: {message}")
    log(payload.get("message") or f"ROS_DOMAIN_ID updated to {args.ros_domain_id}")
    return 0


def ros_topic_show(args, session: DeviceSession) -> int:
    payload = _device_json_get(session, CAMERA_CONFIG_ENDPOINT)
    if args.json:
        print_json(payload)
        return 0
    if not isinstance(payload, dict) or not payload.get("success"):
        raise LooperCliError("Failed to read ROS topic config")
    data = payload.get("data") or {}
    _print_key_values(
        "ROS Topic Config",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Node Name", data.get("nodeName", "unknown")),
            ("Camera Namespace", data.get("cameraNamespace", "unknown")),
            ("Camera Name", data.get("cameraName", "unknown")),
        ],
    )
    return 0


def ros_topic_set(args, session: DeviceSession) -> int:
    if not args.node_name or not args.camera_namespace or not args.camera_name:
        raise LooperCliError(
            "Provide --node-name, --camera-namespace and --camera-name"
        )
    if not args.yes:
        answer = (
            input(
                f"Set ROS topic config node_name={args.node_name} "
                f"camera_namespace={args.camera_namespace} camera_name={args.camera_name}? [y/N]: "
            )
            .strip()
            .lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1
    payload = _device_json_post(
        session,
        CAMERA_CONFIG_ENDPOINT,
        {
            "nodeName": args.node_name,
            "cameraNamespace": args.camera_namespace,
            "cameraName": args.camera_name,
        },
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        message = (
            payload.get("message") if isinstance(payload, dict) else "request failed"
        )
        raise LooperCliError(f"ROS topic config update failed: {message}")
    log(payload.get("message") or "ROS topic config updated successfully")
    return 0


def monitor_status(args, session: DeviceSession) -> int:
    payload = {
        "cpuMonitor": _device_json_get(session, CPU_MONITOR_ENDPOINT),
        "memoryMonitor": _device_json_get(session, MEMORY_MONITOR_ENDPOINT),
        "systemInfo": _device_json_get(session, SYSTEM_INFO_ENDPOINT),
        "ipConfig": _device_json_get(session, IP_CONFIG_ENDPOINT),
        "timeSyncSetting": _device_json_get(session, TIME_SYNC_SETTING_ENDPOINT),
        "deviceVersions": get_ota_device_versions(session),
    }
    if args.json:
        print_json(payload)
        return 0

    cpu_data = payload["cpuMonitor"] or {}
    memory_data = payload["memoryMonitor"] or {}
    system_data = payload["systemInfo"] or {}
    ip_data = (payload["ipConfig"] or {}).get("data") or {}
    time_sync_data = (payload["timeSyncSetting"] or {}).get("data") or {}
    version_data = payload["deviceVersions"] or {}
    _print_key_values(
        "System Monitor",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Average CPU", f"{cpu_data.get('average', 0):.2f}%"),
            ("Memory Usage", f"{memory_data.get('usage', 0):.2f}%"),
            ("Temperature", f"{system_data.get('temperature', 0):.1f}C"),
            ("Uptime", system_data.get("uptimeStr", "unknown")),
            ("Master IP", ip_data.get("masterIp", "unknown")),
            ("Time Sync", "success" if time_sync_data.get("synced") else "failed"),
            ("Time Sync Enable", "on" if time_sync_data.get("enabled") else "off"),
            ("softwareVersion", _display_version(version_data.get("softwareVersion"))),
            ("firewareVersion", _display_version(version_data.get("firewareVersion"))),
        ],
    )
    return 0


def system_time_show(args, session: DeviceSession) -> int:
    payload = _device_json_get(session, SYSTEM_TIME_ENDPOINT)
    if args.json:
        print_json(payload)
        return 0
    _print_key_values(
        "System Time",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Formatted", payload.get("formatted", "unknown")),
            ("Timestamp", payload.get("timestamp", "unknown")),
            ("Timestamp Nanos", payload.get("timestampNanos", "unknown")),
        ],
    )
    return 0


def time_sync_status(args, session: DeviceSession) -> int:
    payload = _device_json_get(session, TIME_SYNC_SETTING_ENDPOINT)
    if not isinstance(payload, dict) or not payload.get("success"):
        raise LooperCliError("Failed to read time sync status")
    if args.json:
        print_json(payload)
        return 0

    data = payload.get("data") or {}
    _print_key_values(
        "Time Synchronization",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Sync Status", "success" if data.get("synced") else "failed"),
            ("Enable Status", "on" if data.get("enabled") else "off"),
        ],
    )
    return 0


def time_sync_set_enabled(args, session: DeviceSession, enabled: bool) -> int:
    action = "enable" if enabled else "disable"
    if not args.yes:
        answer = (
            input(f"Proceed to {action} NTP time synchronization? [y/N]: ")
            .strip()
            .lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1

    payload = _device_json_post(
        session,
        TIME_SYNC_SETTING_ENDPOINT,
        {"enabled": enabled},
        timeout=30.0,
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        message = (
            payload.get("message") if isinstance(payload, dict) else "request failed"
        )
        raise LooperCliError(f"Time sync setting update failed: {message}")

    data = payload.get("data") or {}
    log(payload.get("message") or "Time sync setting saved")
    _print_key_values(
        "Time Synchronization",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Sync Status", "success" if data.get("synced") else "failed"),
            ("Enable Status", "on" if data.get("enabled") else "off"),
        ],
    )
    return 0


def system_info_show(args, session: DeviceSession) -> int:
    payload = _device_json_get(session, SYSTEM_INFO_ENDPOINT)
    if args.json:
        print_json(payload)
        return 0
    _print_key_values(
        "System Info",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Temperature", f"{payload.get('temperature', 0):.1f}C"),
            ("Uptime Hours", payload.get("uptimeHours", "unknown")),
            ("Uptime", payload.get("uptimeStr", "unknown")),
        ],
    )
    return 0


def system_sync_time(args, session: DeviceSession) -> int:
    sample_count = args.samples
    interval_ms = args.interval_ms
    measurements = []
    log(f"Collecting {sample_count} latency samples")
    for measurement_id in range(sample_count):
        client_send_time = int(time.time() * 1000)
        response = _device_json_post(
            session,
            TIME_SYNC_PING_ENDPOINT,
            {"clientTime": client_send_time, "measurementId": measurement_id},
            timeout=5.0,
        )
        client_recv_time = int(time.time() * 1000)
        _ = response
        rtt = client_recv_time - client_send_time
        measurements.append(
            {
                "id": measurement_id,
                "clientSendTime": client_send_time,
                "clientRecvTime": client_recv_time,
                "rtt": rtt,
            }
        )
        if measurement_id < sample_count - 1:
            time.sleep(interval_ms / 1000.0)

    measurements.sort(key=lambda item: item["rtt"])
    selected_count = max(1, int((sample_count + 1) / 2))
    selected = measurements[:selected_count]
    rtts = [item["rtt"] for item in selected]
    min_rtt = min(rtts)
    median_rtt = statistics.median(rtts)
    avg_rtt = statistics.mean(rtts)
    frontend_current_time_ms = int(time.time() * 1000)
    target_time_ms = int(frontend_current_time_ms + round(median_rtt / 2.0))

    if not args.yes:
        answer = (
            input(
                f"Sync device time using median RTT {median_rtt:.1f} ms and target {target_time_ms}? [y/N]: "
            )
            .strip()
            .lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1

    payload = _device_json_post(
        session,
        SET_TIME_V2_ENDPOINT,
        {
            "frontendCurrentTimeMs": frontend_current_time_ms,
            "targetTimeMs": target_time_ms,
            "minRTT": min_rtt,
            "medianRTT": median_rtt,
            "avgRTT": avg_rtt,
            "pingMeasurements": selected,
            "totalMeasurements": len(measurements),
            "qualityMeasurements": len(selected),
            "measurementMethod": "best-rtt-selection",
        },
        timeout=10.0,
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        message = (
            payload.get("error") if isinstance(payload, dict) else "request failed"
        )
        raise LooperCliError(f"Time sync failed: {message}")
    log(
        f"Device time synchronized successfully (min RTT {min_rtt} ms, median RTT {median_rtt:.1f} ms, samples {len(selected)}/{len(measurements)})"
    )
    return 0


def reboot_device(args, session: DeviceSession) -> int:
    if not args.yes:
        answer = input("Proceed with device reboot? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1

    errors = []
    for path in REBOOT_ENDPOINT_CANDIDATES:
        for payload in ({}, {"action": "reboot"}):
            try:
                response = _device_json_post(session, path, payload)
                if not isinstance(response, dict) or response.get("success", True):
                    log(f"Reboot command accepted via {path}")
                    if isinstance(response, dict) and response.get("message"):
                        log(response["message"])
                    return 0
                errors.append(f"{path}: {response.get('message', 'request rejected')}")
            except HTTPError as exc:
                if exc.code == 404:
                    continue
                message = exc.read().decode("utf-8", "replace")
                errors.append(f"{path}: HTTP {exc.code} {message or exc.reason}")
            except (URLError, OSError, TimeoutError) as exc:
                errors.append(f"{path}: {exc}")

    raise LooperCliError(
        "No supported reboot endpoint was detected on the current device firmware. "
        + (f"Last errors: {'; '.join(errors[:3])}" if errors else "")
    )


def _try_post_candidates(
    session: DeviceSession, candidates: list[str], payload: dict, action_name: str
):
    errors = []
    for path in candidates:
        try:
            response = _device_json_post(session, path, payload)
            if not isinstance(response, dict) or response.get("success", True):
                return path, response
            errors.append(f"{path}: {response.get('message', 'request rejected')}")
        except HTTPError as exc:
            if exc.code == 404:
                continue
            message = exc.read().decode("utf-8", "replace")
            errors.append(f"{path}: HTTP {exc.code} {message or exc.reason}")
        except (URLError, OSError, TimeoutError) as exc:
            errors.append(f"{path}: {exc}")
    raise LooperCliError(
        f"Failed to {action_name}. "
        + (f"Last errors: {'; '.join(errors[:3])}" if errors else "No supported endpoint detected.")
    )


def insightfull_start(_arg, session: DeviceSession) -> int:
    path, payload = _try_post_candidates(
        session, INSIGHT_START_ENDPOINT_CANDIDATES, {}, "start insightfull"
    )
    message = payload.get("message") if isinstance(payload, dict) else None
    log(message or f"Insightfull started successfully via {path}")
    return 0


def insightfull_pause(_arg, session: DeviceSession) -> int:
    path, payload = _try_post_candidates(
        session, INSIGHT_PAUSE_ENDPOINT_CANDIDATES, {}, "pause insightfull"
    )
    message = payload.get("message") if isinstance(payload, dict) else None
    log(message or f"Insightfull paused successfully via {path}")
    return 0


def insightfull_stop(_arg, session: DeviceSession) -> int:
    path, payload = _try_post_candidates(
        session, INSIGHT_STOP_ENDPOINT_CANDIDATES, {}, "stop insightfull"
    )
    message = payload.get("message") if isinstance(payload, dict) else None
    log(message or f"Insightfull stopped successfully via {path}")
    return 0


def system_recovery(args, session: DeviceSession) -> int:
    mode = str(args.mode or "").strip().lower()
    if mode not in {"shallow", "deep"}:
        raise LooperCliError("Recovery mode must be either 'shallow' or 'deep'")

    if mode == "shallow":
        description = "restore the initial state of the current version"
    else:
        description = "delete all software and require OTA upgrade again"

    if not args.yes:
        answer = (
            input(f"Proceed with {mode} recovery and {description}? [y/N]: ")
            .strip()
            .lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1

    device_base_url = session.ensure_resolved()
    log(f"Resolved device endpoint: {device_base_url}")
    log(f"Recovery mode: {mode}")

    ws_url = urljoin(device_base_url, "/api/ota/ws").replace("http://", "ws://")
    log_streamer = DeviceLogStreamer(ws_url)
    log_streamer.start()
    try:
        payload = _device_json_post(
            session,
            SYSTEM_RECOVERY_ENDPOINT,
            {"mode": mode},
            timeout=30.0,
        )
        if isinstance(payload, dict) and not payload.get("success", True):
            raise LooperCliError(
                f"{mode} recovery request failed: {payload.get('message') or 'request rejected'}"
            )

        message = payload.get("message") if isinstance(payload, dict) else None
        log(message or f"{mode} recovery started successfully")
        watch_seconds = max(int(getattr(args, "watch_seconds", 6000) or 0), 0)
        if watch_seconds > 0:
            log(f"Watching device logs for {watch_seconds}s")
            time.sleep(watch_seconds)
    finally:
        log_streamer.stop()
    return 0


def calibration_restore(args, session: DeviceSession) -> int:
    if not args.yes:
        answer = input(
            "Proceed with restoring calibration backup files? [y/N]: "
        ).strip().lower()
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1

    payload = _device_json_post(session, RESTORE_ENDPOINT, {}, timeout=30.0)
    if isinstance(payload, dict) and not payload.get("success", True):
        raise LooperCliError(
            f"Calibration restore failed: {payload.get('message') or 'request rejected'}"
        )

    message = payload.get("message") if isinstance(payload, dict) else None
    log(message or "Calibration restore completed successfully")
    return 0


def camera_fps(args, session: DeviceSession) -> int:
    if args.fps:
        if args.fps not in {"20", "30", "60"}:
            raise LooperCliError("Invalid fps. Supported values are 20, 30, or 60")
        if not args.yes:
            answer = input(
                f"Set camera FPS to {args.fps}? [y/N]: "
            ).strip().lower()
            if answer not in {"y", "yes"}:
                log("Aborted by user")
                return 1

        payload = _device_json_post(
            session,
            CAMERA_FPS_ENDPOINT,
            {"fps": args.fps},
            timeout=30.0,
        )
        if isinstance(payload, dict) and not payload.get("success", True):
            raise LooperCliError(
                f"Camera FPS update failed: {payload.get('message') or 'request rejected'}"
            )
        message = payload.get("message") if isinstance(payload, dict) else None
        log(message or f"Camera FPS set to {args.fps}")
        return 0

    payload = _device_json_get(session, CAMERA_FPS_ENDPOINT)
    if not isinstance(payload, dict) or not payload.get("success", True):
        raise LooperCliError("Failed to read camera FPS")

    data = payload.get("data") or {}
    fps_value = data.get("fps") or "unknown"

    if args.json:
        print_json(payload)
        return 0

    _print_key_values(
        "Camera FPS",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Current FPS", fps_value),
        ],
    )
    return 0


def deep_flow_show(args, session: DeviceSession) -> int:
    payload = _device_json_get(session, DEEP_FLOW_ENDPOINT)
    if not isinstance(payload, dict) or not payload.get("success", True):
        raise LooperCliError("Failed to read deep flow status")

    if args.json:
        print_json(payload)
        return 0

    data = payload.get("data") or {}
    if "enabled" in data:
        state = "on" if data.get("enabled") else "off"
    else:
        # Some firmware returns success without echoing the stored state.
        state = "unknown"

    _print_key_values(
        "Deep Flow",
        [
            ("Device Endpoint", session.ensure_resolved()),
            ("Deep Flow", state),
        ],
    )
    return 0


def deep_flow_set(args, session: DeviceSession, enabled: bool) -> int:
    action = "enable" if enabled else "disable"
    if not args.yes:
        answer = (
            input(f"Proceed to {action} deep flow? [y/N]: ").strip().lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1

    payload = _device_json_post(
        session,
        DEEP_FLOW_ENDPOINT,
        {"enabled": enabled},
        timeout=30.0,
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        message = (
            payload.get("message") if isinstance(payload, dict) else "request failed"
        )
        raise LooperCliError(f"Deep flow update failed: {message}")
    log(payload.get("message") or f"Deep flow {action}d successfully")
    return 0


def calibration_status(_args, session: DeviceSession) -> int:
    payload = _device_json_get(session, CALIBRATION_MODE_ENDPOINT)
    if not isinstance(payload, dict) or not payload.get("success"):
        raise LooperCliError("Failed to read calibration mode status")
    current_mode = bool((payload.get("data") or {}).get("calibrationMode", False))
    print(PRODUCT_NAME)
    print(f"Device Endpoint   : {session.ensure_resolved()}")
    print(f"Calibration Mode : {'enabled' if current_mode else 'disabled'}")
    return 0


def calibration_set_mode(args, session: DeviceSession, enabled: bool) -> int:
    mode_name = "enable" if enabled else "disable"
    if not args.yes:
        answer = (
            input(f"Proceed with calibration mode {mode_name}? [y/N]: ").strip().lower()
        )
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1
    payload = _device_json_post(
        session, CALIBRATION_MODE_ENDPOINT, {"action": mode_name}
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        message = (
            payload.get("message") if isinstance(payload, dict) else "request failed"
        )
        raise LooperCliError(f"Calibration mode update failed: {message}")
    log(payload.get("message") or f"Calibration mode {mode_name}d successfully")
    return 0


def _build_multipart_body(file_path: str, field_name: str = "file"):
    boundary = f"----LooperCliBoundary{os.getpid()}"
    file_name = os.path.basename(file_path)
    with open(file_path, "rb") as handle:
        file_bytes = handle.read()
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8"),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return boundary, b"".join(parts)


def calibration_upload(args, session: DeviceSession) -> int:
    if not os.path.exists(args.file):
        raise LooperCliError(f"Calibration file not found: {args.file}")

    boundary, body = _build_multipart_body(args.file)
    errors = []
    custom_candidates = [args.endpoint] if args.endpoint else []
    candidates = [
        path for path in custom_candidates + CALIBRATION_UPLOAD_CANDIDATES if path
    ]
    file_name = os.path.basename(args.file)

    for path in candidates:
        url = _device_url(session, path)
        try:
            request = Request(
                url,
                data=body,
                headers=build_headers(
                    {"Content-Type": f"multipart/form-data; boundary={boundary}"}
                ),
                method="POST",
            )
            with urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8", "replace")
            if raw:
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"success": True, "message": raw}
            else:
                payload = {"success": True}
            if payload.get("success", True):
                log(f"Calibration file uploaded successfully via {path}")
                if payload.get("message"):
                    log(payload["message"])
                return 0
            errors.append(f"{path}: {payload.get('message', 'upload rejected')}")
        except HTTPError as exc:
            if exc.code == 404:
                continue
            message = exc.read().decode("utf-8", "replace")
            errors.append(f"{path}: HTTP {exc.code} {message or exc.reason}")
        except (URLError, OSError, TimeoutError) as exc:
            errors.append(f"{path}: {exc}")

    raise LooperCliError(
        "No supported calibration upload endpoint was detected on the current device firmware. "
        + (f"Tried {file_name}. " if file_name else "")
        + (f"Last errors: {'; '.join(errors[:3])}" if errors else "")
    )


def _build_system_snapshot(session: DeviceSession) -> dict:
    return {
        "deviceEndpoint": session.ensure_resolved(),
        "version": session.ensure_version(),
        "systemTime": _device_json_get(session, "/api/system-time"),
        "timeSyncSetting": _device_json_get(session, TIME_SYNC_SETTING_ENDPOINT),
        "ipConfig": _device_json_get(session, "/api/ip-config"),
        "ddsType": _device_json_get(session, "/api/dds-type"),
        "calibrationMode": _device_json_get(session, CALIBRATION_MODE_ENDPOINT),
        "cpuMonitor": _device_json_get(session, "/api/cpu-monitor"),
        "memoryMonitor": _device_json_get(session, "/api/memory-monitor"),
        "systemInfo": _device_json_get(session, "/api/system-info"),
    }


def fetch_logs(args, session: DeviceSession) -> int:
    errors = []
    custom_candidates = [args.endpoint] if args.endpoint else []
    candidates = [path for path in custom_candidates + LOG_DOWNLOAD_CANDIDATES if path]
    for path in candidates:
        try:
            data = http_get_bytes(_device_url(session, path), timeout=120)
            if data:
                if args.output:
                    with open(args.output, "wb") as handle:
                        handle.write(data)
                    log(f"System logs written to {args.output}")
                else:
                    try:
                        print(data.decode("utf-8"), end="")
                    except UnicodeDecodeError:
                        raise LooperCliError(
                            "Binary log content received. Re-run with --output to save the file."
                        )
                return 0
        except HTTPError as exc:
            if exc.code == 404:
                continue
            message = exc.read().decode("utf-8", "replace")
            errors.append(f"{path}: HTTP {exc.code} {message or exc.reason}")
        except (URLError, OSError, TimeoutError) as exc:
            errors.append(f"{path}: {exc}")

    snapshot = _build_system_snapshot(session)
    output = json.dumps(snapshot, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")
        log(
            f"No native log download endpoint was detected; wrote diagnostic snapshot to {args.output}"
        )
    else:
        print(output)
        log(
            "No native log download endpoint was detected; emitted a diagnostic system snapshot instead"
        )
    return 0
