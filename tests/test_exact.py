"""Tests for exact.py: the sampled/full content fingerprint and grouping.

The sampling threshold is shrunk to a few bytes so the head+tail path can be
exercised with tiny files instead of 100 MB ones.
"""
import hashlib
import tempfile
import shutil
import unittest
from pathlib import Path

import exact


class _TmpMixin(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        # Shrink sampling so size>8 bytes samples first 4 + last 4.
        self._orig = (exact.SAMPLE_BYTES, exact.SAMPLE_THRESHOLD)
        exact.SAMPLE_BYTES = 4
        exact.SAMPLE_THRESHOLD = 8

    def tearDown(self):
        exact.SAMPLE_BYTES, exact.SAMPLE_THRESHOLD = self._orig
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return p


class TestSampledFingerprint(_TmpMixin):
    def test_small_file_is_full_hash_with_size_prefix(self):
        p = self.write("a.bin", b"abcdef")          # 6 bytes <= threshold(8)
        expected = hashlib.sha256(b"6:abcdef").hexdigest()
        self.assertEqual(exact.sampled_fingerprint(p), expected)

    def test_large_file_samples_head_and_tail_plus_size(self):
        p = self.write("b.bin", b"AAAA" + b"MIDDLE" + b"CCCC")   # size 14 > 8
        expected = hashlib.sha256(b"14:" + b"AAAA" + b"CCCC").hexdigest()
        self.assertEqual(exact.sampled_fingerprint(p), expected)

    def test_sampling_collides_but_full_hash_separates(self):
        f1 = self.write("f1.bin", b"AAAA" + b"111111" + b"CCCC")  # same head/tail/size
        f2 = self.write("f2.bin", b"AAAA" + b"222222" + b"CCCC")  # different middle
        self.assertEqual(exact.sampled_fingerprint(f1), exact.sampled_fingerprint(f2))
        self.assertNotEqual(exact.fingerprint(f1), exact.fingerprint(f2))

    def test_passed_size_matches_stat_size(self):
        p = self.write("c.bin", b"abcdef")
        self.assertEqual(exact.sampled_fingerprint(p), exact.sampled_fingerprint(p, size=6))


class _FakeCache:
    def __init__(self):
        self.store = {}
    def get(self, kind, path):
        return self.store.get((kind, str(path)))
    def put(self, kind, path, value):
        self.store[(kind, str(path))] = value


class TestFindExactDuplicates(_TmpMixin):
    def test_identical_files_grouped(self):
        a = self.write("a", b"same-content")
        b = self.write("b", b"same-content")
        c = self.write("c", b"different!!")          # different size
        groups = exact.find_exact_duplicates([a, b, c])
        self.assertEqual(len(groups), 1)
        self.assertEqual({p.name for p in groups[0]}, {"a", "b"})

    def test_same_size_different_content_not_grouped(self):
        a = self.write("a", b"AAAA")
        b = self.write("b", b"BBBB")                 # same size, different content
        self.assertEqual(exact.find_exact_duplicates([a, b]), [])

    def test_different_sizes_never_grouped(self):
        a = self.write("a", b"AA")
        b = self.write("b", b"AAAA")
        self.assertEqual(exact.find_exact_duplicates([a, b]), [])

    def test_sample_mode_matches_full_mode(self):
        a = self.write("a", b"same-content")
        b = self.write("b", b"same-content")
        full = exact.find_exact_duplicates([a, b], sample=False)
        sampled = exact.find_exact_duplicates([a, b], sample=True)
        self.assertEqual([sorted(p.name for p in g) for g in full],
                         [sorted(p.name for p in g) for g in sampled])

    def test_cache_reuse_skips_rehash(self):
        a = self.write("a", b"same-content")
        b = self.write("b", b"same-content")
        cache = _FakeCache()
        seen = []
        exact.find_exact_duplicates([a, b], cache=cache, progress=seen.append)
        self.assertEqual(len(seen), 2)               # both hashed (cache miss)
        seen.clear()
        groups = exact.find_exact_duplicates([a, b], cache=cache, progress=seen.append)
        self.assertEqual(seen, [])                    # both from cache: no hashing
        self.assertEqual(len(groups), 1)


if __name__ == "__main__":
    unittest.main()
