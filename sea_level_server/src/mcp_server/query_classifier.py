"""
Query classification module for Sea Level Data with updated schema.

This module processes natural language queries using an LLM,
determining whether they require database access or general knowledge answers.
"""

import json
import requests
import time
import logging
from typing import Dict, Any, Optional

from src.config import CLIMATEGPT_API_URL, CLIMATEGPT_AUTH, QUERY_TIMEOUT
from src.mcp_server.cache_utils import SimpleCache
from src.mcp_server.query_utils import clean_json_response, is_valid_classification

# Set up logging
logger = logging.getLogger('query_classifier')

# Initialize cache
query_cache = SimpleCache(max_size=100, ttl=3600)  # Cache for 1 hour

def classify_and_plan(query: str) -> Dict[str, Any]:
    """
    Use LLM to classify a query and generate a response plan.
    
    Args:
        query: The natural language query to classify
        
    Returns:
        Dict with query classification and execution plan/answer
    """
    start_time = time.time()
    
    # For frequently asked questions, try to use cache more aggressively
    cache_key = f"classify_{query.lower().strip()}"
    cached_result = query_cache.get(cache_key)
    if cached_result:
        logger.info(f"Using cached classification for query: {query[:50]}...")
        return cached_result
    
    # Create a detailed schema description with sample data
    schema_info = """
DATABASE SCHEMA:

Table: Global_Change_In_Mean_Sea_Level
  - ID (INTEGER): Unique identifier for each measurement
  - Country (TEXT): Country name (e.g., "World")
  - Unit (TEXT): Measurement unit (e.g., "Millimeters")
  - Source (TEXT): Data source organization
  - Region (TEXT): Specific sea or ocean region (e.g., "Baltic Sea", "North Sea")
  - Date (TEXT): Date of measurement in YYYY-MM-DD format
  - Sea_Level_Change (REAL): The sea level measurement value
  
  Sample data: 
  [
    {"ID": 19, "Country": "World", "Unit": "Millimeters", "Source": "National Oceanic and Atmospheric Administration", "Region": "Baltic Sea", "Date": "1992-10-18", "Sea_Level_Change": -160.41},
    {"ID": 30, "Country": "World", "Unit": "Millimeters", "Source": "National Oceanic and Atmospheric Administration", "Region": "Baltic Sea", "Date": "1992-10-29", "Sea_Level_Change": -171.61},
    {"ID": 149, "Country": "World", "Unit": "Millimeters", "Source": "National Oceanic and Atmospheric Administration", "Region": "Baltic Sea", "Date": "1992-12-17", "Sea_Level_Change": 214.89},
    {"ID": 171, "Country": "World", "Unit": "Millimeters", "Source": "National Oceanic and Atmospheric Administration", "Region": "Baltic Sea", "Date": "1992-12-26", "Sea_Level_Change": 221.09},
    {"ID": 230, "Country": "World", "Unit": "Millimeters", "Source": "National Oceanic and Atmospheric Administration", "Region": "North Sea", "Date": "1993-01-15", "Sea_Level_Change": 258.97}
  ]
"""
    
    # SQLite function limitations and alternatives
    sqlite_guidance = """
IMPORTANT SQLITE FUNCTION LIMITATIONS AND ALTERNATIVES:

1. Date Handling:
   - SQLite stores dates as strings, you'll need to use date functions carefully
   - Use strftime() function for date formatting and calculations
   - Example: strftime('%Y', Date) to extract the year
   
2. Moving Averages:
   - To calculate a moving average, use window functions or self-joins
   - Example: For a 3-point moving average:
     SELECT Date, AVG(Sea_Level_Change) OVER (ORDER BY Date ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) as moving_avg
     FROM Global_Change_In_Mean_Sea_Level

3. Aggregation by Year:
   - Group by year using: GROUP BY strftime('%Y', Date)
   - Example:
     SELECT strftime('%Y', Date) as Year, AVG(Sea_Level_Change) as average_level
     FROM Global_Change_In_Mean_Sea_Level
     GROUP BY strftime('%Y', Date)

4. Standard Deviation:
   - Instead of STDDEV, use:
     SELECT SQRT(AVG(Sea_Level_Change * Sea_Level_Change) - AVG(Sea_Level_Change) * AVG(Sea_Level_Change)) 
     FROM Global_Change_In_Mean_Sea_Level;

5. Date Range Queries:
   - For date ranges, use comparison operators with ISO date format:
     WHERE Date BETWEEN '2010-01-01' AND '2020-12-31'
     or
     WHERE strftime('%Y', Date) BETWEEN '2010' AND '2020'
     
6. Regional Analysis:
   - To filter by region: WHERE Region = 'Baltic Sea'
   - To compare regions: GROUP BY Region
"""

    # Include sample working SQL queries
    sample_queries = """
# 1. Get all sea level measurements
SELECT * FROM Global_Change_In_Mean_Sea_Level ORDER BY Date;

# 2. Get sea level measurements for a specific time period
SELECT Date, Sea_Level_Change 
FROM Global_Change_In_Mean_Sea_Level 
WHERE Date BETWEEN '1995-01-01' AND '2000-12-31'
ORDER BY Date;

# 3. Calculate yearly averages
SELECT strftime('%Y', Date) as Year, AVG(Sea_Level_Change) as average_level
FROM Global_Change_In_Mean_Sea_Level
GROUP BY strftime('%Y', Date)
ORDER BY Year;

# 4. Calculate the rate of change between consecutive measurements for a specific region
SELECT Date, 
       Sea_Level_Change,
       Sea_Level_Change - LAG(Sea_Level_Change) OVER (ORDER BY Date) as rate_of_change
FROM Global_Change_In_Mean_Sea_Level
WHERE Region = 'Baltic Sea'
ORDER BY Date;

# 5. Compare average sea level change across different regions
SELECT Region, AVG(Sea_Level_Change) as avg_change
FROM Global_Change_In_Mean_Sea_Level
GROUP BY Region
ORDER BY avg_change DESC;

# 6. Find months with highest sea level changes
SELECT strftime('%Y-%m', Date) as Month, AVG(Sea_Level_Change) as avg_level
FROM Global_Change_In_Mean_Sea_Level
GROUP BY Month
ORDER BY avg_level DESC
LIMIT 10;
"""

    prompt = f"""
You are an expert in sea level data analysis. I need you to process this user query:

USER QUERY: "{query}"

First, determine if this is:
1) A general knowledge question about sea levels, climate change, or related topics that can be answered without database access, OR
2) A database query that requires accessing our sea level database

Our database has the following structure:
{schema_info}

{sqlite_guidance}

IMPORTANT RULES FOR SQL GENERATION:
1. Use ONLY the EXACT table and column names shown in the schema (Global_Change_In_Mean_Sea_Level, ID, Country, Unit, Source, Region, Date, Sea_Level_Change)
2. Make sure to reference 'Sea_Level_Change' exactly (with underscores) for the measurements
3. Handle dates properly using the guidance above
4. YOUR SQL QUERIES MUST NEVER START WITH OR INCLUDE THE KEYWORD 'ANALYZE'. JUST START DIRECTLY WITH 'SELECT'.
5. ALWAYS ADAPT YOUR QUERIES FOR SQLITE LIMITATIONS AS DESCRIBED ABOVE.

EXAMPLE SQL QUERIES THAT WORK:
{sample_queries}

YOUR RESPONSE MUST BE VALID JSON with this structure:
{{
  "query_type": "general_knowledge" or "database",
  
  // For general_knowledge queries:
  "answer": "Detailed answer to the question",
  
  // For database queries:
  "execution_plan": {{
    "steps": [
      {{
        "id": "step1",
        "description": "Description of this step",
        "sql": "SQL query for this step"
      }}
    ]
  }}
}}
"""
    
    logger.info(f"Sending query to LLM for classification and planning")
    
    try:
        # Send the prompt to LLM
        payload = {
            "model": "/cache/climategpt_8b_latest",
            "messages": [
                {"role": "system", "content": "You are an AI assistant specialized in sea level data analysis."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3
        }
        
        # Implement retry with exponential backoff
        max_retries = 3
        retry_delay = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    CLIMATEGPT_API_URL, 
                    json=payload, 
                    auth=CLIMATEGPT_AUTH,
                    timeout=(30, QUERY_TIMEOUT)  # 30 seconds for connection, full timeout for response
                )
                response.raise_for_status()
                
                # Parse the response
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Always clean the JSON before parsing
                cleaned_content = clean_json_response(content)
                
                # After parsing the JSON
                try:
                    classification = json.loads(cleaned_content)
                    
                    # Validate the classification before caching
                    if not is_valid_classification(classification):
                        logger.warning(f"Invalid classification from API: {classification}")
                        # Don't cache invalid classifications
                        return {
                            "query_type": "general_knowledge",
                            "answer": "I couldn't process your question correctly. Could you try rephrasing it?"
                        }
                    
                    logger.info(f"Successfully classified query as {classification.get('query_type', 'unknown')}")
                    logger.info(f"Classification completed in {time.time() - start_time:.2f}s")
                    
                    # Only cache valid classifications
                    query_cache.set(cache_key, classification)
                    return classification
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON even after cleanup: {str(e)}")
                    logger.debug(f"Cleaned content was: {cleaned_content[:200]}...")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying JSON parsing (attempt {attempt+1}/{max_retries})")
                        time.sleep(retry_delay * (attempt + 1))
                    else:
                        raise ValueError("Invalid response format from LLM")
                    
            except requests.exceptions.Timeout:
                last_error = "timeout"
                logger.warning(f"Timeout error on attempt {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    backoff_time = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                
            except requests.exceptions.ConnectionError:
                last_error = "connection"
                logger.warning(f"Connection error on attempt {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    backoff_time = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"API request error: {str(e)}")
                last_error = "request"
                if attempt < max_retries - 1:
                    backoff_time = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                    
            # All retries failed
        logger.error(f"API request failed after {max_retries} attempts")
        
        # Provide clear error messages based on the type of error
        if last_error == "timeout":
            raise requests.exceptions.Timeout("LLM API request timed out")
        elif last_error == "connection":
            raise requests.exceptions.ConnectionError("Unable to connect to LLM API")
        else:
            raise requests.exceptions.RequestException(f"API request failed: {last_error}")
            
    except Exception as e:
        logger.error(f"Error in query classification or execution: {str(e)}")
        return {
            "query_type": "general_knowledge",
            "answer": f"Error: {str(e)}. Please try again later."
        }