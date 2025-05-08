"""
Query classification module for ClimateGPT.

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
    
    Args:
        query: The natural language query to classify
        
    Returns:
        Dict with query classification and execution plan/answer
    """
    start_time = time.time()
    
    # For frequently asked climate questions, try to use cache more aggressively
    cache_key = f"classify_{query.lower().strip()}"
    cached_result = query_cache.get(cache_key)
    if cached_result:
        logger.info(f"Using cached classification for query: {query[:50]}...")
        return cached_result
    
    # Create a detailed schema description with sample data
    schema_info = """
DATABASE SCHEMA:

Table: Greenhouse_Gases
  - ghg_id (INTEGER PRIMARY KEY): Unique identifier for greenhouse gas
  - ghg_name (TEXT): Name of the greenhouse gas (e.g., Carbon Dioxide, Methane, Nitrous Oxide)
  - ghg_category (TEXT): Category of the greenhouse gas (e.g., CO2, CH4, N2O)
  Sample data: 
  [
    {"ghg_id": 1, "ghg_name": "Carbon Dioxide", "ghg_category": "CO2"},
    {"ghg_id": 2, "ghg_name": "Nitrous Oxide", "ghg_category": "N2O"},
    {"ghg_id": 3, "ghg_name": "Methane", "ghg_category": "CH4"}
  ]

Table: Sectors
  - sector_id (INTEGER PRIMARY KEY): Unique identifier for the sector
  - sector (TEXT): Name of the sector (e.g., Agriculture, Energy, Transportation)
  - subsector (TEXT): Subsector name
  - category (TEXT): Category
  - sub_category_1 to sub_category_5 (TEXT): Additional categorization
  - dataset_type (TEXT): Type of dataset
  Sample data:
  [
    {"sector_id": 1, "sector": "Agriculture", "subsector": "CO2 Emissions from Liming, Urea Application and Other Carbon-Containing Fertilizers"},
    {"sector_id": 275, "sector": "Energy", "subsector": "Fossil Fuel Combustion"}, 
    {"sector_id": 300, "sector": "Transportation", "subsector": "Mobile Sources"}
  ]

Table: Fuels
  - fuel_id (INTEGER PRIMARY KEY): Unique identifier for fuel type
  - fuel1 (TEXT): Primary fuel name (e.g., Coal, Natural Gas, Petroleum)
  - fuel2 (TEXT): Secondary fuel classification
  Sample data:
  [
    {"fuel_id": 1, "fuel1": "Unknown", "fuel2": "Unknown"},
    {"fuel_id": 2, "fuel1": "Coal", "fuel2": "Unknown"},
    {"fuel_id": 3, "fuel1": "Natural Gas", "fuel2": "Unknown"}
  ]

Table: Geography
  - geo_id (INTEGER PRIMARY KEY): Unique identifier for geographic region
  - geo_ref (TEXT): Reference code for the region (e.g., CA, NY, TX)
  - region_name (TEXT): Full name of the region (e.g., California, New York, Texas)
  Sample data:
  [
    {"geo_id": 1, "geo_ref": "AK", "region_name": "Alaska"},
    {"geo_id": 2, "geo_ref": "AL", "region_name": "Alabama"},
    {"geo_id": 5, "geo_ref": "CA", "region_name": "California"}
  ]

Table: Emissions (FACT TABLE)
  - emission_id (INTEGER PRIMARY KEY): Unique identifier for emission record
  - year (INTEGER): Year of the emission record
  - ghg_id (INTEGER): Foreign key to Greenhouse_Gases
  - sector_id (INTEGER): Foreign key to Sectors
  - fuel_id (INTEGER): Foreign key to Fuels
  - geo_id (INTEGER): Foreign key to Geography
  - emissions (REAL): Amount of emissions
  Sample data:
  [
    {"emission_id": 1, "year": 1990, "ghg_id": 1, "sector_id": 275, "fuel_id": 1, "geo_id": 1, "emissions": 0.0029738932251386},
    {"emission_id": 2, "year": 1990, "ghg_id": 1, "sector_id": 275, "fuel_id": 1, "geo_id": 2, "emissions": 0.6373067565518994}
  ]

RELATIONSHIPS:
- Emissions.ghg_id → Greenhouse_Gases.ghg_id
- Emissions.sector_id → Sectors.sector_id
- Emissions.fuel_id → Fuels.fuel_id
- Emissions.geo_id → Geography.geo_id

DATA COVERAGE:
- Years: 1990 to 2022
"""
    
    # SQLite function limitations and alternatives
    sqlite_guidance = """
IMPORTANT SQLITE FUNCTION LIMITATIONS AND ALTERNATIVES:

1. Percentiles:
   - SQLite does NOT support PERCENTILE_CONT or PERCENTILE_DISC.
   - Use this pattern:
     SELECT emissions
     FROM (SELECT emissions FROM Emissions ORDER BY emissions)
     LIMIT 1 OFFSET (
       SELECT CAST(COUNT(*) * 0.25 AS INT) FROM Emissions
     );
   - Do not return only the OFFSET index; use LIMIT 1 OFFSET (...) to get the percentile value.

2. Median:
   - For median (50th percentile), use:
     SELECT AVG(emissions) FROM (
       SELECT emissions FROM Emissions ORDER BY emissions
       LIMIT 2 OFFSET (SELECT (COUNT(*) - 1) / 2 FROM Emissions)
     );

3. Standard Deviation:
   - Instead of STDDEV, use:
     SELECT SQRT(AVG(emissions * emissions) - AVG(emissions) * AVG(emissions)) FROM Emissions;

4. String aggregation:
   - Instead of STRING_AGG/LISTAGG, use the SQLite GROUP_CONCAT function:
     SELECT GROUP_CONCAT(column_name, ',') FROM table_name;

5. Statistical calculations:
   - For complex statistical calculations, prefer to use multiple steps with temporary results
   - For top-N emissions by state and gas type, filter by ghg_category and year, join Geography, and use ORDER BY + LIMIT.

Remember to adapt these patterns to include your necessary JOIN statements and WHERE clauses.
"""

    # Include sample working SQL queries - removing ANALYZE keyword
    sample_queries = """
# 1. Query for total CO2 emissions by year
SELECT e.year, SUM(e.emissions) as total_emissions 
FROM Emissions e 
JOIN Greenhouse_Gases gg ON e.ghg_id = gg.ghg_id 
WHERE gg.ghg_name = 'Carbon Dioxide' 
GROUP BY e.year 
ORDER BY e.year;

# 2. Compare emissions between two states
SELECT g.region_name, SUM(e.emissions) as total_emissions 
FROM Emissions e 
JOIN Geography g ON e.geo_id = g.geo_id 
WHERE g.region_name IN ('California', 'Texas') AND e.year = 2020
GROUP BY g.region_name;

# 3. Get emissions by sector
SELECT s.sector, SUM(e.emissions) as total_emissions 
FROM Emissions e 
JOIN Sectors s ON e.sector_id = s.sector_id 
WHERE e.year = 2020
GROUP BY s.sector
ORDER BY total_emissions DESC;

# 4. Get methane emissions trend over a decade
SELECT e.year, SUM(e.emissions) as total_emissions 
FROM Emissions e 
JOIN Greenhouse_Gases gg ON e.ghg_id = gg.ghg_id 
WHERE gg.ghg_name = 'Methane' AND e.year >= 2010 AND e.year <= 2020
GROUP BY e.year
ORDER BY e.year;

# 5. Emissions by fuel type
SELECT f.fuel1, SUM(e.emissions) as total_emissions 
FROM Emissions e 
JOIN Fuels f ON e.fuel_id = f.fuel_id 
WHERE e.year = 2020
GROUP BY f.fuel1
ORDER BY total_emissions DESC;
"""

    prompt = f"""
You are an expert in climate data analysis. I need you to process this user query:

USER QUERY: "{query}"

First, determine if this is:
1) A general knowledge question about climate change that can be answered without database access, OR
2) A database query that requires accessing our climate emissions database

Our database has the following structure:
{schema_info}

{sqlite_guidance}

IMPORTANT RULES FOR SQL GENERATION:
1. Use ONLY the EXACT table and column names shown in the schema
2. Always use proper JOIN statements when querying across tables
3. Use appropriate table aliases (e.g., e for Emissions, g for Geography, s for Sectors, gg for Greenhouse_Gases)
4. Join Emissions with Greenhouse_Gases using e.ghg_id = gg.ghg_id
5. Join Emissions with Geography using e.geo_id = g.geo_id
6. Join Emissions with Sectors using e.sector_id = s.sector_id
7. When querying specific regions, always use geo_ref or region_name from Geography table
8. YOUR SQL QUERIES MUST NEVER START WITH OR INCLUDE THE KEYWORD 'ANALYZE'. JUST START DIRECTLY WITH 'SELECT'.
9. ALWAYS ADAPT YOUR QUERIES FOR SQLITE LIMITATIONS AS DESCRIBED ABOVE.

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
                {"role": "system", "content": "You are an AI assistant specialized in climate data analysis."},
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
                      return {
                          "error": "Failed to generate SQL for this query",
                          "details": f"The model returned an incomplete response: {classification}"
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
