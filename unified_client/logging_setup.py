"""
Logging setup for Climate Client.

This module provides a central logging configuration for the client.
"""

import logging
import os
import sys

from config import LOG_LEVEL, LOG_FILE

def setup_logging(logger_name='climate_client'):
    """
    Set up logging configuration for the client.
    
    Args:
        logger_name: Name of the logger to configure
        
    Returns:
        Configured logger instance
    """
    # Parse log level string to logging constant
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create handlers
    # Create directory for log file if it doesn't exist
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Create formatters and add to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger