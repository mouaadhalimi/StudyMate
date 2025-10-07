

from pathlib import Path
from docx import Document as DocxDocument
from pypdf import PdfReader

class DocumentLoader:
    """
    DocumentLoader
    --------------

    A unified document reader utility that loads text content from various
    file formats into plain UTF-8 strings.

    This class abstracts away the details of reading different file types
    (currently supports .pdf, .docx, and .txt), providing a single unified
    `load()` method for downstream modules in the RAG pipeline.

    Using this class ensures consistency, avoids code duplication, and makes
    it easy to add support for new document types in the future.

    Supported formats:
        - PDF (.pdf)   → Extracts text from each page using `pypdf.PdfReader`.
        - DOCX (.docx) → Extracts paragraph text using `python-docx`.
        - TXT (.txt)   → Reads as plain UTF-8 text.

    Example:
        >>> from pathlib import Path
        >>> from src.modules.document_loader import DocumentLoader
        >>> loader = DocumentLoader()
        >>> text = loader.load(Path("data/mouad/example.pdf"))
        >>> print(text[:500])

    Notes:
        - PDF text extraction depends on the internal structure of the file.
          Complex layouts may produce unordered text; use LayoutExtractor
          (AI-based) for layout-aware extraction instead.
        - This loader is meant for raw text ingestion only, not layout analysis.
    """
    def __init__(self):
        pass

    def load(self, path: Path) -> str:
        """
        Load a document from a supported file and return its text content.

        Args:
            path (Path): Path to the document file.

        Returns:
            str: Extracted UTF-8 text content.

        Raises:
            ValueError: If the file extension is not supported.
        """
        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._load_pdf(path)
        if ext == ".docx":
            return self._load_docx(path)
        if ext == ".txt":
            return self._load_txt(path)
        raise ValueError(f"Unsupported file type: {ext}")

    def _load_pdf(self, path: Path) -> str:
        """
        Extract text from a PDF file using pypdf.

        Args:
            path (Path): Path to the PDF file.

        Returns:
            str: Concatenated text content from all pages.
        """
        reader = PdfReader(str(path))
        text = []
        for page in reader.pages:
            text.append(page.extract_text() or "")
        return "\n".join(text)

    def _load_docx(self, path: Path) -> str:
        """
        Extract text from a DOCX file using python-docx.

        Args:
            path (Path): Path to the DOCX file.

        Returns:
            str: Concatenated text content from all paragraphs.
        """
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs)

    def _load_txt(self, path: Path) -> str:
        """
        Read plain text from a TXT file.

        Args:
            path (Path): Path to the TXT file.

        Returns:
            str: File content as a UTF-8 string.
        """
        return path.read_text(encoding="utf-8", errors="ignore")