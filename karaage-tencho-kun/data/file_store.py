# In-memory file store for plugin endpoint downloads
# Shared between file_writer tool and file_download endpoint

import threading
import time
import uuid

FILE_TTL_SECONDS = 3600  # 1 hour


_lock = threading.Lock()
_store: dict[str, dict] = {}
# Each entry: {
#   "content": bytes,
#   "filename": str,
#   "mime_type": str,
#   "created_at": float,
# }


def store_file(content: bytes, filename: str, mime_type: str) -> str:
    """Store file content and return a unique file_id."""
    file_id = uuid.uuid4().hex
    with _lock:
        _cleanup_expired()
        _store[file_id] = {
            "content": content,
            "filename": filename,
            "mime_type": mime_type,
            "created_at": time.time(),
        }
    return file_id


def get_file(file_id: str) -> dict | None:
    """Retrieve file by ID. Returns None if not found or expired."""
    with _lock:
        entry = _store.get(file_id)
        if entry is None:
            return None
        if time.time() - entry["created_at"] > FILE_TTL_SECONDS:
            del _store[file_id]
            return None
        return entry


def _cleanup_expired() -> None:
    """Remove expired entries. Called while lock is held."""
    now = time.time()
    expired = [k for k, v in _store.items() if now - v["created_at"] > FILE_TTL_SECONDS]
    for k in expired:
        del _store[k]
