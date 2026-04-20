import base64
import hashlib
import json
import os
import re
import secrets
import socket
import struct
import sys
import textwrap
import threading
import time
from typing import Iterable, List
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from looper_cli import DEFAULT_PER_PAGE, PB_BASE_URL, PRODUCT_NAME, UPLOAD_CHUNK_SIZE
from looper_cli.device import DeviceSession, get_device_version
from looper_cli.errors import LooperCliError
from looper_cli.http import DEFAULT_HEADERS, http_json, http_post_bytes, open_request
from looper_cli.output import (
    clear_inline_status,
    format_duration,
    log,
    render_inline_status,
)


def fetch_ota_records(pb_base_url: str, per_page: int = DEFAULT_PER_PAGE) -> List[dict]:
    query = urlencode({"page": 1, "perPage": per_page, "sort": "-created"})
    url = f"{pb_base_url}/api/collections/ota/records?{query}"
    payload = http_json(url)
    items = payload.get("items", []) if payload else []
    if not isinstance(items, list):
        raise LooperCliError("Invalid OTA response payload")
    return items


def normalize_version(version: str) -> List[int]:
    parts = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return parts


def filter_release_records(records: Iterable[dict]) -> List[dict]:
    release_records = [record for record in records if record.get("release") is True]
    return release_records or list(records)


def pick_latest_record(records: List[dict]) -> dict:
    if not records:
        raise LooperCliError("No OTA records found")
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
        manifest = record.get("manifest") or {}
        if manifest.get("version") == version:
            return record
    raise LooperCliError(f"Version {version} not found")


def build_file_url(pb_base_url: str, record: dict, filename: str) -> str:
    collection = record.get("collectionId") or record.get("collectionName")
    record_id = record.get("id")
    if not collection or not record_id:
        raise LooperCliError("OTA record is missing collection or id")
    return f"{pb_base_url}/api/files/{collection}/{record_id}/{filename}"


def download_signature_base64(pb_base_url: str, record: dict) -> str:
    signature_name = record.get("signature")
    if not signature_name:
        return ""
    url = build_file_url(pb_base_url, record, signature_name)
    log(f"Downloading signature: {signature_name}")
    data = open_request(url, headers=DEFAULT_HEADERS, timeout=120).read()
    return base64.b64encode(data).decode("ascii")


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
                    raise LooperCliError(
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
            except (OSError, TimeoutError, LooperCliError) as exc:
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
                raise LooperCliError("websocket closed during handshake")
            data += chunk
        return data

    @staticmethod
    def _read_exact(sock: socket.socket, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise LooperCliError("websocket connection closed")
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
            for line in lines:
                if not line:
                    continue
                clear_inline_status()
                if self.inline_active:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    self.inline_active = False
                print(line, flush=True)

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
    manifest = json.dumps(record.get("manifest") or {}, separators=(",", ":"))
    file_url = build_file_url(pb_base_url, record, filename)
    log(f"Streaming firmware: {filename}")
    with open_request(file_url, headers=DEFAULT_HEADERS, timeout=120) as response:
        total_size = response.length
        if total_size is None:
            content_length = response.headers.get("Content-Length")
            total_size = int(content_length) if content_length else 0
        if not total_size:
            raise LooperCliError(f"Unknown file size for {filename}")
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
            raise LooperCliError(
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
        raise LooperCliError(
            f"Failed to start OTA ({exc.code}): {message or exc.reason}"
        ) from exc
    log("OTA process started")


def describe_record(record: dict) -> List[str]:
    manifest = record.get("manifest") or {}
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
    note_lines = format_release_notes(description)
    if note_lines:
        lines.append(f"Notes       : {note_lines[0]}")
        for chunk in note_lines[1:]:
            lines.append(f"              {chunk}")
    else:
        lines.append("Notes       : -")
    return lines


def format_release_notes(description: str) -> List[str]:
    if not description:
        return []

    normalized = re.sub(r"\s+", " ", description).strip()
    normalized = re.sub(r"(?i)\b(Update Log|Important Notes)\b", r"\n\1", normalized)
    normalized = re.sub(r"(?:(?<=^)|(?<=\s))(\d+)\.(?=[A-Z`])", r"\n\1. ", normalized)
    normalized = re.sub(
        r"(?:(?<=^)|(?<=\s))(\d+)\.\s+(?=[A-Z`])", r"\n\1. ", normalized
    )
    parts = [part.strip() for part in normalized.split("\n") if part.strip()]

    lines: List[str] = []
    for part in parts:
        if re.fullmatch(r"(?i)update log|important notes", part):
            if lines:
                lines.append("")
            lines.append(part)
            continue

        indent = "  " if re.match(r"^\d+\.\s", part) else ""
        wrapped = textwrap.wrap(
            part,
            width=96,
            initial_indent=indent,
            subsequent_indent="    " if indent else "  ",
        )
        if (
            lines
            and lines[-1] != ""
            and not re.fullmatch(r"(?i)update log|important notes", lines[-1])
        ):
            lines.append("")
        lines.extend(wrapped or [part])

    compacted: List[str] = []
    for line in lines:
        if line == "" and (not compacted or compacted[-1] == ""):
            continue
        compacted.append(line)
    if compacted and compacted[-1] == "":
        compacted.pop()
    return compacted


def print_release_list(args, session: DeviceSession) -> int:
    print(PRODUCT_NAME)
    print(f"Device Endpoint : {session.ensure_resolved()}")
    print(f"Current Version : {session.ensure_version() or 'unknown'}")
    print()
    records = fetch_ota_records(args.pb_base_url, args.per_page)
    for index, record in enumerate(filter_release_records(records), start=1):
        print(f"Release [{index}]")
        for line in describe_record(record):
            print(line)
        print()
    return 0


def run_ota_upgrade(args, session: DeviceSession) -> int:
    records = fetch_ota_records(args.pb_base_url, args.per_page)
    target = (
        pick_latest_record(records)
        if args.latest
        else find_record_by_version(records, args.version)
    )
    manifest = target.get("manifest") or {}
    version = manifest.get("version", "unknown")
    firmware_files = target.get("firmware") or []
    if not firmware_files:
        raise LooperCliError(f"No firmware files found for version {version}")

    device_base_url = session.ensure_resolved()
    current_version = session.ensure_version() or get_device_version(device_base_url)
    log(f"Resolved device endpoint: {device_base_url}")
    if current_version:
        log(f"Current firmware version: {current_version}")
    log(f"Target firmware version: {version}")
    log(f"Release record ID: {target.get('id')}")
    log(f"Firmware package count: {len(firmware_files)}")
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
        for index, filename in enumerate(firmware_files, start=1):
            log(f"Uploading file {index}/{len(firmware_files)}")
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
