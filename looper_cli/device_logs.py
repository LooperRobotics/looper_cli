import base64
import os
import secrets
import socket
import struct
import sys
import threading
import time

from looper_cli.errors import LooperCliError
from looper_cli.output import clear_inline_status, log


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
