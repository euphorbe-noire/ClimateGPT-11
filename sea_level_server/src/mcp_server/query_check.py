"""
Input validation and sanitization module for ClimateMCP.

This module provides functions to validate and clean user input before processing,
leveraging ClimateGPT for query validation when appropriate.
"""

import re
import json
import logging
import requests
from typing import Tuple, Optional, Dict, Any

from src.config import (
    MIN_QUERY_LENGTH, MAX_QUERY_LENGTH, 
    CLIMATEGPT_API_URL, CLIMATEGPT_AUTH
)

# Set up logging
logger = logging.getLogger('query_check')

# Basic SQL injection patterns to check for quick rejection
SQL_INJECTION_PATTERNS = [
    r';\s*--',              # SQL comment after semicolon
    r';\s*\/\*.*?\*\/',     # SQL block comment after semicolon
    r'UNION\s+SELECT',      # UNION SELECT statement
    r'INSERT\s+INTO',       # INSERT statement
    r'UPDATE\s+.*?SET',     # UPDATE statement
    r'DELETE\s+FROM',       # DELETE statement
    r'DROP\s+TABLE',        # DROP TABLE statement
    r'ALTER\s+TABLE',       # ALTER TABLE statement
    r'EXEC\s*\(',           # EXEC statement
    r'EXECUTE\s*\(',        # EXECUTE statement
]

def check_query(prompt: str) -> Tuple[bool, Optional[str]]:
    """
    Validates a user prompt before processing it.
    
    This function performs basic validation locally and then
    may use the LLM for more sophisticated validation.
    
    Args:
        prompt: The natural language query from the user
        
    Returns:
        Tuple containing:
            - Boolean indicating if the prompt is valid (True) or invalid (False)
            - Error message if invalid, None otherwise
    """
    # Check for empty or whitespace-only prompts
    if not prompt or prompt.strip() == "":
        return False, "Empty query. Please provide a specific question about climate data."
    
    # Clean the text for validation
    cleaned_prompt = clean_text(prompt)
    
    # Check minimum length (too short prompts are often ambiguous)
    if len(cleaned_prompt) < MIN_QUERY_LENGTH:
        return False, f"Query is too short. Please provide more details about what climate data you're looking for (at least {MIN_QUERY_LENGTH} characters)."
    
    # Check for obvious SQL injection attempts
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, cleaned_prompt, re.IGNORECASE):
            return False, "Invalid query pattern detected. Please rephrase your question in natural language."
    
    # Maximum length check to prevent unreasonably large prompts
    if len(cleaned_prompt) > MAX_QUERY_LENGTH:
        return False, f"Query is too long. Please make your question more concise (under {MAX_QUERY_LENGTH} characters)."
    
    # For queries that pass basic validation, we trust the LLM
    # to handle determining relevance and further validation
    return True, None

def validate_with_llm(query: str) -> Tuple[bool, Optional[str]]:
    """
    Use ClimateGPT to validate if a query is relevant and appropriate.
    
    This is an optional, more sophisticated validation that can be used 
    when basic validation passes but we want additional checks.
    
    Args:
        query: The user query to validate
        
    Returns:
        Tuple with validation result and error message if any
    """
    prompt = f"""
Evaluate if this query is related to climate data or climate change:

Query: "{query}"

Respond with a JSON object with these fields:
- "is_valid": true/false indicating if the query is relevant to climate data
- "reason": brief explanation of your decision
- "suggestion": an alternative query if the original one is not valid

Only respond with valid JSON.
"""
    
    try:
        # Make a request to ClimateGPT with a short timeout
        payload = {
            "model": "/cache/climategpt_8b_latest",
            "messages": [
                {"role": "system", "content": "You validate climate data queries for relevance and appropriateness."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        response = requests.post(
            CLIMATEGPT_API_URL, 
            json=payload, 
            auth=CLIMATEGPT_AUTH,
            timeout=5  # Short timeout since this is optional validation
        )
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        validation_result = json.loads(content)
        
        if validation_result.get("is_valid", True):
            return True, None
        else:
            message = f"This query doesn't appear to be related to climate data. {validation_result.get('reason', '')}"
            if validation_result.get("suggestion"):
                message += f" Try instead: \"{validation_result.get('suggestion')}\""
            return False, message
            
    except Exception as e:
        # If LLM validation fails, we default to allowing the query
        # (since it already passed basic validation)
        logger.warning(f"LLM validation failed: {str(e)}")
        return True, None

def clean_text(prompt: str) -> str:
    """
    Sanitizes a user prompt to remove potential problematic characters or patterns.
    
    Args:
        prompt: The user query to sanitize
        
    Returns:
        Sanitized prompt string with problematic elements removed
    """
    # Convert to string if not already
    prompt = str(prompt)
    
    # Remove any SQL comment patterns
    prompt = re.sub(r'--.*', '', prompt)
    prompt = re.sub(r'/\*.*?\*/', '', prompt, flags=re.DOTALL)
    
    # Remove excessive whitespace
    prompt = re.sub(r'\s+', ' ', prompt).strip()
    
    # Remove any control characters
    prompt = re.sub(r'[\x00-\x1F\x7F]', '', prompt)
    
    # Normalize Unicode characters (convert lookalikes to standard ASCII)
    # This helps prevent Unicode-based SQL injection attempts
    replacements = {
        '–': '-',   # En dash
        '—': '-',   # Em dash
        ''': "'",   # Curly quote
        ''': "'",   # Curly quote
        '"': '"',   # Curly double quote
        '"': '"',   # Curly double quote
        '«': '"',   # Guillemet
        '»': '"',   # Guillemet
    }
    
    for old, new in replacements.items():
        prompt = prompt.replace(old, new)
    
    return prompt

def sanitize_sql_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize parameters that will be used in SQL queries.
    
    Args:
        params: Dictionary of parameter names and values
        
    Returns:
        Dictionary with sanitized values
    """
    sanitized = {}
    
    for key, value in params.items():
        if isinstance(value, str):
            # Clean string values
            sanitized[key] = clean_text(value)
        else:
            # Non-string values are passed through unchanged
            sanitized[key] = value
    
    return sanitized