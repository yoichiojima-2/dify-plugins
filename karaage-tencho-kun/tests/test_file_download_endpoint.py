import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from data import file_store
from endpoints.file_download import FileDownloadEndpoint


class TestFileDownloadEndpoint(unittest.TestCase):
    def setUp(self):
        """Clean the store and create endpoint instance."""
        with file_store._lock:
            file_store._store.clear()

        # Create endpoint with mock session
        self.endpoint = object.__new__(FileDownloadEndpoint)
        self.endpoint.session = MagicMock()

    def test_returns_200_for_valid_file(self) -> None:
        file_id = file_store.store_file(
            b"<html>dashboard</html>", "dashboard.html", "text/html"
        )

        response = self.endpoint._invoke(
            r=MagicMock(),
            values={"file_id": file_id},
            settings={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"<html>dashboard</html>")
        self.assertEqual(response.content_type, "text/html")
        self.assertIn("dashboard.html", response.headers.get("Content-Disposition", ""))

    def test_returns_404_for_unknown_file(self) -> None:
        response = self.endpoint._invoke(
            r=MagicMock(),
            values={"file_id": "nonexistent"},
            settings={},
        )

        self.assertEqual(response.status_code, 404)

    def test_returns_404_for_expired_file(self) -> None:
        import time

        file_id = file_store.store_file(b"old", "old.html", "text/html")

        # Expire the file
        with file_store._lock:
            file_store._store[file_id]["created_at"] = time.time() - file_store.FILE_TTL_SECONDS - 1

        response = self.endpoint._invoke(
            r=MagicMock(),
            values={"file_id": file_id},
            settings={},
        )

        self.assertEqual(response.status_code, 404)

    def test_csv_file_has_correct_content_type(self) -> None:
        file_id = file_store.store_file(
            b"a,b,c\n1,2,3", "data.csv", "text/csv"
        )

        response = self.endpoint._invoke(
            r=MagicMock(),
            values={"file_id": file_id},
            settings={},
        )

        self.assertEqual(response.content_type, "text/csv")
        self.assertIn("data.csv", response.headers.get("Content-Disposition", ""))


if __name__ == "__main__":
    unittest.main()
