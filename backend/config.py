from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    ai_provider: str = "groq"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    mistral_api_key: str = ""
    openai_api_key: str = ""

    output_dir: str = "outputs"
    jobs_dir: str = "jobs"
    templates_dir: str = "templates"
    max_input_size_mb: int = 10
    pdf_timeout_seconds: int = 30

    # Optional: fixed admin auth secret. If left empty, a stable secret is
    # generated once and persisted to backend/.secret_key on first run,
    # so admin sessions no longer break on every server restart.
    secret_key: str = ""

    # Watchdog: how long (minutes) a job can sit in "queued"/"processing"
    # without any progress update before it's auto-marked as failed.
    stale_job_timeout_minutes: int = 20

    # CORS — comma-separated allowed origins. Empty string = allow all ("*").
    cors_origins: str = ""


settings = Settings()
