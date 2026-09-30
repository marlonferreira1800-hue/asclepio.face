import csv
import tempfile
import unittest
from pathlib import Path

from src.models import FrameMetrics, SessionSummary
from src.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_save_export_and_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SessionStore(Path(folder) / "test.db")
            summary = SessionSummary("a", "b", 2.0, 1, 0.8, {"estável": 1}, 0)
            sample = FrameMetrics(0.1, True, 120, 100, 30, 0.9, quality=0.8, activation_level="estável")
            session_id = store.save(summary, [sample])
            self.assertEqual(len(store.list_sessions()), 1)
            target = Path(folder) / "out.csv"
            store.export_csv(session_id, target)
            with target.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["activation_level"], "estável")
            store.delete(session_id)
            self.assertEqual(store.list_sessions(), [])
            store.close()


if __name__ == "__main__":
    unittest.main()
