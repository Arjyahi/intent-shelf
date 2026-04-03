# Collaborative Retrieval

Collaborative retrieval is IntentShelf's long-term personalization source. It uses historical purchases from the H&M training split to recommend products based on shared behavior patterns across users.

## Role In The System

- powers `GET /users/{user_id}/recommendations/collaborative`
- contributes personalized candidates to blended feed generation
- provides the strongest signal when a user has usable purchase history

## Model Choice

The current implementation uses the `implicit` library with a BPR model.

Why this fits the project:

- it is ranking-oriented
- it works well with implicit feedback such as purchases
- it stays lightweight enough for a beginner-readable repo
- it is easier to run in this environment than a more complex recommendation stack

## Training Inputs

- `data/processed/interactions_train.parquet`
- `data/processed/products.parquet`

The validation split is kept separate and is not used for collaborative training.

## Build Script And Artifacts

Training script:

- `scripts/retrieval/collaborative/train_implicit.py`

Saved artifacts:

- `artifacts/models/implicit_model.npz`
- `artifacts/models/collaborative_training_metadata.json`
- `artifacts/indexes/collaborative_user_item_matrix.npz`
- `artifacts/indexes/user_id_lookup.json`
- `artifacts/indexes/product_id_lookup_collaborative.json`

## Retrieval Flow

1. Train interactions are aggregated into a sparse user-item matrix.
2. Duplicate user-product purchases are collapsed into one weighted interaction.
3. The BPR model learns latent factors from those implicit positives.
4. At request time the backend looks up the user, scores candidate products, and optionally filters seen items.
5. If the user is missing from the training set, the service can fall back to a popularity-style list.

## API Surface

- `GET /users/{user_id}/recommendations/collaborative?k=20&exclude_seen_items=true`

Collaborative scores are not compared directly against other retrieval scores. They are normalized later during candidate blending.

## Tradeoffs

- strong for repeat or warm users, weak for true cold-start cases
- limited to what historical purchases can reveal
- intentionally simple compared with a larger feature-rich recommender stack

## Related Docs

- [architecture.md](architecture.md)
- [candidate_blending.md](candidate_blending.md)
- [offline_evaluation.md](offline_evaluation.md)
