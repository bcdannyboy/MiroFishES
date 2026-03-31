"""
Text processing service.
"""

import re
from typing import Any, Dict, List, Optional

from ..utils.file_parser import FileParser, split_text_into_chunks
from ..models.source_units import build_source_unit_id


class TextProcessor:
    """Text processor."""
    
    @staticmethod
    def extract_from_files(file_paths: List[str]) -> str:
        """Extract text from multiple files."""
        return FileParser.extract_from_multiple(file_paths)
    
    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
        source_units: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """
        Split text into chunks.
        
        Args:
            text: Source text
            chunk_size: Chunk size
            overlap: Overlap size
            
        Returns:
            List of text chunks
        """
        if source_units:
            return TextProcessor._split_text_by_source_units(
                text=text,
                chunk_size=chunk_size,
                overlap=overlap,
                source_units=source_units,
            )
        return split_text_into_chunks(text, chunk_size, overlap)
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        Preprocess text.
        - Remove extra whitespace
        - Normalize line breaks
        
        Args:
            text: Source text
            
        Returns:
            Processed text
        """
        # Normalize line breaks.
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = text.replace('\u00a0', ' ').replace('\t', ' ')

        normalized_lines = []
        for line in text.split('\n'):
            compact_line = re.sub(r'[^\S\n]+', ' ', line).strip()
            normalized_lines.append(compact_line)
        text = '\n'.join(normalized_lines)

        # Remove repeated blank lines while keeping at most two.
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def build_source_units(
        *,
        text: str,
        source_record: Dict[str, Any],
        combined_text_start: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Build deterministic semantic source units from one preprocessed document."""
        if not text.strip():
            return []

        lines = text.split('\n')
        positions = []
        cursor = 0
        for index, line in enumerate(lines):
            start = cursor
            end = start + len(line)
            positions.append((start, end))
            cursor = end + (1 if index < len(lines) - 1 else 0)

        units: List[Dict[str, Any]] = []
        heading_stack: List[Dict[str, Any]] = []
        index = 0
        unit_order = 1

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if not stripped:
                index += 1
                continue

            if TextProcessor._is_heading(stripped):
                heading_level = TextProcessor._heading_level(stripped)
                heading_title = stripped.lstrip('#').strip()
                heading_stack = [
                    item for item in heading_stack if item["level"] < heading_level
                ]
                heading_stack.append({"level": heading_level, "title": heading_title})
                units.append(
                    TextProcessor._build_unit(
                        source_record=source_record,
                        unit_order=unit_order,
                        unit_type="heading",
                        text_slice=text,
                        start=positions[index][0],
                        end=positions[index][1],
                        combined_text_start=combined_text_start,
                        metadata={
                            "heading_level": heading_level,
                            "heading_path": [item["title"] for item in heading_stack],
                        },
                    )
                )
                unit_order += 1
                index += 1
                continue

            if TextProcessor._is_table_line(stripped):
                start_index = index
                end_index = index
                while end_index + 1 < len(lines) and TextProcessor._is_table_line(
                    lines[end_index + 1].strip()
                ):
                    end_index += 1
                units.append(
                    TextProcessor._build_unit(
                        source_record=source_record,
                        unit_order=unit_order,
                        unit_type="table",
                        text_slice=text,
                        start=positions[start_index][0],
                        end=positions[end_index][1],
                        combined_text_start=combined_text_start,
                        metadata={
                            "heading_path": [item["title"] for item in heading_stack],
                            "row_count": end_index - start_index + 1,
                        },
                    )
                )
                unit_order += 1
                index = end_index + 1
                continue

            if TextProcessor._is_quote_line(stripped):
                start_index = index
                end_index = index
                while end_index + 1 < len(lines) and TextProcessor._is_quote_line(
                    lines[end_index + 1].strip()
                ):
                    end_index += 1
                units.append(
                    TextProcessor._build_unit(
                        source_record=source_record,
                        unit_order=unit_order,
                        unit_type="quote",
                        text_slice=text,
                        start=positions[start_index][0],
                        end=positions[end_index][1],
                        combined_text_start=combined_text_start,
                        metadata={
                            "heading_path": [item["title"] for item in heading_stack],
                        },
                    )
                )
                unit_order += 1
                index = end_index + 1
                continue

            speaker_match = TextProcessor._match_speaker_turn(stripped)
            if speaker_match:
                start_index = index
                end_index = index
                while (
                    end_index + 1 < len(lines)
                    and lines[end_index + 1].strip()
                    and not TextProcessor._match_speaker_turn(lines[end_index + 1].strip())
                    and not TextProcessor._is_special_line(lines[end_index + 1].strip())
                ):
                    end_index += 1
                units.append(
                    TextProcessor._build_unit(
                        source_record=source_record,
                        unit_order=unit_order,
                        unit_type="speaker_turn",
                        text_slice=text,
                        start=positions[start_index][0],
                        end=positions[end_index][1],
                        combined_text_start=combined_text_start,
                        metadata={
                            "heading_path": [item["title"] for item in heading_stack],
                            "speaker": speaker_match.group("speaker").strip(),
                            "timestamp": (
                                speaker_match.group("timestamp").strip("[]")
                                if speaker_match.group("timestamp")
                                else None
                            ),
                        },
                    )
                )
                unit_order += 1
                index = end_index + 1
                continue

            if TextProcessor._is_list_item(stripped):
                start_index = index
                end_index = index
                while (
                    end_index + 1 < len(lines)
                    and lines[end_index + 1].strip()
                    and not TextProcessor._is_special_line(lines[end_index + 1].strip())
                ):
                    end_index += 1
                units.append(
                    TextProcessor._build_unit(
                        source_record=source_record,
                        unit_order=unit_order,
                        unit_type="list_item",
                        text_slice=text,
                        start=positions[start_index][0],
                        end=positions[end_index][1],
                        combined_text_start=combined_text_start,
                        metadata={
                            "heading_path": [item["title"] for item in heading_stack],
                        },
                    )
                )
                unit_order += 1
                index = end_index + 1
                continue

            start_index = index
            end_index = index
            while (
                end_index + 1 < len(lines)
                and lines[end_index + 1].strip()
                and not TextProcessor._is_special_line(lines[end_index + 1].strip())
            ):
                end_index += 1

            units.append(
                TextProcessor._build_unit(
                    source_record=source_record,
                    unit_order=unit_order,
                    unit_type="paragraph",
                    text_slice=text,
                    start=positions[start_index][0],
                    end=positions[end_index][1],
                    combined_text_start=combined_text_start,
                    metadata={
                        "heading_path": [item["title"] for item in heading_stack],
                    },
                )
            )
            unit_order += 1
            index = end_index + 1

        return units
    
    @staticmethod
    def get_text_stats(text: str) -> dict:
        """Return text statistics."""
        return {
            "total_chars": len(text),
            "total_lines": text.count('\n') + 1,
            "total_words": len(text.split()),
        }

    @staticmethod
    def _build_unit(
        *,
        source_record: Dict[str, Any],
        unit_order: int,
        unit_type: str,
        text_slice: str,
        start: int,
        end: int,
        combined_text_start: Optional[int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        stable_source_id = source_record.get("stable_source_id") or source_record.get("source_id")
        unit_text = text_slice[start:end].strip()
        combined_start = combined_text_start + start if combined_text_start is not None else None
        combined_end = combined_text_start + end if combined_text_start is not None else None
        return {
            "unit_id": build_source_unit_id(stable_source_id, unit_order),
            "source_id": source_record.get("source_id"),
            "stable_source_id": stable_source_id,
            "source_sha256": source_record.get("sha256"),
            "original_filename": source_record.get("original_filename"),
            "relative_path": source_record.get("relative_path"),
            "source_order": source_record.get("source_order"),
            "unit_order": unit_order,
            "unit_type": unit_type,
            "char_start": start,
            "char_end": end,
            "combined_text_start": combined_start,
            "combined_text_end": combined_end,
            "text": unit_text,
            "metadata": metadata or {},
            "extraction_warnings": list(source_record.get("parser_warnings") or []),
        }

    @staticmethod
    def _split_text_by_source_units(
        *,
        text: str,
        chunk_size: int,
        overlap: int,
        source_units: List[Dict[str, Any]],
    ) -> List[str]:
        normalized_units = [
            unit
            for unit in sorted(source_units, key=lambda item: item.get("char_start", 0))
            if isinstance(unit, dict)
            and isinstance(unit.get("char_start"), int)
            and isinstance(unit.get("char_end"), int)
            and unit.get("char_end") > unit.get("char_start")
        ]
        if not normalized_units:
            return split_text_into_chunks(text, chunk_size, overlap)

        chunks: List[str] = []
        start_index = 0
        while start_index < len(normalized_units):
            end_index = start_index
            chunk_start = normalized_units[start_index]["char_start"]
            chunk_end = normalized_units[start_index]["char_end"]

            while end_index + 1 < len(normalized_units):
                candidate_end = normalized_units[end_index + 1]["char_end"]
                candidate_text = text[chunk_start:candidate_end].strip()
                allow_heading_pair = (
                    end_index == start_index
                    and normalized_units[start_index].get("unit_type") == "heading"
                    and len(candidate_text) <= int(chunk_size * 1.2)
                )
                if candidate_text and len(candidate_text) > chunk_size and not allow_heading_pair:
                    break
                end_index += 1
                chunk_end = candidate_end

            chunk = text[chunk_start:chunk_end].strip()
            if chunk:
                chunks.append(chunk)

            next_index = end_index + 1
            if overlap > 0 and end_index > start_index:
                overlap_chars = 0
                overlap_index = end_index
                while overlap_index > start_index and overlap_chars < overlap:
                    overlap_chars = chunk_end - normalized_units[overlap_index]["char_start"]
                    overlap_index -= 1
                next_index = max(overlap_index + 1, start_index + 1)

            start_index = next_index

        return chunks

    @staticmethod
    def _is_heading(line: str) -> bool:
        return bool(re.match(r"^#{1,6}\s+\S", line)) or bool(
            re.match(r"^[A-Z][A-Z0-9 /&-]{2,80}:?$", line)
        )

    @staticmethod
    def _heading_level(line: str) -> int:
        if line.startswith("#"):
            return len(line) - len(line.lstrip("#"))
        return 1

    @staticmethod
    def _is_list_item(line: str) -> bool:
        return bool(re.match(r"^(?:[-*+]|\d+[.)])\s+\S", line))

    @staticmethod
    def _is_quote_line(line: str) -> bool:
        return line.startswith(">")

    @staticmethod
    def _is_table_line(line: str) -> bool:
        return line.count("|") >= 2 or "\t" in line

    @staticmethod
    def _match_speaker_turn(line: str):
        return re.match(
            r"^(?:(?P<timestamp>\[?\d{1,2}:\d{2}(?::\d{2})?\]?)\s+)?(?P<speaker>[A-Z][A-Za-z0-9 _./-]{0,60}):\s*(?P<body>.+)$",
            line,
        )

    @staticmethod
    def _is_special_line(line: str) -> bool:
        return (
            TextProcessor._is_heading(line)
            or TextProcessor._is_list_item(line)
            or TextProcessor._is_quote_line(line)
            or TextProcessor._is_table_line(line)
            or bool(TextProcessor._match_speaker_turn(line))
        )
