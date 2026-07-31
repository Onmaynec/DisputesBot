from __future__ import annotations

import re


def detect_stance(text: str) -> str | None:
    """Detect an explicitly stated pro/con stance in Russian text."""

    normalized = " ".join(text.casefold().replace("ё", "е").split())
    pro_patterns = (
        r"^за\b",
        r"\bя\s+за\b",
        r"\bподдерживаю\b",
        r"\bсогласен\b",
        r"\bсогласна\b",
    )
    con_patterns = (
        r"^против\b",
        r"\bя\s+против\b",
        r"\bне\s+поддерживаю\b",
        r"\bне\s+согласен\b",
        r"\bне\s+согласна\b",
    )
    if any(re.search(pattern, normalized) for pattern in con_patterns):
        return "против"
    if any(re.search(pattern, normalized) for pattern in pro_patterns):
        return "за"
    return None
