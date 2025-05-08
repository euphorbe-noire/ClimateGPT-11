# climate_server/config.py
"""
Configuration settings for Climate Server.

This file contains configuration settings for the Climate Server application.
Environment variables can be used to override default settings.
"""

import os
import sys

# Add base directory to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ----- SYSTEM SETTINGS -----
# Version information
SERVER_VERSION = "0.1.2"

# ----- DATABASE SETTINGS -----
# Database path
DB_PATH = os.environ.get("CLIMATE_SERVER_DB_PATH", os.path.join(BASE_DIR, "src/database/ClimateGPT.db"))

# Database connection settings
DB_CONNECTION_TIMEOUT = int(os.environ.get("CLIMATE_SERVER_DB_CONNECTION_TIMEOUT", "300"))  # 5 minutes
DB_QUERY_TIMEOUT = int(os.environ.get("CLIMATE_SERVER_DB_QUERY_TIMEOUT", "600"))  # 10 minutes
DB_BUSY_TIMEOUT = int(os.environ.get("CLIMATE_SERVER_DB_BUSY_TIMEOUT", "60000"))  # 60 seconds in milliseconds
DB_MAX_RETRIES = int(os.environ.get("CLIMATE_SERVER_DB_MAX_RETRIES", "3"))  # Number of times to retry database operations

# ----- API SETTINGS -----
# ClimateGPT API settings with fallbacks
PRIMARY_API_URL = os.environ.get(
    "CLIMATEGPT_API_URL", 
    "https://erasmus.ai/models/climategpt_8b_latest/v1/chat/completions"
)
BACKUP_API_URL = os.environ.get(
    "CLIMATEGPT_BACKUP_API_URL", 
    "https://backup.erasmus.ai/models/climategpt_8b_latest/v1/chat/completions"
)
# Use the first available API
CLIMATEGPT_API_URL = PRIMARY_API_URL

# API authentication 
CLIMATEGPT_USER = os.environ.get("CLIMATEGPT_USER", "ai")
CLIMATEGPT_PASSWORD = os.environ.get("CLIMATEGPT_PASSWORD", "4climate")
CLIMATEGPT_AUTH = (CLIMATEGPT_USER, CLIMATEGPT_PASSWORD)

# Circuit breaker settings for API health
API_CIRCUIT_BREAKER_THRESHOLD = int(os.environ.get("CLIMATEGPT_CIRCUIT_BREAKER_THRESHOLD", "5"))  # 5 failures
API_CIRCUIT_BREAKER_TIMEOUT = int(os.environ.get("CLIMATEGPT_CIRCUIT_BREAKER_TIMEOUT", "300"))  # 5 minutes

# ----- SERVER SETTINGS -----
# API server configuration
API_HOST = os.environ.get("CLIMATE_SERVER_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("CLIMATE_SERVER_API_PORT", "8000"))

# Timeout settings
QUERY_TIMEOUT = int(os.environ.get("CLIMATE_SERVER_QUERY_TIMEOUT", "600"))  # 10 minutes for API calls
CONNECT_TIMEOUT = int(os.environ.get("CLIMATE_SERVER_CONNECT_TIMEOUT", "120"))  # 2 minutes for connection

# ----- CACHE SETTINGS -----
# Cache controls
SQL_CACHE_SIZE = int(os.environ.get("CLIMATE_SERVER_SQL_CACHE_SIZE", "200"))
INSIGHT_CACHE_SIZE = int(os.environ.get("CLIMATE_SERVER_INSIGHT_CACHE_SIZE", "100"))
CACHE_TTL = int(os.environ.get("CLIMATE_SERVER_CACHE_TTL", "7200"))  # 2 hours in seconds
PERMANENT_CACHE_PATH = os.environ.get("CLIMATE_SERVER_PERMANENT_CACHE", os.path.join(BASE_DIR, "cache/query_cache.json"))

# ----- LOGGING SETTINGS -----
# Logging configuration
LOG_LEVEL = os.environ.get("CLIMATE_SERVER_LOG_LEVEL", "INFO")
LOG_FILE = os.environ.get("CLIMATE_SERVER_LOG_FILE", os.path.join(BASE_DIR, "logs/emissions_server.log"))
LOG_ROTATION = os.environ.get("CLIMATE_SERVER_LOG_ROTATION", "5MB")  # Rotate logs at 5MB

# ----- QUERY SETTINGS -----
# Query validation and display
MIN_QUERY_LENGTH = int(os.environ.get("CLIMATE_SERVER_MIN_QUERY_LENGTH", "10"))
MAX_QUERY_LENGTH = int(os.environ.get("CLIMATE_SERVER_MAX_QUERY_LENGTH", "500"))
MAX_DISPLAY_ROWS = int(os.environ.get("CLIMATE_SERVER_MAX_DISPLAY_ROWS", "15"))
MAX_RESULT_ROWS = int(os.environ.get("CLIMATE_SERVER_MAX_RESULT_ROWS", "200"))

# ----- ERROR TRACKING SETTINGS -----
ERROR_HISTORY_LIMIT = int(os.environ.get("CLIMATE_SERVER_ERROR_HISTORY_LIMIT", "20"))

# ----- DEFAULT RESPONSES -----
# These provide fallback responses when the API is unavailable
DEFAULT_CLIMATE_RESPONSES = {
    "greenhouse_gas": "Greenhouse gases include carbon dioxide (CO2), methane (CH4), nitrous oxide (N2O), and fluorinated gases. These gases trap heat in the Earth's atmosphere, contributing to global warming.",
    "global_warming": "Global warming is the long-term heating of Earth's climate system observed since the pre-industrial period due to human activities, primarily fossil fuel burning, which increases heat-trapping greenhouse gas levels in Earth's atmosphere.",
    "climate_change": "Climate change refers to long-term shifts in temperatures and weather patterns. These shifts may be natural, but since the 1800s, human activities have been the main driver of climate change, primarily due to the burning of fossil fuels like coal, oil, and gas, which produces heat-trapping gases."
}

