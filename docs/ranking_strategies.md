# Ranking Strategies

Ranking strategies are named configuration bundles for the reranker. They let the same pipeline be presented and evaluated under different priorities without adding separate ranking implementations.

## Current Strategy Set

| Key | Intent |
| --- | --- |
| `default` | Balanced mix of blended score, search, session, collaborative support, and moderate diversity. |
| `search_intent_boosted` | Pushes explicit query intent harder when search should dominate. |
| `session_boosted` | Pushes recent browsing behavior harder when short-term intent should dominate. |
| `diversity_boosted` | Applies stronger early-list diversity pressure to avoid narrow result sets. |

## Why This Abstraction Exists

- strategy names can be surfaced directly in the frontend
- offline evaluation can compare stable presets instead of ad hoc weight changes
- the API can report both the requested and resolved strategy
- the reranking pipeline stays beginner-readable

## Resolution Behavior

The strategy registry:

- lists all available strategies
- resolves the requested key
- falls back to `default` when the key is unknown
- returns the resolved config in ranking responses

That makes strategy behavior explicit instead of hiding it inside ranking code.

## API Surface

- `GET /ranking/strategies`
- `POST /feed/rerank`
- `POST /feed/explain`

The feed responses record:

- requested strategy key
- resolved strategy key
- whether fallback was used
- effective feature weights and diversity settings

## How It Fits The Demo

The frontend can switch ranking styles live without changing the retrieval stack or retraining anything. That makes the project easier to demonstrate and easier to discuss in interviews.

## Related Docs

- [reranking.md](reranking.md)
- [offline_evaluation.md](offline_evaluation.md)
- [architecture.md](architecture.md)
