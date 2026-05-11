"""Write a PColumn-compatible workdir layout that pl-dev's `pt.import-dir`
template can consume directly. Bypasses pfconv/PT entirely so pl-dev's
post-run MakeCacheReadOnly chmod works on files we already chown to host."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import polars as pl


@dataclass
class AxisSchema:
    id: str
    type: str  # "Int" | "Long" | "String"


@dataclass
class ColumnSchema:
    id: str
    type: str  # "Int" | "Long" | "Float" | "Double" | "String"


_POLARS_DTYPE = {
    "Int": pl.Int32,
    "Long": pl.Int64,
    "Float": pl.Float32,
    "Double": pl.Float64,
    "String": pl.Utf8,
}


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_pframe(
    out_dir: Path,
    rows: list[dict],
    axes: list[AxisSchema],
    columns: list[ColumnSchema],
    partition_filename: str = "partition_0.parquet",
) -> list[Path]:
    """Emit one parquet file + one .datainfo per value column. The .datainfo
    files follow the schema pt.import-dir expects (ParquetPartitioned, one
    "[]" part for partitionKeyLength=0). Returns paths of all files written
    so the caller can chown_to_host them.

    `rows` must contain every axis + every value column."""
    out_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = out_dir / partition_filename
    schema = {a.id: _POLARS_DTYPE[a.type] for a in axes}
    schema.update({c.id: _POLARS_DTYPE[c.type] for c in columns})

    df = pl.DataFrame(rows, schema=schema) if rows else pl.DataFrame(schema=schema)
    df.write_parquet(parquet_path)
    digest = _sha256_of(parquet_path)
    n_rows = df.height

    written: list[Path] = [parquet_path]
    for col in columns:
        datainfo = {
            "type": "ParquetPartitioned",
            "partitionKeyLength": 0,
            "parts": {
                "[]": {
                    "data": partition_filename,
                    "dataDigest": digest,
                    "axes": [{"id": a.id, "type": a.type} for a in axes],
                    "column": {"id": col.id, "type": col.type},
                    "stats": {"numberOfRows": n_rows},
                }
            },
        }
        info_path = out_dir / f"{col.id}.datainfo"
        info_path.write_text(json.dumps(datainfo))
        written.append(info_path)
    return written


def chown_paths_to_host(paths: Iterable[Path]) -> None:
    """Match every output file to the bind-mounted workdir's owner so
    pl-dev's MakeCacheReadOnly chmod doesn't EPERM. No-op outside Docker."""
    import os

    try:
        stat = os.stat("/workdir")
    except (FileNotFoundError, PermissionError, OSError):
        return

    for p in paths:
        try:
            os.chown(p, stat.st_uid, stat.st_gid)
        except (FileNotFoundError, PermissionError, OSError):
            pass
