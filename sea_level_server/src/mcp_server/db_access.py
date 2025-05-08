"""
Database access module for SeaLevelMCP with the new schema.

This module provides functions to interact with the SQLite database,
including query execution and database metadata retrieval.
"""

import re
import time
import logging
import sqlite3
import pandas as pd
from typing import Dict, Any, Optional

from src.config import (
    DB_PATH, DB_CONNECTION_TIMEOUT, DB_QUERY_TIMEOUT, 
    DB_BUSY_TIMEOUT, DB_MAX_RETRIES
)
from src.mcp_server.retry_utils import retry, fallback, logger

class DBConnectionError(Exception):
    """Exception raised when database connection fails."""
    pass

class DBQueryError(Exception):
    """Exception raised when query execution fails."""
    pass

@fallback(default_return=lambda e: pd.DataFrame(), logger=logger)
@retry(exceptions=(sqlite3.OperationalError, sqlite3.DatabaseError), tries=DB_MAX_RETRIES, delay=1, backoff=2, logger=logger)
def execute_query(sql_query: str) -> pd.DataFrame:
    """Execute a SQL query and return results as a pandas DataFrame."""
    logger.info(f"Executing SQL query: {sql_query[:50]}...")
    
    # Validate the query for safety
    validate_query(sql_query)
    
    # Remove trailing semicolon if present
    sql_query = sql_query.rstrip(';')
    
    # Remove ANALYZE statement prefix which causes syntax errors
    sql_query = remove_analyze_keyword(sql_query)
    
    # Execute with timeout protection
    start_time = time.time()
    conn = None
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECTION_TIMEOUT)
        
        # Set a busy timeout to handle concurrent access
        conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT}")
        
        # Improve performance with these pragmas
        conn.execute("PRAGMA cache_size = 10000")  # Increase cache size
        conn.execute("PRAGMA temp_store = MEMORY")  # Store temp tables in memory
        conn.execute("PRAGMA journal_mode = WAL")   # Use Write-Ahead Logging
        
        # Start a reader transaction for better concurrency
        conn.execute("BEGIN")
        
        # Execute the query directly
        df = pd.read_sql_query(sql_query, conn)
        
        # Check if we exceeded timeout after query completes
        if time.time() - start_time > DB_QUERY_TIMEOUT:
            logger.warning(f"Query execution exceeded timeout: {sql_query}")
        
        # Log successful execution
        logger.info(f"Query executed successfully, returned {len(df)} rows in {time.time() - start_time:.2f}s")
        
        return df
    except sqlite3.Error as e:
        logger.error(f"SQLite error executing query: {str(e)}")
        raise DBQueryError(f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error executing query: {str(e)}")
        raise DBQueryError(f"Unexpected error: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {str(e)}")

def remove_analyze_keyword(sql_query: str) -> str:
    """
    Remove ANALYZE keyword from SQL queries.
    
    Args:
        sql_query: SQL query string to clean
        
    Returns:
        Cleaned SQL query string
    """
    # Handle when ANALYZE is at the beginning
    if sql_query.upper().strip().startswith('ANALYZE '):
        sql_query = sql_query.strip()[8:].strip()
    
    # Handle when ANALYZE is elsewhere in the query
    elif 'ANALYZE ' in sql_query.upper():
        sql_query = sql_query.upper().replace('ANALYZE ', '').lower()
    
    return sql_query

def validate_query(sql_query: str) -> None:
    """
    Validate a SQL query for safety.
    
    Args:
        sql_query: SQL query string to validate
        
    Raises:
        ValueError: If the query contains dangerous commands
    """
    sql_query_upper = sql_query.upper()
    
    # List of dangerous SQL commands that should not be allowed
    dangerous_commands = [
        'DROP ', 'DELETE ', 'UPDATE ', 'INSERT ', 'ALTER ', 'CREATE ', 
        'TRUNCATE ', 'GRANT ', 'REVOKE ', 'ATTACH ', 'DETACH '
    ]
    
    # Check for dangerous commands
    for cmd in dangerous_commands:
        if cmd in sql_query_upper:
            logger.warning(f"Dangerous SQL command detected: {sql_query}")
            raise ValueError(f"Dangerous SQL command detected: {cmd.strip()}")
    
    # Check for basic syntax problems that could cause errors
    syntax_issues = [
        # Check for missing spaces in common clauses
        (r'\bWHERE[A-Z]', 'Missing space after WHERE clause'),
        (r'\bFROM[A-Z]', 'Missing space after FROM clause'),
        (r'\bJOIN[A-Z]', 'Missing space after JOIN clause'),
        (r'\bGROUP BY[A-Z]', 'Missing space after GROUP BY clause'),
        (r'\bORDER BY[A-Z]', 'Missing space after ORDER BY clause'),
        
        # Check for potential subquery issues
        (r'\)\s*[A-Z]+\s*\(', 'Possible syntax error around parentheses')
    ]
    
    # Log warnings but don't block execution - our cleaning function will try to fix these
    for pattern, message in syntax_issues:
        if re.search(pattern, sql_query_upper):
            logger.warning(f"SQL syntax issue detected: {message} in query: {sql_query}")

def get_table_stats() -> Dict[str, Any]:
    """
    Get basic statistics about the database tables.
    
    Returns:
        Dictionary with table statistics
    """
    stats = {}
    conn = None
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECTION_TIMEOUT)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            
            # Skip SQLite internal tables
            if table_name.startswith('sqlite_'):
                continue
                
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            row_count = cursor.fetchone()[0]
            
            # Get column count
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns_info = cursor.fetchall()
            column_count = len(columns_info)
            
            # Get column names
            column_names = [col[1] for col in columns_info]
            
            # Store basic table stats
            stats[table_name] = {
                "rows": row_count,
                "columns": column_count,
                "column_names": column_names
            }
            
            # For sea level data, try to get date range
            if "Date" in column_names:
                try:
                    cursor.execute(f"SELECT MIN(Date), MAX(Date) FROM {table_name};")
                    min_date, max_date = cursor.fetchone()
                    stats[table_name]["date_range"] = (min_date, max_date)
                except sqlite3.Error as e:
                    logger.warning(f"Error getting date range: {str(e)}")
                    
            # Get regions covered
            if "Region" in column_names:
                try:
                    cursor.execute(f"SELECT DISTINCT Region FROM {table_name};")
                    regions = [row[0] for row in cursor.fetchall()]
                    stats[table_name]["regions"] = regions
                except sqlite3.Error as e:
                    logger.warning(f"Error getting regions: {str(e)}")
            
            # Get countries covered
            if "Country" in column_names:
                try:
                    cursor.execute(f"SELECT DISTINCT Country FROM {table_name};")
                    countries = [row[0] for row in cursor.fetchall()]
                    stats[table_name]["countries"] = countries
                except sqlite3.Error as e:
                    logger.warning(f"Error getting countries: {str(e)}")
        
        return stats
    except sqlite3.Error as e:
        logger.error(f"SQLite error getting table stats: {str(e)}")
        return {"error": f"Database error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error getting table stats: {str(e)}")
        return {"error": str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {str(e)}")