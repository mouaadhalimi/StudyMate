
import json
from pathlib import Path
from typing import Any, List, Dict
from sentence_transformers import SentenceTransformer
from chromadb import PersistentClient
from src.core.utils import FileManager
import hnswlib
import numpy as np


class Indexer:
    """
    Indexer — Build and store semantic embeddings for user documents in a multi-user RAG pipeline.

    This class performs the indexing stage of a Retrieval-Augmented Generation (RAG) system.
    It takes preprocessed text chunks (from the ingestion stage), generates dense vector
    embeddings for each chunk using a SentenceTransformer, and stores them in a persistent
    ChromaDB vector database.

    Each user's embeddings are isolated via a `user_id` tag in the metadata to ensure privacy
    and prevent data overlap between users.
    """

    def __init__(self, config:dict, file_manager:FileManager, logger, user_id:str)-> None:
        """
        Initialize the Indexer for a specific user.

        This method prepares:
          - The per-user chunk file path (`chunks_<user_id>.json`)
          - The persistent ChromaDB vector store
          - The SentenceTransformer model used for embedding generation

        Args:
            config (dict): Configuration dictionary (usually from config.yaml).
                Must include:
                    - paths.chunks_file: Base path to the chunks JSON file
                    - paths.vector_db: Directory path for the ChromaDB store
                    - models.embedding_model: SentenceTransformer model name
            file_manager (FileManager): Utility class for file I/O operations.
            logger (Logger): Logger instance (e.g., Loguru) for progress and error tracking.
            user_id (str): Unique identifier of the current user (used for data isolation).
        """
        self.logger = logger
        self.files = file_manager
        self.user_id = user_id

        path=config['paths']
        self.chunks_file = Path(path['chunks_file']).with_name(f'chunks_{user_id}.json')
        self.vector_db_dir = Path(path['vector_db'])

        self.embed_model=SentenceTransformer(config["models"]['embedding_model'])
        self.client= PersistentClient(path=str(self.vector_db_dir))
        self.collection = self.client.get_or_create_collection('documents')

        self.logger.info('Indexer initialized for user {user_id}')
    
    def load_chunks(self) -> List[Dict[str, Any]]:
        """
        Load preprocessed text chunks for this user from a JSON file.

        The chunk file is expected to be produced by the ingestion pipeline and
        should contain dictionaries with fields such as:
            - "filename"
            - "chunk_id"
            - "text"
            - "user_id"

        Returns:
            List[Dict[str, Any]]: A list of chunk dictionaries. Returns an empty list if no file exists.

        Side Effects:
            Logs:
                - A warning if the chunks file is missing.
                - An info message with the number of loaded chunks if found.
        """
        if not self.chunks_file.exists():
            self.logger.warning(f"No chunks file found for user {self.user_id}")
            return[]
        chunks = self.files.load_json(self.chunks_file)
        self.logger.info(f"Loaded {len(chunks)} chunks from {self.chunks_file} for user {self.user_id}")
        return chunks 



    def index_chunks(self, chunks:List[Dict])-> None:
        """
        Generate dense embeddings for user chunks and store them in ChromaDB.

        Workflow:
            1. Encode each text chunk using the configured SentenceTransformer model.
            2. Normalize the embeddings for cosine similarity.
            3. Add the text, embeddings, and metadata into the ChromaDB collection.
            4. Build an approximate nearest neighbor (ANN) index with HNSWlib for fast search.
            5. Save both the index and a mapping file for user-specific lookup.

        Args:
            chunks (List[Dict[str, Any]]): A list of preprocessed text chunks containing:
                - "text" (str): Chunk text content.
                - "filename" (str): Original source file name.
                - "chunk_id" (str/int): Unique chunk identifier.

        Notes:
            - For large datasets, consider batching the `add()` calls for performance.
            - Metadata includes user_id to ensure search results are user-isolated.
        """

        embedding = []
        ids = []
        metadatas = []
        texts = []
        for ch in chunks:
            emb = self.embed_model.encode(ch['text']).astype(np.float32)
            emb = emb / (np.linalg.norm(emb) + 1e-12)
            uid = str(ch["chunk_id"])
            ids.append(uid)
            embedding.append(emb)
            texts.append(ch['text'])
            metadatas.append({
                "user_id": self.user_id,
                "filename": ch["filename"],
                "chunk_id": ch["chunk_id"]
            })
        self.collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=[emb.tolist() for emb in embedding])

        dim = len(embedding[0])
        index = hnswlib.Index(space="cosine",dim=dim)
        index.init_index(max_elements=(len(embedding)*2), ef_construction=200, M=16)
        index.add_items(np.array(embedding), ids= np.arange(len(embedding)))

        index.save_index(f"hnsw_index_{self.user_id}.bin")
        idx_to_uid = {str(i): str(ch["chunk_id"]) for i, ch in enumerate(chunks)}
        with open(f"mapping_{self.user_id}.json", "w") as f:
            json.dump(idx_to_uid, f)    
        self.logger.info(f"Stored {len(chunks)} chunks in Chroma + HNSW for user {self.user_id}")
    def run(self)-> None:
        """
        Execute the full indexing workflow for the current user.

        Steps:
            1. Load the user-specific chunks JSON file.
            2. Generate embeddings and index them in ChromaDB.
            3. Save an HNSWlib index for fast vector search.

        Side Effects:
            - Writes embeddings and metadata into the persistent ChromaDB store.
            - Creates local index and mapping files per user.
            - Logs progress and completion.
        """
        
        self.logger.info('Starting indexing for user {self.user_id} ...')
        chunks = self.load_chunks()
        if chunks:
            self.index_chunks(chunks)
        self.logger.info("Indexing finished for user {self.user_id}")