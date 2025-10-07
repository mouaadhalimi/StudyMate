
from typing import Dict, List
from sentence_transformers import CrossEncoder

class Reranker:
    """
    Reranker — Re-rank retrieved documents using a cross-encoder model.

    This class uses a fine-tuned transformer model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`)
    to compute relevance scores between a query and a set of candidate documents.
    It produces more accurate ranking than simple embedding-based similarity,
    at the cost of higher computational overhead.

    Typical usage:
        ```python
        reranker = Reranker()
        reranked_docs = reranker.rerank(query="what is quantum computing?", docs=docs, top_k=5)
        ```
    """
    def __init__(self, model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", logger=None)-> None:
        """
        Initialize the reranker with a given cross-encoder model.

        Args:
            model_name (str): Name or path of the pretrained CrossEncoder model.
                              Defaults to `"cross-encoder/ms-marco-MiniLM-L-6-v2"`.
            logger (Optional[Logger]): Optional logger for status messages.
        """
        self.logger = logger
        self.reranker = CrossEncoder(model_name)
        if self.logger:
            self.logger.info(f"Reranker initialized with {model_name}")

    def rerank(self, query: str, docs: List[Dict], top_k: int = 3) -> List[Dict]:
        """
        Re-rank a list of retrieved documents based on semantic relevance to a query.

        Args:
            query (str): The search query or user question.
            docs (List[Dict]): A list of candidate documents. Each document should be a dictionary containing:
                - "text" (str): The document or passage text.
                - Optionally "id", "score", or "metadata" keys.
            top_k (int): Number of top results to return after reranking (default: 3).

        Returns:
            List[Dict]: A list of the top-k documents, sorted by descending "rerank_score".
                        Each dictionary will include a new key:
                            - "rerank_score" (float): The cross-encoder relevance score.

        Example:
            ```python
            query = "What is photosynthesis?"
            docs = [{"id": 1, "text": "Photosynthesis converts light energy into chemical energy."}, ...]
            top_docs = reranker.rerank(query, docs, top_k=5)
            ```
        """
        if not docs:
            return []

  
        pairs = [(query, d["text"]) for d in docs]

       
        scores = self.reranker.predict(pairs)


        for i, d in enumerate(docs):
            d["rerank_score"] = float(scores[i])

      
        reranked = sorted(docs, key=lambda x: x["rerank_score"], reverse=True)

        if self.logger:
            self.logger.info(f"Reranked {len(docs)} docs for query '{query}'")

        return reranked[:top_k]
