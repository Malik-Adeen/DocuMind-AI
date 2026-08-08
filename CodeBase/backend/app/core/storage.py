from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

READ_ONLY = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH


@dataclass(frozen=True, slots=True)
class StoredUpload:
    path: str
    sha256: str
    byte_size: int


def store_upload(content: bytes, *, filename: str, upload_dir: Path) -> StoredUpload:
    digest = hashlib.sha256(content).hexdigest()
    suffix = Path(filename).suffix.lower()
    target_dir = upload_dir / digest[:2] / digest[2:4]
    target = target_dir / f"{digest}{suffix}"

    if not target.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=target_dir)
        try:
            with os.fdopen(handle, "wb") as raw:
                raw.write(content)
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        target.chmod(READ_ONLY)

    return StoredUpload(path=str(target), sha256=digest, byte_size=len(content))
