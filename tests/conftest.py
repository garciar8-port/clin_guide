from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_spl_xml() -> bytes:
    return (FIXTURES_DIR / "sample_spl.xml").read_bytes()
