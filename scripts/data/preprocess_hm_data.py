import argparse
from datetime import datetime, timezone

import pandas as pd

from config import (
    COMBINED_TEXT_COLUMNS,
    DEFAULT_INTERACTION_CHUNKSIZE,
    INTERACTION_COLUMNS,
    INTERACTION_SOURCE_COLUMNS,
    PRODUCT_COLUMNS,
    PRODUCT_SOURCE_COLUMNS,
    PROCESSED_FILES,
    USER_COLUMNS,
    USER_SOURCE_COLUMNS,
    RAW_FILES,
)
from helpers import (
    append_parquet_chunk,
    build_combined_text,
    canonicalize_product_id_series,
    canonicalize_user_id_series,
    close_parquet_writer,
    clean_age_series,
    clean_text_series,
    format_timestamp,
    normalize_fashion_news_series,
    normalize_status_series,
    reset_output_file,
    resolve_image_path,
    write_dataframe_to_parquet,
    write_json,
)
from validate_raw_data import validate_required_raw_inputs


def preprocess_products() -> tuple[pd.DataFrame, dict[str, object]]:
    """Create the cleaned products table and attach image-path metadata."""
    raw_products = pd.read_csv(
        RAW_FILES["articles"],
        usecols=PRODUCT_SOURCE_COLUMNS,
        dtype={
            "article_id": "string",
            "prod_name": "string",
            "product_type_name": "string",
            "product_group_name": "string",
            "graphical_appearance_name": "string",
            "colour_group_name": "string",
            "perceived_colour_value_name": "string",
            "perceived_colour_master_name": "string",
            "department_name": "string",
            "index_name": "string",
            "index_group_name": "string",
            "section_name": "string",
            "garment_group_name": "string",
            "detail_desc": "string",
        },
        low_memory=False,
    )

    products = raw_products.rename(
        columns={
            "article_id": "product_id",
            "prod_name": "product_name",
        }
    ).copy()

    products["product_id"] = canonicalize_product_id_series(products["product_id"])

    text_columns = [column for column in products.columns if column != "product_id"]
    for column in text_columns:
        products[column] = clean_text_series(products[column])

    products = products.dropna(subset=["product_id", "product_name"]).drop_duplicates(
        subset=["product_id"]
    )

    image_mapping = products["product_id"].apply(resolve_image_path)
    products["image_path"] = image_mapping.str[0]
    products["has_image"] = image_mapping.str[1].fillna(False).astype(bool)
    products["combined_text"] = products.apply(
        build_combined_text,
        axis=1,
        text_columns=COMBINED_TEXT_COLUMNS,
    )

    products = products[PRODUCT_COLUMNS]

    summary = {
        "raw_rows": int(len(raw_products)),
        "output_rows": int(len(products)),
        "rows_with_images": int(products["has_image"].sum()),
        "image_coverage_rate": round(float(products["has_image"].mean()), 4),
        "missing_detail_desc_rows": int(products["detail_desc"].isna().sum()),
        "columns": PRODUCT_COLUMNS,
    }

    return products, summary


def preprocess_users() -> tuple[pd.DataFrame, dict[str, object]]:
    """Create the cleaned users table with a small, readable feature set."""
    raw_users = pd.read_csv(
        RAW_FILES["customers"],
        usecols=USER_SOURCE_COLUMNS,
        dtype={
            "customer_id": "string",
            "club_member_status": "string",
            "fashion_news_frequency": "string",
            "postal_code": "string",
        },
        low_memory=False,
    )

    users = raw_users.rename(columns={"customer_id": "user_id"}).copy()
    users["user_id"] = canonicalize_user_id_series(users["user_id"])
    users["club_member_status"] = normalize_status_series(users["club_member_status"])
    users["fashion_news_frequency"] = normalize_fashion_news_series(
        users["fashion_news_frequency"]
    )
    users["age"] = clean_age_series(users["age"])
    users["postal_code"] = clean_text_series(users["postal_code"])

    users = users.dropna(subset=["user_id"]).drop_duplicates(subset=["user_id"])
    users = users[USER_COLUMNS]

    summary = {
        "raw_rows": int(len(raw_users)),
        "output_rows": int(len(users)),
        "missing_age_rows": int(users["age"].isna().sum()),
        "columns": USER_COLUMNS,
    }

    return users, summary


def preprocess_interactions(
    valid_user_ids: set[str],
    valid_product_ids: set[str],
    chunk_size: int,
) -> dict[str, object]:
    """Stream the large transactions file into one cleaned interactions table."""
    output_path = PROCESSED_FILES["interactions"]
    reset_output_file(output_path)

    summary = {
        "raw_rows": 0,
        "output_rows": 0,
        "dropped_missing_core_fields": 0,
        "dropped_invalid_price": 0,
        "dropped_unknown_user": 0,
        "dropped_unknown_product": 0,
        "date_min": None,
        "date_max": None,
        "columns": INTERACTION_COLUMNS,
    }
    writer = None

    chunk_iterator = pd.read_csv(
        RAW_FILES["transactions"],
        usecols=INTERACTION_SOURCE_COLUMNS,
        dtype={
            "customer_id": "string",
            "article_id": "string",
            "price": "float32",
            "sales_channel_id": "Int8",
        },
        chunksize=chunk_size,
        low_memory=False,
    )

    try:
        for chunk in chunk_iterator:
            summary["raw_rows"] += int(len(chunk))

            interactions = chunk.rename(
                columns={
                    "customer_id": "user_id",
                    "article_id": "product_id",
                }
            ).copy()

            interactions["user_id"] = canonicalize_user_id_series(interactions["user_id"])
            interactions["product_id"] = canonicalize_product_id_series(
                interactions["product_id"]
            )
            interactions["t_dat"] = pd.to_datetime(interactions["t_dat"], errors="coerce")
            interactions["price"] = pd.to_numeric(interactions["price"], errors="coerce")
            interactions["sales_channel_id"] = pd.to_numeric(
                interactions["sales_channel_id"], errors="coerce"
            ).astype("Int8")
            interactions["interaction_strength"] = 1.0

            missing_core_mask = interactions[
                ["user_id", "product_id", "t_dat"]
            ].isna().any(axis=1)
            summary["dropped_missing_core_fields"] += int(missing_core_mask.sum())
            interactions = interactions.loc[~missing_core_mask]

            invalid_price_mask = interactions["price"].isna() | (interactions["price"] <= 0)
            summary["dropped_invalid_price"] += int(invalid_price_mask.sum())
            interactions = interactions.loc[~invalid_price_mask]

            known_user_mask = interactions["user_id"].isin(valid_user_ids)
            summary["dropped_unknown_user"] += int((~known_user_mask).sum())
            interactions = interactions.loc[known_user_mask]

            known_product_mask = interactions["product_id"].isin(valid_product_ids)
            summary["dropped_unknown_product"] += int((~known_product_mask).sum())
            interactions = interactions.loc[known_product_mask]

            if interactions.empty:
                continue

            interactions = interactions[INTERACTION_COLUMNS]

            chunk_min = interactions["t_dat"].min()
            chunk_max = interactions["t_dat"].max()

            summary["date_min"] = (
                chunk_min
                if summary["date_min"] is None
                else min(summary["date_min"], chunk_min)
            )
            summary["date_max"] = (
                chunk_max
                if summary["date_max"] is None
                else max(summary["date_max"], chunk_max)
            )

            summary["output_rows"] += int(len(interactions))
            writer = append_parquet_chunk(interactions, output_path, writer)
    finally:
        close_parquet_writer(writer)

    if summary["output_rows"] == 0:
        write_dataframe_to_parquet(pd.DataFrame(columns=INTERACTION_COLUMNS), output_path)

    summary["total_rows_dropped"] = (
        summary["dropped_missing_core_fields"]
        + summary["dropped_invalid_price"]
        + summary["dropped_unknown_user"]
        + summary["dropped_unknown_product"]
    )
    summary["drop_rate"] = round(
        summary["total_rows_dropped"] / summary["raw_rows"], 4
    ) if summary["raw_rows"] else 0.0
    summary["drop_reason_explanations"] = {
        "dropped_missing_core_fields": (
            "Rows missing user_id, product_id, or a parseable transaction date."
        ),
        "dropped_invalid_price": "Rows with missing price or non-positive price.",
        "dropped_unknown_user": "Rows whose user_id did not survive the cleaned users table.",
        "dropped_unknown_product": "Rows whose product_id did not survive the cleaned products table.",
    }

    return summary


def build_preprocessing_summary(
    products_summary: dict[str, object],
    users_summary: dict[str, object],
    interactions_summary: dict[str, object],
    chunk_size: int,
) -> dict[str, object]:
    """Collect the main Phase 1 preprocessing facts in one JSON document."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Phase 1 keeps the preprocessing logic intentionally simple and inspectable.",
            "Transactions are processed in chunks because the raw file is much larger than the product and user tables.",
            "Processed outputs are stored as parquet so later experiments can reload them faster with better type preservation than CSV.",
            "Each interaction row represents one purchase event, so interaction_strength is fixed to 1.0 for now.",
        ],
        "config": {
            "interaction_chunk_size": chunk_size,
            "products_output": PROCESSED_FILES["products"].as_posix(),
            "users_output": PROCESSED_FILES["users"].as_posix(),
            "interactions_output": PROCESSED_FILES["interactions"].as_posix(),
            "output_format": "parquet",
        },
        "products": products_summary,
        "users": users_summary,
        "interactions": {
            **interactions_summary,
            "date_min": format_timestamp(interactions_summary["date_min"]),
            "date_max": format_timestamp(interactions_summary["date_max"]),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess the raw H&M data into clean Phase 1 tables."
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_INTERACTION_CHUNKSIZE,
        help="Number of transaction rows to process at a time.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_required_raw_inputs()

    products, products_summary = preprocess_products()
    users, users_summary = preprocess_users()

    write_dataframe_to_parquet(products, PROCESSED_FILES["products"])
    write_dataframe_to_parquet(users, PROCESSED_FILES["users"])

    valid_user_ids = set(users["user_id"].dropna().tolist())
    valid_product_ids = set(products["product_id"].dropna().tolist())

    interactions_summary = preprocess_interactions(
        valid_user_ids=valid_user_ids,
        valid_product_ids=valid_product_ids,
        chunk_size=args.chunk_size,
    )

    summary_payload = build_preprocessing_summary(
        products_summary=products_summary,
        users_summary=users_summary,
        interactions_summary=interactions_summary,
        chunk_size=args.chunk_size,
    )
    write_json(summary_payload, PROCESSED_FILES["preprocessing_summary"])

    print("Preprocessing complete.")
    print(f"  products: {PROCESSED_FILES['products'].as_posix()}")
    print(f"  users: {PROCESSED_FILES['users'].as_posix()}")
    print(f"  interactions: {PROCESSED_FILES['interactions'].as_posix()}")
    print(f"  interaction rows read: {interactions_summary['raw_rows']:,}")
    print(f"  interaction rows kept: {interactions_summary['output_rows']:,}")
    print(
        "  interaction rows dropped: "
        f"{interactions_summary['total_rows_dropped']:,} "
        f"({interactions_summary['drop_rate']:.2%})"
    )
    print(
        "    dropped_missing_core_fields: "
        f"{interactions_summary['dropped_missing_core_fields']:,}"
    )
    print(
        "    dropped_invalid_price: "
        f"{interactions_summary['dropped_invalid_price']:,}"
    )
    print(
        "    dropped_unknown_user: "
        f"{interactions_summary['dropped_unknown_user']:,}"
    )
    print(
        "    dropped_unknown_product: "
        f"{interactions_summary['dropped_unknown_product']:,}"
    )
    print(
        "  TODO(phase-2): replace the constant interaction_strength only after "
        "multiple interaction types exist."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
