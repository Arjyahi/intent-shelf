import sys
from pathlib import Path

import pandas as pd

from config import IMAGES_DIR, RAW_FILES, REQUIRED_COLUMNS
from helpers import count_image_files


def validate_required_raw_inputs() -> dict[str, object]:
    """Check that the expected raw H&M files and columns are present."""
    missing_files = [name for name, path in RAW_FILES.items() if not path.exists()]
    if missing_files:
        missing_labels = ", ".join(missing_files)
        raise FileNotFoundError(
            f"Missing required raw input file(s): {missing_labels}. "
            "Place the H&M CSV files inside data/raw/ before running Phase 1 scripts."
        )

    files_summary: dict[str, dict[str, object]] = {}

    for name, path in RAW_FILES.items():
        header_df = pd.read_csv(path, nrows=0)
        available_columns = list(header_df.columns)
        required_columns = REQUIRED_COLUMNS[name]
        missing_columns = sorted(set(required_columns) - set(available_columns))

        if missing_columns:
            missing_labels = ", ".join(missing_columns)
            raise ValueError(
                f"{path.name} is missing required column(s): {missing_labels}."
            )

        files_summary[name] = {
            "path": path.as_posix(),
            "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
            "required_columns_checked": required_columns,
            "available_column_count": len(available_columns),
        }

    images_summary = {
        "path": IMAGES_DIR.as_posix(),
        "exists": IMAGES_DIR.exists(),
        "image_count": count_image_files() if IMAGES_DIR.exists() else 0,
    }

    return {
        "files": files_summary,
        "images": images_summary,
    }


def print_validation_summary(summary: dict[str, object]) -> None:
    """Print a compact human-readable validation report."""
    print("IntentShelf Phase 1 raw data validation")
    print()

    files = summary["files"]
    for name, info in files.items():
        print(f"[OK] {name}")
        print(f"  path: {info['path']}")
        print(f"  size_mb: {info['size_mb']}")
        print(f"  required_columns_checked: {len(info['required_columns_checked'])}")

    images = summary["images"]
    status = "found" if images["exists"] else "missing"
    print()
    print(f"Images folder: {status}")
    print(f"  path: {images['path']}")
    print(f"  image_count: {images['image_count']}")

    print()
    print("Validation passed.")


def main() -> int:
    try:
        summary = validate_required_raw_inputs()
        print_validation_summary(summary)
        return 0
    except Exception as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
