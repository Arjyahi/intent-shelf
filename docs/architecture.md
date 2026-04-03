# IntentShelf Architecture

IntentShelf is a layered fashion discovery system built to show how retrieval, ranking, explainability, persistence, and product UX fit together in one repo. The project uses the H&M dataset for offline data and PostgreSQL for live runtime state.

## Layered View

| Layer | Responsibility | Main implementation areas |
| --- | --- | --- |
| Data layer | Validates raw files, builds cleaned parquet tables, maps images, and creates a chronological split. | `scripts/data/`, `data/processed/` |
| Retrieval layer | Produces candidates from multimodal content, collaborative filtering, lexical search, and recent session behavior. | `backend/app/services/*retrieval.py`, `scripts/retrieval/`, `artifacts/` |
| Blending layer | Merges source lists into one candidate pool with normalized scores and provenance. | `backend/app/services/candidate_blending.py` |
| Reranking layer | Reorders the blended pool with transparent feature weights and diversity controls. | `backend/app/services/reranking.py` |
| Explainability layer | Converts ranking evidence into deterministic explanation text. | `backend/app/services/explainability.py` |
| Persistence/runtime layer | Stores sessions, events, likes, saves, cart state, impressions, and feed request logs in PostgreSQL. | `backend/app/db/`, `backend/app/repositories/`, `backend/app/services/persistence.py` |
| Frontend/product layer | Exposes a discovery feed, search flow, product detail modal, and stateful interactions. | `frontend/src/` |

## Typical Request Flows

### Home Feed

1. The frontend bootstraps runtime state from PostgreSQL.
2. The feed request sends `user_id`, current session context, recent session events, like events, save events, and the selected ranking strategy.
3. The backend gathers candidates from the enabled retrieval sources.
4. Candidate blending normalizes per-source scores, deduplicates by `product_id`, and preserves provenance.
5. Reranking computes explicit features, applies strategy-specific weights, adds diversity penalties, and produces final order.
6. Explainability attaches grounded recommendation reasons.
7. Persistence logs the feed request and the returned impressions.

### Search

1. The frontend calls `GET /search`.
2. The backend uses the TF-IDF index to score lexical matches.
3. If a `session_id` is provided, the search event is also persisted.
4. The frontend can open product detail directly from search results or return to the main feed.

### Product Detail And Similar Items

1. The frontend opens a product detail modal for the selected item.
2. The backend calls the multimodal content retriever through `GET /products/{product_id}/similar`.
3. Similar items are shown alongside the explanation panel and product metadata.
4. Like, save, and cart actions are written to PostgreSQL and later reused for session-aware ranking.

## Data And Storage Boundaries

- `data/raw/`: raw H&M source files and images
- `data/processed/`: cleaned product, user, and interaction tables plus split metadata
- `artifacts/indexes/`: FAISS, TF-IDF, and lookup artifacts used at serving time
- `artifacts/models/`: collaborative model and embedding metadata
- `artifacts/reports/`: offline evaluation outputs
- PostgreSQL: runtime application state and analytics-friendly logs

The serving stack intentionally keeps catalog and retrieval artifacts on disk rather than moving everything into the database. PostgreSQL is used for live app state and runtime behavior, not as the primary retrieval store.

## Related Docs

- [multimodal_retrieval.md](multimodal_retrieval.md)
- [collaborative_retrieval.md](collaborative_retrieval.md)
- [search_retrieval.md](search_retrieval.md)
- [session_retrieval.md](session_retrieval.md)
- [candidate_blending.md](candidate_blending.md)
- [reranking.md](reranking.md)
- [explainability.md](explainability.md)
- [ranking_strategies.md](ranking_strategies.md)
- [postgres_integration.md](postgres_integration.md)
- [offline_evaluation.md](offline_evaluation.md)
