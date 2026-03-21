import logging
import os
from datetime import datetime
from config import Config

def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """Настроить логгер"""
    os.makedirs(Config.LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # File handler
    file_handler = logging.FileHandler(
        f"{Config.LOG_DIR}/{name}_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Global logger
logger = setup_logger('tg_manager')