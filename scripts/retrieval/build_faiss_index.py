import argparse
import faiss
import numpy as np
import json
from config import FAISS_INDEX_PATH, MULTIMODAL_EMBEDDINGS_PATH, PRODUCT_ID_LOOKUP_PATH
from helpers import l2_normalize


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a FAISS index over multimodal product embeddings."
    )
    return parser.parse_args()


def main() -> int:
    parse_args()

    embeddings = np.load(MULTIMODAL_EMBEDDINGS_PATH).astype(np.float32)
    embeddings = l2_normalize(embeddings)

    with PRODUCT_ID_LOOKUP_PATH.open("r", encoding="utf-8") as handle:
        product_id_lookup = json.load(handle)

    if embeddings.shape[0] != len(product_id_lookup):
        raise ValueError(
            "Embedding rows and product_id lookup length do not match. "
            "Re-run the fusion step before building the FAISS index."
        )
    if embeddings.shape[0] == 0:
        raise ValueError("No multimodal embeddings found. Cannot build an empty FAISS index.")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(np.ascontiguousarray(embeddings))
    faiss.write_index(index, str(FAISS_INDEX_PATH))

    print("FAISS index build complete.")
    print(f"  vectors indexed: {embeddings.shape[0]:,}")
    print(f"  embedding_dim: {embeddings.shape[1]}")
    print(f"  output: {FAISS_INDEX_PATH.as_posix()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
