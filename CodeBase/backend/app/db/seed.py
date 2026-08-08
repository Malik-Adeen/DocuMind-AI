from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.core.storage import store_upload
from app.db.fixtures import DOCUMENTS, EXTRACTIONS, PIPELINE_VERSION
from app.db.models import Document, Extraction, User
from app.db.session import get_sessionmaker

PASSWORD = "mock-password"
SEED_USERS = (
    ("viewer@ptcl.internal", "Viewer User", "viewer"),
    ("reviewer@ptcl.internal", "Reviewer User", "reviewer"),
    ("admin@ptcl.internal", "Admin User", "admin"),
)
PLACEHOLDER = b"%PDF-1.4 seeded fixture document\n"


def seed_users(db: Session) -> dict[str, User]:
    users = {}
    for email, name, role in SEED_USERS:
        user = db.scalars(select(User).where(User.email == email)).first()
        if user is None:
            user = User(
                id=uuid.uuid5(uuid.NAMESPACE_URL, email),
                email=email,
                name=name,
                password_hash=hash_password(PASSWORD),
                role=role,
            )
            db.add(user)
        users[role] = user
    db.commit()
    return users


def seed_review_state_documents(db: Session, settings: Settings) -> None:
    admin = db.scalars(select(User).where(User.role == "admin")).first()

    for document_id, record in DOCUMENTS.items():
        parsed = uuid.UUID(document_id)
        if db.get(Document, parsed) is not None:
            continue

        stored = store_upload(
            PLACEHOLDER + document_id.encode(),
            filename=str(record["filename"]),
            upload_dir=Path(settings.upload_dir),
        )
        db.add(
            Document(
                id=parsed,
                filename=str(record["filename"]),
                storage_path=stored.path,
                content_type="application/pdf",
                byte_size=stored.byte_size,
                sha256=stored.sha256,
                data_classification=str(record["data_classification"]),
                status=str(record["status"]),
                document_type=str(record["document_type"]),
                uploaded_by=admin.id if admin else None,
            )
        )
        db.flush()

        result = EXTRACTIONS[document_id]
        db.add(
            Extraction(
                id=uuid.UUID(str(result["extraction_id"])),
                document_id=parsed,
                pipeline_version=dict(PIPELINE_VERSION),
                result=result,
                status=str(result["status"]),
            )
        )
    db.commit()


def seed(db: Session, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    seed_users(db)
    seed_review_state_documents(db, resolved)


def main() -> None:
    with get_sessionmaker()() as db:
        seed(db)
    print("seeded: 3 users, 3 review-state documents")


if __name__ == "__main__":
    main()
