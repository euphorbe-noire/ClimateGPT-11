"""
Main query processor module for ClimateGPT.

This module serves as the entry point for processing natural language queries,
delegating to specialized modules for classification, execution, and insight generation.
"""

import time
import logging
import base64
from typing import Dict, Any

from src.mcp_server.query_classifier import classify_and_plan, query_cache
from src.mcp_server.query_executor import execute_plan
from src.mcp_server.insight_generator import generate_insights
from src.mcp_server.query_utils import handle_error, is_valid_classification
from src.mcp_server.cache_utils import SimpleCache
from src.mcp_server.visualization_generator import create_visualization
from src.config import VISUALIZATION_ENABLED

insight_cache = SimpleCache(max_size=100, ttl=3600)
visualization_cache = SimpleCache(max_size=50, ttl=3600)

# Set up logging
logger = logging.getLogger('query_processor')

def process_query(query: str) -> Dict[str, Any]:
    """
    Process a natural language query using the ClimateGPT model.
    
    Args:
        query: The user's natural language query
        
    Returns:
        Dict containing processed results and metadata
    """
    start_time = time.time()
    
    # Check if this query is in the cache
    cached_result = query_cache.get(query)
    if cached_result:
        logger.info(f"Using cached result for query: {query[:50]}...")
        return cached_result
    
    # The query is not in cache, we need to process it
    try:
        # Step 1: Classify the query and get a plan or answer
        classification = classify_and_plan(query)
        
        # Validate the classification before proceeding or caching
        if not is_valid_classification(classification):
            logger.warning(f"Invalid classification response, not caching: {classification}")
            return handle_error("Invalid response format from ClimateGPT", start_time)
        
        if classification.get("query_type") == "general_knowledge":
            # Handle general knowledge questions
            result = {
                "type": "general_knowledge",
                "answer": classification.get("answer", "I don't have specific information on that topic."),
                "execution_time": time.time() - start_time
            }
        else:
            # Handle database queries
            # Extract the execution plan
            if "execution_plan" not in classification or "steps" not in classification["execution_plan"]:
                logger.error(f"Invalid plan format from ClimateGPT: {classification}")
                return handle_error("Invalid response format from ClimateGPT", start_time)
                
            steps = classification["execution_plan"]["steps"]
            if not steps:
                logger.error("Empty execution plan from ClimateGPT")
                return handle_error("No query steps provided", start_time)
            
            # Execute the plan
            execution_result = execute_plan(steps, query)
            if "error" in execution_result:
                return handle_error(execution_result["error"], start_time)
            
            # Generate visualization if enabled and data is suitable
            visualization = None
            if VISUALIZATION_ENABLED:
                try:
                    # Check if visualization is already in cache
                    viz_cache_key = f"viz_{query}"
                    visualization = visualization_cache.get(viz_cache_key)
                    
                    if not visualization and execution_result.get("results"):
                        data = execution_result.get("results")
                        # Check if data is suitable for visualization
                        if is_data_visualizable(data):
                            logger.info("Generating visualization for query")
                            visualization_bytes = create_visualization(query, data)
                            if visualization_bytes:
                                # Convert to base64 for transmission
                                visualization = base64.b64encode(visualization_bytes).decode('utf-8')
                                visualization_cache.set(viz_cache_key, visualization)
                                logger.info("Visualization generated successfully")
                            else:
                                logger.warning("Failed to generate visualization")
                except Exception as e:
                    logger.error(f"Error in visualization generation: {str(e)}")
                    # Continue without visualization if it fails
            
            # Add execution time and type
            result = {
                "type": "database",
                "results": execution_result.get("results"),
                "insights": execution_result.get("insights"),
                "plan": {"steps": steps},
                "visualization": visualization,
                "execution_time": time.time() - start_time
            }
        
        # Only cache successful results
        query_cache.set(query, result)
        return result
        
    except Exception as e:
        logger.error(f"Error in query processing: {str(e)}")
        return handle_error(f"Query processing error: {str(e)}", start_time)

def is_data_visualizable(data: Dict[str, Any]) -> bool:
    """
    Check if the data is suitable for visualization.
    
    Args:
        data: Dictionary with columns and data arrays
        
    Returns:
        Boolean indicating if data can be visualized
    """
    if not data or "columns" not in data or "data" not in data:
        return False
        
    columns = data.get("columns", [])
    rows = data.get("data", [])
    
    # Need at least 2 columns and some rows for visualization
    if len(columns) < 1 or len(rows) < 2:
        return False
        
    # Check if there's at least one numerical and one categorical/time column
    has_numerical = False
    has_categorical_or_time = False
    
    # Sample the first row
    if rows:
        for i, value in enumerate(rows[0]):
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit()):
                has_numerical = True
            elif isinstance(value, str) and (value.lower() in ['year', 'date', 'time'] or any(c in columns[i].lower() for c in ['year', 'date', 'time'])):
                has_categorical_or_time = True
                
    # For trend data, we specifically look for time series patterns
    if 'year' in [col.lower() for col in columns] or 'date' in [col.lower() for col in columns]:
        has_categorical_or_time = True
        
    return has_numerical and (len(columns) > 1 or has_categorical_or_time)