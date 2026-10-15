import pytest
from scripts.generate_transactions import generate


def test_generator_rejects_rates_that_leave_no_valid_share(tmp_path):
    with pytest.raises(ValueError, match="rates must sum"):
        generate(tmp_path / "invalid.csv", total=2, duplicate_rate=0.9, invalid_rate=0.1)
