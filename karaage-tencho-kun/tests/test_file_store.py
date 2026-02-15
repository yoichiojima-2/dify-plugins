import sys
import time
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import _file_store


class TestFileStore(unittest.TestCase):
    def setUp(self):
        _file_store._store.clear()

    def test_store_and_retrieve(self) -> None:
        file_id = _file_store.store_file(b"<html>hello</html>")
        result = _file_store.get_file(file_id)
        self.assertEqual(result, b"<html>hello</html>")

    def test_returns_none_for_unknown_id(self) -> None:
        result = _file_store.get_file("nonexistent")
        self.assertIsNone(result)

    def test_unique_ids(self) -> None:
        id1 = _file_store.store_file(b"a")
        id2 = _file_store.store_file(b"b")
        self.assertNotEqual(id1, id2)

    def test_ttl_expiration(self) -> None:
        file_id = _file_store.store_file(b"data")
        # Manually set created_at to past
        content, _ = _file_store._store[file_id]
        _file_store._store[file_id] = (content, time.time() - _file_store.TTL_SECONDS - 1)

        result = _file_store.get_file(file_id)
        self.assertIsNone(result)

    def test_cleanup_removes_expired(self) -> None:
        file_id = _file_store.store_file(b"old")
        content, _ = _file_store._store[file_id]
        _file_store._store[file_id] = (content, time.time() - _file_store.TTL_SECONDS - 1)

        # Storing a new file triggers cleanup
        _file_store.store_file(b"new")
        self.assertNotIn(file_id, _file_store._store)

    def test_stores_bytes(self) -> None:
        data = "日本語コンテンツ".encode("utf-8")
        file_id = _file_store.store_file(data)
        result = _file_store.get_file(file_id)
        self.assertEqual(result, data)


if __name__ == "__main__":
    unittest.main()
