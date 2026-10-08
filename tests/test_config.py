import pytest  # noqa: D100

from config import Settings


def test_timezone_is_configurable_and_validated() -> None:  # noqa: D103
    assert Settings(timezone="UTC").timezone == "UTC"  # noqa: S101

    with pytest.raises(ValueError, match="Onbekende tijdzone"):
        Settings(timezone="Invalid/Timezone")
