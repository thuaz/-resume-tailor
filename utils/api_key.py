"""Load ANTHROPIC_API_KEY from .env file or environment variable."""
import os
from pathlib import Path

from dotenv import load_dotenv


def load_api_key() -> str | None:
    """Load API key, trying .env file first, then environment variable.

    Returns the key string, or None if not found.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    return os.getenv("ANTHROPIC_API_KEY")
