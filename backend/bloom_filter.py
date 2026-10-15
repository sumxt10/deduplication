"""A bounded rotating Bloom filter used only as a duplicate-screening hint."""
import hashlib
import math
import time


class SlidingWindowBloomFilter:
    def __init__(self, capacity=100_000, error_rate=0.001, slices=3, slice_seconds=300):
        if capacity <= 0 or not 0 < error_rate < 1 or slices < 1:
            raise ValueError("invalid Bloom filter configuration")
        self.capacity, self.error_rate = capacity, error_rate
        self.slices, self.slice_seconds = slices, slice_seconds
        self.bit_count = max(8, int(-capacity * math.log(error_rate) / math.log(2) ** 2))
        self.hash_count = max(1, int(self.bit_count / capacity * math.log(2)))
        self._windows = [bytearray((self.bit_count + 7) // 8) for _ in range(slices)]
        self._index, self._started = 0, time.monotonic()
        self.positives = self.negatives = self.insertions = 0
        self.confirmed_duplicates = self.false_positives = 0

    @property
    def memory_bytes(self):
        return sum(len(window) for window in self._windows)

    @property
    def config(self):
        return {"capacity": self.capacity, "error_rate": self.error_rate,
                "slices": self.slices, "slice_seconds": self.slice_seconds,
                "bits": self.bit_count, "hashes": self.hash_count,
                "memory_bytes": self.memory_bytes}

    def _rotate(self):
        steps = int((time.monotonic() - self._started) // self.slice_seconds)
        if steps:
            for _ in range(min(steps, self.slices)):
                self._index = (self._index + 1) % self.slices
                self._windows[self._index] = bytearray(len(self._windows[0]))
            self._started += steps * self.slice_seconds

    def _indexes(self, value):
        digest = hashlib.sha256(value.encode()).digest()
        first = int.from_bytes(digest[:8], "big")
        second = int.from_bytes(digest[8:16], "big") or 1
        for index in range(self.hash_count):
            yield (first + index * second) % self.bit_count

    def add(self, value):
        self._rotate()
        for index in self._indexes(value):
            self._windows[self._index][index // 8] |= 1 << (index % 8)
        self.insertions += 1

    def __contains__(self, value):
        self._rotate()
        result = any(all(window[index // 8] & (1 << (index % 8))
                         for index in self._indexes(value)) for window in self._windows)
        if result:
            self.positives += 1
        else:
            self.negatives += 1
        return result

    def reset(self):
        self._windows = [bytearray(len(self._windows[0])) for _ in self._windows]
        self._index, self._started = 0, time.monotonic()