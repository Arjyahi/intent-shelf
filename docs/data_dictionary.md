# IntentShelf Phase 1 Data Dictionary

This document describes the cleaned Phase 1 tables produced from the raw H&M dataset.

Phase 1 scope is intentionally limited to:

- raw file validation
- tabular preprocessing
- product-to-image-path mapping
- chronological train/validation splitting

It does **not** include retrieval, ranking, embeddings, or database modeling.

## Source Files Used

- `data/raw/articles.csv`
- `data/raw/customers.csv`
- `data/raw/transactions_train.csv`
- `data/raw/images/`

Ignored in Phase 1:

- `data/raw/sample_submission.csv`

## ID Conventions

- `product_id`: a zero-padded 10-character string derived from `article_id`
- `user_id`: the raw `customer_id` string, trimmed but otherwise unchanged

The zero-padded `product_id` makes the product table, interaction table, and image filenames line up cleanly.

## Processed Tables

### `products.parquet`

One row per product/article from `articles.csv`, stored as parquet.

Important columns:

- `product_id`: canonical product key used across the repo
- `product_name`: cleaned version of `prod_name`
- `product_type_name`, `product_group_name`, `garment_group_name`: broad product taxonomy
- `graphical_appearance_name`, `colour_group_name`, `perceived_colour_value_name`, `perceived_colour_master_name`: style and color metadata
- `department_name`, `index_name`, `index_group_name`, `section_name`: merchandising hierarchy fields
- `detail_desc`: free-text product description when available
- `image_path`: relative repo path to the expected product image file if it exists
- `has_image`: boolean image availability flag
- `combined_text`: concatenated text field reserved for later search and text-embedding work

Key preprocessing choices:

- keep readable name fields instead of every numeric taxonomy code
- preserve both short taxonomy labels and longer free text
- do not touch image pixels yet
- store missing `image_path` as empty / null and use `has_image` for explicit availability

### `users.parquet`

One row per customer from `customers.csv`, stored as parquet.

Important columns:

- `user_id`: canonical user key
- `club_member_status`: cleaned membership status, filled with `UNKNOWN` when missing
- `fashion_news_frequency`: normalized to uppercase categories such as `NONE`, `MONTHLY`, `REGULARLY`, or `UNKNOWN`
- `age`: numeric age, with clearly implausible values removed if they appear
- `postal_code`: hashed postal code string from the source data

Key preprocessing choices:

- keep only the user attributes that are easy to understand and likely useful later
- exclude cryptic raw fields like `FN` and `Active` for now to keep the first pass understandable

### `interactions.parquet`

One row per purchase interaction from `transactions_train.csv`, stored as parquet.

Important columns:

- `user_id`
- `product_id`
- `t_dat`: parsed transaction date
- `price`
- `sales_channel_id`
- `interaction_strength`: fixed to `1.0` because every Phase 1 interaction is a purchase row

Key preprocessing choices:

- parse `t_dat` into a real timestamp column
- drop rows missing core join keys or dates
- drop rows with non-positive or missing prices
- keep all valid purchase rows rather than deduplicating repeated purchases

## Image Mapping Rules

The H&M image directory uses filenames based on zero-padded article IDs.

Example:

- raw article id: `108775015`
- canonical `product_id`: `0108775015`
- expected image path: `data/raw/images/010/0108775015.jpg`

Phase 1 only checks whether that file exists and stores the path when present.

## Time-Based Split

The split script creates:

- `interactions_train.parquet`
- `interactions_val.parquet`
- `split_metadata.json`

The default rule is:

- reserve the final 7 calendar days of interactions for validation
- keep everything earlier in train

This is a simpler and more defensible first recommender-system evaluation setup than a random split because it respects time.

## Output Summaries

Phase 1 also writes:

- `preprocessing_summary.json`: row counts, drop counts, image coverage, date range, and output paths
- `split_metadata.json`: exact validation start date, split row counts, and unique user/product counts per split

## Why Processed Outputs Use Parquet

Raw H&M files stay as CSV because that is how the source dataset arrives from Kaggle.

Processed outputs switch to parquet because it is a better working format for later recommender experiments:

- better type preservation for timestamps, booleans, and nullable columns
- smaller files than plain CSV
- faster reloads when iterating on retrieval and evaluation code

TODO(phase-2): add richer dataset profiling once retrieval candidates and offline metrics exist.
