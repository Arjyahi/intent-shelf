# Offline Evaluation

IntentShelf includes a recommendation-only offline benchmark over the held-out validation purchases. The goal is to compare stable ranking strategies under the same candidate pool and chronological split, not to overclaim online product performance.

## Benchmark Setup

- evaluation mode: `recommendation_only_purchase_holdout`
- validation window: September 16, 2020 to September 22, 2020
- evaluated users: `63,412`
- validation users available: `68,984`
- dropped users without train history: `5,572`
- report cut-off: `K=20`

Ground-truth relevance is the set of distinct validation purchases for each evaluated user.

## What The Benchmark Uses

- `user_id` is always provided
- the latest train purchase can be used as the content anchor
- the same blended candidate pool is shared across strategy comparisons
- seen train products can be filtered before reranking

## What It Does Not Prove

- true search quality, because no grounded query logs exist in the holdout labels
- true session quality, because no real runtime browsing sequences exist in the holdout labels
- explanation usefulness, because purchase logs do not score explanations
- online product impact, because persisted runtime events are not part of this benchmark

## Main Results At K=20

| Strategy | NDCG@20 | Recall@20 | Coverage@20 |
| --- | ---: | ---: | ---: |
| `session_boosted` | `0.0049` | `0.0091` | `0.7054` |
| `search_intent_boosted` | `0.0046` | `0.0093` | `0.7083` |
| `default` | `0.0044` | `0.0091` | `0.7021` |
| `diversity_boosted` | `0.0041` | `0.0084` | `0.6932` |

Interpretation:

- `session_boosted` produced the best top-line ranking quality by NDCG@20 in this run
- `search_intent_boosted` produced the best Recall@20
- `diversity_boosted` traded off some top-line relevance for more varied early results
- the differences are real but modest, which is a credible outcome for a heuristic strategy comparison

## Reports

Generated outputs live in `artifacts/reports/`:

- `offline_eval_summary.json`
- `offline_eval_metrics.csv`
- `strategy_comparison.csv`
- `offline_eval_notes.md`

## Run Command

```powershell
python scripts/evaluation/evaluate_pipeline.py
```

## Related Docs

- [ranking_strategies.md](ranking_strategies.md)
- [reranking.md](reranking.md)
- [candidate_blending.md](candidate_blending.md)
