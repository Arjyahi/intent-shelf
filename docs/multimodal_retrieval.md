# Multimodal Content Retrieval

IntentShelf uses multimodal content retrieval for item-to-item discovery. This is the retrieval path behind similar products and the content-based source used when the feed has an anchor product.

## Role In The System

- powers `GET /products/{product_id}/similar`
- provides anchor-based candidates to the blended feed
- captures product similarity from both text and imagery

This component generates candidates. It does not decide final feed order on its own.

## Inputs And Build Steps

Inputs:

- `data/processed/products.parquet`
- product images under `data/raw/images/`

Build scripts:

- `scripts/retrieval/generate_text_embeddings.py`
- `scripts/retrieval/generate_image_embeddings.py`
- `scripts/retrieval/fuse_multimodal_embeddings.py`
- `scripts/retrieval/build_faiss_index.py`

## Main Artifacts

- `artifacts/indexes/product_text_embeddings.npy`
- `artifacts/indexes/product_image_embeddings.npy`
- `artifacts/indexes/product_image_available_mask.npy`
- `artifacts/indexes/product_multimodal_embeddings.npy`
- `artifacts/indexes/product_id_lookup.json`
- `artifacts/indexes/product_multimodal.faiss`
- `artifacts/models/text_embedding_metadata.json`
- `artifacts/models/image_embedding_metadata.json`
- `artifacts/models/multimodal_embedding_metadata.json`

## Retrieval Flow

1. Product metadata is converted into text embeddings.
2. Available product images are converted into image embeddings.
3. The text and image vectors are fused into one shared product representation.
4. A FAISS index is built over the fused vectors.
5. Similar-item requests query the index and map result rows back to `product_id`.

The current setup uses CLIP so text and images share a comparable embedding space without custom model training.

## API Surface

- `GET /products/{product_id}/similar?k=12`

The same embeddings are also reused by session retrieval, which keeps short-term intent modeling simple and inspectable.

## Tradeoffs

- strong for item-to-item discovery, but not a substitute for full personalization
- depends on image availability and metadata quality
- intentionally uses one shared pretrained model family rather than a custom tuned stack

## Related Docs

- [architecture.md](architecture.md)
- [session_retrieval.md](session_retrieval.md)
- [candidate_blending.md](candidate_blending.md)
