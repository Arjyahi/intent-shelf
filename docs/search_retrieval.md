# Search Retrieval

Search retrieval handles explicit text intent. IntentShelf uses a lexical TF-IDF search index over cleaned product metadata to power direct catalog lookup without requiring a semantic search model.

## Role In The System

- powers `GET /search`
- returns direct search results in the frontend
- contributes search-driven candidates and signals to the blended feed

## Indexed Fields

The search index is built from readable product metadata, including:

- `product_name`
- `product_type_name`
- `product_group_name`
- `colour_group_name`
- `department_name`
- `combined_text`

Short taxonomy fields are intentionally emphasized so queries like `black top` or `linen dress` stay easy to match.

## Build Script And Artifacts

Build script:

- `scripts/retrieval/search/build_search_index.py`

Saved artifacts:

- `artifacts/models/product_search_vectorizer.pkl`
- `artifacts/models/search_index_metadata.json`
- `artifacts/indexes/product_search_tfidf_matrix.npz`
- `artifacts/indexes/product_search_product_id_lookup.json`

## Retrieval Flow

1. Product metadata is converted into one search document per product.
2. The TF-IDF vectorizer builds a sparse vocabulary over that corpus.
3. Incoming queries are encoded into the same space.
4. Cosine similarity scores products against the query vector.
5. The backend returns positive-score matches with catalog metadata.

## API Surface

- `GET /search?query=black%20top&k=20`

When `session_id` is included on the request, the backend also persists a search event so runtime intent can be analyzed later.

## Tradeoffs

- highly inspectable and deterministic
- good for explicit lexical matches
- does not capture deeper semantic similarity the way an embedding-based search system would

## Related Docs

- [architecture.md](architecture.md)
- [candidate_blending.md](candidate_blending.md)
- [postgres_integration.md](postgres_integration.md)
