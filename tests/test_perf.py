"""Tests for perf.py: the read-speed EMA and the estimate label. PERF_FILE is
redirected to a temp path so the real perf.json is never touched."""
import tempfile
import shutil
import unittest
from unittest import mock
from pathlib import Path

import perf


class TestPerf(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self._orig = perf.PERF_FILE
        perf.PERF_FILE = self.dir / "perf.json"

    def tearDown(self):
        perf.PERF_FILE = self._orig
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_default_before_any_measurement(self):
        self.assertEqual(perf.read_mbps(), perf.DEFAULT_MBPS)

    def test_first_record_sets_value(self):
        perf.record(100_000_000, 1.0)            # 100 MB in 1s -> 100 MB/s
        self.assertEqual(perf.read_mbps(), 100.0)

    def test_second_record_is_ema(self):
        perf.record(100_000_000, 1.0)            # -> 100
        perf.record(200_000_000, 1.0)            # 0.7*100 + 0.3*200 = 130
        self.assertEqual(perf.read_mbps(), 130.0)

    def test_nonpositive_is_ignored(self):
        perf.record(0, 1.0)
        perf.record(100_000_000, 0)
        self.assertEqual(perf.read_mbps(), perf.DEFAULT_MBPS)

    def test_estimate_label_seconds(self):
        with mock.patch.object(perf, "read_mbps", return_value=100.0):
            self.assertEqual(perf.estimate_label(1_000_000_000),
                             "~10s to full-hash 1.0 GB")

    def test_estimate_label_minutes(self):
        with mock.patch.object(perf, "read_mbps", return_value=100.0):
            self.assertEqual(perf.estimate_label(20_000_000_000),
                             "~3m to full-hash 20.0 GB")


if __name__ == "__main__":
    unittest.main()
