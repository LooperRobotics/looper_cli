from datetime import datetime
import sys
import threading


OUTPUT_LOCK = threading.Lock()
INLINE_STATUS_ACTIVE = False
INLINE_STATUS_WIDTH = 0


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


def log(message: str) -> None:
    clear_inline_status()
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"
