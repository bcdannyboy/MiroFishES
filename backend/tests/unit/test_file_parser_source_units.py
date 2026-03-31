import hashlib
import importlib
from pathlib import Path


def _load_file_parser_module():
    return importlib.import_module("app.utils.file_parser")


def test_extract_document_returns_text_hash_and_identity(tmp_path):
    module = _load_file_parser_module()
    file_path = tmp_path / "memo.md"
    file_path.write_text("# Market Update\n\nDemand improved.\n", encoding="utf-8")

    document = module.FileParser.extract_document(str(file_path))

    assert document["filename"] == "memo.md"
    assert document["extension"] == ".md"
    assert document["path"] == str(file_path)
    assert document["sha256"] == hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert document["text"].startswith("# Market Update")
    assert document["extraction_warnings"] == []
