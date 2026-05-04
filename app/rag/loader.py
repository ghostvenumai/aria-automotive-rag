from __future__ import annotations

from pathlib import Path

from app.rag.models import Document


SUPPORTED_EXTENSIONS = {".md", ".txt"}


def load_documents(base_dir: Path) -> list[Document]:
    documents: list[Document] = []
    if not base_dir.exists():
        return documents

    for path in sorted(base_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        documents.append(
            Document(
                doc_id=path.stem,
                title=path.stem.replace("-", " ").replace("_", " ").title(),
                text=text,
                source_path=str(path),
                metadata={"extension": path.suffix.lower()},
            )
        )
    return documents

