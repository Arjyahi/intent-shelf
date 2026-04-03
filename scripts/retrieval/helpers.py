import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from config import PROCESSED_PRODUCTS_PATH


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(data: Any, path: Path) -> None:
    ensure_parent_directory(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(make_json_safe(data), handle, indent=2)
        handle.write("\n")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if value is pd.NA:
        return None
    return value


def is_non_empty_text(value: object) -> bool:
    if value is None or value is pd.NA:
        return False
    text = str(value).strip()
    return bool(text)


def load_products(limit: int | None, columns: list[str] | None = None) -> pd.DataFrame:
    products = pd.read_parquet(PROCESSED_PRODUCTS_PATH, columns=columns)
    if limit is not None:
        products = products.head(limit).copy()
    return products.reset_index(drop=True)


def build_text_input(
    record: Mapping[str, object],
    fallback_columns: list[str],
) -> tuple[str, bool, bool]:
    """
    Return one safe text input string for CLIP.

    The tuple contains:
    1. the text string
    2. whether fallback fields were used instead of combined_text
    3. whether a generic placeholder had to be used
    """
    combined_text = record.get("combined_text")
    if is_non_empty_text(combined_text):
        return str(combined_text).strip(), False, False

    parts: list[str] = []
    seen: set[str] = set()

    for column in fallback_columns:
        value = record.get(column)
        if not is_non_empty_text(value):
            continue

        text = str(value).strip()
        normalized = text.lower()
        if normalized in seen:
            continue

        parts.append(text)
        seen.add(normalized)

    if parts:
        return " | ".join(parts), True, False

    return "fashion item", True, True


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0, 1.0, norms)
    return (vectors / safe_norms).astype(np.float32)


def batch_ranges(total_size: int, batch_size: int):
    for start in range(0, total_size, batch_size):
        end = min(start + batch_size, total_size)
        yield start, end
