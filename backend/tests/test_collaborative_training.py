import json
import sys
from pathlib import Path

import pandas as pd
from scipy.sparse import load_npz

import pytest

pytest.importorskip("implicit")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.retrieval.collaborative.config import (
    CollaborativeArtifactPaths,
    CollaborativeTrainingConfig,
)
from scripts.retrieval.collaborative.train_implicit import train_and_save_artifacts


def test_implicit_training_writes_expected_artifacts(tmp_path) -> None:
    interactions = pd.DataFrame(
        [
            {"user_id": "u1", "product_id": "p1", "interaction_strength": 1.0},
            {"user_id": "u1", "product_id": "p1", "interaction_strength": 1.0},
            {"user_id": "u1", "product_id": "p2", "interaction_strength": 1.0},
            {"user_id": "u2", "product_id": "p2", "interaction_strength": 1.0},
            {"user_id": "u2", "product_id": "p3", "interaction_strength": 1.0},
            {"user_id": "u3", "product_id": "p2", "interaction_strength": 1.0},
            {"user_id": "u3", "product_id": "p3", "interaction_strength": 1.0},
            {"user_id": "u4", "product_id": "p2", "interaction_strength": 1.0},
            {"user_id": "u5", "product_id": "p9", "interaction_strength": 1.0},
        ]
    )
    interactions_path = tmp_path / "interactions_train.parquet"
    interactions.to_parquet(interactions_path, index=False)

    products = pd.DataFrame(
        [
            {"product_id": "p1"},
            {"product_id": "p2"},
            {"product_id": "p3"},
        ]
    )
    products_path = tmp_path / "products.parquet"
    products.to_parquet(products_path, index=False)

    artifact_paths = CollaborativeArtifactPaths(
        model_path=tmp_path / "artifacts" / "models" / "implicit_model.npz",
        user_id_lookup_path=tmp_path / "artifacts" / "indexes" / "user_id_lookup.json",
        product_id_lookup_path=tmp_path / "artifacts" / "indexes" / "product_id_lookup_collaborative.json",
        user_item_matrix_path=tmp_path / "artifacts" / "indexes" / "collaborative_user_item_matrix.npz",
        training_metadata_path=tmp_path / "artifacts" / "models" / "collaborative_training_metadata.json",
    )
    config = CollaborativeTrainingConfig(
        interactions_path=interactions_path,
        products_path=products_path,
        factors=8,
        iterations=6,
        num_threads=1,
        artifact_paths=artifact_paths,
    )

    metadata = train_and_save_artifacts(config=config, artifact_paths=artifact_paths)

    assert artifact_paths.model_path.exists()
    assert artifact_paths.user_id_lookup_path.exists()
    assert artifact_paths.product_id_lookup_path.exists()
    assert artifact_paths.user_item_matrix_path.exists()
    assert artifact_paths.training_metadata_path.exists()

    assert metadata["duplicate_rows_collapsed"] == 1
    assert metadata["dropped_missing_product_rows"] == 1
    assert metadata["matrix_shape"] == [4, 3]
    assert metadata["matrix_nnz"] == 7

    saved_user_lookup = json.loads(artifact_paths.user_id_lookup_path.read_text(encoding="utf-8"))
    saved_product_lookup = json.loads(artifact_paths.product_id_lookup_path.read_text(encoding="utf-8"))
    saved_matrix = load_npz(artifact_paths.user_item_matrix_path).tocsr()

    assert saved_user_lookup == ["u1", "u2", "u3", "u4"]
    assert saved_product_lookup == ["p1", "p2", "p3"]
    assert float(saved_matrix[0, 0]) == 2.0
    assert saved_matrix.shape == (4, 3)

    saved_metadata = json.loads(
        artifact_paths.training_metadata_path.read_text(encoding="utf-8")
    )
    assert saved_metadata["model_name"] == "implicit"
    assert saved_metadata["model_type"] == "bpr"
