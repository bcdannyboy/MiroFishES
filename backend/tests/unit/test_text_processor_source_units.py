import importlib


def _load_text_processor_module():
    return importlib.import_module("app.services.text_processor")


def test_preprocess_text_preserves_semantic_markers_while_normalizing_whitespace():
    module = _load_text_processor_module()

    processed = module.TextProcessor.preprocess_text(
        " # Market Update \r\n\r\n- First signal\t\t\r\n>  Quoted line  \r\n\r\n"
    )

    assert processed == "# Market Update\n\n- First signal\n> Quoted line"


def test_build_source_units_detects_semantic_boundaries_with_stable_ids():
    module = _load_text_processor_module()
    text = (
        "# Market Update\n\n"
        "Demand improved across districts.\n\n"
        "- Foot traffic up\n"
        "- Vacancy down\n\n"
        "> Operators reported faster lease-ups.\n\n"
        "| Metric | Value |\n"
        "| --- | --- |\n"
        "| Demand | Up |\n\n"
        "00:01 Analyst: Demand looks stronger.\n"
        "00:02 Moderator: What changed?"
    )
    source_record = {
        "source_id": "src-1",
        "stable_source_id": "src-abc123def456",
        "sha256": "a" * 64,
        "original_filename": "memo.md",
        "relative_path": "files/memo.md",
        "source_order": 1,
        "parser_warnings": ["normalized_tabs"],
    }

    first_units = module.TextProcessor.build_source_units(
        text=text,
        source_record=source_record,
        combined_text_start=120,
    )
    second_units = module.TextProcessor.build_source_units(
        text=text,
        source_record=source_record,
        combined_text_start=120,
    )

    assert [unit["unit_type"] for unit in first_units] == [
        "heading",
        "paragraph",
        "list_item",
        "list_item",
        "quote",
        "table",
        "speaker_turn",
        "speaker_turn",
    ]
    assert [unit["unit_id"] for unit in first_units] == [
        unit["unit_id"] for unit in second_units
    ]
    assert first_units[1]["text"] == "Demand improved across districts."
    assert first_units[1]["char_start"] < first_units[1]["char_end"]
    assert first_units[1]["combined_text_start"] == 120 + first_units[1]["char_start"]
    assert first_units[0]["extraction_warnings"] == ["normalized_tabs"]
    assert first_units[-2]["metadata"]["speaker"] == "Analyst"
    assert first_units[-2]["metadata"]["timestamp"] == "00:01"


def test_split_text_prefers_source_unit_boundaries_when_available():
    module = _load_text_processor_module()
    text = (
        "Heading One\n\n"
        "Paragraph one keeps context intact.\n\n"
        "Paragraph two stays whole as well."
    )
    source_units = [
        {
            "unit_id": "u1",
            "unit_type": "heading",
            "char_start": 0,
            "char_end": 11,
            "text": "Heading One",
        },
        {
            "unit_id": "u2",
            "unit_type": "paragraph",
            "char_start": 13,
            "char_end": 48,
            "text": "Paragraph one keeps context intact.",
        },
        {
            "unit_id": "u3",
            "unit_type": "paragraph",
            "char_start": 50,
            "char_end": len(text),
            "text": "Paragraph two stays whole as well.",
        },
    ]

    chunks = module.TextProcessor.split_text(
        text,
        chunk_size=46,
        overlap=0,
        source_units=source_units,
    )

    assert chunks == [
        "Heading One\n\nParagraph one keeps context intact.",
        "Paragraph two stays whole as well.",
    ]
