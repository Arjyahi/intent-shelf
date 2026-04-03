# Explainability

IntentShelf uses deterministic explainability so each recommendation can carry a short, grounded reason. The goal is not conversational copywriting. The goal is traceable recommendation evidence that can be inspected in the backend and shown in the product UI.

## Design Principles

- deterministic instead of generative
- grounded in actual retrieval and reranking metadata
- short enough for product UI
- easy to debug when ranking behavior changes

## Evidence Sources

The explanation layer reads information already produced by the ranking stack, including:

- contributing sources
- normalized and weighted source scores
- ranking strategy metadata
- reranking features
- score breakdowns
- query presence
- anchor-product presence
- session usage
- source summaries such as collaborative fallback behavior

It does not invent evidence that the pipeline did not produce.

## Rule Priority

The primary short reason is chosen from a simple ordered rule set:

1. search-led evidence
2. session-led evidence
3. content-similarity evidence
4. collaborative evidence
5. popularity fallback evidence
6. generic blended-discovery fallback

Supporting reasons can be attached when additional useful evidence exists.

## API Surface

- `POST /feed/explain`

The response contains:

- ranked products
- explanation text
- explanation tags
- optional evidence blocks
- strategy and score metadata

## Why This Matters

The explanation layer closes the loop between ranking logic and product experience. It makes the recommendation system easier to trust during demos and easier to inspect during development.

## Tradeoffs

- explanation quality is only as good as the evidence generated upstream
- deterministic rules are easier to trust, but less expressive than free-form natural language systems
- offline purchase logs cannot fully validate whether users find the explanations useful

## Related Docs

- [reranking.md](reranking.md)
- [candidate_blending.md](candidate_blending.md)
- [offline_evaluation.md](offline_evaluation.md)
