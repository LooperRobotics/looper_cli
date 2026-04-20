import json
from typing import Dict, Optional
from urllib.request import Request, urlopen


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


def build_headers(headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    merged = DEFAULT_HEADERS.copy()
    if headers:
        merged.update(headers)
    return merged


def http_json(
    url: str,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60,
):
    request = Request(url, data=data, headers=build_headers(headers), method=method)
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def http_get_bytes(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 120,
) -> bytes:
    request = Request(url, headers=build_headers(headers))
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def http_post_bytes(
    url: str,
    data: bytes,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 300,
) -> None:
    request = Request(url, data=data, headers=build_headers(headers), method="POST")
    with urlopen(request, timeout=timeout) as response:
        response.read()


def open_request(
    url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 120
):
    request = Request(url, headers=build_headers(headers))
    return urlopen(request, timeout=timeout)
