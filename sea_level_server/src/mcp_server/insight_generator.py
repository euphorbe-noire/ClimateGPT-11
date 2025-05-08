"""
Insight generation module for sea level data with the updated schema.

This module generates insights from query results using an LLM.
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
    Generate insights about sea level data query results using an LLM.
    
    Args:
        query: The original user query
        result_data: Dictionary with columns and data arrays
        final_step: The final step that was executed
        
    Returns:
        Insights text about sea level data
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
    
    # Get column information
    columns = result_data.get("columns", [])
    
    # Create a prompt that reflects the new schema
    prompt = f"""
Analyze these sea level data results for the query: "{query}"

SQL Query:
{final_step.get('sql', 'No SQL available')}

Results:
{json.dumps(data_sample, indent=2)}

The sea level database has the following schema:
- ID: Unique identifier for each measurement
- Country: Country name (e.g., "World")
- Unit: Measurement unit (e.g., "Millimeters")
- Source: Data source organization
- Region: Specific sea or ocean region (e.g., "Baltic Sea", "North Sea")
- Date: Date of the measurement in YYYY-MM-DD format
- Sea_Level_Change: The sea level measurement value in the specified unit

Provide a clear, factual insight that explains:
1. What patterns or trends are visible in this sea level data
2. If there are multiple regions in the data, compare their sea level patterns
3. The significance of these trends in relation to climate change
4. Any notable implications of these findings for coastal communities

Focus on being concise, informative, and accurate. Limit your response to 3 paragraphs maximum.

When discussing sea level changes:
- Note if the data shows rising or falling trends
- Specify the rate of change if calculable (e.g., mm per year)
- Mention any seasonal patterns if visible in the data
- Comment on variability between regions if multiple regions are present
"""
    
    try:
        payload = {
            "model": "/cache/climategpt_8b_latest",
            "messages": [
                {"role": "system", "content": "You are an AI assistant specialized in sea level data analysis."},
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
        
        # Analyze based on column availability
        has_date = 'Date' in columns
        has_region = 'Region' in columns
        has_sea_level = 'Sea_Level_Change' in columns
        
        # Get date column index if available
        date_idx = columns.index('Date') if has_date else None
        
        # Get region column index if available
        region_idx = columns.index('Region') if has_region else None
        
        # Get sea level column index if available
        sea_level_idx = columns.index('Sea_Level_Change') if has_sea_level else None
        
        if has_date and has_sea_level and row_count > 1:
            # Try to analyze time series data
            try:
                # Extract start and end entries
                start_date = data[0][date_idx]
                start_value = float(data[0][sea_level_idx])
                end_date = data[-1][date_idx]
                end_value = float(data[-1][sea_level_idx])
                
                # Calculate overall change
                change = end_value - start_value
                
                # Determine if rising or falling and create appropriate message
                if change > 0:
                    trend = "rising"
                    impact = "This rising trend in sea levels is consistent with global warming patterns and may impact coastal communities through increased flooding and erosion."
                elif change < 0:
                    trend = "falling"
                    impact = "This falling trend is unusual compared to global patterns and may reflect local geological factors or measurement anomalies."
                else:
                    trend = "stable"
                    impact = "This stability in sea levels is unusual compared to global trends and warrants further investigation."
                
                # Check if we have unit information
                unit = "mm"
                unit_idx = columns.index('Unit') if 'Unit' in columns else None
                if unit_idx is not None and row_count > 0:
                    unit_value = data[0][unit_idx]
                    if isinstance(unit_value, str):
                        if unit_value.lower() == "millimeters":
                            unit = "mm"
                        else:
                            unit = unit_value
                
                # Get region information if available
                region_info = ""
                if has_region and len(set(row[region_idx] for row in data)) > 1:
                    regions = set(row[region_idx] for row in data)
                    region_info = f" across different regions ({', '.join(regions)})"
                
                return f"The sea level data{region_info} shows a {trend} trend from {start_date} to {end_date}, with a change of {change:.2f} {unit}. {impact} This dataset contains {row_count} measurements, providing a meaningful time series for analysis."
            except Exception as e:
                logger.warning(f"Error in time series analysis: {str(e)}")
        
        # If regional analysis is possible
        if has_region and has_sea_level:
            try:
                # Group by region
                regions = {}
                for row in data:
                    region = row[region_idx]
                    value = float(row[sea_level_idx])
                    if region not in regions:
                        regions[region] = []
                    regions[region].append(value)
                
                # Calculate average by region
                region_avgs = {r: sum(v)/len(v) for r, v in regions.items()}
                
                # Find max and min regions
                max_region = max(region_avgs.items(), key=lambda x: x[1])
                min_region = min(region_avgs.items(), key=lambda x: x[1])
                
                return f"The data contains sea level measurements for {len(regions)} different regions. The {max_region[0]} region shows the highest average sea level at {max_region[1]:.2f} units, while the {min_region[0]} region shows the lowest at {min_region[1]:.2f} units. This regional variation highlights the complexity of sea level changes, which can be influenced by local factors such as ocean currents, wind patterns, and geological activity."
            except Exception as e:
                logger.warning(f"Error in regional analysis: {str(e)}")
        
        # Generic insight
        return f"The query returned {row_count} rows of sea level data with {len(columns)} columns. Sea levels globally have been rising at an accelerating rate in recent decades, with significant implications for coastal regions and ecosystems. Regional variations in sea level change can be substantial, influenced by factors like ocean currents, wind patterns, and geological activity."
        
    except Exception as e:
        logger.error(f"Error generating fallback insight: {str(e)}")
        return "The query returned sea level data results, but detailed analysis is not available."