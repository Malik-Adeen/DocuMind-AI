from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.db.queries import current_extraction
from app.schemas.extraction import field_names

MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
LEADING_COLUMNS = ("document_id", "document_type", "status")


def write_workbook(db: Session, *, document_ids: list[uuid.UUID], target: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "extractions"
    sheet.append([*LEADING_COLUMNS, *field_names()])

    for document_id in document_ids:
        view = current_extraction(db, document_id)
        if view is None:
            continue
        sheet.append(
            [
                str(document_id),
                _document_type(view),
                str(view.get("status", "")),
                *(_value(view, name) for name in field_names()),
            ]
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)
    return target


def _document_type(view: dict[str, Any]) -> str:
    document_type = view.get("document_type") or {}
    return str(document_type.get("value", "unknown"))


def _value(view: dict[str, Any], name: str) -> str:
    field = (view.get("fields") or {}).get(name)
    if not field or field.get("value") is None:
        return ""
    return str(field["value"])
