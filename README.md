# IntentShelf

IntentShelf is a production-style full-stack fashion discovery system built on the H&M dataset. It combines multimodal retrieval, collaborative recommendation, lexical search, session-aware candidate generation, transparent reranking, deterministic explainability, and PostgreSQL-backed runtime logging in a demo-ready product experience.

## Project Highlights

- Built an end-to-end recommendation stack that blends collaborative, multimodal content, search, and session candidates before transparent reranking.
- Shipped a Pinterest-style Next.js discovery experience with strategy switching, explanation panels, similar items, likes, saves, cart state, and persisted runtime context.
- Added PostgreSQL persistence for sessions, session events, likes, saves, cart items, impressions, and feed request logs to support realistic product analytics and strategy comparison.
- Evaluated stable ranking strategies on a chronological recommendation-only purchase holdout covering 63,412 users with train history.

## Demo Overview

IntentShelf is designed to feel like a small product, not just a modeling repo. The frontend centers on a fashion discovery feed backed by a layered retrieval and ranking pipeline:

- browse a personalized feed
- switch between ranking strategies
- run lexical catalog search
- open a product detail view with similar items
- inspect grounded explanation text
- like, save, and add items to cart
- persist session behavior for future ranking and analytics work

## Why This Project Exists

Recommendation projects often stop at offline notebooks or isolated model scripts. IntentShelf exists to show the more complete product story: data preparation, retrieval, ranking, explainability, persistence, evaluation, and a usable frontend tied together in one coherent repo.

## System Architecture

| Layer | Responsibility |
| --- | --- |
| Data layer | Validates raw H&M files, builds cleaned parquet tables, maps product images, and creates a chronological train/validation split. |
| Retrieval layer | Generates candidates from multimodal content similarity, collaborative filtering, lexical search, and recent session activity. |
| Blending layer | Normalizes per-source scores, deduplicates candidates by `product_id`, and preserves source provenance. |
| Reranking layer | Reorders the shared candidate pool with explicit feature weights, diversity penalties, and named ranking strategies. |
| Explainability layer | Produces deterministic, evidence-grounded recommendation reasons from retrieval and reranking metadata. |
| Persistence/runtime layer | Stores sessions, session events, likes, saves, cart state, impressions, search events, and feed request logs in PostgreSQL. |
| Frontend/product layer | Presents a Pinterest-style discovery experience with search, strategy controls, detail views, and stateful user interactions. |

The compact architecture summary lives in [docs/architecture.md](docs/architecture.md).

## Retrieval And Ranking Stack

1. Multimodal content retrieval uses CLIP text and image embeddings plus FAISS for item-to-item similarity and anchor-based feed candidates.
2. Collaborative retrieval uses an `implicit` BPR model trained on historical purchases to generate personalized candidates from train interactions.
3. Search retrieval uses TF-IDF over cleaned catalog metadata for explicit lexical intent.
4. Session retrieval builds a weighted embedding from recent product-linked runtime events and queries the shared multimodal index.
5. Candidate blending merges the four sources into one pool with min-max score normalization, explicit source weights, and provenance tracking.
6. Transparent reranking computes readable feature signals, applies a weighted score formula, adds deterministic diversity penalties, and exposes four strategy presets.

Detailed docs:

- [docs/multimodal_retrieval.md](docs/multimodal_retrieval.md)
- [docs/collaborative_retrieval.md](docs/collaborative_retrieval.md)
- [docs/search_retrieval.md](docs/search_retrieval.md)
- [docs/session_retrieval.md](docs/session_retrieval.md)
- [docs/candidate_blending.md](docs/candidate_blending.md)
- [docs/reranking.md](docs/reranking.md)
- [docs/ranking_strategies.md](docs/ranking_strategies.md)
- [docs/explainability.md](docs/explainability.md)

## Product Experience

The frontend is a Pinterest-style discovery UI built in Next.js 15 and React 19. The current experience includes:

- a feed powered by the backend blending and reranking stack
- a ranking strategy selector backed by `GET /ranking/strategies`
- lexical search without leaving the discovery flow
- product detail modals with similar items
- explanation panels tied to actual retrieval and ranking evidence
- likes, saves, and cart state that survive page refreshes through PostgreSQL-backed persistence

## Persistence And Runtime Logging

IntentShelf now includes a real runtime persistence layer rather than keeping all app behavior in memory. PostgreSQL stores:

- sessions
- session events
- search events
- impression events
- likes
- saves
- cart items
- feed request logs

This supports:

- session-aware retrieval and reranking bootstrapping
- truthful impression logging
- state continuity for the frontend
- groundwork for future online strategy comparison and product analytics

More detail: [docs/postgres_integration.md](docs/postgres_integration.md)

## Offline Evaluation Summary

The final offline benchmark is intentionally modest and honest:

- evaluation mode: `recommendation_only_purchase_holdout`
- validation window: September 16, 2020 to September 22, 2020
- evaluated users: `63,412` out of `68,984` validation users
- inputs: `user_id` plus the latest train purchase as an optional content anchor
- labels: distinct validation purchases per user

At `K=20`, the strategy comparison looked like this:

| Strategy | NDCG@20 | Recall@20 | Notes |
| --- | ---: | ---: | --- |
| `session_boosted` | `0.0049` | `0.0091` | Best NDCG@20 in this benchmark. |
| `search_intent_boosted` | `0.0046` | `0.0093` | Best Recall@20 in this benchmark. |
| `default` | `0.0044` | `0.0091` | Balanced baseline. |
| `diversity_boosted` | `0.0041` | `0.0084` | Most diversity-focused, lowest top-line relevance here. |

Important caveats:

- this benchmark evaluates purchase-holdout recommendation quality, not online engagement
- no search queries were fabricated, so the search-oriented strategy is not a true search benchmark
- no session browsing sequences were fabricated, so the session-oriented strategy is not a true online session benchmark
- runtime analytics from persisted impressions and user events would be the next step for online validation

More detail: [docs/offline_evaluation.md](docs/offline_evaluation.md)

## Tech Stack

| Area | Tools |
| --- | --- |
| Backend | FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn |
| Frontend | Next.js 15, React 19 |
| Persistence | PostgreSQL 16, Psycopg |
| Retrieval and ranking | CLIP, FAISS, `implicit`, scikit-learn, NumPy, SciPy |
| Data processing | pandas, PyArrow |
| Packaging and local orchestration | Docker Compose, Makefile |

## Repository Structure

```text
.
|-- backend/                 # FastAPI app, retrieval services, persistence, tests, Alembic
|-- frontend/                # Next.js app and API proxy routes
|-- scripts/
|   |-- data/                # Raw-data validation, preprocessing, and time split
|   |-- retrieval/           # Embedding, search, and collaborative artifact builders
|   `-- evaluation/          # Offline evaluation pipeline
|-- data/
|   |-- raw/                 # H&M source files and images (not committed)
|   `-- processed/           # Cleaned parquet tables and split metadata
|-- artifacts/
|   |-- indexes/             # FAISS, TF-IDF, and lookup artifacts
|   |-- models/              # Retrieval model metadata and collaborative model
|   `-- reports/             # Offline evaluation summaries and strategy comparison outputs
|-- docs/                    # Architecture and component docs
|-- notebooks/               # Optional exploratory work
|-- docker-compose.yml
|-- requirements-data.txt
`-- README.md
```

## Screenshots

Replace these SVG placeholders with real screenshots when you capture the final demo. The filenames are already stable so the README links do not need to change later.

| Home feed | Product detail | Feed controls |
| --- | --- | --- |
| ![Home feed](docs/assets/home-feed-intentshelf.svg) | ![Product detail](docs/assets/product-details.png) | ![Feed controls](docs/assets/feed-controls.png) |

Asset notes: [docs/assets/README.md](docs/assets/README.md)

## Local Setup

### Prerequisites

- Python 3.11+ recommended
- Node.js 20+
- Docker Desktop or another Docker Compose runtime for local PostgreSQL
- The raw H&M dataset placed under `data/raw/`

Expected raw data layout:

```text
data/raw/
  articles.csv
  customers.csv
  transactions_train.csv
  images/
```

### Environment Files

Create local environment files from the checked-in examples:

```powershell
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env.local
```

### Optional: Build Data And Retrieval Artifacts

If `data/processed/` and `artifacts/` are not already populated, run the pipeline components in order:

```powershell
python -m pip install -r requirements-data.txt
python scripts/data/run_phase1.py

python -m pip install -r backend/requirements.txt
python scripts/retrieval/generate_text_embeddings.py
python scripts/retrieval/generate_image_embeddings.py
python scripts/retrieval/fuse_multimodal_embeddings.py
python scripts/retrieval/build_faiss_index.py
python scripts/retrieval/collaborative/train_implicit.py
python scripts/retrieval/search/build_search_index.py
```

## Environment Variables

### Root `.env`

| Variable | Purpose | Default example |
| --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | Compose project name | `intentshelf` |
| `BACKEND_PORT` | Backend port published by Docker | `18001` |
| `FRONTEND_PORT` | Frontend port published by Docker | `13000` |
| `POSTGRES_PORT` | Local PostgreSQL port | `5433` |
| `POSTGRES_DB` | PostgreSQL database name | `intentshelf` |
| `POSTGRES_USER` | PostgreSQL username | `intentshelf` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `intentshelf` |
| `DATABASE_URL` | Local backend database URL | `postgresql+psycopg://intentshelf:intentshelf@127.0.0.1:5433/intentshelf` |
| `NEXT_PUBLIC_API_BASE_URL` | Browser-facing backend URL | `http://127.0.0.1:18001` |

### `backend/.env`

| Variable | Purpose |
| --- | --- |
| `INTENTSHELF_APP_NAME` | FastAPI title |
| `INTENTSHELF_APP_ENV` | Environment label |
| `INTENTSHELF_DEBUG` | FastAPI debug toggle |
| `INTENTSHELF_API_PORT` | Local backend port |
| `INTENTSHELF_DATABASE_URL` | SQLAlchemy database URL |

### `frontend/.env.local`

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_APP_NAME` | Frontend display name |
| `NEXT_PUBLIC_API_BASE_URL` | URL used by the browser to call the backend |
| `INTENTSHELF_BACKEND_URL` | Server-side proxy target inside Next.js |
| `NEXT_PUBLIC_DEFAULT_USER_ID` | Seed user used for local demo bootstrapping |

## Running The Project

### Manual Local Run

Start PostgreSQL:

```powershell
docker compose up -d postgres
```

Install dependencies:

```powershell
python -m pip install -r requirements-data.txt
python -m pip install -r backend/requirements.txt
cd frontend
npm install
cd ..
```

Run migrations:

```powershell
cd backend
python -m alembic upgrade head
cd ..
```

Start the backend on `18001`:

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 18001
```

Start the frontend:

```powershell
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 13000
```

Open:

- frontend: `http://127.0.0.1:13000`
- backend docs: `http://127.0.0.1:18001/docs`

### Docker Compose Run

```powershell
docker compose up --build
```

With the provided root `.env`, Docker publishes:

- frontend: `http://127.0.0.1:13000`
- backend: `http://127.0.0.1:18001`
- postgres: `127.0.0.1:5433`

## How To Demo IntentShelf Locally

1. Start PostgreSQL with `docker compose up -d postgres`.
2. Run `python -m alembic upgrade head` from `backend/`.
3. Start the backend on port `18001`.
4. Start the frontend and open `http://127.0.0.1:13000`.
5. Load the home feed and switch between `default`, `search_intent_boosted`, `session_boosted`, and `diversity_boosted`.
6. Search for catalog terms like `black top`, `summer dress`, or `beige cardigan`.
7. Open a product detail modal, inspect the explanation panel, and view similar items.
8. Like, save, and add items to cart, then refresh to confirm persisted runtime state.

## Sample API Calls

List ranking strategies:

```bash
curl "http://127.0.0.1:18001/ranking/strategies"
```

Search the catalog:

```bash
curl "http://127.0.0.1:18001/search?query=black%20top&k=12"
```

Fetch similar items:

```bash
curl "http://127.0.0.1:18001/products/0108775015/similar?k=12"
```

Explain a feed request:

```bash
curl -X POST "http://127.0.0.1:18001/feed/explain" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_demo_001",
    "ranking_strategy": "default",
    "query": "black top",
    "session_events": [],
    "like_events": [],
    "save_events": [],
    "blended_k": 20,
    "reranked_k": 12,
    "explanation_options": {
      "include_evidence": true,
      "max_supporting_reasons": 2
    }
  }'
```

## Limitations And Honest Tradeoffs

- The offline benchmark is recommendation-only purchase holdout, not an online experiment.
- Search and session strategies are compared under the same held-out purchase setup, but they are not fully validated search or session benchmarks.
- The frontend demonstrates product discovery behavior, not a complete commerce stack.
- The serving stack still relies on parquet files and generated artifacts for catalog and retrieval data rather than a full production feature store.
- The project intentionally avoids auth, checkout, payments, inventory, and heavy platform complexity so the recommendation stack stays readable.

## Future Work

- Use persisted runtime events for online-style dashboarding and A/B-style strategy comparison.
- Add better artifact versioning and promotion flows for embeddings, indexes, and evaluation reports.
- Expand evaluation beyond purchase holdout with richer session-aware and search-aware validation.
- Capture real screenshots or short demo GIFs for the portfolio version of the repo.

## Further Reading

- [docs/architecture.md](docs/architecture.md)
- [docs/multimodal_retrieval.md](docs/multimodal_retrieval.md)
- [docs/collaborative_retrieval.md](docs/collaborative_retrieval.md)
- [docs/search_retrieval.md](docs/search_retrieval.md)
- [docs/session_retrieval.md](docs/session_retrieval.md)
- [docs/candidate_blending.md](docs/candidate_blending.md)
- [docs/reranking.md](docs/reranking.md)
- [docs/explainability.md](docs/explainability.md)
- [docs/ranking_strategies.md](docs/ranking_strategies.md)
- [docs/postgres_integration.md](docs/postgres_integration.md)
- [docs/offline_evaluation.md](docs/offline_evaluation.md)
