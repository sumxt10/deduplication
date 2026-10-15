from backend.storage import Storage


def test_storage_initializes(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'test.db'}")
    assert storage.summary()["total_deliveries"] == 0
