"""
Main entrypoint for the RAG (Retrieval-Augmented Generation) pipeline.

This script orchestrates the full pipeline stages for each user:
    1. ingest   – Extract structured text chunks from documents.
    2. index    – Embed chunks and store them in the vector database.
    3. search   – Retrieve and rerank relevant chunks for a given query.
    4. answer   – Generate a contextual answer using an LLM (Ollama).

Usage:
    python -m src.main <stage> <user_id> [optional question/query]

Example:
    python -m src.main ingest user123
    python -m src.main index user123
    python -m src.main search user123 "What is supply chain management?"
    python -m src.main answer user123 "Summarize this document set."
"""

from pathlib import Path
import sys
import multiprocessing as mp

from src.pipeline.answerer import Answerer
from src.pipeline.searcher import Searcher
from src.pipeline.indexer import Indexer
from src.pipeline.ingestor import Ingestor
from src.modules.model_server import model_server
from src.modules.reranker import Reranker

from src.core.Logger import LoggerManager
from src.core.utils import FileManager
from src.core.block_processor import BlockProcessor
from src.core.chunk_builder import ChunkBuilder
from src.modules.layout_extractor import LayoutExtractor
from src.modules.document_loader import DocumentLoader
from src.modules.entity_extractor import EntityExtractor


def run_ingest_stage(config: dict, files: FileManager, logger, user_id: str) -> None:
    """
    Run the ingestion stage: extract, clean, and chunk documents for a given user.

    Steps:
        - Launch the model server for layout analysis and OCR
        - Extract layout blocks from documents
        - Remove headers/footers and duplicates
        - Split text into chunks and save them as JSON
    """
    logger.info(f"Starting ingestion stage for user '{user_id}'...")

    manager = mp.Manager()
    server_req_q = manager.Queue()
    server_resp_q = manager.Queue()

    # Start the YOLO-based document layout model server in a separate process
    server = mp.Process(
        target=model_server,
        args=(server_req_q, server_resp_q, "models/yolov8n-doclaynet.pt"),
        daemon=True,
    )
    server.start()

    # Initialize processing modules
    blockproc = BlockProcessor(logger)
    layout = LayoutExtractor(
        file_manager=files,
        config_path=Path("config/config.yaml"),
        server_req_q=server_req_q,
        server_resp_q=server_resp_q,
        ocr_lang="eng",
    )
    loader = DocumentLoader()
    entities = EntityExtractor(files, Path("config/config.yaml"))

    chunk_size = int(config["chunking"]["chunk_size"])
    tokenizer_model = config["tokenizer"]["model"]
    chunker = ChunkBuilder(
        tokenizer_model=tokenizer_model, chunk_size=chunk_size, logger=logger
    )

    ingestor = Ingestor(
        config=config,
        file_manager=files,
        layout_extractor=layout,
        document_loader=loader,
        block_processor=blockproc,
        entity_extractor=entities,
        chunk_builder=chunker,
        logger=logger,
        user_id=user_id,
        mode="layout",
        server_req_q=server_req_q,
        server_resp_q=server_resp_q,
    )

    # Run ingestion
    ingestor.run()

    # Stop model server cleanly
    server_req_q.put(None)
    server_resp_q.put(None)
    server.join()
    logger.info(f"Ingestion stage completed for user '{user_id}'.")


def run_index_stage(config: dict, files: FileManager, logger, user_id: str) -> None:
    """
    Run the indexing stage: convert text chunks into embeddings and store them.
    """
    logger.info(f"Starting indexing stage for user '{user_id}'...")
    indexer = Indexer(config, files, logger, user_id)
    indexer.run()
    logger.info(f"Indexing stage completed for user '{user_id}'.")


def run_search_stage(config: dict, files: FileManager, logger, user_id: str, query: str) -> None:
    """
    Run the semantic search stage for a user query.
    Retrieves the most relevant chunks and re-ranks them using a Cross-Encoder.
    """
    logger.info(f"Starting search stage for user '{user_id}' with query: {query}")

    searcher = Searcher(config, files, logger, user_id)
    results = searcher.search(query, top_k=20)

    reranker = Reranker(logger=logger)
    reranked = reranker.rerank(query, results, top_k=5)

    print("\n🔍 Top 5 Re-ranked Results:")
    for i, res in enumerate(reranked, start=1):
        print(f"\nResult {i}:")
        print(f"  File: {res['metadata']['filename']}")
        print(f"  Score: {res['rerank_score']:.4f}")
        print(f"  Text: {res['text'][:250]}...")

    logger.info(f"Search stage completed for user '{user_id}'.")


def run_answer_stage(config: dict, files: FileManager, logger, user_id: str, question: str) -> None:
    """
    Run the answer generation stage.
    Uses retrieved chunks + LLM (Ollama) to produce a contextual answer.
    """
    logger.info(f"Starting answer stage for user '{user_id}' with question: {question}")
    answerer = Answerer(config, files, logger, user_id)
    answerer.run(question)
    logger.info(f"Answer stage completed for user '{user_id}'.")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)

    # Initialize global logger
    log_manager = LoggerManager(Path("storage/logs"))
    logger = log_manager.get_logger()

    files = FileManager(logger)
    config = files.load_config(Path("config/config.yaml"))

    if len(sys.argv) < 3:
        print("\nUsage:")
        print("  python -m src.main <stage> <user_id> [query/question]\n")
        print("Available stages:")
        print("  ingest   – Extract and chunk documents")
        print("  index    – Generate embeddings and build vector DB")
        print("  search   – Perform semantic retrieval")
        print("  answer   – Generate contextual answers with LLM\n")
        sys.exit(1)

    stage = sys.argv[1].lower()
    user_id = sys.argv[2]
    extra = " ".join(sys.argv[3:]).strip()

    try:
        if stage == "ingest":
            run_ingest_stage(config, files, logger, user_id)
        elif stage == "index":
            run_index_stage(config, files, logger, user_id)
        elif stage == "search":
            query = extra or "What is HCL?"
            run_search_stage(config, files, logger, user_id, query)
        elif stage == "answer":
            question = extra or "Generate me exams for these courses."
            run_answer_stage(config, files, logger, user_id, question)
        else:
            logger.error(f"Unknown stage: '{stage}'. Please specify one of: ingest | index | search | answer")
    except Exception as e:
        logger.exception(f"Pipeline execution failed: {e}")
        sys.exit(1)
