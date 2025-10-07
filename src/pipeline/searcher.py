
import json
from pathlib import Path
from typing import Any, List, Dict
from sentence_transformers import SentenceTransformer
from chromadb import PersistentClient
from src.core.utils import FileManager
import hnswlib
import numpy as np


class Searcher:
    """
    Searcher — Semantic Retrieval Component for a Multi-User RAG Pipeline.

    This class performs semantic similarity search over document chunks stored
    in ChromaDB and indexed with HNSWlib. Each user’s data is isolated through
    user-specific index and metadata filtering.

    Responsibilities:
        1. Encode natural-language queries into dense embeddings.
        2. Retrieve the most semantically similar chunks using an ANN index.
        3. Return results restricted to the current user's data.
    """

    def __init__(self, config:dict, file_manager:FileManager, logger, user_id:str)-> None:
        """
        Initialize the Searcher instance for a given user.

        This method sets up the embedding model, ChromaDB connection, and
        the HNSWlib index dedicated to this user's data.

        Args:
            config (dict): Configuration dictionary (typically from config.yaml).
                Must include:
                    - paths.vector_db: Directory for the ChromaDB store.
                    - models.embedding_model: SentenceTransformer model name.
            file_manager (FileManager): Utility for file and configuration management.
            logger (Logger): Logger instance (e.g., Loguru) for progress tracking.
            user_id (str): Unique identifier of the user, ensuring data isolation.
        """
        self.logger = logger
        self.files= file_manager
        self.user_id = user_id

        paths = config['paths']
        self.vector_db_dir = Path(paths["vector_db"])
        self.embed_model = SentenceTransformer(config['models']["embedding_model"])
        self.client=PersistentClient(path=str(self.vector_db_dir))
        self.collection=self.client.get_or_create_collection("documents")
        dim = self.embed_model.get_sentence_embedding_dimension()
        self.index = hnswlib.Index(space="cosine", dim=dim)
        self.index.load_index(f"hnsw_index_{self.user_id}.bin")

        self.logger.info("Searcher initialized for user {user_id}")
    

    def search (self, query:str, top_k:int=20)-> List[Dict[str, Any]]:
        """
        Perform a semantic similarity search for a given user query.

        Workflow:
            1. Encode the natural-language query into a normalized vector.
            2. Use the HNSWlib index to perform approximate nearest-neighbor search.
            3. Retrieve the corresponding documents and metadata from ChromaDB.
            4. Return results restricted to the current user's data.

        Args:
            query (str): The natural-language question or information need.
            top_k (int): Number of top matches to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: List of result dictionaries sorted by similarity, e.g.:
                [
                    {
                        "id": str,
                        "text": str,
                        "score": float,
                        "metadata": {
                            "user_id": str,
                            "filename": str,
                            "chunk_id": int
                        }
                    },
                    ...
                ]
        """
  
        query_emb = self.embed_model.encode(query).astype(np.float32)
        query_emb = query_emb / (np.linalg.norm(query_emb) + 1e-12)
        with open(f"mapping_{self.user_id}.json") as f:
            idx_to_uid = json.load(f)


        self.index.set_ef(top_k * 10)
        labels, distances = self.index.knn_query(query_emb, k=top_k)
        ids = [int(idx_to_uid[str(i)]) for i in labels[0]]
        scores = distances[0].tolist()

        results = self.collection.get(ids=[str(i) for i in ids])
        matched = []
        for i in range(len(results["ids"])):
            matched.append({
                "id": int(results["ids"][i]),
                "text": results["documents"][i],
                "score": scores[i],
                "metadata": results["metadatas"][i]
            })

        self.logger.info(f"Found {len(matched)} results for: {query}")
        return matched

    
    def run (self, query:str)-> None:
        """
        Run an interactive semantic search and print formatted results.

        This helper method is mainly used for debugging or command-line inspection.
        It performs a semantic search and prints results in a readable format.

        Args:
            query (str): The user's query or question.

        Returns:
            None
        """
        self.logger.info(f"Searching for: {query}")
        results = self.search(query)
        for i, res in enumerate(results):
            print(f"\nResult {i+1}:")
            print(f"File: {res['metadata']['filename']}")
            print(f"Score: {res['score']:.4f}")
            print(f"Text: {res['text'][:200]}...")
        self.logger.info(" Search finished.")

        