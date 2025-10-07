
from pathlib import Path
import json
import yaml

class FileManager:
    """
        A utility class to handle common file operations like:
        - loading YAML config files
        - saving and loading JSON data
        - ensuring folders exist

        This centralizes all file-related logic for the pipeline.
    """


    def __init__(self, logger=None):
        """
        Initialize the FileManager.

        Args:
            logger (optional): A Loguru logger instance for optional logging.
                               If provided, all actions will be logged.
        """

        self.logger = logger
    



    def ensure_dir(self, path:Path):
        """
        Ensure that a directory exists at the given path.

        If the directory does not exist, it will be created (including parent folders).

        Args:
            path (Path): The path of the directory to ensure exists.
        """
        path.mkdir(parents=True, exist_ok=True)
        if self.logger:
            self.logger.info(f'Ensured directory : {path}') 
    



    def load_config(self, path:Path) -> dict:

        """
        Load a YAML configuration file from the specified path.

        Args:
            path (Path): Path to the YAML config file.

        Returns:
            dict: Parsed configuration as a Python dictionary.

        Raises:
            FileNotFoundError: If the config file does not exist.
            yaml.YAMLError: If the file is not a valid YAML format.
        """

        if not path.exists():
            raise FileNotFoundError(f'Config file not found at {path}')
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if self.logger:
            self.logger.info(f"Loaded config from: {path}")
        return config
    



    def save_json(self, data, path:Path):
        """
        Save a Python object as a JSON file (UTF-8 encoded + pretty printed).

        Args:
            data (Any): Any JSON-serializable Python object to save.
            path (Path): Path where the JSON file will be saved.

        Note:
            Creates the parent directory if it does not exist.
        """

        self.ensure_dir(path.parent)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False, indent=2)
        if self.logger:
            self.logger.info(f"Saved Json to: {path}")
    



    
    def load_json(self, path:Path):
        """
        Load and parse data from a JSON file.

        Args:
            path (Path): Path to the JSON file.

        Returns:
            Any: Parsed JSON content as a Python object.

        Raises:
            FileNotFoundError: If the JSON file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        if not path.exists():
            raise FileNotFoundError(f'JSON file not found at {path}')
        with open (path, 'r', encoding='utf-8') as f:
            data=json.load(f)
        if self.logger:
            self.logger.info(f'Loaded JSON from: {path}')
        return data
