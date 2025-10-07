
from pathlib import Path
from src.core.utils import FileManager
import spacy

class EntityExtractor:
    """
    EntityExtractor (NER)
    ----------------------

    An NLP-powered module that enriches document layout blocks with
    **named entities** (NER: :contentReference[oaicite:0]{index=0})
    to provide semantic metadata for downstream retrieval in RAG pipelines.

    This class uses a pretrained :contentReference[oaicite:1]{index=1} model
    (default: `en_core_web_trf`) to detect entities like:
        - PERSON (people names)
        - ORG (organizations, companies, universities)
        - GPE (countries, cities)
        - DATE, TIME, MONEY, PERCENT, etc.

    It should be used **after** the LayoutExtractor and **before** chunking
    or vectorization, so each content block has structured semantic tags
    that can improve search relevance, filtering, and knowledge graph linking.

    Input format (from LayoutExtractor):
        [
            {"type": "text", "text": "Meeting with OpenAI in San Francisco", ...},
            ...
        ]

    Output format:
        [
            {
                "type": "text",
                "text": "Meeting with OpenAI in San Francisco",
                "entities": [
                    {"text": "OpenAI", "label": "ORG"},
                    {"text": "San Francisco", "label": "GPE"}
                ]
            },
            ...
        ]

    Example:
        >>> from pathlib import Path
        >>> from src.core.file_manager import FileManager
        >>> from src.modules.entity_extractor import EntityExtractor
        >>> fm = FileManager()
        >>> ex = EntityExtractor(fm, Path("config/config.yaml"))
        >>> blocks = [{"text": "Meeting with OpenAI in San Francisco"}]
        >>> enriched = ex.add_entities(blocks)
        >>> print(enriched[0]["entities"])

    Notes:
        - Default model is `en_core_web_trf` (high accuracy, transformer-based)
        - Heavier than `en_core_web_sm` but much better for real-world documents
        - This step enriches the semantic layer of each block for smarter retrieval
    """


    def __init__(self, file_manager:FileManager, config_path:Path):
        """
        Initialize the EntityExtractor and load the spaCy NER model.

        Args:
            file_manager (FileManager): Utility class to load YAML configs.
            config_path (Path): Path to the configuration file.
        """

        self.files = file_manager
        cfg = self.files.load_config(config_path)
        nlp_cfg = cfg.get("ner", {})
        model_name = nlp_cfg.get("model", "en_core_web_trf")

        self.nlp = spacy.load(model_name)
    

    def add_entities(self, blocks: list[dict]) -> list[dict]:
        """
        Detect named entities inside each block and append them to the block.

        Each block's `text` is processed through the spaCy NER pipeline.
        Detected entities are added as a new field `entities`.

        Args:
            blocks (list[dict]): List of layout blocks.

        Returns:
            list[dict]: Same blocks enriched with an `entities` field.

        Example:
            >>> blocks = [{"text": "Meeting with OpenAI in San Francisco"}]
            >>> result = ex.add_entities(blocks)
            >>> print(result[0]["entities"])
            # [{'text': 'OpenAI', 'label': 'ORG'}, {'text': 'San Francisco', 'label': 'GPE'}]
        """
        for b in blocks:
            doc = self.nlp(b["text"])
            ents = [{"text": e.text, "label": e.label_} for e in doc.ents]
            b["entities"] = ents
        return blocks