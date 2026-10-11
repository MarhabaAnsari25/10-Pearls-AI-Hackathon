"""Load environment configuration (guide §7.6)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = Path(__file__).resolve().parent

# Prefer project-root .env; fall back to source/.env
load_dotenv(ROOT / ".env")
load_dotenv(SOURCE_DIR / ".env")


def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            f"Copy source/.env.example to .env and set your API key."
        )
    return value


MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "google").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.5-flash-lite").strip()
MODEL_FALLBACK = os.getenv("MODEL_FALLBACK", "gemini-3.1-flash-lite").strip()
API_KEY = require("API_KEY")
