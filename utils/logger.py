import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

class EmojiSafeFileHandler(logging.FileHandler):
    """File handler that handles UnicodeEncodeError by replacing problematic characters."""
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            msg = record.msg.encode('ascii', 'replace').decode('ascii')
            record.msg = msg
            super().emit(record)

def setup_logger(name):
    """Set up a logger with file and console handlers."""
    os.makedirs('logs', exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # Change to DEBUG for more details during troubleshooting
    
    # Avoid duplicate handlers if logger is reused
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler with rotation (max 5MB, keep 3 backups)
    log_file = f"logs/downloader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger