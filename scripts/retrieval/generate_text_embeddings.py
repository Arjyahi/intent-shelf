import argparse

import numpy as np

from clip_utils import ClipEmbedder
from config import (
    BASIC_PRODUCT_COLUMNS,
    DEFAULT_CLIP_MODEL_NAME,
    DEFAULT_TEXT_BATCH_SIZE,
    PRODUCT_TEXT_FALLBACK_COLUMNS,
    TEXT_EMBEDDINGS_PATH,
    TEXT_METADATA_PATH,
)
from helpers import batch_ranges, build_text_input, load_products, utc_now_iso, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate CLIP text embeddings from processed products.parquet."
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_CLIP_MODEL_NAME,
        help="Pretrained CLIP model name.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_TEXT_BATCH_SIZE,
        help="Number of products to encode per text batch.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional product limit for development or debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    products = load_products(limit=args.limit, columns=BASIC_PRODUCT_COLUMNS)
    embedder = ClipEmbedder.load(args.model_name)

    batch_vectors: list[np.ndarray] = []
    fallback_text_count = 0
    placeholder_text_count = 0

    for batch_number, (start, end) in enumerate(
        batch_ranges(len(products), args.batch_size),
        start=1,
    ):
        batch_records = products.iloc[start:end].to_dict(orient="records")
        batch_texts: list[str] = []

        for record in batch_records:
            text_input, used_fallback, used_placeholder = build_text_input(
                record=record,
                fallback_columns=PRODUCT_TEXT_FALLBACK_COLUMNS,
            )
            batch_texts.append(text_input)
            fallback_text_count += int(used_fallback)
            placeholder_text_count += int(used_placeholder)

        batch_vectors.append(embedder.encode_texts(batch_texts))
        print(
            f"[text] encoded batch {batch_number} "
            f"({end}/{len(products)} products)"
        )

    text_embeddings = (
        np.vstack(batch_vectors).astype(np.float32)
        if batch_vectors
        else np.empty((0, embedder.embedding_dim), dtype=np.float32)
    )
    np.save(TEXT_EMBEDDINGS_PATH, text_embeddings)

    metadata = {
        "generated_at": utc_now_iso(),
        "input_type": "text",
        "input_table": "data/processed/products.parquet",
        "output_embeddings_path": TEXT_EMBEDDINGS_PATH,
        "metadata_path": TEXT_METADATA_PATH,
        "model_name": embedder.model_name,
        "device": embedder.device,
        "batch_size": args.batch_size,
        "embedding_dim": int(text_embeddings.shape[1]) if text_embeddings.size else embedder.embedding_dim,
        "product_count": len(products),
        "text_field": "combined_text",
        "fallback_columns": PRODUCT_TEXT_FALLBACK_COLUMNS,
        "fallback_text_count": fallback_text_count,
        "placeholder_text_count": placeholder_text_count,
        "normalized": True,
        "limit": args.limit,
        "notes": [
            "Text embeddings are generated from combined_text when available.",
            "If combined_text is empty, the script falls back to a simple concatenation of core product metadata.",
            "These vectors stay aligned to the processed products row order.",
        ],
    }
    write_json(metadata, TEXT_METADATA_PATH)

    print("Text embedding generation complete.")
    print(f"  products encoded: {len(products):,}")
    print(f"  output: {TEXT_EMBEDDINGS_PATH.as_posix()}")
    print(f"  embedding_dim: {metadata['embedding_dim']}")
    print(f"  fallback_text_count: {fallback_text_count:,}")
    print(f"  placeholder_text_count: {placeholder_text_count:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
