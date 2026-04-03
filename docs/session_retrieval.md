# Session Retrieval

Session retrieval captures short-term intent from live browsing behavior. It uses recent product-linked events from the current session and turns them into a single embedding that can query the shared multimodal index.

## Role In The System

- powers `POST /sessions/recommendations`
- contributes short-term intent candidates to the blended feed
- helps bridge the gap between anonymous browsing behavior and long-term purchase history

## Runtime Signals Used

The current implementation consumes product-linked session behavior such as:

- `product_view`
- `detail_open`
- `similar_item_click`
- `like`
- `save`

Unsupported or non-product-linked events are ignored cleanly.

## Retrieval Flow

1. Collect recent session, like, and save events from the request or persistence layer.
2. Keep the most recent supported product-linked signals.
3. Apply simple explicit event weights.
4. Look up the corresponding product embeddings from the multimodal index.
5. Average those vectors into one session representation.
6. Query FAISS for nearest neighboring products.

This keeps the first session-aware retriever transparent and easy to inspect. It does not use sequence models or neural session architectures.

## Dependencies

Session retrieval reuses the multimodal content artifacts:

- `artifacts/indexes/product_multimodal.faiss`
- `artifacts/indexes/product_id_lookup.json`
- `artifacts/models/multimodal_embedding_metadata.json`

## API Surface

- `POST /sessions/recommendations`

The same session events can also be stored in PostgreSQL and reloaded into future feed requests.

## Tradeoffs

- reacts to short-term browsing behavior quickly
- simple enough to reason about end to end
- not a replacement for richer session-sequence modeling

## Related Docs

- [architecture.md](architecture.md)
- [multimodal_retrieval.md](multimodal_retrieval.md)
- [postgres_integration.md](postgres_integration.md)
- [candidate_blending.md](candidate_blending.md)
