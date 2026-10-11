"""Gemini API client with primary model and fallback (guide §9)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from . import config

RETRYABLE_MARKERS = (
    "RESOURCE_EXHAUSTED",
    "429",
    "rate limit",
    "quota",
    "UNAVAILABLE",
    "503",
    "500",
    "INTERNAL",
    "deadline",
    "timeout",
)


class GeminiClient:
    def __init__(self, min_interval_sec: float = 4.5) -> None:
        self.client = genai.Client(api_key=config.API_KEY)
        self.primary = config.MODEL_NAME
        self.fallback = config.MODEL_FALLBACK
        self.min_interval_sec = min_interval_sec
        self._last_call_at = 0.0

    def _throttle(self) -> None:
        """Stay under free-tier ~15 requests/min."""
        elapsed = time.time() - self._last_call_at
        wait = self.min_interval_sec - elapsed
        if wait > 0:
            time.sleep(wait)

    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> str:
        self._throttle()
        contents: list[Any] = []
        if image_path is not None:
            data = image_path.read_bytes()
            suffix = image_path.suffix.lower()
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }.get(suffix, "image/png")
            contents.append(types.Part.from_bytes(data=data, mime_type=mime))
        contents.append(prompt)

        models = [self.primary]
        if self.fallback and self.fallback != self.primary:
            models.append(self.fallback)

        last_error: Exception | None = None
        for model in models:
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            temperature=temperature,
                            response_mime_type="text/plain",
                        ),
                    )
                    self._last_call_at = time.time()
                    text = (response.text or "").strip()
                    if not text:
                        raise RuntimeError(f"Empty response from {model}")
                    if model != self.primary:
                        print(f"  [gemini] used fallback model: {model}")
                    return text
                except Exception as exc:  # noqa: BLE001 — surface provider errors with retry
                    last_error = exc
                    msg = str(exc).lower()
                    retryable = any(m.lower() in msg for m in RETRYABLE_MARKERS)
                    if retryable and attempt < max_retries - 1:
                        wait = 2 ** (attempt + 1)
                        print(f"  [gemini] {model} retry in {wait}s: {exc}")
                        time.sleep(wait)
                        continue
                    # Non-retryable on this model → try fallback
                    print(f"  [gemini] {model} failed: {exc}")
                    break

        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")
