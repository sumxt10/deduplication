from backend.bloom_filter import SlidingWindowBloomFilter


def test_bloom_insert_and_config():
    bloom = SlidingWindowBloomFilter(100, 0.01)
    bloom.add("x")
    assert "x" in bloom
    assert bloom.memory_bytes > 0