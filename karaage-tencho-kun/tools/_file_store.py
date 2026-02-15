# HTML ファイルのインメモリストア
# file_writer ツールとエンドポイント間で共有される

import time
import uuid

_store: dict[str, tuple[bytes, float]] = {}  # {file_id: (content, created_at)}

TTL_SECONDS = 3600  # 1 hour


def store_file(content: bytes) -> str:
    _cleanup()
    file_id = uuid.uuid4().hex
    _store[file_id] = (content, time.time())
    return file_id


def get_file(file_id: str) -> bytes | None:
    entry = _store.get(file_id)
    if entry is None:
        return None
    content, created_at = entry
    if time.time() - created_at > TTL_SECONDS:
        _store.pop(file_id, None)
        return None
    return content


def _cleanup() -> None:
    now = time.time()
    expired = [fid for fid, (_, ts) in _store.items() if now - ts > TTL_SECONDS]
    for fid in expired:
        _store.pop(fid, None)
