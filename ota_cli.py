#!/usr/bin/env python3

import argparse
import base64
import concurrent.futures
import hashlib
import json
import os
import secrets
import socket
import struct
import sys
import threading
import time
import textwrap
from datetime import datetime
from typing import Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


PB_BASE_URL = "https://looper-robotics.com/pb"
DEFAULT_DEVICE_BASE_URL = "http://192.168.137.100"
DEFAULT_PER_PAGE = 50
UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024
DEVICE_DETECTION_TIMEOUT = 2.0
PRODUCT_NAME = "LooperRobotics Insight Series OTA CLI"
CLI_VERSION = "1.0.0"
DEVICE_BASE_URL_CANDIDATES = [
    "http://192.168.137.100",
    "http://looperrobotics.net",
    "http://169.254.10.1",
    "http://looper.local",
]
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
OUTPUT_LOCK = threading.Lock()
INLINE_STATUS_ACTIVE = False
INLINE_STATUS_WIDTH = 0


class OtaError(Exception):
    pass


def log(message: str) -> None:
    clear_inline_status()
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def clear_inline_status() -> None:
    global INLINE_STATUS_ACTIVE
    global INLINE_STATUS_WIDTH

    with OUTPUT_LOCK:
        if not INLINE_STATUS_ACTIVE:
            return
        sys.stdout.write("\r" + (" " * INLINE_STATUS_WIDTH) + "\r")
        sys.stdout.flush()
        INLINE_STATUS_ACTIVE = False
        INLINE_STATUS_WIDTH = 0


def render_inline_status(message: str) -> None:
    global INLINE_STATUS_ACTIVE
    global INLINE_STATUS_WIDTH

    with OUTPUT_LOCK:
        padded_width = max(INLINE_STATUS_WIDTH, len(message))
        sys.stdout.write("\r" + message.ljust(padded_width))
        sys.stdout.flush()
        INLINE_STATUS_ACTIVE = True
        INLINE_STATUS_WIDTH = padded_width


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def http_json(
    url: str,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60,
):
    request_headers = DEFAULT_HEADERS.copy()
    if headers:
        request_headers.update(headers)
    request = Request(url, data=data, headers=request_headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def normalize_device_base_url(url: str) -> str:
    return url.rstrip("/")


def http_post_bytes(
    url: str, data: bytes, headers: Optional[Dict[str, str]] = None
) -> None:
    request_headers = DEFAULT_HEADERS.copy()
    if headers:
        request_headers.update(headers)
    request = Request(url, data=data, headers=request_headers, method="POST")
    with urlopen(request, timeout=300) as response:
        response.read()


def normalize_device_base_url(url: str) -> str:
    return url.rstrip("/")


def normalize_product_names(data) -> List[str]:
    if isinstance(data, str):
        return [item.strip() for item in data.split(",") if item.strip()]
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    return []


def fetch_product_names(device_base_url: str) -> List[str]:
    payload = http_json(
        f"{normalize_device_base_url(device_base_url)}/api/ota/product-names",
        timeout=10,
    )
    if not isinstance(payload, dict):
        raise OtaError("Invalid OTA product names response")
    return normalize_product_names(payload.get("data"))


def fetch_product_records(pb_base_url: str, product_names: List[str]) -> dict:
    product_map = {}
    if not product_names:
        return product_map

    filter_expr = " || ".join(
        f'slug="{name}"' for name in product_names if name
    )
    if not filter_expr:
        return product_map

    query = urlencode({"filter": filter_expr, "perPage": 100})
    url = f"{pb_base_url}/api/collections/products/records?{query}"
    payload = http_json(url)
    items = payload.get("items", []) if payload else []
    if not isinstance(items, list):
        raise OtaError("Invalid products response payload")

    for item in items:
        slug = item.get("slug")
        if slug:
            product_map[str(slug)] = item
    return product_map


def filter_ota_records_by_device(
    records: List[dict], product_map: dict, product_names: List[str]
) -> List[dict]:
    if not product_names:
        return records

    id_set = {
        item.get("id")
        for item in product_map.values()
        if item.get("id")
    }
    slug_set = set(product_map.keys()) or {name for name in product_names if name}

    valid_records: List[dict] = []
    for record in records:
        product_field = record.get("product")
        if product_field is None:
            continue

        ota_products: List[str] = []
        if isinstance(product_field, list):
            ota_products = [str(p).strip() for p in product_field if str(p).strip()]
        elif isinstance(product_field, dict):
            candidate_slug = str(product_field.get("slug", "")).strip()
            candidate_id = str(product_field.get("id", "")).strip()
            ota_products = [value for value in (candidate_slug, candidate_id) if value]
        elif isinstance(product_field, str):
            ota_products = [p.strip() for p in product_field.split(",") if p.strip()]
        else:
            ota_products = [str(product_field).strip()]

        for ota_product in ota_products:
            if ota_product in slug_set or ota_product in id_set:
                valid_records.append(record)
                break

    return valid_records


def fetch_ota_records(pb_base_url: str, per_page: int = DEFAULT_PER_PAGE) -> List[dict]:
    query = urlencode({"page": 1, "perPage": per_page, "sort": "-created"})
    url = f"{pb_base_url}/api/collections/ota/records?{query}"
    payload = http_json(url)
    items = payload.get("items", []) if payload else []
    if not isinstance(items, list):
        raise OtaError("Invalid OTA response payload")
    return items


def fetch_ota_records_for_device(
    pb_base_url: str, device_base_url: str, per_page: int = DEFAULT_PER_PAGE
) -> List[dict]:
    records = fetch_ota_records(pb_base_url, per_page)
    try:
        product_names = fetch_product_names(device_base_url)
    except OtaError as exc:
        log(f"Warning: unable to fetch product names: {exc}")
        return records

    product_map = {}
    try:
        product_map = fetch_product_records(pb_base_url, product_names)
    except OtaError as exc:
        log(f"Warning: unable to fetch product metadata: {exc}")

    return filter_ota_records_by_device(records, product_map, product_names)


def normalize_version(version: str) -> List[int]:
    parts = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return parts


def normalize_manifest(manifest) -> dict:
    if not manifest:
        return {}
    if isinstance(manifest, str):
        try:
            return json.loads(manifest)
        except json.JSONDecodeError:
            return {}
    if isinstance(manifest, dict):
        return manifest
    return {}


def compare_version(current: str, target: str) -> int:
    def tokenize(value: str) -> List[str]:
        return re.findall(r"[0-9]+|[A-Za-z]+", str(value or "").strip())

    left = tokenize(current)
    right = tokenize(target)
    max_length = max(len(left), len(right))

    for index in range(max_length):
        left_token = left[index] if index < len(left) else "0"
        right_token = right[index] if index < len(right) else "0"

        try:
            left_number = int(left_token)
            left_is_number = True
        except ValueError:
            left_number = 0
            left_is_number = False

        try:
            right_number = int(right_token)
            right_is_number = True
        except ValueError:
            right_number = 0
            right_is_number = False

        if left_is_number and right_is_number:
            if left_number > right_number:
                return 1
            if left_number < right_number:
                return -1
            continue

        left_value = str(left_token).lower()
        right_value = str(right_token).lower()
        if left_value > right_value:
            return 1
        if left_value < right_value:
            return -1

    return 0


def filter_release_records(records: Iterable[dict]) -> List[dict]:
    release_records = [record for record in records if record.get("release") is True]
    return release_records or list(records)


def pick_latest_record(records: List[dict]) -> dict:
    if not records:
        raise OtaError("No OTA records found")
    release_records = filter_release_records(records)
    return sorted(
        release_records,
        key=lambda item: (
            normalize_version(item.get("manifest", {}).get("version", "0.0.0")),
            item.get("created", ""),
        ),
        reverse=True,
    )[0]


def find_record_by_version(records: List[dict], version: str) -> dict:
    for record in records:
        manifest = normalize_manifest(record.get("manifest"))
        if manifest.get("version") == version:
            return record
    raise OtaError(f"Version {version} not found")


def build_file_url(pb_base_url: str, record: dict, filename: str) -> str:
    collection = record.get("collectionId") or record.get("collectionName")
    record_id = record.get("id")
    if not collection or not record_id:
        raise OtaError("OTA record is missing collection or id")
    return f"{pb_base_url}/api/files/{collection}/{record_id}/{filename}"


def download_signature_base64(pb_base_url: str, record: dict) -> str:
    signature_name = record.get("signature")
    if not signature_name:
        return ""
    url = build_file_url(pb_base_url, record, signature_name)
    log(f"Downloading signature: {signature_name}")
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=120) as response:
        data = response.read()
    return base64.b64encode(data).decode("ascii")


def fetch_device_versions(device_base_url: str) -> dict:
    payload = http_json(f"{device_base_url}/api/ota/device-versions", timeout=10)
    if not isinstance(payload, dict):
        raise OtaError("Invalid OTA device versions response")
    return payload


def check_initial_version(device_base_url: str, initial_version: str) -> dict:
    payload = http_json(
        f"{device_base_url}/api/ota/initial-version-check",
        method="POST",
        data=json.dumps({"initialVersion": initial_version or ""}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    if not isinstance(payload, dict):
        raise OtaError("Invalid initial version check response")
    return payload


def filter_firmware_files(
    record: dict, filenames: List[str], device_versions: dict
) -> List[str] | None:
    manifest = normalize_manifest(record.get("manifest"))
    if not manifest.get("software_version") and not manifest.get("fireware_version"):
        return None

    filtered_files: List[str] = []
    software_version = device_versions.get("softwareVersion") or ""
    fireware_version = device_versions.get("firewareVersion") or ""

    for filename in filenames:
        if not manifest.get("software_version") and not manifest.get("fireware_version"):
            return None

        if filename.startswith("looperapp_"):
            log(
                f"Skip {filename}: raw package is skipped during incremental selection"
            )
            continue

        if (
            filename.startswith("update_")
            and manifest.get("software_version")
            and software_version
            and compare_version(software_version, manifest["software_version"]) >= 0
        ):
            log(
                f"Skip {filename}: current software version {software_version} >= target {manifest['software_version']}"
            )
            continue

        if (
            filename.startswith("all_in_one")
            and manifest.get("fireware_version")
            and fireware_version
            and compare_version(fireware_version, manifest["fireware_version"]) >= 0
        ):
            log(
                f"Skip {filename}: current fireware version {fireware_version} >= target {manifest['fireware_version']}"
            )
            continue

        filtered_files.append(filename)

    return filtered_files


class DeviceLogStreamer:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.inline_active = False

    def start(self) -> None:
        self.thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self.stop_event.set()
        self.thread.join(timeout=timeout)

    def _run(self) -> None:
        from urllib.parse import urlparse

        parsed = urlparse(self.ws_url)
        host = parsed.hostname
        port = parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        if not host:
            log("[device] invalid websocket host")
            return

        while not self.stop_event.is_set():
            sock = None
            try:
                sock = socket.create_connection((host, port), timeout=5)
                key = base64.b64encode(os.urandom(16)).decode("ascii")
                request = (
                    f"GET {path} HTTP/1.1\r\n"
                    f"Host: {host}:{port}\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Key: {key}\r\n"
                    "Sec-WebSocket-Version: 13\r\n\r\n"
                )
                sock.sendall(request.encode("ascii"))
                response = self._recv_http_headers(sock)
                if b" 101 " not in response.split(b"\r\n", 1)[0]:
                    raise OtaError(
                        f"websocket handshake failed: {response.splitlines()[0].decode('utf-8', 'replace')}"
                    )
                log("[device] websocket connected")
                sock.settimeout(1.0)
                while not self.stop_event.is_set():
                    try:
                        opcode, payload = self._read_frame(sock)
                    except socket.timeout:
                        continue
                    if opcode == 0x1:
                        text = payload.decode("utf-8", "replace")
                        if text:
                            self._print_device_text(text)
                    elif opcode == 0x8:
                        break
                    elif opcode == 0x9:
                        self._send_pong(sock, payload)
            except (OSError, TimeoutError, URLError, OtaError) as exc:
                if not self.stop_event.is_set():
                    log(f"[device] websocket reconnecting: {exc}")
                    time.sleep(2)
            finally:
                if self.inline_active:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    self.inline_active = False
                if sock:
                    try:
                        sock.close()
                    except OSError:
                        pass

    @staticmethod
    def _recv_http_headers(sock: socket.socket) -> bytes:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise OtaError("websocket closed during handshake")
            data += chunk
        return data

    @staticmethod
    def _read_exact(sock: socket.socket, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise OtaError("websocket connection closed")
            data += chunk
        return data

    def _read_frame(self, sock: socket.socket):
        header = self._read_exact(sock, 2)
        first, second = header[0], header[1]
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        payload_length = second & 0x7F
        if payload_length == 126:
            payload_length = struct.unpack("!H", self._read_exact(sock, 2))[0]
        elif payload_length == 127:
            payload_length = struct.unpack("!Q", self._read_exact(sock, 8))[0]
        mask_key = self._read_exact(sock, 4) if masked else b""
        payload = self._read_exact(sock, payload_length) if payload_length else b""
        if masked:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def _print_device_text(self, text: str) -> None:
        normalized = text.replace("\r\n", "\n")
        parts = normalized.split("\r")

        for index, part in enumerate(parts):
            if not part:
                continue

            is_inline = index > 0 and "\n" not in part
            if is_inline:
                sys.stdout.write("\r" + part)
                sys.stdout.flush()
                self.inline_active = True
                continue

            lines = part.split("\n")
            for line_index, line in enumerate(lines):
                if not line:
                    continue
                clear_inline_status()
                if self.inline_active:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    self.inline_active = False
                print(line, flush=True)
                if line_index < len(lines) - 1:
                    self.inline_active = False

    @staticmethod
    def _send_pong(sock: socket.socket, payload: bytes = b"") -> None:
        frame = bytearray()
        frame.append(0x8A)
        payload = payload or b""
        length = len(payload)
        mask_key = secrets.token_bytes(4)
        if length < 126:
            frame.append(0x80 | length)
        elif length < (1 << 16):
            frame.append(0x80 | 126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(0x80 | 127)
            frame.extend(struct.pack("!Q", length))
        frame.extend(mask_key)
        frame.extend(bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload)))
        sock.sendall(frame)


def upload_firmware_file(
    pb_base_url: str,
    device_base_url: str,
    record: dict,
    filename: str,
    task_id: str,
    signature_b64: str,
) -> None:
    manifest = json.dumps(normalize_manifest(record.get("manifest")), separators=(",", ":"))
    file_url = build_file_url(pb_base_url, record, filename)
    log(f"Streaming firmware: {filename}")
    request = Request(file_url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=120) as response:
        total_size = response.length
        if total_size is None:
            content_length = response.headers.get("Content-Length")
            total_size = int(content_length) if content_length else 0
        if not total_size:
            raise OtaError(f"Unknown file size for {filename}")

        log(f"File size: {total_size / 1024 / 1024:.2f} MB")
        uploaded = 0
        pending = bytearray()
        started_at = time.time()
        while True:
            chunk = response.read(1024 * 1024)
            if chunk:
                pending.extend(chunk)

            flush_chunk = bool(pending) and (
                (len(pending) >= UPLOAD_CHUNK_SIZE) or (not chunk)
            )
            if flush_chunk:
                query = urlencode(
                    {
                        "filename": filename,
                        "offset": str(uploaded),
                        "total": str(total_size),
                        "id": task_id,
                        "manifest": manifest,
                        "signature": signature_b64,
                    }
                )
                upload_url = f"{device_base_url}/api/ota/upload?{query}"
                http_post_bytes(
                    upload_url,
                    bytes(pending),
                    headers={"Content-Type": "application/octet-stream"},
                )
                uploaded += len(pending)
                pending = bytearray()

                elapsed = max(time.time() - started_at, 0.001)
                speed_mb = uploaded / elapsed / 1024 / 1024
                percent = int(uploaded * 100 / total_size)
                remaining_bytes = max(total_size - uploaded, 0)
                eta_seconds = remaining_bytes / max(uploaded / elapsed, 1)
                render_inline_status(
                    f"Upload progress {filename}: {percent}% "
                    f"({uploaded / 1024 / 1024:.2f}MB/{total_size / 1024 / 1024:.2f}MB) "
                    f"{speed_mb:.2f}MB/s ETA {format_duration(eta_seconds)}"
                )

            if not chunk:
                break

        if uploaded != total_size:
            raise OtaError(
                f"Uploaded size mismatch for {filename}: {uploaded} != {total_size}"
            )
        clear_inline_status()


def start_ota(device_base_url: str, task_id: str) -> None:
    start_url = f"{device_base_url}/api/ota/start?id={task_id}"
    request = Request(start_url, data=b"", method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except HTTPError as exc:
        message = exc.read().decode("utf-8", "replace")
        raise OtaError(
            f"Failed to start OTA ({exc.code}): {message or exc.reason}"
        ) from exc
    log("OTA process started")


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
    for candidate in DEVICE_BASE_URL_CANDIDATES:
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

    raise OtaError(
        "Unable to reach device version endpoint from any known address: "
        + ", ".join(candidates)
    )


def describe_record(record: dict) -> List[str]:
    manifest = normalize_manifest(record.get("manifest"))
    version = manifest.get("version", "unknown")
    release_date = manifest.get("releaseDate") or record.get("created", "")
    description = " ".join((manifest.get("description") or "").strip().split())
    file_count = len(record.get("firmware") or [])
    release_flag = "release" if record.get("release") else "non-release"
    record_id = record.get("id", "unknown")
    lines = [
        f"Version     : {version}",
        f"Release Date: {release_date}",
        f"Files       : {file_count}",
        f"Channel     : {release_flag}",
        f"Record ID   : {record_id}",
    ]
    if description:
        wrapped = textwrap.wrap(description, width=100)
        if wrapped:
            lines.append(f"Notes       : {wrapped[0]}")
            for chunk in wrapped[1:]:
                lines.append(f"              {chunk}")
        else:
            lines.append("Notes       : -")
    else:
        lines.append("Notes       : -")
    return lines


def current_status(args) -> int:
    device_base_url = resolve_device_base_url(args.device_base_url)
    current = get_device_version(device_base_url)
    print(PRODUCT_NAME)
    print(f"Device Endpoint : {device_base_url}")
    print(f"Current Version : {current or 'unknown'}")
    return 0


def list_versions(args) -> int:
    device_base_url = resolve_device_base_url(args.device_base_url)
    current = get_device_version(device_base_url)
    print(PRODUCT_NAME)
    print(f"Device Endpoint : {device_base_url}")
    print(f"Current Version : {current or 'unknown'}")
    print()

    records = fetch_ota_records_for_device(
        args.pb_base_url, device_base_url, args.per_page
    )
    for index, record in enumerate(filter_release_records(records), start=1):
        print(f"Release [{index}]")
        for line in describe_record(record):
            print(line)
        print()
    return 0


def run_upgrade(args) -> int:
    device_base_url = resolve_device_base_url(args.device_base_url)
    records = fetch_ota_records_for_device(
        args.pb_base_url, device_base_url, args.per_page
    )
    target = (
        pick_latest_record(records)
        if args.latest
        else find_record_by_version(records, args.version)
    )

    manifest = normalize_manifest(target.get("manifest"))
    version = manifest.get("version", "unknown")
    firmware_files = [filename for filename in (target.get("firmware") or []) if filename]
    if not firmware_files:
        raise OtaError(f"No firmware files found for version {version}")

    current = get_device_version(device_base_url)
    log(f"Resolved device endpoint: {device_base_url}")
    if current:
        log(f"Current firmware version: {current}")
    log(f"Target firmware version: {version}")
    log(f"Release record ID: {target.get('id')}")
    initial_version_result = check_initial_version(
        device_base_url, manifest.get("initial_version", "")
    )
    if initial_version_result.get("forceFullDownload"):
        log(
            "initial_version updated: "
            f"{initial_version_result.get('currentVersion') or 'empty'} -> "
            f"{initial_version_result.get('incomingVersion') or ''}, all files will be downloaded"
        )
        files_to_download = firmware_files
    else:
        log("Fetching current device versions...")
        device_versions = fetch_device_versions(device_base_url)
        log(
            "Current software version: "
            f"{device_versions.get('softwareVersion') or 'unknown'}, "
            f"fireware version: {device_versions.get('firewareVersion') or 'unknown'}"
        )
        files_to_download = filter_firmware_files(
            target, firmware_files, device_versions
        )

    if files_to_download is None or not files_to_download:
        raise OtaError(
            "No files need download; repeated upgrades or downgrades are not supported"
        )

    log(f"Firmware package count: {len(files_to_download)}")
    if not args.yes:
        answer = input("Proceed with OTA upgrade? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            log("Aborted by user")
            return 1

    task_id = hashlib.sha256(f"{time.time_ns()}-{version}".encode("utf-8")).hexdigest()[
        :24
    ]
    ws_url = urljoin(device_base_url, "/api/ota/ws").replace("http://", "ws://")
    log_streamer = DeviceLogStreamer(ws_url)
    log_streamer.start()

    try:
        signature_b64 = download_signature_base64(args.pb_base_url, target)
        for index, filename in enumerate(files_to_download, start=1):
            log(f"Downloading and uploading file: {filename} ({index}/{len(files_to_download)})")
            upload_firmware_file(
                args.pb_base_url,
                device_base_url,
                target,
                filename,
                task_id,
                signature_b64,
            )

        log("All firmware files uploaded")
        start_ota(device_base_url, task_id)

        if args.watch_seconds > 0:
            log(f"Watching device logs for {args.watch_seconds}s")
            time.sleep(args.watch_seconds)

        latest_version = get_device_version(device_base_url)
        if latest_version:
            log(f"Device version endpoint now reports: {latest_version}")
    finally:
        log_streamer.stop()

    return 0


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
            raise OtaError(f"Unknown help topic: {args.topic}")
        subparser.print_help()
    else:
        parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Official command-line utility for managing OTA release discovery "
            "and Ota Updates on LooperRobotics Insight Series cameras."
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
        help="Target device base URL; if omitted, the CLI auto-detects a reachable Insight device endpoint",
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
        "topic", nargs="?", choices=["help", "current", "list", "upgrade"]
    )
    help_parser.set_defaults(func=help_command)

    current_parser = subparsers.add_parser(
        "current", help="Show the detected device endpoint and current firmware version"
    )
    current_parser.set_defaults(func=current_status)

    list_parser = subparsers.add_parser(
        "list", help="List published OTA releases for Insight Series devices"
    )
    list_parser.set_defaults(func=list_versions)

    upgrade_parser = subparsers.add_parser(
        "upgrade", help="Download, upload, and start an OTA Ota Update"
    )
    target_group = upgrade_parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--version", help="Target firmware version, for example 1.2.3"
    )
    target_group.add_argument(
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
    upgrade_parser.set_defaults(func=run_upgrade)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        log("Interrupted")
        return 130
    except OtaError as exc:
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
