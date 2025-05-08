"""
Logging setup for Climate Server.

This module provides a central logging configuration for all server components.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
import sys

# Import config from absolute path
import src.config as config

def setup_logging(logger_name='climate_server'):
    """
    Set up logging configuration for the server.
    
    Args:
        logger_name: Name of the logger to configure
        
    Returns:
        Configured logger instance
    """
    # Parse log level string to logging constant
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create handlers
    # Parse rotation size (e.g., "5MB" to bytes)
    rotation_size = config.LOG_ROTATION
    if rotation_size.endswith('MB'):
        max_bytes = int(rotation_size[:-2]) * 1024 * 1024
    elif rotation_size.endswith('KB'):
        max_bytes = int(rotation_size[:-2]) * 1024
    else:
        max_bytes = 5 * 1024 * 1024  # Default to 5MB
    
    # Create directory for log file if it doesn't exist
    log_dir = os.path.dirname(config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=max_bytes,
        backupCount=3
    )
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