from pathlib import Path
from backend.config import settings


def test_settings_loaded():
    assert isinstance(settings.ai_provider, str)


def test_default_provider():
    assert settings.ai_provider == "mistral"


def test_output_dir():
    assert settings.output_dir == "outputs"


def test_env_file_exists():
    assert (Path(__file__).parent.parent / ".env").exists()
