from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_PRODUCTS_PATH = REPO_ROOT / "data" / "processed" / "products.parquet"

ARTIFACT_MODELS_DIR = REPO_ROOT / "artifacts" / "models"
ARTIFACT_INDEXES_DIR = REPO_ROOT / "artifacts" / "indexes"

DEFAULT_VECTORIZER_PATH = ARTIFACT_MODELS_DIR / "product_search_vectorizer.pkl"
DEFAULT_INDEX_METADATA_PATH = ARTIFACT_MODELS_DIR / "search_index_metadata.json"
DEFAULT_TFIDF_MATRIX_PATH = ARTIFACT_INDEXES_DIR / "product_search_tfidf_matrix.npz"
DEFAULT_PRODUCT_ID_LOOKUP_PATH = ARTIFACT_INDEXES_DIR / "product_search_product_id_lookup.json"

SEARCH_FIELD_WEIGHTS = {
    "product_name": 3,
    "product_type_name": 2,
    "product_group_name": 2,
    "colour_group_name": 2,
    "department_name": 1,
    "combined_text": 1,
}

DEFAULT_TOP_K = 20
DEFAULT_NGRAM_RANGE = (1, 2)
DEFAULT_STOP_WORDS = "english"
DEFAULT_MIN_DF = 1
DEFAULT_SUBLINEAR_TF = True
DEFAULT_NORM = "l2"


@dataclass(frozen=True)
class SearchArtifactPaths:
    vectorizer_path: Path = DEFAULT_VECTORIZER_PATH
    metadata_path: Path = DEFAULT_INDEX_METADATA_PATH
    tfidf_matrix_path: Path = DEFAULT_TFIDF_MATRIX_PATH
    product_id_lookup_path: Path = DEFAULT_PRODUCT_ID_LOOKUP_PATH


def default_artifact_paths() -> SearchArtifactPaths:
    return SearchArtifactPaths()


@dataclass(frozen=True)
class SearchIndexConfig:
    products_path: Path = DEFAULT_PRODUCTS_PATH
    searchable_fields: tuple[str, ...] = tuple(SEARCH_FIELD_WEIGHTS.keys())
    field_weights: dict[str, int] = field(default_factory=lambda: dict(SEARCH_FIELD_WEIGHTS))
    top_k_default: int = DEFAULT_TOP_K
    ngram_range: tuple[int, int] = DEFAULT_NGRAM_RANGE
    stop_words: str | None = DEFAULT_STOP_WORDS
    min_df: int = DEFAULT_MIN_DF
    sublinear_tf: bool = DEFAULT_SUBLINEAR_TF
    norm: str = DEFAULT_NORM
    artifact_paths: SearchArtifactPaths = field(default_factory=default_artifact_paths)


def default_search_config() -> SearchIndexConfig:
    return SearchIndexConfig()
