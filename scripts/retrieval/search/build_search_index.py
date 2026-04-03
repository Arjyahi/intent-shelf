import argparse
import json
import pickle
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from scipy.sparse import csr_matrix, save_npz
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from .config import SearchArtifactPaths, SearchIndexConfig, default_search_config
except ImportError:
    from config import SearchArtifactPaths, SearchIndexConfig, default_search_config


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_directories(paths: list[Path]) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def save_pickle(path: Path, payload: object) -> None:
    with path.open("wb") as handle:
        pickle.dump(payload, handle)


def normalize_text_value(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def build_weighted_search_document(
    row: pd.Series,
    field_weights: dict[str, int],
) -> str:
    """
    Build one lexical document from explicit product metadata fields.

    Higher-priority fields are repeated more times before TF-IDF vectorization.
    That keeps the weighting easy to inspect and avoids hidden ranking logic.
    """

    parts: list[str] = []
    for field_name, weight in field_weights.items():
        field_text = normalize_text_value(row.get(field_name))
        if not field_text or weight <= 0:
            continue
        parts.extend([field_text] * weight)
    return " ".join(parts)


def load_products_for_index(
    products_path: Path,
    searchable_fields: tuple[str, ...],
    limit_rows: int | None = None,
) -> pd.DataFrame:
    required_columns = ["product_id", *searchable_fields]
    products = pd.read_parquet(products_path, columns=required_columns).copy()
    products["product_id"] = products["product_id"].astype(str)

    if products["product_id"].duplicated().any():
        raise ValueError("products.parquet contains duplicate product_id values.")

    if limit_rows is not None:
        products = products.head(limit_rows).copy()

    return products.sort_values("product_id").reset_index(drop=True)


def build_search_index(
    config: SearchIndexConfig,
    limit_rows: int | None = None,
) -> tuple[pd.DataFrame, TfidfVectorizer, csr_matrix, int]:
    products = load_products_for_index(
        products_path=config.products_path,
        searchable_fields=config.searchable_fields,
        limit_rows=limit_rows,
    )

    search_documents = products.apply(
        lambda row: build_weighted_search_document(row=row, field_weights=config.field_weights),
        axis=1,
    )

    non_empty_mask = search_documents.str.len() > 0
    indexed_products = products.loc[non_empty_mask].reset_index(drop=True)
    indexed_documents = search_documents.loc[non_empty_mask].tolist()
    dropped_empty_documents = int((~non_empty_mask).sum())

    if not indexed_documents:
        raise ValueError(
            "No searchable product documents were created. "
            "Inspect the configured searchable fields and the products input."
        )

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        stop_words=config.stop_words,
        ngram_range=config.ngram_range,
        min_df=config.min_df,
        sublinear_tf=config.sublinear_tf,
        norm=config.norm,
    )
    tfidf_matrix = vectorizer.fit_transform(indexed_documents).tocsr()

    return indexed_products, vectorizer, tfidf_matrix, dropped_empty_documents


def build_index_metadata(
    config: SearchIndexConfig,
    artifact_paths: SearchArtifactPaths,
    indexed_products: pd.DataFrame,
    tfidf_matrix: csr_matrix,
    vocabulary_size: int,
    dropped_empty_documents: int,
    limit_rows: int | None = None,
) -> dict[str, object]:
    return {
        "generated_at": utc_timestamp(),
        "phase": "phase_5_search_retrieval",
        "retrieval_method": "lexical_tfidf",
        "scoring_method": "cosine_similarity_over_l2_normalized_tfidf",
        "vectorizer_type": "sklearn.feature_extraction.text.TfidfVectorizer",
        "input_products_path": config.products_path.as_posix(),
        "output_vectorizer_path": artifact_paths.vectorizer_path.as_posix(),
        "output_metadata_path": artifact_paths.metadata_path.as_posix(),
        "output_tfidf_matrix_path": artifact_paths.tfidf_matrix_path.as_posix(),
        "output_product_lookup_path": artifact_paths.product_id_lookup_path.as_posix(),
        "indexed_fields": list(config.searchable_fields),
        "field_weights": dict(config.field_weights),
        "top_k_default": config.top_k_default,
        "stop_words": config.stop_words,
        "ngram_range": list(config.ngram_range),
        "min_df": config.min_df,
        "sublinear_tf": config.sublinear_tf,
        "norm": config.norm,
        "limit_rows": limit_rows,
        "products_indexed": int(len(indexed_products)),
        "dropped_empty_documents": dropped_empty_documents,
        "vocabulary_size": vocabulary_size,
        "matrix_shape": [int(tfidf_matrix.shape[0]), int(tfidf_matrix.shape[1])],
        "matrix_nnz": int(tfidf_matrix.nnz),
        "notes": [
            "Search documents are built from explicit product metadata fields and combined_text.",
            "Field weighting is implemented by repeating higher-priority fields before TF-IDF vectorization.",
            "This Phase 5 index is lexical only. It does not use CLIP text embeddings, personalization, session context, blending, or reranking.",
            "TODO(phase-6): pass lexical search candidates into search-plus-recommendation blending.",
        ],
    }


def build_and_save_search_artifacts(
    config: SearchIndexConfig | None = None,
    artifact_paths: SearchArtifactPaths | None = None,
    limit_rows: int | None = None,
) -> dict[str, object]:
    config = config or default_search_config()
    artifact_paths = artifact_paths or config.artifact_paths

    if not config.products_path.exists():
        raise FileNotFoundError(
            "Missing products.parquet. Run the Phase 1 preprocessing pipeline first."
        )

    indexed_products, vectorizer, tfidf_matrix, dropped_empty_documents = build_search_index(
        config=config,
        limit_rows=limit_rows,
    )

    ensure_parent_directories(
        [
            artifact_paths.vectorizer_path,
            artifact_paths.metadata_path,
            artifact_paths.tfidf_matrix_path,
            artifact_paths.product_id_lookup_path,
        ]
    )

    save_pickle(artifact_paths.vectorizer_path, vectorizer)
    save_npz(artifact_paths.tfidf_matrix_path, tfidf_matrix)

    product_id_lookup = indexed_products["product_id"].tolist()
    with artifact_paths.product_id_lookup_path.open("w", encoding="utf-8") as handle:
        json.dump(product_id_lookup, handle)

    metadata = build_index_metadata(
        config=config,
        artifact_paths=artifact_paths,
        indexed_products=indexed_products,
        tfidf_matrix=tfidf_matrix,
        vocabulary_size=int(len(vectorizer.vocabulary_)),
        dropped_empty_documents=dropped_empty_documents,
        limit_rows=limit_rows,
    )
    save_json(artifact_paths.metadata_path, metadata)

    return metadata


def parse_args() -> argparse.Namespace:
    defaults = default_search_config()

    parser = argparse.ArgumentParser(
        description="Build a Phase 5 lexical TF-IDF search index from products.parquet."
    )
    parser.add_argument(
        "--products-path",
        type=Path,
        default=defaults.products_path,
        help="Path to the processed products parquet file.",
    )
    parser.add_argument(
        "--vectorizer-path",
        type=Path,
        default=defaults.artifact_paths.vectorizer_path,
        help="Where to save the fitted TF-IDF vectorizer.",
    )
    parser.add_argument(
        "--metadata-path",
        type=Path,
        default=defaults.artifact_paths.metadata_path,
        help="Where to save the search index metadata JSON.",
    )
    parser.add_argument(
        "--tfidf-matrix-path",
        type=Path,
        default=defaults.artifact_paths.tfidf_matrix_path,
        help="Where to save the sparse TF-IDF product matrix.",
    )
    parser.add_argument(
        "--product-lookup-path",
        type=Path,
        default=defaults.artifact_paths.product_id_lookup_path,
        help="Where to save the product_id lookup list for TF-IDF matrix rows.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit for quick local iteration.",
    )
    parser.add_argument(
        "--top-k-default",
        type=int,
        default=defaults.top_k_default,
        help="Default result count stored in the metadata artifact.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    artifact_paths = SearchArtifactPaths(
        vectorizer_path=args.vectorizer_path,
        metadata_path=args.metadata_path,
        tfidf_matrix_path=args.tfidf_matrix_path,
        product_id_lookup_path=args.product_lookup_path,
    )
    config = SearchIndexConfig(
        products_path=args.products_path,
        top_k_default=args.top_k_default,
        artifact_paths=artifact_paths,
    )

    metadata = build_and_save_search_artifacts(
        config=config,
        artifact_paths=artifact_paths,
        limit_rows=args.limit,
    )

    print("Lexical search index build complete.")
    print(f"  vectorizer_path: {artifact_paths.vectorizer_path.as_posix()}")
    print(f"  tfidf_matrix_path: {artifact_paths.tfidf_matrix_path.as_posix()}")
    print(f"  product_lookup_path: {artifact_paths.product_id_lookup_path.as_posix()}")
    print(f"  metadata_path: {artifact_paths.metadata_path.as_posix()}")
    print(f"  products_indexed: {metadata['products_indexed']:,}")
    print(f"  vocabulary_size: {metadata['vocabulary_size']:,}")
    print(f"  matrix_shape: {metadata['matrix_shape']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
