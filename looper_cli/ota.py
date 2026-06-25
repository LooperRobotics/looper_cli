import base64
import hashlib
import json
import re
import textwrap
import time
from typing import Iterable, List
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from looper_cli import DEFAULT_PER_PAGE, PB_BASE_URL, PRODUCT_NAME, UPLOAD_CHUNK_SIZE
from looper_cli.device import DeviceSession, get_device_version
from looper_cli.device_logs import DeviceLogStreamer
from looper_cli.errors import LooperCliError
from looper_cli.http import DEFAULT_HEADERS, http_json, http_post_bytes, open_request
from looper_cli.output import (
    clear_inline_status,
    format_duration,
    log,
    render_inline_status,
)


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


def fetch_ota_records(pb_base_url: str, per_page: int = DEFAULT_PER_PAGE) -> List[dict]:
    query = urlencode({"page": 1, "perPage": per_page, "sort": "-created"})
    url = f"{pb_base_url}/api/collections/ota/records?{query}"
    payload = http_json(url)
    items = payload.get("items", []) if payload else []
    if not isinstance(items, list):
        raise LooperCliError("Invalid OTA response payload")
    return items

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
        raise LooperCliError("Invalid OTA product names response")
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
        raise LooperCliError("Invalid products response payload")

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


def fetch_ota_records_for_device(
    pb_base_url: str, device_base_url: str, per_page: int = DEFAULT_PER_PAGE
) -> List[dict]:
    records = fetch_ota_records(pb_base_url, per_page)
    try:
        product_names = fetch_product_names(device_base_url)
    except LooperCliError as exc:
        log(f"Warning: unable to fetch product names: {exc}")
        return records

    product_map = {}
    try:
        product_map = fetch_product_records(pb_base_url, product_names)
    except LooperCliError as exc:
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
        raise LooperCliError("No OTA records found")
    return records[0]


def find_record_by_version(records: List[dict], version: str) -> dict:
    for record in records:
        manifest = normalize_manifest(record.get("manifest"))
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


def fetch_device_versions(device_base_url: str) -> dict:
    payload = http_json(f"{device_base_url}/api/ota/device-versions", timeout=10)
    if not isinstance(payload, dict):
        raise LooperCliError("Invalid OTA device versions response")
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
        raise LooperCliError("Invalid initial version check response")
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


def upload_firmware_file(
    pb_base_url: str,
    device_base_url: str,
    record: dict,
    filename: str,
    task_id: str,
    signature_b64: str,
) -> None:
    manifest = json.dumps(
        normalize_manifest(record.get("manifest")), separators=(",", ":")
    )
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
    device_base_url = session.ensure_resolved()
    print(PRODUCT_NAME)
    print(f"Device Endpoint : {device_base_url}")
    print(f"Current Version : {session.ensure_version() or 'unknown'}")
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


def run_ota_upgrade(args, session: DeviceSession) -> int:
    device_base_url = session.ensure_resolved()
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
        raise LooperCliError(f"No firmware files found for version {version}")

    device_base_url = session.ensure_resolved()
    current_version = session.ensure_version() or get_device_version(device_base_url)
    log(f"Resolved device endpoint: {device_base_url}")
    if current_version:
        log(f"Current firmware version: {current_version}")
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
        raise LooperCliError(
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
