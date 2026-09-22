from backend.config import settings


def test_settings_loaded():
    assert isinstance(settings.ai_provider, str)


def test_default_provider():
    assert settings.ai_provider == "mistral"


def test_output_dir():
    assert settings.output_dir == "outputs"


# test_env_file_exists() removed 2026-09-22: it asserted a local .env file exists,
# which is correctly gitignored and never present on a fresh CI checkout — this
# tested a developer's local setup, not application behaviour, and could never
# have passed in CI (found while chasing `pytest -x` through a chain of
# independent, pre-existing failures the flag had been masking one at a time).
