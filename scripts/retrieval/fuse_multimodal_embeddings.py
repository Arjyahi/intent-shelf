import argparse
import numpy as np

from config import (
    BASIC_PRODUCT_COLUMNS,
    DEFAULT_FUSION_ALPHA,
    IMAGE_AVAILABLE_MASK_PATH,
    IMAGE_EMBEDDINGS_PATH,
    IMAGE_METADATA_PATH,
    MULTIMODAL_EMBEDDINGS_PATH,
    MULTIMODAL_METADATA_PATH,
    PRODUCT_ID_LOOKUP_PATH,
    TEXT_EMBEDDINGS_PATH,
    TEXT_METADATA_PATH,
)
from helpers import l2_normalize, load_json, load_products, utc_now_iso, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fuse CLIP text and image embeddings into one multimodal product representation."
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_FUSION_ALPHA,
        help="Weight given to text embeddings when both text and image embeddings exist.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional product limit for development or debugging.",
    )
    return parser.parse_args()


def validate_alignment(
    products_count: int,
    text_embeddings: np.ndarray,
    image_embeddings: np.ndarray,
    image_available_mask: np.ndarray,
) -> None:
    if text_embeddings.shape[0] != products_count:
        raise ValueError(
            "Text embeddings are not aligned with the current products table. "
            "Re-run generate_text_embeddings.py with the same --limit setting."
        )
    if image_embeddings.shape[0] != products_count:
        raise ValueError(
            "Image embeddings are not aligned with the current products table. "
            "Re-run generate_image_embeddings.py with the same --limit setting."
        )
    if image_available_mask.shape[0] != products_count:
        raise ValueError("Image availability mask is not aligned with the current products table.")
    if text_embeddings.shape[1] != image_embeddings.shape[1]:
        raise ValueError("Text and image embeddings must have the same dimension before fusion.")


def main() -> int:
    args = parse_args()
    if not 0.0 <= args.alpha <= 1.0:
        raise ValueError("--alpha must be between 0.0 and 1.0.")

    products = load_products(limit=args.limit, columns=BASIC_PRODUCT_COLUMNS)
    text_embeddings = np.load(TEXT_EMBEDDINGS_PATH)
    image_embeddings = np.load(IMAGE_EMBEDDINGS_PATH)
    image_available_mask = np.load(IMAGE_AVAILABLE_MASK_PATH).astype(bool)

    validate_alignment(
        products_count=len(products),
        text_embeddings=text_embeddings,
        image_embeddings=image_embeddings,
        image_available_mask=image_available_mask,
    )

    text_metadata = load_json(TEXT_METADATA_PATH)
    image_metadata = load_json(IMAGE_METADATA_PATH)
    if text_metadata["model_name"] != image_metadata["model_name"]:
        raise ValueError("Text and image embeddings were generated with different CLIP models.")

    fused_embeddings = text_embeddings.copy()
    fused_embeddings[image_available_mask] = (
        args.alpha * text_embeddings[image_available_mask]
        + (1.0 - args.alpha) * image_embeddings[image_available_mask]
    )
    fused_embeddings = l2_normalize(fused_embeddings)

    np.save(MULTIMODAL_EMBEDDINGS_PATH, fused_embeddings)
    write_json(products["product_id"].tolist(), PRODUCT_ID_LOOKUP_PATH)

    metadata = {
        "generated_at": utc_now_iso(),
        "model_name": text_metadata["model_name"],
        "fusion_alpha": args.alpha,
        "product_count": len(products),
        "embedding_dim": int(fused_embeddings.shape[1]) if fused_embeddings.size else 0,
        "products_with_image_embedding": int(image_available_mask.sum()),
        "products_without_image_embedding": int(len(products) - image_available_mask.sum()),
        "text_embeddings_path": TEXT_EMBEDDINGS_PATH,
        "image_embeddings_path": IMAGE_EMBEDDINGS_PATH,
        "image_available_mask_path": IMAGE_AVAILABLE_MASK_PATH,
        "output_embeddings_path": MULTIMODAL_EMBEDDINGS_PATH,
        "product_id_lookup_path": PRODUCT_ID_LOOKUP_PATH,
        "metadata_path": MULTIMODAL_METADATA_PATH,
        "normalized": True,
        "limit": args.limit,
        "notes": [
            "If an image embedding exists, fused = alpha * text + (1 - alpha) * image.",
            "If an image embedding does not exist, fused = text embedding.",
            "The fused vectors are L2-normalized before indexing.",
        ],
    }
    write_json(metadata, MULTIMODAL_METADATA_PATH)

    print("Multimodal fusion complete.")
    print(f"  products fused: {len(products):,}")
    print(f"  products_with_image_embedding: {int(image_available_mask.sum()):,}")
    print(f"  fusion_alpha: {args.alpha}")
    print(f"  output: {MULTIMODAL_EMBEDDINGS_PATH.as_posix()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
