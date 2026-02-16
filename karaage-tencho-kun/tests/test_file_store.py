import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from data import file_store


class TestFileStore(unittest.TestCase):
    def setUp(self):
        """Clean the store before each test."""
        with file_store._lock:
            file_store._store.clear()

    def test_store_file_returns_unique_id(self) -> None:
        id1 = file_store.store_file(b"content1", "file1.html", "text/html")
        id2 = file_store.store_file(b"content2", "file2.html", "text/html")
        self.assertIsInstance(id1, str)
        self.assertIsInstance(id2, str)
        self.assertNotEqual(id1, id2)

    def test_get_file_retrieves_stored_content(self) -> None:
        file_id = file_store.store_file(b"<html>test</html>", "test.html", "text/html")
        entry = file_store.get_file(file_id)

        self.assertIsNotNone(entry)
        self.assertEqual(entry["content"], b"<html>test</html>")
        self.assertEqual(entry["filename"], "test.html")
        self.assertEqual(entry["mime_type"], "text/html")

    def test_get_file_returns_none_for_unknown_id(self) -> None:
        result = file_store.get_file("nonexistent")
        self.assertIsNone(result)

    def test_get_file_returns_none_for_expired(self) -> None:
        file_id = file_store.store_file(b"content", "old.html", "text/html")

        # Manually expire the file
        with file_store._lock:
            file_store._store[file_id]["created_at"] = time.time() - file_store.FILE_TTL_SECONDS - 1

        result = file_store.get_file(file_id)
        self.assertIsNone(result)

    def test_cleanup_removes_expired_entries(self) -> None:
        # Store two files
        id1 = file_store.store_file(b"old", "old.html", "text/html")
        id2 = file_store.store_file(b"new", "new.html", "text/html")

        # Expire the first one
        with file_store._lock:
            file_store._store[id1]["created_at"] = time.time() - file_store.FILE_TTL_SECONDS - 1

        # Storing a new file triggers cleanup
        file_store.store_file(b"trigger", "trigger.html", "text/html")

        self.assertIsNone(file_store.get_file(id1))
        self.assertIsNotNone(file_store.get_file(id2))


if __name__ == "__main__":
    unittest.main()
