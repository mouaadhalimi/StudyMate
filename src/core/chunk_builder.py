
from typing import List, Dict, Optional
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from semantic_text_splitter import TextSplitter
from typing import List, Dict


class ChunkBuilder:
    """
    Handles the construction of clean, semantically coherent text chunks
    from preprocessed document blocks.

    The `ChunkBuilder` combines and cleans small text segments, removes near-duplicates,
    and then splits long text into manageable chunks suitable for embedding and retrieval.
    """

    def __init__(self, tokenizer_model: str, chunk_size:int=500, logger=None):
        """
        Initialize the chunk builder.

        Args:
            tokenizer_model (str): Name of the tokenizer model (for compatibility/future use).
            chunk_size (int): Desired chunk size in characters.
            logger: Optional logger instance for debug and info messages.
        """
        self.logger = logger
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", " ", ""],  
        )

    

    @staticmethod
    def _clean_text(text:str)->str:
        """
        Normalize and clean text by removing unwanted breaks and extra spaces.

        Args:
            text (str): Raw input text.

        Returns:
            str: Cleaned version of the text.
        """
        text = re.sub(r"-\n", "", text)
        text = re.sub(r"\n+", "\n", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip() 
    
    def remove_near_duplicates(self, blocks:List[Dict], windows:int = 10)->List[Dict]:
        """
        Remove near-duplicate blocks based on local textual similarity.

        This operates in a sliding window to avoid repeated fragments
        (common in OCRed documents or templated forms).

        Args:
            blocks (List[Dict]): List of block dictionaries with at least a `"text"` key.
            windows (int): Number of recent blocks to consider for duplicate comparison.

        Returns:
            List[Dict]: Deduplicated list of blocks.
        """
        seen: List[str] = []
        cleaned: List[Dict] = []
        for b in blocks:
            txt = re.sub(r"\s+", " ", b["text"]).strip().lower()
            if txt in seen[-windows:]:
                if self.logger:
                    self.logger.debug(f"Duplicate removed (local window): {txt[:50]}...")
                continue
            cleaned.append(b)
            seen.append(txt)
        return cleaned

    def merge_small_blocks(self, blocks: List[Dict], min_words:int=20) ->List[Dict]:
        """
        Merge small consecutive text blocks into larger coherent segments.

        This prevents short fragments from being treated as standalone chunks
        (which can fragment meaning and hurt embedding quality).

        Args:
            blocks (List[Dict]): List of layout/text blocks (each with 'text' and optionally 'page').
            min_words (int): Minimum word count threshold below which blocks are merged.

        Returns:
            List[Dict]: List of merged blocks.
        """
        merged: List[Dict] = []
        buffer: Optional[Dict] = None
        
        for b in blocks:
            txt = b["text"].strip()
            page = b.get("page", 0)

            word_count = len(txt.split())

            if word_count < min_words:
                if buffer is None:
                    buffer = b.copy()
                
                else:
                    if buffer.get("page", 0) == page:
                        buffer["text"]+= " "+txt
                        
                    else:
                        merged.append(buffer)
                        buffer = b.copy()
        
            else:
                if buffer:
                    if buffer.get("page", 0)==page:
                        buffer["text"] += " "+txt
                       
                        merged.append(buffer)
                        buffer = None
                        
                    else:
                        merged.append(buffer)
                        merged.append(b)
                        buffer = None
                else:
                    merged.append(b)
        if buffer:
            merged.append(buffer)
        return merged
    def split_text(self, text:str) -> list[str]:
        """
        Split a long text into smaller, semantically coherent chunks.

        Uses the `RecursiveCharacterTextSplitter` to intelligently split text
        at natural language boundaries (paragraphs, sentences, spaces).

        Args:
            text (str): The text to split.

        Returns:
            List[str]: List of chunk strings.
        """
 
        return self.splitter.split_text(text)
 
