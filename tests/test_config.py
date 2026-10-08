import pytest

from config import Settings


def test_timezone_is_configurable_and_validated() -> None:
    assert Settings(timezone="UTC").timezone == "UTC"

    with pytest.raises(ValueError, match="Onbekende tijdzone"):
        Settings(timezone="Invalid/Timezone")
