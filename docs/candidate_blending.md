# Candidate Blending

Candidate blending is the layer that turns multiple retrieval lists into one shared candidate pool. It sits between retrieval and reranking so each source can stay independently understandable while the final feed still works from one unified set of products.

## Responsibilities

- call the enabled retrievers
- normalize scores inside each source list
- deduplicate candidates by `product_id`
- preserve source provenance
- compute one blended score per candidate

Blending does not produce the final display order. That is the reranker's job.

## Sources

The current blend can combine:

- collaborative retrieval
- multimodal content retrieval
- lexical search retrieval
- session retrieval

Each source sees a different kind of intent, so keeping them separate before blending makes the system easier to debug and evaluate.

## Score Handling

Raw scores from different retrievers are not directly comparable. Candidate blending therefore applies min-max normalization inside each source list before weighting and summing contributions.

Default source weights:

- collaborative: `1.0`
- session: `1.2`
- search: `1.3`
- content: `0.9`

Those values are explicit heuristics, not calibrated probabilities.

## Output Contract

Each blended candidate keeps:

- product metadata
- `blended_score`
- contributing sources
- raw per-source scores
- normalized per-source scores
- weighted per-source scores
- source rank positions

That provenance is later reused by reranking and explainability.

## API Surface

- `POST /candidates/blend`

The feed endpoints call this layer internally as part of the full ranking pipeline.

## Why Blending And Reranking Stay Separate

Blending answers: "Which products should be in the shared pool?"

Reranking answers: "How should that pool be ordered for the final experience?"

Keeping those concerns separate makes the system easier to reason about and easier to evaluate strategy changes without rewriting the retrievers.

## Related Docs

- [architecture.md](architecture.md)
- [reranking.md](reranking.md)
- [explainability.md](explainability.md)
