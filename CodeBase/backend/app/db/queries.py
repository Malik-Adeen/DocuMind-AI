from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

CURRENT_EXTRACTION_VIEW = text("""
WITH latest AS (
    SELECT e.id, e.document_id, e.result, e.status, e.seq
    FROM extractions e
    WHERE e.document_id = :document_id
    ORDER BY e.seq DESC
    LIMIT 1
),
applied AS (
    SELECT DISTINCT ON (c.field) c.field, c.value
    FROM corrections c
    JOIN latest l ON l.id = c.extraction_id
    ORDER BY c.field, c.seq DESC
),
patch AS (
    SELECT jsonb_object_agg(
               a.field,
               COALESCE(l.result #> ARRAY['fields', a.field], '{"confidence": 0.0}'::jsonb)
               || jsonb_build_object(
                      'value', to_jsonb(a.value),
                      'verified', true,
                      'source', jsonb_build_object('origin', 'human')
                  )
               || '{"gate": null, "gate_error": null}'::jsonb
           ) AS fields
    FROM applied a
    CROSS JOIN latest l
)
SELECT jsonb_set(
           l.result,
           '{fields}',
           COALESCE(l.result -> 'fields', '{}'::jsonb) || COALESCE(p.fields, '{}'::jsonb)
       ) AS result
FROM latest l
LEFT JOIN patch p ON true
""")


UNVERIFIED_FIELD_COUNT = text("""
WITH newest AS (
    SELECT DISTINCT ON (e.document_id) e.id, e.document_id, e.result
    FROM extractions e
    WHERE e.document_id = ANY(:document_ids)
    ORDER BY e.document_id, e.seq DESC
),
corrected AS (
    SELECT DISTINCT c.extraction_id, c.field
    FROM corrections c
    JOIN newest n ON n.id = c.extraction_id
)
SELECT n.document_id,
       count(*) FILTER (
           WHERE field.value -> 'verified' = 'false'::jsonb
             AND NOT EXISTS (
                 SELECT 1 FROM corrected co
                 WHERE co.extraction_id = n.id AND co.field = field.key
             )
       ) AS unverified
FROM newest n
LEFT JOIN LATERAL jsonb_each(COALESCE(n.result -> 'fields', '{}'::jsonb)) AS field ON true
GROUP BY n.document_id
""")


def current_extraction(session: Session, document_id: uuid.UUID) -> dict[str, Any] | None:
    row = session.execute(CURRENT_EXTRACTION_VIEW, {"document_id": document_id}).first()
    if row is None:
        return None
    result: dict[str, Any] = row[0]
    return result


def unverified_field_counts(
    session: Session,
    document_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    if not document_ids:
        return {}
    rows = session.execute(UNVERIFIED_FIELD_COUNT, {"document_ids": document_ids}).all()
    return {row.document_id: int(row.unverified) for row in rows}
