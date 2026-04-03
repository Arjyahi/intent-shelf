from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class ProductCatalogPaths:
    products_path: Path


def default_catalog_paths() -> ProductCatalogPaths:
    repo_root = Path(__file__).resolve().parents[3]
    return ProductCatalogPaths(
        products_path=repo_root / "data" / "processed" / "products.parquet",
    )


class ProductCatalogService:
    """Reads minimal product metadata from the existing processed catalog."""

    def __init__(self, paths: ProductCatalogPaths | None = None) -> None:
        self.paths = paths or default_catalog_paths()
        self._products: pd.DataFrame | None = None

    def _load(self) -> None:
        if self._products is not None:
            return

        if not self.paths.products_path.exists():
            self._products = pd.DataFrame(columns=["product_id"]).set_index("product_id")
            return

        products = pd.read_parquet(
            self.paths.products_path,
            columns=[
                "product_id",
                "product_name",
                "product_type_name",
                "product_group_name",
                "colour_group_name",
                "department_name",
                "image_path",
            ],
        )
        products["product_id"] = products["product_id"].astype(str)
        self._products = products.set_index("product_id", drop=False)

    def get_snapshot(self, product_id: str) -> dict[str, object]:
        self._load()
        assert self._products is not None

        if product_id not in self._products.index:
            return {}

        product = self._products.loc[product_id]
        return {
            "product_name": product["product_name"],
            "product_type_name": product["product_type_name"],
            "product_group_name": product["product_group_name"],
            "colour_group_name": product["colour_group_name"],
            "department_name": product["department_name"],
            "image_path": product["image_path"],
        }


@lru_cache(maxsize=1)
def get_product_catalog_service() -> ProductCatalogService:
    return ProductCatalogService()
