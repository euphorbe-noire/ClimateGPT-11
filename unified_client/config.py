# climate_client/config.py
"""
Configuration settings for Climate Client.

This file contains configuration settings for the Climate Client application.
Environment variables can be used to override default settings.
Server routing is configured through the server_registry.json file.
"""

import os
import sys

# Add base directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ----- REGISTRY SETTINGS -----
# Path to server registry file
REGISTRY_PATH = os.path.join(BASE_DIR, "server_registry.json")

# ----- CLI SETTINGS -----
CLI_API_URL = os.environ.get("CLIMATE_CLIENT_API_URL", "http://127.0.0.1:8000")
CLI_TABLE_ROW_LIMIT = int(os.environ.get("CLIMATE_CLIENT_TABLE_ROW_LIMIT", "15"))
CLI_REQUEST_TIMEOUT = int(os.environ.get("CLIMATE_CLIENT_REQUEST_TIMEOUT", "600"))  # 10 minutes
CLI_BANNER_STYLE = os.environ.get("CLIMATE_CLIENT_BANNER_STYLE", "green")
CLI_MAX_RETRIES = int(os.environ.get("CLIMATE_CLIENT_MAX_RETRIES", "5"))
CLI_RETRY_DELAY = int(os.environ.get("CLIMATE_CLIENT_RETRY_DELAY", "5"))

# ----- CLIMATEGPT API SETTINGS -----
# ClimateGPT API configuration for general knowledge questions
CLIMATEGPT_API_URL = os.environ.get(
    "CLIMATEGPT_API_URL", 
    "https://erasmus.ai/models/climategpt_8b_latest/v1/chat/completions"
)
CLIMATEGPT_USER = os.environ.get("CLIMATEGPT_USER", "ai")
CLIMATEGPT_PASSWORD = os.environ.get("CLIMATEGPT_PASSWORD", "4climate")
CLIMATEGPT_TIMEOUT = int(os.environ.get("CLIMATEGPT_TIMEOUT", "120"))  # 2 minutes
CLIMATEGPT_MAX_TOKENS = int(os.environ.get("CLIMATEGPT_MAX_TOKENS", "2000"))
CLIMATEGPT_TEMPERATURE = float(os.environ.get("CLIMATEGPT_TEMPERATURE", "0.7"))

# ---- Logging Settings ----
LOG_LEVEL = os.environ.get("CLIMATE_CLIENT_LOG_LEVEL", "INFO")
LOG_FILE = os.environ.get("CLIMATE_CLIENT_LOG_FILE", os.path.join(BASE_DIR, "../unified_client/logs/climate_client.log"))