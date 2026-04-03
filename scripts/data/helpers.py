import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import IMAGES_DIR, REPO_ROOT


def ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def reset_output_file(path: Path) -> None:
    ensure_parent_directory(path)
    if path.exists():
        path.unlink()


def clean_text_series(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip()
    return cleaned.where(cleaned.ne(""), pd.NA)


def canonicalize_product_id_series(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip()
    cleaned = cleaned.str.replace(".0", "", regex=False)
    cleaned = cleaned.str.replace(r"\D", "", regex=True)
    cleaned = cleaned.where(cleaned.str.len().fillna(0) > 0, pd.NA)
    return cleaned.str.zfill(10)


def canonicalize_user_id_series(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip()
    return cleaned.where(cleaned.ne(""), pd.NA)


def normalize_status_series(series: pd.Series) -> pd.Series:
    cleaned = clean_text_series(series)
    cleaned = cleaned.str.upper()
    return cleaned.fillna("UNKNOWN")


def normalize_fashion_news_series(series: pd.Series) -> pd.Series:
    cleaned = clean_text_series(series)
    cleaned = cleaned.str.upper()
    cleaned = cleaned.replace({"NONE": "NONE", "MONTHLY": "MONTHLY", "REGULARLY": "REGULARLY"})
    return cleaned.fillna("UNKNOWN")


def clean_age_series(series: pd.Series) -> pd.Series:
    cleaned = pd.to_numeric(series, errors="coerce")
    cleaned = cleaned.where((cleaned >= 13) & (cleaned <= 100), pd.NA)
    return cleaned


def build_image_relative_path(product_id: str) -> Path:
    return Path("data") / "raw" / "images" / product_id[:3] / f"{product_id}.jpg"


def resolve_image_path(product_id: str) -> tuple[str | None, bool]:
    relative_path = build_image_relative_path(product_id)
    absolute_path = REPO_ROOT / relative_path
    if absolute_path.exists():
        return relative_path.as_posix(), True
    return None, False


def count_image_files() -> int:
    if not IMAGES_DIR.exists():
        return 0
    return sum(1 for _ in IMAGES_DIR.rglob("*.jpg"))


def build_combined_text(row: pd.Series, text_columns: list[str]) -> str:
    seen: set[str] = set()
    parts: list[str] = []

    for column in text_columns:
        value = row[column]
        if pd.isna(value):
            continue

        text = str(value).strip()
        if not text:
            continue

        normalized = text.lower()
        if normalized in seen:
            continue

        parts.append(text)
        seen.add(normalized)

    return " | ".join(parts)


def write_dataframe_to_parquet(df: pd.DataFrame, path: Path) -> None:
    ensure_parent_directory(path)
    df.to_parquet(path, index=False, engine="pyarrow")


def append_parquet_chunk(
    df: pd.DataFrame,
    path: Path,
    writer: pq.ParquetWriter | None,
) -> pq.ParquetWriter:
    """
    Append one cleaned chunk to a parquet file.

    Parquet is not line-appendable like CSV, so we keep a writer open and add
    one row group per chunk. That keeps the transaction pipeline readable
    without loading the full table into memory at once.
    """
    ensure_parent_directory(path)
    table = pa.Table.from_pandas(df, preserve_index=False)

    if writer is None:
        writer = pq.ParquetWriter(path, table.schema)

    writer.write_table(table)
    return writer


def close_parquet_writer(writer: pq.ParquetWriter | None) -> None:
    if writer is not None:
        writer.close()


def iter_parquet_batches(
    path: Path,
    batch_size: int,
    columns: list[str] | None = None,
):
    parquet_file = pq.ParquetFile(path)
    yield from parquet_file.iter_batches(batch_size=batch_size, columns=columns)


def format_timestamp(value: pd.Timestamp | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    raise TypeError(f"Expected timestamp-like value, received {type(value)!r}")


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if value is pd.NA:
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        return make_json_safe(value.item())
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def write_json(data: dict[str, Any], path: Path) -> None:
    ensure_parent_directory(path)
    serializable_data = make_json_safe(data)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(serializable_data, handle, indent=2)
        handle.write("\n")
