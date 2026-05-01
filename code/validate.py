"""
SupportBrain — validate.py
Validates support_issues/output.csv for correctness and completeness.

Usage:
    python code/validate.py
"""

import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate output.csv relative to this file (code/validate.py → repo root)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_CSV = REPO_ROOT / "support_issues" / "output.csv"

REQUIRED_COLUMNS = [
    "Issue", "Subject", "Company",
    "response", "product_area", "status", "request_type", "justification",
]
VALID_STATUSES = {"Replied", "Escalated"}
VALID_REQUEST_TYPES = {"product_issue", "feature_request", "bug", "invalid"}


def validate(path: Path) -> list[str]:
    """
    Validate the output CSV. Returns a list of error strings (empty = all good).
    """
    errors: list[str] = []

    if not path.exists():
        return [f"File not found: {path}"]

    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    # Column check
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing_cols:
        errors.append(f"Missing columns: {', '.join(missing_cols)}")
        return errors  # Can't validate rows without required columns

    for i, row in enumerate(rows, start=1):
        # Status check
        status = row.get("status", "").strip()
        if status not in VALID_STATUSES:
            errors.append(f"Row {i}: invalid status '{status}' (must be Replied or Escalated)")

        # Request type check
        req_type = row.get("request_type", "").strip()
        if req_type not in VALID_REQUEST_TYPES:
            errors.append(
                f"Row {i}: invalid request_type '{req_type}' "
                f"(must be one of {', '.join(sorted(VALID_REQUEST_TYPES))})"
            )

        # Non-empty response check
        response = row.get("response", "").strip()
        if not response:
            errors.append(f"Row {i}: response field is empty")

    return errors


def main() -> None:
    errors = validate(OUTPUT_CSV)
    row_count = 0
    if OUTPUT_CSV.exists():
        with OUTPUT_CSV.open(encoding="utf-8", newline="") as fh:
            row_count = sum(1 for _ in csv.DictReader(fh))

    if errors:
        print(f"❌ Validation failed — {len(errors)} issue(s) found in {OUTPUT_CSV.name}:\n")
        for err in errors:
            print(f"  • {err}")
        sys.exit(1)
    else:
        print(f"✅ All {row_count} rows valid — {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
