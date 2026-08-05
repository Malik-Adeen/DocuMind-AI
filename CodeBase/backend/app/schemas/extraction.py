from __future__ import annotations

import json
import pathlib
from functools import lru_cache
from typing import Any

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[3].parent / "Docs" / "EXTRACTION_SCHEMA.json"


@lru_cache
def extraction_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text())
    return schema


@lru_cache
def field_names() -> tuple[str, ...]:
    properties = extraction_schema()["properties"]["fields"]["properties"]
    return tuple(properties)


@lru_cache
def schema_version() -> str:
    pipeline = extraction_schema()["properties"]["pipeline_version"]["properties"]
    version: str = pipeline["schema_version"]["const"]
    return version


@lru_cache
def terminal_statuses() -> frozenset[str]:
    return frozenset(extraction_schema()["properties"]["status"]["enum"])
