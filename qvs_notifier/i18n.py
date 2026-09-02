"""Small, dependency-free translation service shared by every UI surface."""
from __future__ import annotations

import json
import locale
from functools import lru_cache
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).with_name("locales")
SUPPORTED_LOCALES = ("en-US", "zh-CN")


def normalize_locale(value: str | None) -> str:
    value = (value or "").replace("_", "-").lower()
    if value.startswith("zh"):
        return "zh-CN"
    if value.startswith("en"):
        return "en-US"
    return "en-US"


def system_locale() -> str:
    return normalize_locale(locale.getlocale()[0] or locale.getdefaultlocale()[0])


@lru_cache(maxsize=None)
def messages(language: str) -> dict[str, str]:
    language = normalize_locale(language)
    english = json.loads((LOCALES_DIR / "en-US.json").read_text(encoding="utf-8"))
    if language == "en-US":
        return english
    localized = json.loads((LOCALES_DIR / f"{language}.json").read_text(encoding="utf-8"))
    return {**english, **localized}


def translate(key: str, language: str | None = None, **values: Any) -> str:
    text = messages(language or system_locale()).get(key, messages("en-US").get(key, key))
    return text.format(**values)


def web_messages(language: str | None = None) -> dict[str, str]:
    """Return only public strings for the browser locale endpoint."""
    return messages(language or system_locale()).copy()
