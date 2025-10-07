
from typing import Literal
from loguru import logger as logguru_logger
from pathlib import Path


class LoggerManager:
    """
    Centralized logger manager for the RAG pipeline.

    This class sets up a consistent logging configuration across all modules.
    It ensures that logs are written both to the console and to a rotating log file.

    Features:
        - Creates the log directory if it doesn't exist.
        - Uses Loguru for structured, colorful, and thread-safe logging.
        - Writes logs to a file with rotation and retention policies.
    """

    def __init__(self, log_dir: Path, level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"):
        """
        Initialize and configure the logger.

        Args:
            log_dir (Path): Directory path where log files will be stored.
            level (Literal): Logging verbosity level (default: "INFO").
        """
        self.log_dir = log_dir
        self.level = level.upper()

        self.log_dir.mkdir(parents=True, exist_ok=True)

        logguru_logger.remove()

        logfile = self.log_dir / "logging_project.log"
        logguru_logger.add(
            logfile,
            rotation="1MB",  
            retention=5,
            level=self.level,
            enqueue=True
        )

        logguru_logger.add(
            lambda msg: print(msg, end=""),
            level=self.level
        )
        self.logger = logguru_logger
        self.logger.info(f"Logger initialized at {logfile}")

    def get_logger(self):
        """
        Retrieve the configured Loguru logger.

        Returns:
            loguru.Logger: The global, preconfigured logger instance.
        """
        return self.logger
