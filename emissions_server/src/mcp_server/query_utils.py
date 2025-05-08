"""
Utility functions for query processing in ClimateGPT.

This module provides utility functions for cleaning SQL queries,
parsing JSON, and validating query responses.
"""

import re
import time
import json
from typing import Dict, Any

def clean_json_response(content: str) -> str:
    """
    Clean and fix malformed JSON responses from ClimateGPT.
    This is applied to all responses by default.
    
    Args:
        content: Original JSON string from the API
        
    Returns:
        Cleaned JSON string that can be properly parsed
    """
    # Remove extra whitespace and tabs
    content = re.sub(r'\s+', ' ', content)
    
    # Fix common formatting issues
    content = content.replace(' : ', ': ')
    content = content.replace(' , ', ', ')
    content = content.replace('\t', '')
    
    # Fix missing commas between properties
    content = re.sub(r'}\s*{', '}, {', content)
    content = re.sub(r'"\s*{', '", {', content)
    
    # Fix trailing commas
    content = re.sub(r',\s*}', '}', content)
    content = re.sub(r',\s*]', ']', content)
    
    # Fix double commas
    content = re.sub(r',,', ',', content)
    
    # Fix common patterns specific to the ClimateGPT responses
    content = re.sub(r'"\s*,\s*"', '", "', content)
    
    return content

def clean_sql_query(sql: str) -> str:
    """
    Clean and fix SQL queries from ClimateGPT to ensure they work with our schema.
    
    Args:
        sql: Original SQL query string
        
    Returns:
        Cleaned SQL query
    """
    # Remove ANALYZE keyword if present (fixing a major issue)
    if sql.strip().upper().startswith('ANALYZE '):
        sql = sql.strip()[8:]
    
    # Fix spacing issues between year values and keywords
    sql = re.sub(r'(\d+)([A-Za-z])', r'\1 \2', sql)
    
    # Fix common mathematical issues - add spaces around operators
    sql = re.sub(r'(\w)\-(\w)', r'\1 - \2', sql)
    sql = re.sub(r'(\w)\+(\w)', r'\1 + \2', sql)
    sql = re.sub(r'(\w)\/(\w)', r'\1 / \2', sql)
    sql = re.sub(r'(\w)\*(\w)', r'\1 * \2', sql)
    
    # Fix any common errors in column references
    sql = sql.replace('Emissions.emissions', 'e.emissions')
    sql = sql.replace('Greenhouse_Gases.ghg_name', 'gg.ghg_name')
    sql = sql.replace('Geography.region_name', 'g.region_name')
    sql = sql.replace('Sectors.sector', 's.sector')
    
    # Fix other common mistakes found in the logs
    sql = sql.replace('g.Name', 'g.region_name')
    sql = sql.replace('Greenhouse_Gas_ID', 'ghg_id')
    sql = sql.replace('greenhouse_gas_id', 'ghg_id')
    sql = sql.replace('geography_id', 'geo_id')
    sql = sql.replace('T1.name', 'T1.ghg_name')
    sql = sql.replace('T2.name', 'T2.region_name')
    sql = sql.replace('g.name', 'g.region_name')
    sql = sql.replace('gg.name', 'gg.ghg_name')
    sql = sql.replace('s.name', 's.sector')
    
    # Fix improper alias references in subqueries
    sql = re.sub(r'from\s+\(\s*select.*?\)\s+as\s+(\w+)\s+where\s+\1\.', 
                lambda m: m.group(0).replace('e.', m.group(1) + '.'), 
                sql, flags=re.IGNORECASE | re.DOTALL)
    
    # Fix query syntax for the CAGR calculation error observed in logs
    if "total_emissions_2020 - total_emissions_2000" in sql:
        sql = sql.replace("SELECT (SELECT", "SELECT ((SELECT")
        sql = sql.replace(") / 20", ")) / 20")
    
    # Remove any trailing semicolons
    sql = sql.rstrip(';')
    
    return sql

def handle_error(error_message: str, start_time: float) -> Dict[str, Any]:
    """Create a standardized error response."""
    return {
        "type": "error",
        "error": error_message,
        "execution_time": time.time() - start_time
    }

def is_valid_classification(classification: Dict[str, Any]) -> bool:
    """
    Validate if a classification response is valid and can be cached.
    
    Args:
        classification: The classification response from ClimateGPT
        
    Returns:
        Boolean indicating if this response is valid
    """
    # Check if classification exists and has required fields
    if not classification:
        return False
    
    # Check if query_type exists and is valid
    query_type = classification.get("query_type")
    if not query_type or query_type not in ("general_knowledge", "database"):
        return False
    
    # For general knowledge queries, check if answer exists
    if query_type == "general_knowledge" and "answer" not in classification:
        return False
    
    # For database queries, check execution plan structure
    if query_type == "database":
        if "execution_plan" not in classification:
            return False
        
        # Check if steps exist and is a list
        steps = classification.get("execution_plan", {}).get("steps")
        if not steps or not isinstance(steps, list):
            return False
        
        # Check if steps have required fields
        for step in steps:
            if not isinstance(step, dict) or "sql" not in step:
                return False
    
    return True