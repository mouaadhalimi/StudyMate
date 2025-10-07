
from pathlib import Path
import fitz
from docx import Document as DocxDocument
from concurrent.futures import ThreadPoolExecutor

from src.core.utils import FileManager
from src.modules.page_job import page_job


class LayoutExtractor:
    """
    LayoutExtractor — Extracts structured layout blocks from documents (PDF, DOCX, TXT)
    using OCR and model-based layout detection through a multiprocessing model server.

    This class acts as a bridge between raw document files and downstream
    semantic processing (e.g., block cleaning, chunking, and embedding).
    """

    def __init__(self, file_manager: FileManager, config_path: Path, 
                 server_req_q=None,
                    server_resp_q=None,
 
                     ocr_lang="eng")-> None:
        """
        Initialize the LayoutExtractor with configuration and optional OCR queues.

        Args:
            file_manager (FileManager): Utility for reading configuration files and managing storage.
            config_path (Path): Path to the YAML configuration file for layout settings.
            server_req_q (Optional[Any]): Multiprocessing queue to send page data to the model server.
            server_resp_q (Optional[Any]): Multiprocessing queue to receive OCR/layout results.
            ocr_lang (str): OCR language code (default: "eng").
        """
        self.files = file_manager
        cfg = self.files.load_config(config_path)
        layout_cfg = cfg.get("layout", {})

        self.dpi = layout_cfg.get("pdf_dpi", 150)
        self.score_thresh = layout_cfg.get("score_thresh", 0.5)
        self.server_req_q = server_req_q
  
        self.server_resp_q = server_resp_q
        self.ocr_lang = ocr_lang

    def _extract_pdf(self, path: Path) -> list[dict]:
        """
        Extract structured layout blocks from a PDF file using OCR and layout analysis.

        This method:
            - Converts each PDF page into a high-resolution image.
            - Sends the page image to a model server for OCR/layout detection.
            - Collects and sorts all detected text blocks by page and vertical position.

        Args:
            path (Path): Path to the PDF document.

        Returns:
            List[Dict]: A list of text block dictionaries, each containing fields such as:
                - "type": Block type (e.g., text, title, table, etc.)
                - "text": Extracted text
                - "page": Page number
                - "y": Vertical coordinate on the page
        """
        doc = fitz.open(path)
        print(doc)
        tasks = []

        for page in doc:
            pix = page.get_pixmap(dpi=self.dpi)
       
            tasks.append((page.number, pix.tobytes("png"), self.ocr_lang, 
                          self.server_req_q, 
                          self.server_resp_q

                          ))

        page_blocks_lists = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            for result in executor.map(page_job, tasks):
                page_blocks_lists.append(result)

        blocks = [blk for lst in page_blocks_lists for blk in lst]
        return sorted(blocks, key=lambda b: (b["page"], b["y"]))

    def _extract_docx(self, path: Path) -> list[dict]:
        """
        Extract text blocks from a Microsoft Word (.docx) file.

        This method preserves paragraph structure and identifies headings
        based on style names.

        Args:
            path (Path): Path to the DOCX document.

        Returns:
            List[Dict]: List of paragraph blocks with type ("text" or "title").
        """
        doc = DocxDocument(str(path))
        blocks = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if not txt:
                continue
            btype = "title" if "heading" in p.style.name.lower() else "text"
            blocks.append({
                "type": btype,
                "text": txt,
                "page": 0,
                "y": 0.0
            })
        return blocks

    def _extract_txt(self, path: Path) -> list[dict]:
        """
        Extract paragraph blocks from a plain text (.txt) file.

        The method splits text by double newlines to separate paragraphs.

        Args:
            path (Path): Path to the text file.

        Returns:
            List[Dict]: List of paragraph blocks with sequential page and Y-index.
        """
        content = Path(path).read_text(encoding="utf-8", errors="ignore")
        paras = [p.strip() for p in content.split("\n\n") if p.strip()]
        return [
            {"type": "text", "text": p, "page": 0, "y": i}
            for i, p in enumerate(paras)
        ]

    def extract(self, path: Path) -> list[dict]:
        """
        Automatically detect file type and extract structured layout blocks.

        Supported file types:
            - PDF  (.pdf)
            - Word (.docx)
            - Text (.txt)

        Args:
            path (Path): Path to the document to extract.

        Returns:
            List[Dict]: Extracted layout/text blocks.

        Raises:
            ValueError: If the file type is unsupported.
        """
        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._extract_pdf(path)
        if ext == ".docx":
            return self._extract_docx(path)
        if ext == ".txt":
            return self._extract_txt(path)
        raise ValueError(f"Unsupported file type: {ext}")


