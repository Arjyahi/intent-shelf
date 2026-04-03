# Reranking

Reranking is the final decision layer for the feed. It takes the blended candidate pool and reorders it with explicit feature weights, diversity penalties, and named ranking strategies.

## Responsibilities

- compute readable per-candidate ranking features
- apply a transparent weighted score formula
- add deterministic diversity penalties at the top of the list
- expose enough metadata for explainability and debugging

IntentShelf intentionally uses a transparent heuristic reranker rather than a learned ranking model.

## Core Features

The reranker uses signals such as:

- blended score
- search signal and search presence
- session signal and session presence
- content signal
- collaborative signal
- popularity fallback signal
- multi-source agreement
- exact-anchor penalty

These features are simple by design so they can be read directly from the API payloads and tests.

## Score Structure

The base score is a weighted sum of the feature values. A deterministic diversity penalty is then subtracted while the ranked list is built greedily from top to bottom.

```text
reranked_score = base_reranking_score - diversity_penalty
```

The response returns both feature values and score breakdowns so the output is inspectable.

## Diversity Handling

The current diversity rule penalizes repeated early selections from the same:

- `product_type_name`
- `product_group_name`

This is a lightweight diversification mechanism, not a full diversification framework.

## Strategy Support

The reranker is one pipeline with multiple named presets:

- `default`
- `search_intent_boosted`
- `session_boosted`
- `diversity_boosted`

Those presets are defined by the ranking strategy registry rather than by separate ranking implementations.

## API Surface

- `POST /feed/rerank`
- `POST /feed/explain`

`/feed/explain` runs the same ranking path and then adds explanation metadata on top.

## Related Docs

- [candidate_blending.md](candidate_blending.md)
- [ranking_strategies.md](ranking_strategies.md)
- [explainability.md](explainability.md)
- [offline_evaluation.md](offline_evaluation.md)
