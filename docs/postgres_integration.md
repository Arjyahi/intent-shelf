# PostgreSQL Runtime Persistence

IntentShelf uses PostgreSQL for live runtime state and analytics-friendly logging. The database is not the primary retrieval store for catalog content. It exists to capture what happens inside the product experience.

## What Is Persisted

The runtime layer stores:

- sessions
- session events
- search events
- impression events
- like events
- save events
- cart items
- feed request logs

## Why It Matters

This layer supports:

- restoring frontend state across refreshes
- bootstrapping feed requests from persisted session context
- logging truthful product impressions
- analyzing how strategies behave in a realistic app flow
- preparing the ground for future online evaluation

## Key Backend Surfaces

Session and runtime state:

- `PUT /sessions/{session_id}`
- `POST /sessions/{session_id}/events`
- `GET /state/bootstrap`

Likes, saves, and cart:

- `GET /likes`
- `PUT /likes/{product_id}`
- `GET /saves`
- `PUT /saves/{product_id}`
- `GET /cart`
- `PUT /cart/items/{product_id}`

Search and impression logging:

- `GET /search`
- `POST /events/search`
- `POST /events/impressions`

Feed requests:

- `/feed/rerank` and `/feed/explain` also log request metadata and returned impressions

## Storage Boundary

The persisted tables are runtime-oriented. Catalog metadata, embeddings, and search indexes still live in parquet files and artifact files on disk. That keeps the project simpler while still giving the app realistic statefulness.

## Tradeoffs

- simpler than moving the full serving stack into PostgreSQL
- realistic enough for demo-ready state and logging
- not intended as a complete production analytics platform

## Related Docs

- [architecture.md](architecture.md)
- [session_retrieval.md](session_retrieval.md)
- [offline_evaluation.md](offline_evaluation.md)
