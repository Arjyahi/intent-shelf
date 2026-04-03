import argparse

import numpy as np
from PIL import Image, UnidentifiedImageError

from clip_utils import ClipEmbedder
from config import (
    BASIC_PRODUCT_COLUMNS,
    DEFAULT_CLIP_MODEL_NAME,
    DEFAULT_IMAGE_BATCH_SIZE,
    IMAGE_AVAILABLE_MASK_PATH,
    IMAGE_EMBEDDINGS_PATH,
    IMAGE_METADATA_PATH,
    RAW_IMAGE_ROOT,
)
from helpers import load_products, utc_now_iso, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate CLIP image embeddings for products with readable images."
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_CLIP_MODEL_NAME,
        help="Pretrained CLIP model name.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_IMAGE_BATCH_SIZE,
        help="Number of images to encode per batch.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional product limit for development or debugging.",
    )
    return parser.parse_args()


def flush_image_batch(
    embedder: ClipEmbedder,
    embeddings: np.ndarray,
    available_mask: np.ndarray,
    batch_images: list[Image.Image],
    batch_row_indices: list[int],
) -> None:
    if not batch_images:
        return

    batch_vectors = embedder.encode_images(batch_images)
    embeddings[batch_row_indices] = batch_vectors
    available_mask[batch_row_indices] = True

    batch_images.clear()
    batch_row_indices.clear()


def main() -> int:
    args = parse_args()
    products = load_products(limit=args.limit, columns=BASIC_PRODUCT_COLUMNS)
    embedder = ClipEmbedder.load(args.model_name)

    image_embeddings = np.zeros((len(products), embedder.embedding_dim), dtype=np.float32)
    image_available_mask = np.zeros(len(products), dtype=bool)

    requested_image_count = 0
    encoded_image_count = 0
    missing_file_count = 0
    unreadable_file_count = 0

    batch_images: list[Image.Image] = []
    batch_row_indices: list[int] = []

    for row_index, record in enumerate(products.to_dict(orient="records"), start=0):
        if not bool(record.get("has_image")) or not record.get("image_path"):
            continue

        requested_image_count += 1
        absolute_image_path = RAW_IMAGE_ROOT / str(record["image_path"])

        if not absolute_image_path.exists():
            missing_file_count += 1
            continue

        try:
            with Image.open(absolute_image_path) as image:
                batch_images.append(image.convert("RGB"))
        except (FileNotFoundError, OSError, UnidentifiedImageError):
            unreadable_file_count += 1
            continue

        batch_row_indices.append(row_index)

        if len(batch_images) >= args.batch_size:
            flush_image_batch(
                embedder=embedder,
                embeddings=image_embeddings,
                available_mask=image_available_mask,
                batch_images=batch_images,
                batch_row_indices=batch_row_indices,
            )
            encoded_image_count = int(image_available_mask.sum())
            print(
                f"[image] encoded {encoded_image_count}/{requested_image_count} "
                "requested images so far"
            )

    flush_image_batch(
        embedder=embedder,
        embeddings=image_embeddings,
        available_mask=image_available_mask,
        batch_images=batch_images,
        batch_row_indices=batch_row_indices,
    )
    encoded_image_count = int(image_available_mask.sum())

    np.save(IMAGE_EMBEDDINGS_PATH, image_embeddings)
    np.save(IMAGE_AVAILABLE_MASK_PATH, image_available_mask)

    metadata = {
        "generated_at": utc_now_iso(),
        "input_type": "image",
        "input_table": "data/processed/products.parquet",
        "output_embeddings_path": IMAGE_EMBEDDINGS_PATH,
        "output_mask_path": IMAGE_AVAILABLE_MASK_PATH,
        "metadata_path": IMAGE_METADATA_PATH,
        "model_name": embedder.model_name,
        "device": embedder.device,
        "batch_size": args.batch_size,
        "embedding_dim": embedder.embedding_dim,
        "product_count": len(products),
        "requested_image_count": requested_image_count,
        "encoded_image_count": encoded_image_count,
        "missing_file_count": missing_file_count,
        "unreadable_file_count": unreadable_file_count,
        "rows_without_image_embedding": int(len(products) - encoded_image_count),
        "normalized": True,
        "limit": args.limit,
        "notes": [
            "Image embeddings are zero-filled for rows without a readable image file.",
            "The product_image_available_mask.npy artifact indicates which rows received a real CLIP image embedding.",
            "These vectors stay aligned to the processed products row order.",
        ],
    }
    write_json(metadata, IMAGE_METADATA_PATH)

    print("Image embedding generation complete.")
    print(f"  products scanned: {len(products):,}")
    print(f"  requested_image_count: {requested_image_count:,}")
    print(f"  encoded_image_count: {encoded_image_count:,}")
    print(f"  missing_file_count: {missing_file_count:,}")
    print(f"  unreadable_file_count: {unreadable_file_count:,}")
    print(f"  output: {IMAGE_EMBEDDINGS_PATH.as_posix()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
