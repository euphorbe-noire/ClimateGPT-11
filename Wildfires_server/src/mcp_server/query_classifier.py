"""
Query classification module for WildfireGPT.

This module processes natural language queries using the ClimateGPT model,
determining whether they require database access or general knowledge answers.
"""

import json
import requests
import time
import logging
from typing import Dict, Any, Optional

from src.config import CLIMATEGPT_API_URL, CLIMATEGPT_AUTH, QUERY_TIMEOUT
from src.mcp_server.cache_utils import SimpleCache

# Import utility functions from query_utils.py
from src.mcp_server.query_utils import clean_json_response, is_valid_classification

# Set up logging
logger = logging.getLogger('query_classifier')

# Initialize cache
query_cache = SimpleCache(max_size=100, ttl=3600)  # Cache for 1 hour

def classify_and_plan(query: str) -> Dict[str, Any]:
    """
    Use ClimateGPT to classify a query and generate a response plan.
    Updated to work with wildfire database.
    """
    start_time = time.time()
    
    # For frequently asked wildfire questions, try to use cache more aggressively
    cache_key = f"classify_{query.lower().strip()}"
    cached_result = query_cache.get(cache_key)
    if cached_result:
        logger.info(f"Using cached classification for query: {query[:50]}...")
        return cached_result
    
    # Updated schema description for wildfire database
    schema_info = """
DATABASE SCHEMA:

Table: fire_data
  - latitude (REAL): Geographic latitude coordinate
  - longitude (REAL): Geographic longitude coordinate
  - brightness (REAL): Fire intensity measure (temperature in Kelvin)
  - scan (REAL): Pixel resolution in kilometers
  - track (REAL): Pixel resolution in kilometers
  - acq_date (DATE): Acquisition date (YYYY-MM-DD format)
  - acq_time (TIME): Acquisition time (HHMM format)
  - satellite (TEXT): Satellite that detected the fire (Aqua/Terra)
  - instrument (TEXT): Detection instrument (MODIS)
  - confidence (INTEGER): Detection confidence score (0-100)
  - version (REAL): Detection algorithm version
  - bright_t31 (REAL): Brightness temperature (Channel 31)
  - frp (REAL): Fire Radiative Power (megawatts)
  - daynight (TEXT): Day/Night flag (D/N)
  - type (INTEGER): Detection type (1=active fire, 0=other, 2=other)
IMPORTANT: Dates are stored in YYYY-MM-DD format in the database
Sample data:
[
  {"latitude": 19.447, "longitude": -155.0117, "brightness": 314.4, "confidence": 51, "acq_date": "2015-01-30", "satellite": "Aqua", "type": 1},
  {"latitude": 33.3755, "longitude": -81.58, "brightness": 317.4, "confidence": 68, "acq_date": "2015-01-30", "satellite": "Terra", "type": 0}
]

DATA COVERAGE:
- Temporal coverage: 2015 to present
- Global coverage
- Multiple satellites: Aqua, Terra
- Detection types: Active fires, potential fires, other thermal anomalies
"""
    
    # SQLite function limitations and alternatives
    sqlite_guidance = """
IMPORTANT SQLITE FUNCTION LIMITATIONS AND ALTERNATIVES:

1. Date Handling:
   - Date format is 'YYYY-MM-DD'. Use substr() and strftime() for date operations:
   - To extract year: substr(acq_date, 7, 4)
   - To extract month: substr(acq_date, 4, 2)
   - To extract day: substr(acq_date, 1, 2)
   - For date comparisons, convert to ISO format: 
     substr(acq_date, 7, 4) || '-' || substr(acq_date, 4, 2) || '-' || substr(acq_date, 1, 2)


2. Time Handling:
   - Time format is HHMM (e.g., 1300 for 1:00 PM)
   - To extract hour: CAST(substr(acq_time, 1, 2) AS INTEGER)
   - To extract minute: CAST(substr(acq_time, 3, 2) AS INTEGER)

3. Geographic Regions:
   - To group by region, use CASE statements with latitude/longitude ranges
   - Example for California: 
     CASE WHEN latitude BETWEEN 32.5 AND 42 AND longitude BETWEEN -124.5 AND -114.1 THEN 'California'

4. Statistical calculations:
   - For standard deviation, use: 
     SELECT SQRT(AVG((value - mean) * (value - mean))) FROM 
     (SELECT brightness as value, (SELECT AVG(brightness) FROM fire_data) as mean FROM fire_data)

5. String aggregation:
   - Use GROUP_CONCAT() instead of STRING_AGG/LISTAGG
"""

    # Updated sample queries for wildfire data
    sample_queries = """

# 1. Query for active fire detections by date
SELECT COUNT(*) AS fire_count, 
       substr(acq_date, 7, 4) || '-' || substr(acq_date, 4, 2) || '-' || substr(acq_date, 1, 2) AS formatted_date
FROM fire_data
WHERE type = 1
  AND substr(acq_date, 7, 4) = '2015'  -- Year = 2015
  AND substr(acq_date, 4, 2) = '01'    -- Month = January
GROUP BY acq_date
ORDER BY formatted_date;

# 2. Query for active fire detections by date
SELECT COUNT(*) as fire_count, acq_date 
FROM fire_data 
WHERE type = 1 
GROUP BY acq_date 
ORDER BY acq_date;

# 3. Analyze fire intensity by region (California example)
SELECT AVG(brightness) as avg_brightness, AVG(frp) as avg_frp 
FROM fire_data 
WHERE latitude BETWEEN 32.5 AND 42 
  AND longitude BETWEEN -124.5 AND -114.1 
  AND type = 1;

# 4. Compare fire detections between satellites
SELECT satellite, COUNT(*) as detection_count 
FROM fire_data 
WHERE type = 1 
GROUP BY satellite;

# 5. Find high-confidence fire detections
SELECT latitude, longitude, brightness, frp, acq_date, acq_time 
FROM fire_data 
WHERE confidence > 80 AND type = 1 
ORDER BY frp DESC 
LIMIT 100;

# 6. Day vs night fire detections
SELECT daynight, COUNT(*) as count, AVG(brightness) as avg_brightness 
FROM fire_data 
WHERE type = 1 
GROUP BY daynight;

# 7. Monthly fire trends
SELECT 
    substr(acq_date, 4, 2) as month, 
    substr(acq_date, 7, 4) as year,
    COUNT(*) as fire_count 
FROM fire_data 
WHERE type = 1 
GROUP BY substr(acq_date, 7, 4), substr(acq_date, 4, 2)
ORDER BY year, month;

# 8. Geographic distribution of fires
SELECT 
    CASE 
        WHEN latitude BETWEEN 32.5 AND 42 AND longitude BETWEEN -124.5 AND -114.1 THEN 'California'
        WHEN latitude BETWEEN 30 AND 36.5 AND longitude BETWEEN -106 AND -93.5 THEN 'Texas'
        WHEN latitude BETWEEN 40.5 AND 45 AND longitude BETWEEN -79 AND -71.5 THEN 'New York'
        ELSE 'Other'
    END as region,
    COUNT(*) as fire_count
FROM fire_data
WHERE type = 1
GROUP BY region;


"""

    prompt = f"""
You are an expert in wildfire data analysis. I need you to process this user query:

USER QUERY: "{query}"

First, determine if this is:
1) A general knowledge question about wildfires that can be answered without database access, OR
2) A database query that requires accessing our wildfire detection database

Our database has the following structure:
{schema_info}

{sqlite_guidance}

IMPORTANT RULES FOR SQL GENERATION:
1. Use ONLY the EXACT table name: fire_data
2. When filtering for active fires, use type = 1
3. Confidence scores range from 0-100
4. Date format is 'DD-MM-YYYY' (use substr() for date parsing)
5. Time format is HHMM (e.g., 1300 for 1:00 PM)
6. Brightness and bright_t31 are in Kelvin
7. FRP (Fire Radiative Power) is in megawatts
8. YOUR SQL QUERIES MUST NEVER START WITH OR INCLUDE THE KEYWORD 'ANALYZE'
9. ALWAYS ADAPT YOUR QUERIES FOR SQLITE LIMITATIONS AS DESCRIBED ABOVE
10. For geographic regions, use latitude/longitude ranges with CASE statements

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
    
    logger.info(f"Sending query to ClimateGPT for classification and planning")
    
    try:
        # Send the prompt to ClimateGPT
        payload = {
            "model": "/cache/climategpt_8b_latest",
            "messages": [
                {"role": "system", "content": "You are an AI assistant specialized in wildfire data analysis."},
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
            
                    # Check if we got a list instead of a dictionary
                    if isinstance(classification, list):
                        logger.error(f"Received list instead of dictionary: {classification}")
                        # Convert list to dictionary if possible or use a fallback
                        if classification and isinstance(classification[0], dict):
                            classification = classification[0]  # Use first item if it's a dictionary
                        else:
                            # Fallback to a basic response
                            return {
                                "query_type": "general_knowledge",
                                "answer": "I'm sorry, but I received an unexpected response format. Could you try rephrasing your question?"
                            }
                    
                    # Validate the classification before caching
                    if not is_valid_classification(classification):
                        logger.warning(f"Invalid classification from API: {classification}")
                        # Return a helpful message
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
                        raise ValueError("Invalid response format from ClimateGPT")
                    
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
            raise requests.exceptions.Timeout("ClimateGPT API request timed out")
        elif last_error == "connection":
            raise requests.exceptions.ConnectionError("Unable to connect to ClimateGPT API")
        else:
            raise requests.exceptions.RequestException(f"API request failed: {last_error}")
            
    except Exception as e:
        logger.error(f"Error in query classification or execution: {str(e)}")
        return {
            "query_type": "general_knowledge",
            "answer": f"Error: {str(e)}. Please try again later."
        }

