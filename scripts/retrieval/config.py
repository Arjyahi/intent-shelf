from pathlib import Path

# Phase 3 works from the processed product table created in Phase 1.
REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_PRODUCTS_PATH = REPO_ROOT / "data" / "processed" / "products.parquet"
RAW_IMAGE_ROOT = REPO_ROOT

ARTIFACT_MODELS_DIR = REPO_ROOT / "artifacts" / "models"
ARTIFACT_INDEXES_DIR = REPO_ROOT / "artifacts" / "indexes"

TEXT_EMBEDDINGS_PATH = ARTIFACT_INDEXES_DIR / "product_text_embeddings.npy"
IMAGE_EMBEDDINGS_PATH = ARTIFACT_INDEXES_DIR / "product_image_embeddings.npy"
IMAGE_AVAILABLE_MASK_PATH = ARTIFACT_INDEXES_DIR / "product_image_available_mask.npy"
MULTIMODAL_EMBEDDINGS_PATH = ARTIFACT_INDEXES_DIR / "product_multimodal_embeddings.npy"
PRODUCT_ID_LOOKUP_PATH = ARTIFACT_INDEXES_DIR / "product_id_lookup.json"
FAISS_INDEX_PATH = ARTIFACT_INDEXES_DIR / "product_multimodal.faiss"

TEXT_METADATA_PATH = ARTIFACT_MODELS_DIR / "text_embedding_metadata.json"
IMAGE_METADATA_PATH = ARTIFACT_MODELS_DIR / "image_embedding_metadata.json"
MULTIMODAL_METADATA_PATH = ARTIFACT_MODELS_DIR / "multimodal_embedding_metadata.json"

DEFAULT_CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
DEFAULT_TEXT_BATCH_SIZE = 128
DEFAULT_IMAGE_BATCH_SIZE = 32
DEFAULT_FUSION_ALPHA = 0.6
DEFAULT_TOP_K = 12

PRODUCT_TEXT_FALLBACK_COLUMNS = [
    "product_name",
    "product_type_name",
    "product_group_name",
    "graphical_appearance_name",
    "colour_group_name",
    "department_name",
    "section_name",
    "detail_desc",
]

BASIC_PRODUCT_COLUMNS = [
    "product_id",
    "product_name",
    "product_type_name",
    "product_group_name",
    "detail_desc",
    "image_path",
    "has_image",
    "combined_text",
]
