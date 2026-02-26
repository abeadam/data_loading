import pytest
from pathlib import Path


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require a live TWS/IB Gateway connection",
    )
    config.addinivalue_line(
        "markers",
        "research: marks tests that require on-disk bar data and articles.json files",
    )


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Provides a temporary data directory pre-populated with bars/ and news/ subdirs."""
    (tmp_path / "bars").mkdir()
    (tmp_path / "news").mkdir()
    return tmp_path
