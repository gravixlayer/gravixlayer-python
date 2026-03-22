"""Output formatting utilities for the CLI."""

import json
import sys
from typing import Any, Dict, List, Optional


def _to_serializable(obj: Any) -> Any:
    """Recursively convert dataclass/object to JSON-serializable dict."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_serializable(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_to_serializable(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    serializable = _to_serializable(data)
    json.dump(serializable, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def print_table(rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> None:
    """Print a list of dicts as an aligned table."""
    if not rows:
        print("No results.")
        return

    if columns is None:
        columns = list(rows[0].keys())

    col_widths = {col: len(col) for col in columns}
    str_rows = []
    for row in rows:
        str_row = {}
        for col in columns:
            val = str(row.get(col, ""))
            str_row[col] = val
            col_widths[col] = max(col_widths[col], len(val))
        str_rows.append(str_row)

    header = "  ".join(col.upper().ljust(col_widths[col]) for col in columns)
    separator = "  ".join("-" * col_widths[col] for col in columns)
    print(header)
    print(separator)
    for str_row in str_rows:
        line = "  ".join(str_row[col].ljust(col_widths[col]) for col in columns)
        print(line)


def print_error(msg: str) -> None:
    """Print an error message to stderr and exit with code 1."""
    sys.stderr.write(f"Error: {msg}\n")
    sys.exit(1)


def print_kv(data: Dict[str, Any], indent: int = 0) -> None:
    """Print key-value pairs with aligned formatting."""
    if not data:
        return
    prefix = " " * indent
    max_key = max(len(str(k)) for k in data)
    for k, v in data.items():
        if isinstance(v, dict):
            print(f"{prefix}{str(k).ljust(max_key)}:")
            print_kv(v, indent=indent + 2)
        elif isinstance(v, list):
            print(f"{prefix}{str(k).ljust(max_key)}: {json.dumps(v, default=str)}")
        else:
            print(f"{prefix}{str(k).ljust(max_key)}: {v}")
