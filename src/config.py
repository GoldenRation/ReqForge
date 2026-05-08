"""Configuration management for the Requirements-to-Code Agent system."""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Environment-based defaults ──────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
DEFAULT_TECH_STACK = os.getenv("DEFAULT_TECH_STACK", "spring-boot")

MAX_RETRIES = 3
TEMPERATURE = 0.3
MAX_TOKENS = 8192

# ── Settings file persistence ───────────────────────────────────────────

SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"


def load_settings() -> dict:
    """Load settings from the JSON config file. Returns empty dict if not found."""
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_settings(settings: dict) -> None:
    """Persist settings to the JSON config file."""
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def get_api_key() -> str:
    """Resolve API key: settings file > env var."""
    stored = load_settings().get("api_key", "")
    return stored or ANTHROPIC_API_KEY


def get_model() -> str:
    """Resolve model: settings file > env var > default."""
    stored = load_settings().get("model", "")
    return stored or ANTHROPIC_MODEL


def get_base_url() -> str:
    """Resolve base URL: settings file > env var."""
    stored = load_settings().get("base_url", "")
    return stored or ANTHROPIC_BASE_URL
