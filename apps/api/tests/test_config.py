import pytest

from repolume_api.config import Settings


def test_rejects_unknown_environment() -> None:
    with pytest.raises(ValueError, match="REPOLUME_ENVIRONMENT"):
        Settings(environment="local")
