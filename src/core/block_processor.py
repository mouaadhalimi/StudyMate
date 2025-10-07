
from collections import defaultdict
import re
from typing import List, Dict, Any, Set, Optional

class BlockProcessor:
    """
    A utility class for processing document layout blocks (e.g., OCR or PDF elements).

    The `BlockProcessor` primarily removes recurring headers and footers
    from multi-page documents based on frequency and positional heuristics.
    """

    def __init__(self, logger:Optional[Any] = None):
        """
        Initialize the BlockProcessor.

        Args:
            logger: Optional logger instance for debug and info logging.
        """
        self.logger = logger
    
    @staticmethod
    def _norm_text(s:str)-> str:
        """
        Normalize text by collapsing whitespace, trimming, and lowercasing.

        Args:
            s (str): Input string to normalize.

        Returns:
            str: Normalized, lowercased version of the text.
        """
        s = s or ""
        s = re.sub(r"\s+", " ", s).strip()
        return s.lower()
    
    def remove_page_headers_footers(
            self,
            blocks: list[dict],
            min_repeat: int = 3,
            y_tolerance: int = 20,
            max_header_words: int = 12,
            max_header_chars: int=80) -> List[Dict[str, Any]]:
        """
        Remove recurring header and footer blocks from a list of layout blocks.

        The algorithm detects repeated text elements (short text appearing on multiple pages)
        whose vertical positions (Y-coordinates) vary only slightly. Such patterns
        are treated as headers or footers and removed.

        Args:
            blocks (List[Dict[str, Any]]): List of layout blocks, each containing fields like:
                - `text`: The block's textual content.
                - `y`: Vertical position (used to group repeated lines).
                - `page`: Page number for identifying repeated occurrences.
                - `type`: Optional classification label (e.g. "page-header", "page-footer").
            min_repeat (int): Minimum number of pages where a text must repeat to be considered a header/footer.
            y_tolerance (int): Maximum allowed variation in Y position for repeated text.
            max_header_words (int): Skip texts longer than this word count (too long for headers).
            max_header_chars (int): Skip texts longer than this character count (too long for headers).

        Returns:
            List[Dict[str, Any]]: The cleaned list of blocks with repetitive headers and footers removed.
        """
        
        stats = defaultdict(lambda:{"pages": set(), "ys": []})
        for b in blocks:
            txt = self._norm_text(b.get("text", ""))
            if not txt:
                continue
            if len(txt) > max_header_chars or len(txt.split()) > max_header_words:
                continue

            page = b.get("page", 0)
            y = int(b.get("y", 0))
            stats[txt]["pages"].add(page)
            stats[txt]["ys"].append(y)
        texts_to_drop = set()
        for txt, info in stats.items():
            if len(info["pages"])< min_repeat:
                continue
            ys = sorted(info["ys"])
            if ys[-1] - ys[0] <= y_tolerance:
                texts_to_drop.add(txt)
        cleaned = []
        current_page = None
        seen_header_this_page = False
        for b in blocks:
            page = b.get("page", 0)
            if page != current_page:
                current_page = page
                seen_header_this_page = False
            btype = (b.get("type") or "").lower()
            txt_norm = self._norm_text(b.get("text", ""))
            if btype =="page-footer":
                if self.logger:
                    self.logger.debug(f"drop footer (typef) p{page}: {txt_norm[:60]}")
            if btype == "page-header":
                if seen_header_this_page:
           
                    if self.logger:
                        self.logger.debug(f"drop duplicate header p{page}: {txt_norm[:60]}")
                    continue
                seen_header_this_page = True
           
                if self.logger:
                    self.logger.debug(f"drop header (typed) p{page}: {txt_norm[:60]}")
                continue
            if txt_norm in texts_to_drop:
                if self.logger:
                    self.logger.debug(f"drop repeated header/footer-like p{page}: {txt_norm[:60]}")
                continue
            cleaned.append(b)

        if self.logger:
            self.logger.info(f"Headers/footers cleanup: {len(blocks)} -> {len(cleaned)} blocks")

        return cleaned
   

 