"""
Dataset ingestion pipeline: validate -> load -> clean -> parquet -> profile.

Uploaded files are converted to Parquet on disk. DuckDB then queries the
Parquet file directly (zero-copy columnar reads) instead of the process
holding the whole CSV in memory as a Python object indefinitely -- this is
what lets the same code path scale from a 1 MB CSV to a multi-hundred-MB
file without a rewrite.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.config import get_settings
from app.data.profiler import profile_dataframe

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".tsv"}


class IngestionError(ValueError):
    """Raised for any user-facing validation failure during upload."""


@dataclass
class Dataset:
    dataset_id: str
    name: str
    parquet_path: Path
    profile: dict


def _read_any(path: Path, filename: str) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise IngestionError(f"Unsupported file extension: {suffix}")


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().replace(" ", "_").replace("-", "_").lower() for c in df.columns]

    # Best-effort date parsing for object columns that look like dates,
    # so DuckDB gets a real DATE/TIMESTAMP type instead of a string.
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna().astype(str).head(20)
            if sample.empty:
                continue
            looks_datey = sample.str.match(r"^\d{4}-\d{2}-\d{2}").mean() > 0.7 or \
                sample.str.match(r"^\d{1,2}/\d{1,2}/\d{2,4}").mean() > 0.7
            if looks_datey:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().mean() > 0.7:
                    df[col] = parsed
    return df


def ingest_file(tmp_path: Path, original_filename: str, display_name: str | None = None) -> Dataset:
    settings = get_settings()
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise IngestionError(
            f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    size_mb = tmp_path.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise IngestionError(
            f"File is {size_mb:.1f} MB, which exceeds the {settings.max_upload_mb} MB limit for this MVP."
        )

    try:
        df = _read_any(tmp_path, original_filename)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Could not parse file: {exc}") from exc

    if df.empty:
        raise IngestionError("Uploaded file has no rows.")
    if len(df.columns) == 0:
        raise IngestionError("Uploaded file has no columns.")

    df = _clean(df)
    profile = profile_dataframe(df)

    dataset_id = uuid.uuid4().hex[:12]
    parquet_path = settings.storage_dir / "datasets" / f"{dataset_id}.parquet"
    df.to_parquet(parquet_path, index=False)

    return Dataset(
        dataset_id=dataset_id,
        name=display_name or original_filename,
        parquet_path=parquet_path,
        profile=profile,
    )


def ingest_dataframe(df: pd.DataFrame, name: str) -> Dataset:
    """Used for the built-in sample dataset (no file upload round-trip)."""
    settings = get_settings()
    df = _clean(df)
    profile = profile_dataframe(df)
    dataset_id = uuid.uuid4().hex[:12]
    parquet_path = settings.storage_dir / "datasets" / f"{dataset_id}.parquet"
    df.to_parquet(parquet_path, index=False)
    return Dataset(dataset_id=dataset_id, name=name, parquet_path=parquet_path, profile=profile)
