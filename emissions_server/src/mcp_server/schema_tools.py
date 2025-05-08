"""
Database schema extraction module for ClimateMCP.

This module provides functions to access database schema information.
Since the schema is static, it's loaded once at initialization and
kept in memory for the lifetime of the application.
"""

import sqlite3
from typing import Dict, List, Any, Optional
from emissions_server.src.config import DB_PATH, DB_CONNECTION_TIMEOUT
from emissions_server.src.mcp_server.retry_utils import retry, fallback, logger

# Module-level variable to store the schema once loaded
_SCHEMA: Optional[Dict[str, Any]] = None
_RELATIONSHIPS: Optional[Dict[str, List[Dict[str, Any]]]] = None
_COLUMN_MAP: Optional[Dict[str, str]] = None  # Maps potential column typos to actual names

class DBSchemaError(Exception):
    """Exception raised when schema extraction fails."""
    pass

@fallback(default_return=lambda e: {"tables": [], "error": str(e)}, logger=logger)
@retry(exceptions=(sqlite3.OperationalError, sqlite3.DatabaseError), tries=3, delay=1, backoff=2, logger=logger)
def _load_schema() -> Dict[str, Any]:
    """
    Load the database schema once at initialization.
    This is an internal function that should not be called directly.
    Use get_schema() instead.
    
    Returns:
        Database schema dictionary
        
    Raises:
        DBSchemaError: If there's an issue retrieving the schema
    """
    global _SCHEMA, _RELATIONSHIPS, _COLUMN_MAP
    
    logger.info("Loading database schema (one-time initialization)")
    conn = None
    try:
        # Connect to database with timeout
        conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECTION_TIMEOUT)
        cursor = conn.cursor()

        # Get table names and schema definitions
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        schema = {"tables": []}
        relationships = {}
        column_map = {}

        for table_name, create_sql in tables:
            # Skip SQLite internal tables
            if table_name.startswith('sqlite_'):
                continue
                
            # Extract column names and types
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns_info = cursor.fetchall()

            columns = [
                {
                    "name": col[1],  # col[1] = column name
                    "type": col[2],  # col[2] = column type
                    "nullable": not col[3],  # col[3] = NOT NULL constraint (0 = nullable)
                    "pk": col[5] > 0  # col[5] = primary key (0 = not pk, >0 = pk position)
                } for col in columns_info
            ]

            # Get foreign key information
            cursor.execute(f"PRAGMA foreign_key_list({table_name});")
            fk_info = cursor.fetchall()
            
            foreign_keys = []
            for fk in fk_info:
                foreign_keys.append({
                    "from_column": fk[3],  # local column
                    "to_table": fk[2],  # referenced table
                    "to_column": fk[4]  # referenced column
                })

            schema["tables"].append({
                "name": table_name,
                "columns": columns,
                "foreign_keys": foreign_keys
            })
            
            # Store relationships for this table
            relationships[table_name] = foreign_keys
            
            # Build the column map for typo correction
            for column in columns:
                col_name = column["name"]
                # Add the standard column name
                column_map[f"{table_name}.{col_name}"] = f"{table_name}.{col_name}"
                # Add common abbreviations and aliases
                if table_name == "Greenhouse_Gases":
                    column_map[f"gg.{col_name}"] = f"gg.{col_name}"
                    column_map[f"g.{col_name}"] = f"gg.{col_name}"  # Common error
                    # Handle "name" vs "ghg_name" confusion
                    if col_name == "ghg_name":
                        column_map["gg.name"] = "gg.ghg_name"
                        column_map["g.name"] = "gg.ghg_name"
                elif table_name == "Geography":
                    column_map[f"g.{col_name}"] = f"g.{col_name}"
                    # Handle "name" vs "region_name" confusion
                    if col_name == "region_name":
                        column_map["g.name"] = "g.region_name"
                elif table_name == "Sectors":
                    column_map[f"s.{col_name}"] = f"s.{col_name}"
                    # Handle "name" vs "sector" confusion
                    if col_name == "sector":
                        column_map["s.name"] = "s.sector"
                elif table_name == "Emissions":
                    column_map[f"e.{col_name}"] = f"e.{col_name}"

        logger.info(f"Schema loaded with {len(schema['tables'])} tables")
        
        # Store the schema and relationships globally
        _SCHEMA = schema
        _RELATIONSHIPS = relationships
        _COLUMN_MAP = column_map
        
        return schema
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error loading schema: {str(e)}")
        raise DBSchemaError(f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error loading schema: {str(e)}")
        raise DBSchemaError(f"Unexpected error: {str(e)}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {str(e)}")

def get_schema() -> Dict[str, Any]:
    """
    Get the database schema. The schema is loaded once on first call
    and cached for subsequent calls.
    
    Returns:
        Dictionary with the database schema
    """
    global _SCHEMA
    
    # Load schema if not already loaded
    if _SCHEMA is None:
        _SCHEMA = _load_schema()
        
    return _SCHEMA

def get_table_relationships() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get table relationships based on foreign keys.
    
    Returns:
        Dictionary mapping table names to their relationships
    """
    global _RELATIONSHIPS
    
    # Make sure schema is loaded
    if _SCHEMA is None:
        _SCHEMA = _load_schema()
        
    return _RELATIONSHIPS

def get_table_columns(table_name: str) -> List[Dict[str, Any]]:
    """
    Get column information for a specific table.
    
    Args:
        table_name: Name of the table
        
    Returns:
        List of column definitions or empty list if table not found
    """
    schema = get_schema()
    
    for table in schema["tables"]:
        if table["name"].lower() == table_name.lower():
            return table["columns"]
            
    return []

def correct_column_reference(column_ref: str) -> str:
    """
    Correct common column reference errors in SQL queries.
    
    Args:
        column_ref: Column reference in format "table.column" or "alias.column"
        
    Returns:
        Corrected column reference
    """
    global _COLUMN_MAP
    
    # Make sure column map is loaded
    if _COLUMN_MAP is None:
        _load_schema()
    
    return _COLUMN_MAP.get(column_ref, column_ref)

def validate_sql_against_schema(sql_query: str) -> tuple[bool, str]:
    """
    Validate a SQL query against the actual database schema.
    
    Args:
        sql_query: SQL query to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    
    # This is a placeholder for more advanced validation
    # In a production system, you would want to parse the SQL and check
    # all tables and columns against the schema
    
    # For now, just check for some common issues
    sql_query_upper = sql_query.upper()
    
    # Basic syntax check
    if 'SELECT' not in sql_query_upper:
        return False, "Query must be a SELECT statement"
    
    # Check for tables that don't exist
    schema = get_schema()
    table_names = [table["name"] for table in schema["tables"]]
    
    # Very basic check - could be improved with SQL parsing
    for word in sql_query_upper.split():
        if word in ['FROM', 'JOIN'] and word != sql_query_upper.split()[-1]:
            next_word_idx = sql_query_upper.split().index(word) + 1
            if next_word_idx < len(sql_query_upper.split()):
                potential_table = sql_query_upper.split()[next_word_idx]
                # Strip any non-alphanumeric chars
                potential_table = ''.join(c for c in potential_table if c.isalnum())
                if (potential_table not in table_names and 
                    potential_table not in ['E', 'G', 'GG', 'S', 'F']):
                    return False, f"Table '{potential_table}' not found in schema"
    
    return True, ""