

from pathlib import Path
from typing import List, Dict
import multiprocessing as mp

from src.core.utils import FileManager
from src.modules.layout_extractor import LayoutExtractor
from src.modules.document_loader import DocumentLoader
from src.core.block_processor import BlockProcessor
from src.core.chunk_builder import ChunkBuilder
from src.modules.entity_extractor import EntityExtractor



def process_document_task(doc, user_id, server_req_q, server_resp_q)-> List[Dict]:
    """
    Worker task to process a single document in a separate process.

    Each worker:
      - Initializes a LayoutExtractor
      - Extracts layout blocks (using OCR + model inference)
      - Annotates each block with `filename` and `user_id`

    Args:
        doc (Path): Path to the document file to process.
        user_id (str): Unique user identifier for multi-user isolation.
        server_req_q: Request queue for sending page images to the model server.
        server_resp_q: Response queue for receiving layout results.

    Returns:
        List[Dict]: Extracted and annotated text blocks from the document.
    """
    file_manager = FileManager(None)  
    layout = LayoutExtractor(
        file_manager,
        Path("config/config.yaml"),
        server_req_q=server_req_q,
         server_resp_q=server_resp_q,

        ocr_lang="eng"
    )
    b = layout.extract(doc)
    for blk in b:
        blk["filename"] = doc.name
        blk["user_id"] = user_id
    return b


class Ingestor:
    """
    Ingestor — Orchestrates the ingestion and preprocessing of user documents
    into clean, chunked text suitable for indexing in a RAG pipeline.

    The ingestion workflow includes:
      1. Loading all user documents from a data directory.
      2. Extracting layout or plain text content.
      3. Cleaning headers/footers and merging small blocks.
      4. Splitting text into semantically coherent chunks.
      5. Saving the resulting chunks into a JSON file.

    Supports both "layout" mode (PDFs + OCR + visual parsing)
    and "text" mode (plain-text or DOCX ingestion).
    """
    def __init__(
        self,
        config: dict,
        file_manager: FileManager,
        layout_extractor: LayoutExtractor,
        document_loader: DocumentLoader,
        block_processor: BlockProcessor,
        entity_extractor: EntityExtractor,
        chunk_builder: ChunkBuilder,
        logger,
        user_id: str,
        mode: str = "layout",
        server_req_q=None,
        server_resp_q=None,

    )-> None:
        """
        Initialize the Ingestor with its processing modules and configuration.

        Args:
            config (dict): Global configuration dictionary, must contain:
                - paths.data_dir: Base directory for user document storage.
                - paths.chunks_file: Path template for chunk output file.
            file_manager (FileManager): Utility for file reading/writing.
            layout_extractor (LayoutExtractor): Visual document extractor.
            document_loader (DocumentLoader): Basic text loader (for non-PDFs).
            block_processor (BlockProcessor): Cleans and filters layout blocks.
            entity_extractor (EntityExtractor): Reserved for future metadata extraction.
            chunk_builder (ChunkBuilder): Handles deduplication and text splitting.
            logger (Logger): Logger instance for monitoring progress.
            user_id (str): Unique identifier for the current user.
            mode (str, optional): Ingestion mode — "layout" or "text". Defaults to "layout".
            server_req_q (optional): Multiprocessing request queue for model inference.
            server_resp_q (optional): Multiprocessing response queue for model inference.
        """

        self.logger = logger
        self.files = file_manager
        self.layout = layout_extractor
        self.loader = document_loader
        self.proc = block_processor
        self.entities = entity_extractor
        self.chunker = chunk_builder
        self.user_id = user_id
        self.mode = mode
        self.server_req_q = server_req_q
        self.server_resp_q = server_resp_q

        storage_cfg  = config["paths"]
        self.data_dir = Path(storage_cfg["data_dir"]) / user_id
        self.chunks_file = Path(storage_cfg["chunks_file"]).with_name(f"chunks_{user_id}.json")


    def load_documents(self) -> List[Path]:
        """
        Load all document files for the current user.

        Returns:
            List[Path]: List of document file paths found in the user’s data directory.
                        Returns an empty list if no files are present.

        Side Effects:
            Logs a warning if the user's data directory does not exist.
        """
        if not self.data_dir.exists():
            self.logger.warning(f"No data folder for user {self.user_id}")
            return []
        return [fp for fp in self.data_dir.rglob("*") if fp.is_file()]

    def process_blocks(self, docs: List[Path]) -> List[Dict]:
        """
        Extract layout or text blocks from user documents.

        Depending on the selected mode:
          - "layout" mode uses LayoutExtractor with OCR via multiprocessing.
          - "text" mode uses a simple DocumentLoader for plain text extraction.

        After extraction:
          - Page headers and footers are removed for cleaner content.

        Args:
            docs (List[Path]): List of document file paths to process.

        Returns:
            List[Dict]: Cleaned and flattened list of text blocks across all documents.
        """
        blocks = []

        if self.mode == "layout":

            tasks = [(doc, self.user_id, self.server_req_q, self.server_resp_q) for doc in docs]


            with mp.get_context("spawn").Pool(processes=9) as doc_pool:
                results = doc_pool.starmap(process_document_task, tasks)


            for b in results:
                blocks.extend(b)
        else:
            for doc in docs:
                text = self.loader.load(doc)
                blocks.append({
                    "filename": doc.name,
                    "text": text,
                    "type": "text",
                    "page": 0,
                    "user_id": self.user_id
                })

        blocks = self.proc.remove_page_headers_footers(blocks)
        return blocks

    def build_chunks(self, blocks: List[Dict]) -> List[Dict]:
        """
        Convert text blocks into final semantic chunks for vector indexing.

        Steps:
          1. Remove near-duplicate blocks.
          2. Merge small blocks for coherence.
          3. Split cleaned text into overlapping chunks.

        Args:
            blocks (List[Dict]): Processed layout or text blocks.

        Returns:
            List[Dict]: Final list of chunk dictionaries ready for indexing.
        """
        blocks = self.chunker.remove_near_duplicates(blocks, windows=10)
        blocks = self.chunker.merge_small_blocks(blocks, min_words=20)

        chunks = []
        cid = 0
        for b in blocks:
            for part in self.chunker.split_text(b["text"]):
                chunks.append({
                    "filename": b["filename"],
                    "chunk_id": cid,
                    "text": part,
                    "type": b.get("type", "text"),
                    "page": b.get("page", 0),
                    "user_id": self.user_id,
                })
                cid += 1
        return chunks

    def run(self)-> None:
        """
        Execute the full ingestion workflow for a specific user.

        Workflow:
            1. Load all available documents.
            2. Extract and clean text blocks.
            3. Build final chunks from processed blocks.
            4. Save all chunks as a JSON file for downstream indexing.

        Side Effects:
            - Writes the resulting chunks JSON to storage.
            - Logs progress, document counts, and completion status.
        """
        self.logger.info(f"Starting ingestion for user {self.user_id} ({self.mode} mode)...")
        docs = self.load_documents()
        blocks = self.process_blocks(docs)
        chunks = self.build_chunks(blocks)
        self.files.save_json(chunks, self.chunks_file)
        self.logger.info(f"Saved {len(chunks)} chunks for {self.user_id}")

