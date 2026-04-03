import argparse
from datetime import datetime, timezone

import pandas as pd

from config import (
    DEFAULT_INTERACTION_CHUNKSIZE,
    DEFAULT_VALIDATION_DAYS,
    INTERACTION_COLUMNS,
    PROCESSED_FILES,
)
from helpers import (
    append_parquet_chunk,
    close_parquet_writer,
    format_timestamp,
    iter_parquet_batches,
    reset_output_file,
    write_dataframe_to_parquet,
    write_json,
)


def detect_validation_start_date(
    interactions_path,
    chunk_size: int,
    validation_days: int,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    """Scan the processed interactions file to find the chronological cutoff."""
    min_date: pd.Timestamp | None = None
    max_date: pd.Timestamp | None = None

    for batch in iter_parquet_batches(
        interactions_path,
        batch_size=chunk_size,
        columns=["t_dat"],
    ):
        chunk = batch.to_pandas()
        chunk_min = chunk["t_dat"].min()
        chunk_max = chunk["t_dat"].max()

        min_date = chunk_min if min_date is None else min(min_date, chunk_min)
        max_date = chunk_max if max_date is None else max(max_date, chunk_max)

    if min_date is None or max_date is None:
        raise ValueError("The processed interactions file is empty.")

    validation_start_date = max_date - pd.Timedelta(days=validation_days - 1)
    return min_date, max_date, validation_start_date


def split_interactions(
    interactions_path,
    train_path,
    val_path,
    chunk_size: int,
    validation_start_date: pd.Timestamp,
) -> dict[str, object]:
    """Write train and validation parquet files using one explicit time cutoff."""
    reset_output_file(train_path)
    reset_output_file(val_path)

    summary = {
        "train_rows": 0,
        "val_rows": 0,
        "unique_users_train": 0,
        "unique_users_val": 0,
        "unique_products_train": 0,
        "unique_products_val": 0,
        "train_min_date": None,
        "train_max_date": None,
        "val_min_date": None,
        "val_max_date": None,
    }
    train_user_ids: set[str] = set()
    val_user_ids: set[str] = set()
    train_product_ids: set[str] = set()
    val_product_ids: set[str] = set()
    train_writer = None
    val_writer = None

    try:
        for batch in iter_parquet_batches(interactions_path, batch_size=chunk_size):
            chunk = batch.to_pandas()
            train_chunk = chunk.loc[chunk["t_dat"] < validation_start_date]
            val_chunk = chunk.loc[chunk["t_dat"] >= validation_start_date]

            if not train_chunk.empty:
                summary["train_rows"] += int(len(train_chunk))
                summary["train_min_date"] = (
                    train_chunk["t_dat"].min()
                    if summary["train_min_date"] is None
                    else min(summary["train_min_date"], train_chunk["t_dat"].min())
                )
                summary["train_max_date"] = (
                    train_chunk["t_dat"].max()
                    if summary["train_max_date"] is None
                    else max(summary["train_max_date"], train_chunk["t_dat"].max())
                )
                train_user_ids.update(train_chunk["user_id"].dropna().unique().tolist())
                train_product_ids.update(train_chunk["product_id"].dropna().unique().tolist())
                train_writer = append_parquet_chunk(train_chunk, train_path, train_writer)

            if not val_chunk.empty:
                summary["val_rows"] += int(len(val_chunk))
                summary["val_min_date"] = (
                    val_chunk["t_dat"].min()
                    if summary["val_min_date"] is None
                    else min(summary["val_min_date"], val_chunk["t_dat"].min())
                )
                summary["val_max_date"] = (
                    val_chunk["t_dat"].max()
                    if summary["val_max_date"] is None
                    else max(summary["val_max_date"], val_chunk["t_dat"].max())
                )
                val_user_ids.update(val_chunk["user_id"].dropna().unique().tolist())
                val_product_ids.update(val_chunk["product_id"].dropna().unique().tolist())
                val_writer = append_parquet_chunk(val_chunk, val_path, val_writer)
    finally:
        close_parquet_writer(train_writer)
        close_parquet_writer(val_writer)

    if summary["train_rows"] == 0:
        write_dataframe_to_parquet(pd.DataFrame(columns=INTERACTION_COLUMNS), train_path)

    if summary["val_rows"] == 0:
        write_dataframe_to_parquet(pd.DataFrame(columns=INTERACTION_COLUMNS), val_path)

    summary["unique_users_train"] = len(train_user_ids)
    summary["unique_users_val"] = len(val_user_ids)
    summary["unique_products_train"] = len(train_product_ids)
    summary["unique_products_val"] = len(val_product_ids)

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a chronological train/validation split for interactions."
    )
    parser.add_argument(
        "--validation-days",
        type=int,
        default=DEFAULT_VALIDATION_DAYS,
        help="Number of final calendar days to reserve for validation.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_INTERACTION_CHUNKSIZE,
        help="Number of interaction rows to process at a time.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    interactions_path = PROCESSED_FILES["interactions"]
    if not interactions_path.exists():
        raise FileNotFoundError(
            "Missing processed interactions file. Run scripts/data/preprocess_hm_data.py first."
        )

    if args.validation_days <= 0:
        raise ValueError("--validation-days must be a positive integer.")

    dataset_min_date, dataset_max_date, validation_start_date = detect_validation_start_date(
        interactions_path=interactions_path,
        chunk_size=args.chunk_size,
        validation_days=args.validation_days,
    )

    split_summary = split_interactions(
        interactions_path=interactions_path,
        train_path=PROCESSED_FILES["interactions_train"],
        val_path=PROCESSED_FILES["interactions_val"],
        chunk_size=args.chunk_size,
        validation_start_date=validation_start_date,
    )

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "chronological_last_n_days",
        "validation_days": args.validation_days,
        "dataset_min_date": format_timestamp(dataset_min_date),
        "dataset_max_date": format_timestamp(dataset_max_date),
        "validation_start_date": format_timestamp(validation_start_date),
        "train_rows": split_summary["train_rows"],
        "val_rows": split_summary["val_rows"],
        "unique_users_train": split_summary["unique_users_train"],
        "unique_users_val": split_summary["unique_users_val"],
        "unique_products_train": split_summary["unique_products_train"],
        "unique_products_val": split_summary["unique_products_val"],
        "train_min_date": format_timestamp(split_summary["train_min_date"]),
        "train_max_date": format_timestamp(split_summary["train_max_date"]),
        "val_min_date": format_timestamp(split_summary["val_min_date"]),
        "val_max_date": format_timestamp(split_summary["val_max_date"]),
        "train_output": PROCESSED_FILES["interactions_train"].as_posix(),
        "val_output": PROCESSED_FILES["interactions_val"].as_posix(),
        "notes": [
            "The validation window is the final N calendar days in the interactions table.",
            "This split stays chronological, which is a better first evaluation setup than a random split.",
            "TODO(phase-2): revisit the split strategy after session-aware ranking objectives are defined.",
        ],
    }
    write_json(metadata, PROCESSED_FILES["split_metadata"])

    print("Time-based split complete.")
    print(f"  validation_start_date: {validation_start_date.date().isoformat()}")
    print(f"  train: {PROCESSED_FILES['interactions_train'].as_posix()}")
    print(f"  val: {PROCESSED_FILES['interactions_val'].as_posix()}")
    print(f"  train_rows: {split_summary['train_rows']:,}")
    print(f"  val_rows: {split_summary['val_rows']:,}")
    print(f"  unique_users_train: {split_summary['unique_users_train']:,}")
    print(f"  unique_users_val: {split_summary['unique_users_val']:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
