from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.sparse import coo_matrix, csr_matrix

try:
    from .config import INTERACTION_COLUMNS, PRODUCT_COLUMNS
except ImportError:
    from config import INTERACTION_COLUMNS, PRODUCT_COLUMNS


@dataclass(frozen=True)
class MatrixBuildSummary:
    raw_rows: int
    rows_after_catalog_filter: int
    aggregated_rows: int
    duplicate_rows_collapsed: int
    dropped_missing_product_rows: int
    unique_users_before_thresholds: int
    unique_products_before_thresholds: int
    unique_users_after_thresholds: int
    unique_products_after_thresholds: int
    matrix_rows: int
    matrix_cols: int
    matrix_nnz: int


@dataclass(frozen=True)
class MatrixBuildArtifacts:
    aggregated_interactions: pd.DataFrame
    user_id_lookup: list[str]
    product_id_lookup: list[str]
    interaction_matrix: csr_matrix
    summary: MatrixBuildSummary


def load_catalog_product_ids(products_path: Path) -> set[str]:
    products = pd.read_parquet(products_path, columns=PRODUCT_COLUMNS)
    product_ids = products["product_id"].dropna().astype(str).tolist()
    return set(product_ids)


def load_interactions_dataframe(
    interactions_path: Path,
    limit_rows: int | None = None,
    batch_size: int = 500_000,
) -> pd.DataFrame:
    if limit_rows is None:
        frame = pd.read_parquet(interactions_path, columns=INTERACTION_COLUMNS)
    else:
        parquet_file = pq.ParquetFile(interactions_path)
        chunks: list[pd.DataFrame] = []
        rows_remaining = limit_rows

        for batch in parquet_file.iter_batches(
            batch_size=min(batch_size, max(limit_rows, 1)),
            columns=INTERACTION_COLUMNS,
        ):
            chunk = batch.to_pandas()
            if rows_remaining < len(chunk):
                chunk = chunk.iloc[:rows_remaining].copy()
            chunks.append(chunk)
            rows_remaining -= len(chunk)
            if rows_remaining <= 0:
                break

        if not chunks:
            frame = pd.DataFrame(columns=INTERACTION_COLUMNS)
        else:
            frame = pd.concat(chunks, ignore_index=True)

    frame = frame.dropna(subset=["user_id", "product_id", "interaction_strength"]).copy()
    frame["user_id"] = frame["user_id"].astype(str)
    frame["product_id"] = frame["product_id"].astype(str)
    frame["interaction_strength"] = frame["interaction_strength"].astype(np.float32)
    return frame


def aggregate_interactions(interactions: pd.DataFrame) -> pd.DataFrame:
    if interactions.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "product_id",
                "interaction_strength",
                "raw_interaction_count",
            ]
        )

    aggregated = (
        interactions.groupby(["user_id", "product_id"], as_index=False, sort=False)
        .agg(
            interaction_strength=("interaction_strength", "sum"),
            raw_interaction_count=("interaction_strength", "size"),
        )
        .reset_index(drop=True)
    )
    aggregated["interaction_strength"] = aggregated["interaction_strength"].astype(np.float32)
    aggregated["raw_interaction_count"] = aggregated["raw_interaction_count"].astype(np.int32)
    return aggregated


def filter_to_catalog_products(
    aggregated_interactions: pd.DataFrame,
    catalog_product_ids: set[str],
) -> pd.DataFrame:
    if aggregated_interactions.empty:
        return aggregated_interactions.copy()

    filtered = aggregated_interactions.loc[
        aggregated_interactions["product_id"].isin(catalog_product_ids)
    ].copy()
    return filtered.reset_index(drop=True)


def filter_by_min_interactions(
    aggregated_interactions: pd.DataFrame,
    min_user_interactions: int = 1,
    min_product_interactions: int = 1,
) -> pd.DataFrame:
    if aggregated_interactions.empty:
        return aggregated_interactions.copy()

    filtered = aggregated_interactions

    if min_user_interactions > 1:
        user_counts = filtered.groupby("user_id").size()
        keep_user_ids = set(
            user_counts.loc[user_counts >= min_user_interactions].index.astype(str).tolist()
        )
        filtered = filtered.loc[filtered["user_id"].isin(keep_user_ids)].copy()

    if min_product_interactions > 1:
        product_counts = filtered.groupby("product_id").size()
        keep_product_ids = set(
            product_counts.loc[product_counts >= min_product_interactions].index.astype(str).tolist()
        )
        filtered = filtered.loc[filtered["product_id"].isin(keep_product_ids)].copy()

    return filtered.reset_index(drop=True)


def build_id_lookup(values: pd.Series) -> list[str]:
    return sorted(values.dropna().astype(str).unique().tolist())


def build_sparse_interaction_matrix(
    aggregated_interactions: pd.DataFrame,
    user_id_lookup: list[str],
    product_id_lookup: list[str],
) -> csr_matrix:
    user_id_to_index = {
        user_id: row_index
        for row_index, user_id in enumerate(user_id_lookup)
    }
    product_id_to_index = {
        product_id: col_index
        for col_index, product_id in enumerate(product_id_lookup)
    }

    row_indices = aggregated_interactions["user_id"].map(user_id_to_index).to_numpy(dtype=np.int32)
    col_indices = aggregated_interactions["product_id"].map(product_id_to_index).to_numpy(dtype=np.int32)
    values = aggregated_interactions["interaction_strength"].to_numpy(dtype=np.float32)

    interaction_matrix = coo_matrix(
        (values, (row_indices, col_indices)),
        shape=(len(user_id_lookup), len(product_id_lookup)),
        dtype=np.float32,
    )
    return interaction_matrix.tocsr()


def build_collaborative_matrix_artifacts(
    interactions_path: Path,
    products_path: Path,
    limit_rows: int | None = None,
    batch_size: int = 500_000,
    min_user_interactions: int = 1,
    min_product_interactions: int = 1,
) -> MatrixBuildArtifacts:
    interactions = load_interactions_dataframe(
        interactions_path=interactions_path,
        limit_rows=limit_rows,
        batch_size=batch_size,
    )
    raw_rows = int(len(interactions))

    aggregated_interactions = aggregate_interactions(interactions)
    catalog_product_ids = load_catalog_product_ids(products_path)
    aggregated_interactions = filter_to_catalog_products(
        aggregated_interactions=aggregated_interactions,
        catalog_product_ids=catalog_product_ids,
    )

    rows_after_catalog_filter = int(aggregated_interactions["raw_interaction_count"].sum())
    dropped_missing_product_rows = raw_rows - rows_after_catalog_filter
    duplicate_rows_collapsed = rows_after_catalog_filter - int(len(aggregated_interactions))

    unique_users_before_thresholds = int(aggregated_interactions["user_id"].nunique())
    unique_products_before_thresholds = int(aggregated_interactions["product_id"].nunique())

    filtered_interactions = filter_by_min_interactions(
        aggregated_interactions=aggregated_interactions,
        min_user_interactions=min_user_interactions,
        min_product_interactions=min_product_interactions,
    )

    user_id_lookup = build_id_lookup(filtered_interactions["user_id"])
    product_id_lookup = build_id_lookup(filtered_interactions["product_id"])
    interaction_matrix = build_sparse_interaction_matrix(
        aggregated_interactions=filtered_interactions,
        user_id_lookup=user_id_lookup,
        product_id_lookup=product_id_lookup,
    )

    summary = MatrixBuildSummary(
        raw_rows=raw_rows,
        rows_after_catalog_filter=rows_after_catalog_filter,
        aggregated_rows=int(len(aggregated_interactions)),
        duplicate_rows_collapsed=duplicate_rows_collapsed,
        dropped_missing_product_rows=dropped_missing_product_rows,
        unique_users_before_thresholds=unique_users_before_thresholds,
        unique_products_before_thresholds=unique_products_before_thresholds,
        unique_users_after_thresholds=int(filtered_interactions["user_id"].nunique()),
        unique_products_after_thresholds=int(filtered_interactions["product_id"].nunique()),
        matrix_rows=int(interaction_matrix.shape[0]),
        matrix_cols=int(interaction_matrix.shape[1]),
        matrix_nnz=int(interaction_matrix.nnz),
    )

    return MatrixBuildArtifacts(
        aggregated_interactions=filtered_interactions,
        user_id_lookup=user_id_lookup,
        product_id_lookup=product_id_lookup,
        interaction_matrix=interaction_matrix,
        summary=summary,
    )
