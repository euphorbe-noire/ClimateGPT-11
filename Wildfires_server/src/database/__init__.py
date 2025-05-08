"""
Database access module for Climate Server.

This module provides database connection and query functionality.
"""

from mcp_server.db_access import execute_query, get_table_stats
from mcp_server.schema_tools import get_schema, get_table_columns

__all__ = ["execute_query", "get_table_stats", "get_schema", "get_table_columns"]