from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_INTERACTIONS_PATH = REPO_ROOT / "data" / "processed" / "interactions_train.parquet"
DEFAULT_PRODUCTS_PATH = REPO_ROOT / "data" / "processed" / "products.parquet"

ARTIFACT_MODELS_DIR = REPO_ROOT / "artifacts" / "models"
ARTIFACT_INDEXES_DIR = REPO_ROOT / "artifacts" / "indexes"

DEFAULT_MODEL_PATH = ARTIFACT_MODELS_DIR / "implicit_model.npz"
DEFAULT_USER_ID_LOOKUP_PATH = ARTIFACT_INDEXES_DIR / "user_id_lookup.json"
DEFAULT_PRODUCT_ID_LOOKUP_PATH = ARTIFACT_INDEXES_DIR / "product_id_lookup_collaborative.json"
DEFAULT_USER_ITEM_MATRIX_PATH = ARTIFACT_INDEXES_DIR / "collaborative_user_item_matrix.npz"
DEFAULT_TRAINING_METADATA_PATH = ARTIFACT_MODELS_DIR / "collaborative_training_metadata.json"

INTERACTION_COLUMNS = [
    "user_id",
    "product_id",
    "interaction_strength",
]

PRODUCT_COLUMNS = [
    "product_id",
]

DEFAULT_TOP_K = 20
DEFAULT_EXCLUDE_SEEN_ITEMS = True
DEFAULT_RANDOM_SEED = 42
DEFAULT_INTERACTION_BATCH_SIZE = 500_000
DEFAULT_MIN_USER_INTERACTIONS = 1
DEFAULT_MIN_PRODUCT_INTERACTIONS = 1

DEFAULT_MODEL_BACKEND = "implicit"
DEFAULT_MODEL_TYPE = "bpr"
DEFAULT_FACTORS = 32
DEFAULT_ITERATIONS = 50
DEFAULT_LEARNING_RATE = 0.05
DEFAULT_REGULARIZATION = 0.01
DEFAULT_VERIFY_NEGATIVE_SAMPLES = True
DEFAULT_NUM_THREADS = 4


@dataclass(frozen=True)
class CollaborativeArtifactPaths:
    model_path: Path = DEFAULT_MODEL_PATH
    user_id_lookup_path: Path = DEFAULT_USER_ID_LOOKUP_PATH
    product_id_lookup_path: Path = DEFAULT_PRODUCT_ID_LOOKUP_PATH
    user_item_matrix_path: Path = DEFAULT_USER_ITEM_MATRIX_PATH
    training_metadata_path: Path = DEFAULT_TRAINING_METADATA_PATH


def default_artifact_paths() -> CollaborativeArtifactPaths:
    return CollaborativeArtifactPaths()


@dataclass(frozen=True)
class CollaborativeTrainingConfig:
    interactions_path: Path = DEFAULT_INTERACTIONS_PATH
    products_path: Path = DEFAULT_PRODUCTS_PATH
    top_k_default: int = DEFAULT_TOP_K
    exclude_seen_items_default: bool = DEFAULT_EXCLUDE_SEEN_ITEMS
    random_seed: int = DEFAULT_RANDOM_SEED
    interaction_batch_size: int = DEFAULT_INTERACTION_BATCH_SIZE
    min_user_interactions: int = DEFAULT_MIN_USER_INTERACTIONS
    min_product_interactions: int = DEFAULT_MIN_PRODUCT_INTERACTIONS
    model_backend: str = DEFAULT_MODEL_BACKEND
    model_type: str = DEFAULT_MODEL_TYPE
    factors: int = DEFAULT_FACTORS
    iterations: int = DEFAULT_ITERATIONS
    learning_rate: float = DEFAULT_LEARNING_RATE
    regularization: float = DEFAULT_REGULARIZATION
    verify_negative_samples: bool = DEFAULT_VERIFY_NEGATIVE_SAMPLES
    num_threads: int = DEFAULT_NUM_THREADS
    artifact_paths: CollaborativeArtifactPaths = field(default_factory=default_artifact_paths)


def default_training_config() -> CollaborativeTrainingConfig:
    return CollaborativeTrainingConfig()
