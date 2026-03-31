"""
File parsing utilities.
Supports text extraction from PDF, Markdown, and TXT files.
"""

import hashlib
import os
from pathlib import Path
from typing import List, Optional, Tuple


def _read_text_with_fallback(file_path: str) -> Tuple[str, List[str]]:
    """
    Read a text file and auto-detect the encoding if UTF-8 fails.
    
    Uses a multi-stage fallback strategy:
    1. Try UTF-8 decoding first
    2. Detect encoding with charset_normalizer
    3. Fall back to chardet
    4. Finally use UTF-8 with `errors='replace'`
    
    Args:
        file_path: File path
        
    Returns:
        Decoded text content
    """
    data = Path(file_path).read_bytes()
    
    # Try UTF-8 first.
    try:
        return data.decode('utf-8'), []
    except UnicodeDecodeError:
        pass
    
    # Try charset_normalizer for detection.
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # Fall back to chardet.
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # Final fallback: UTF-8 with replacement characters.
    if not encoding:
        encoding = 'utf-8'
    
    warning_suffix = encoding or 'utf-8'
    if encoding == 'utf-8':
        warning_suffix = 'utf-8-replace'
    return data.decode(encoding, errors='replace'), [f"encoding_fallback:{warning_suffix}"]


def _sha256_file(file_path: str) -> str:
    """Hash one stored file for durable source identity."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


class FileParser:
    """File parser."""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        Extract text from a file.
        
        Args:
            file_path: File path
            
        Returns:
            Extracted text content
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {suffix}")
        
        return cls.extract_document(file_path)["text"]

    @classmethod
    def extract_document(cls, file_path: str) -> dict:
        """Extract a document with file identity and extraction metadata."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {suffix}")

        extraction_warnings: List[str] = []
        if suffix == '.pdf':
            text, extraction_warnings = cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            text, extraction_warnings = cls._extract_from_md(file_path)
        elif suffix == '.txt':
            text, extraction_warnings = cls._extract_from_txt(file_path)
        else:
            raise ValueError(f"Cannot handle file format: {suffix}")

        return {
            "path": str(path),
            "filename": path.name,
            "extension": suffix,
            "text": text,
            "sha256": _sha256_file(file_path),
            "extraction_warnings": extraction_warnings,
        }
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> Tuple[str, List[str]]:
        """Extract text from a PDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF is required: pip install PyMuPDF")
        
        text_parts = []
        warnings: List[str] = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
                else:
                    warnings.append(f"pdf_page_{page.number + 1}_empty")

        if not text_parts:
            warnings.append("pdf_no_extractable_text")

        return "\n\n".join(text_parts), warnings
    
    @staticmethod
    def _extract_from_md(file_path: str) -> Tuple[str, List[str]]:
        """Extract text from Markdown with automatic encoding detection."""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> Tuple[str, List[str]]:
        """Extract text from TXT with automatic encoding detection."""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        Extract and merge text from multiple files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Merged text
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_document(file_path)["text"]
                filename = Path(file_path).name
                all_texts.append(f"=== Document {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== Document {i}: {file_path} (extraction failed: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    Split text into smaller chunks.
    
    Args:
        text: Source text
        chunk_size: Character count per chunk
        overlap: Overlap character count
        
    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to split on sentence boundaries.
        if end < len(text):
            # Find the nearest sentence terminator.
            for sep in ['\u3002', '\uFF01', '\uFF1F', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Start the next chunk from the overlap position.
        start = end - overlap if end < len(text) else len(text)
    
    return chunks
