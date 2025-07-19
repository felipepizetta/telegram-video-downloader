import logging
import os
from datetime import datetime

class EmojiSafeFileHandler(logging.FileHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            msg = record.msg.encode('ascii', 'ignore').decode('ascii')
            record.msg = msg
            super().emit(record)

def setup_logger():
    os.makedirs('logs', exist_ok=True)
    
    logger = logging.getLogger('telegram_downloader')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler with UTF-8 encoding
    log_file = f"logs/downloader_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = EmojiSafeFileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Console handler with emoji fallback
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger