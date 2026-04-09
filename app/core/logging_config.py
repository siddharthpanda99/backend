import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys
from pathlib import Path

class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    Subclass of TimedRotatingFileHandler that handles PermissionError on Windows
    when multiple processes/threads are accessing the log file.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # On Windows, if the file is locked, we just skip rotation for now
            # and continue logging to the current file.
            pass

def setup_logging(log_file: str = "logs/server.log"):
    """
    Configures centralized logging with hourly/daily rotation.
    Format: server.log.YYYY-MM-DD_HH
    """
    log_path = Path(log_file)
    os.makedirs(log_path.parent, exist_ok=True)
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Using SafeTimedRotatingFileHandler for hourly ('H') and daily intervals. 
    handler = SafeTimedRotatingFileHandler(
        log_file, 
        when='H', 
        interval=1, 
        backupCount=72, 
        encoding='utf-8',
        atTime=None
    )
    # The suffix property determines the filename rotation suffix.
    handler.suffix = "%Y-%m-%d_%H"
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            handler,
            logging.StreamHandler(sys.stdout)
        ],
        force=True # Ensure we override any existing basicConfig
    )
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.info(f"💾 [LOGGER] Persistent hourly rotating logs enabled at {log_file}")

if __name__ == "__main__":
    setup_logging()
