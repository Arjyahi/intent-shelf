from pathlib import Path

# The Phase 1 scripts resolve paths from the repository root so they can be
# launched from anywhere.
REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DOCS_DIR = REPO_ROOT / "docs"
IMAGES_DIR = RAW_DIR / "images"

RAW_FILES = {
    "articles": RAW_DIR / "articles.csv",
    "customers": RAW_DIR / "customers.csv",
    "transactions": RAW_DIR / "transactions_train.csv",
}

PROCESSED_FILES = {
    "products": PROCESSED_DIR / "products.parquet",
    "users": PROCESSED_DIR / "users.parquet",
    "interactions": PROCESSED_DIR / "interactions.parquet",
    "interactions_train": PROCESSED_DIR / "interactions_train.parquet",
    "interactions_val": PROCESSED_DIR / "interactions_val.parquet",
    "preprocessing_summary": PROCESSED_DIR / "preprocessing_summary.json",
    "split_metadata": PROCESSED_DIR / "split_metadata.json",
}

PRODUCT_SOURCE_COLUMNS = [
    "article_id",
    "prod_name",
    "product_type_name",
    "product_group_name",
    "graphical_appearance_name",
    "colour_group_name",
    "perceived_colour_value_name",
    "perceived_colour_master_name",
    "department_name",
    "index_name",
    "index_group_name",
    "section_name",
    "garment_group_name",
    "detail_desc",
]

USER_SOURCE_COLUMNS = [
    "customer_id",
    "club_member_status",
    "fashion_news_frequency",
    "age",
    "postal_code",
]

INTERACTION_SOURCE_COLUMNS = [
    "t_dat",
    "customer_id",
    "article_id",
    "price",
    "sales_channel_id",
]

REQUIRED_COLUMNS = {
    "articles": PRODUCT_SOURCE_COLUMNS,
    "customers": USER_SOURCE_COLUMNS,
    "transactions": INTERACTION_SOURCE_COLUMNS,
}

PRODUCT_COLUMNS = [
    "product_id",
    "product_name",
    "product_type_name",
    "product_group_name",
    "graphical_appearance_name",
    "colour_group_name",
    "perceived_colour_value_name",
    "perceived_colour_master_name",
    "department_name",
    "index_name",
    "index_group_name",
    "section_name",
    "garment_group_name",
    "detail_desc",
    "image_path",
    "has_image",
    "combined_text",
]

USER_COLUMNS = [
    "user_id",
    "club_member_status",
    "fashion_news_frequency",
    "age",
    "postal_code",
]

INTERACTION_COLUMNS = [
    "user_id",
    "product_id",
    "t_dat",
    "price",
    "sales_channel_id",
    "interaction_strength",
]

COMBINED_TEXT_COLUMNS = [
    "product_name",
    "product_type_name",
    "product_group_name",
    "graphical_appearance_name",
    "colour_group_name",
    "perceived_colour_value_name",
    "perceived_colour_master_name",
    "department_name",
    "index_name",
    "index_group_name",
    "section_name",
    "garment_group_name",
    "detail_desc",
]

DEFAULT_INTERACTION_CHUNKSIZE = 500_000
DEFAULT_VALIDATION_DAYS = 7
