"""
Insight generation module for ClimateGPT.

This module generates insights from query results using the ClimateGPT model.
"""

import time
import json
import requests
import logging
from typing import Dict, Any

from src.config import CLIMATEGPT_API_URL, CLIMATEGPT_AUTH
from src.mcp_server.cache_utils import SimpleCache
from src.mcp_server.query_utils import clean_json_response

# Set up logging
logger = logging.getLogger('insight_generator')

# Initialize cache
insight_cache = SimpleCache(max_size=50, ttl=3600)

def generate_insights(query: str, result_data: Dict[str, Any], final_step: Dict[str, Any]) -> str:
    """
    Generate insights about query results using ClimateGPT.
    
    Args:
        query: The original user query
        result_data: Dictionary with columns and data arrays
        final_step: The final step that was executed
        
    Returns:
        Insights text from ClimateGPT
    """
    if not result_data or not final_step:
        return "No results available for analysis."
    
    if "data" not in result_data or "columns" not in result_data:
        return "No structured data available for analysis."
    
    # Check if insights are already in cache
    cache_key = f"{query}_{final_step['sql']}"
    cached_insights = insight_cache.get(cache_key)
    if cached_insights:
        return cached_insights
    
    logger.info("Generating insights from results")
    
    # Format the data for the prompt
    data_sample = result_data.copy()
    
    # Limit the amount of data we send to the LLM
    if "data" in data_sample and len(data_sample["data"]) > 10:
        data_sample["data"] = data_sample["data"][:10]
        data_sample["note"] = f"Showing 10 of {len(result_data['data'])} rows"
    
    prompt = f"""
Analyze these climate data results for the query: "{query}"

SQL Query:
{final_step.get('sql', 'No SQL available')}

Results:
{json.dumps(data_sample, indent=2)}

Provide a clear, factual insight that explains:
1. What patterns or trends are visible in this data
2. How this relates to climate change
3. Any notable implications of these findings

Focus on being concise, informative, and accurate. Limit your response to 3 paragraphs maximum.
"""
    
    try:
        payload = {
            "model": "/cache/climategpt_8b_latest",
            "messages": [
                {"role": "system", "content": "You are an AI assistant specialized in climate data analysis."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5
        }
        
        # Simple retry for insights generation
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    CLIMATEGPT_API_URL, 
                    json=payload, 
                    auth=CLIMATEGPT_AUTH,
                    timeout=(10, 30)  # Shorter timeouts for insights
                )
                response.raise_for_status()
                
                # Extract the insight text
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Clean any potential formatting issues
                insight = clean_json_response(content)
                
                # Cache the insights
                insight_cache.set(cache_key, insight)
                
                logger.info("Successfully generated insights")
                return insight
            except Exception as e:
                logger.warning(f"Error generating insights (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Short delay between retries
                    
        # If all retries fail, return a fallback insight
        return generate_fallback_insight(query, result_data)
        
    except Exception as e:
        logger.error(f"Error generating insights: {str(e)}")
        return "I wasn't able to analyze the data in detail. The query returned results, but further analysis would require more processing."

def generate_fallback_insight(query: str, result_data: Dict[str, Any]) -> str:
    """
    Generate a simple fallback insight when API-based insight generation fails.
    
    Args:
        query: The original query
        result_data: The data to analyze
        
    Returns:
        A simple insight based on the data
    """
    try:
        # Extract basic information from the data
        columns = result_data.get("columns", [])
        data = result_data.get("data", [])
        
        if not data or not columns:
            return "No data available for analysis."
            
        # Count rows
        row_count = len(data)
        
        # Try to detect if this is time series data
        time_cols = [i for i, col in enumerate(columns) if col.lower() in ('year', 'date', 'time')]
        
        # Try to detect if this is a comparison
        if row_count == 2 and len(columns) >= 2:
            return f"This data compares two values across {len(columns)} dimensions. " \
                   f"The results show the requested information from the climate database."
        
        # Check if this is a time series
        if time_cols and row_count > 1:
            time_col = time_cols[0]
            # Check if values are increasing or decreasing
            if len(data) >= 2 and isinstance(data[0][time_col], (int, float)) and isinstance(data[-1][time_col], (int, float)):
                start_year = data[0][time_col]
                end_year = data[-1][time_col]
                year_span = end_year - start_year
                
                return f"This data shows a time series from {start_year} to {end_year}, covering {year_span} years. " \
                       f"These historical emissions data can help understand climate trends over time."
        
        # Generic insight
        return f"The query returned {row_count} rows of climate data with {len(columns)} columns. " \
               f"This information can help understand greenhouse gas emissions patterns."
        
    except Exception as e:
        logger.error(f"Error generating fallback insight: {str(e)}")
        return "The query returned climate data results, but detailed analysis is not available."
