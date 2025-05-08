"""
Main query processor module for ClimateGPT.

This module serves as the entry point for processing natural language queries,
delegating to specialized modules for classification, execution, insight generation,
and forecast prediction.
"""

import time
import logging
from typing import Dict, Any

from src.mcp_server.query_classifier import classify_and_plan, query_cache
from src.mcp_server.query_executor import execute_plan
from src.mcp_server.insight_generator import generate_insights
from src.mcp_server.query_utils import handle_error, is_valid_classification
from src.mcp_server.cache_utils import SimpleCache
from src.utils.visualization import get_visualization_for_results
from src.utils.forecast_detector import is_forecast_query
from src.utils.forecast_executor import execute_forecast

# Initialize caches
insight_cache = SimpleCache(max_size=100, ttl=3600)

# Set up logging
logger = logging.getLogger('query_processor')

def process_query(query: str) -> Dict[str, Any]:
    start_time = time.time()
    
    # Lazy import to avoid circular dependencies
    def update_stats(stat_type, name):
        # Only import when the function is called
        import importlib
        try:
            app_module = importlib.import_module("app")
            
            if stat_type == "tool":
                if hasattr(app_module, "increment_tool_usage"):
                    app_module.increment_tool_usage(name)
            elif stat_type == "routing":
                if hasattr(app_module, "increment_routing_decision"):
                    app_module.increment_routing_decision(name)
            else:
                if hasattr(app_module, "increment_stat"):
                    app_module.increment_stat(name)
        except (ImportError, AttributeError) as e:
            logger.warning(f"Could not update stats: {str(e)}")
    
    # Check if this query is in the cache
    cached_result = query_cache.get(query)
    if cached_result:
        logger.info(f"Using cached result for query: {query[:50]}...")
        return cached_result
    
    # Check if this is a forecast query
    is_forecast, forecast_params = is_forecast_query(query)
    
    if is_forecast and forecast_params:
        logger.info(f"Detected forecast query with parameters: {forecast_params}")
        
        # Update tool usage stats
        update_stats("tool", "forecast")
        
        # Execute forecast directly
        forecast_result = execute_forecast(forecast_params, query)
        
        # If there was an error, return it
        if "error" in forecast_result:
            return {
                "type": "error",
                "error": forecast_result["error"],
                "execution_time": time.time() - start_time
            }
        
        # Format the result in a standard structure
        result = {
            "type": "database",  # Keep as database type for compatibility with client
            "results": forecast_result.get("results"),
            "insights": forecast_result.get("insights"),
            "plan": {"steps": [{"id": "forecast", "description": "Forecast query", "sql": forecast_result.get("sql")}]},
            "visualization": forecast_result.get("visualization"),
            "execution_time": time.time() - start_time,
            "metadata": {  # Store in metadata to avoid breaking client
                "server_used": "emissions_server"
            }
        }
        
        # Update routing decision stats
        update_stats("routing", "emissions_server")
        
        # Don't cache forecast results as they should be recalculated each time
        return result
    
    # If not a forecast query, proceed with standard processing
    try:
        # Step 1: Classify the query and get a plan or answer
        classification = classify_and_plan(query)
        
        # Update server selection stats
        update_stats("stat", "server_selection_requests")
        
        # Check if classifier returned an error
        if "error" in classification:
            logger.error(f"Error from classifier: {classification['error']}")
            return handle_error(classification['error'], start_time)
        
        # Validate the classification before proceeding or caching
        if not is_valid_classification(classification):
            logger.warning(f"Invalid classification response, not caching: {classification}")
            return handle_error("Invalid response format from ClimateGPT", start_time)
        
        if classification.get("query_type") == "general_knowledge":
            # Handle general knowledge questions
            update_stats("tool", "insight_generation")
            update_stats("routing", "climategpt_api")
            
            result = {
                "type": "general_knowledge",
                "answer": classification.get("answer", "I don't have specific information on that topic."),
                "execution_time": time.time() - start_time,
                "metadata": {  # Store in metadata to avoid breaking client
                    "server_used": "climategpt_api"
                }
            }
        else:
            # Handle database queries
            update_stats("tool", "query_processing")
            update_stats("tool", "database_access")
            update_stats("routing", "emissions_server")
            
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
            
            # Check if results can be visualized
            visualization = None
            forecast_metadata = None
            
            # If this is a database result with forecast metadata
            if "forecast_metadata" in execution_result:
                forecast_metadata = execution_result["forecast_metadata"]
            
            if "results" in execution_result:
                update_stats("tool", "visualization")
                visualization = get_visualization_for_results(
                    execution_result["results"], 
                    query,
                    forecast_metadata
                )
                
                # If we have visualization, update insights to include visualization reference
                if visualization and "insights" in execution_result:
                    execution_result["insights"] = _enhance_insights_with_visualization(
                        execution_result["insights"], 
                        visualization["type"],
                        visualization["title"]
                    )
            
            # Add execution time and type
            result = {
                "type": "database",
                "results": execution_result.get("results"),
                "insights": execution_result.get("insights"),
                "plan": {"steps": steps},
                "execution_time": time.time() - start_time,
                "metadata": {  # Store in metadata to avoid breaking client
                    "server_used": "emissions_server" 
                }
            }
            
            # Add visualization if available
            if visualization:
                result["visualization"] = visualization
                logger.info(f"Added visualization of type: {visualization['type']}")
            
            # Add forecast metadata if this was a forecast
            if forecast_metadata:
                result["forecast_metadata"] = forecast_metadata
        
        # Only cache successful results
        query_cache.set(query, result)
        return result
        
    except Exception as e:
        logger.error(f"Error in query processing: {str(e)}")
        return handle_error(f"Query processing error: {str(e)}", start_time)
    
def _enhance_insights_with_visualization(insights: str, viz_type: str, viz_title: str) -> str:
    """
    Enhance insights text with references to the visualization.
    
    Args:
        insights: Original insights text
        viz_type: Type of visualization
        viz_title: Title of visualization
        
    Returns:
        Enhanced insights text
    """
    # Don't modify if insights are empty or just whitespace
    if not insights or insights.strip() == "":
        return insights
    
    # Map visualization types to readable formats
    viz_type_display = {
        "line": "line chart",
        "bar": "bar chart",
        "bar_horizontal": "horizontal bar chart",
        "pie": "pie chart",
    }.get(viz_type, "visualization")
    
    # Add a reference to the visualization at the end
    visualization_reference = f"\n\nThe {viz_type_display} titled '{viz_title}' provides a visual representation of these findings."
    
    return insights + visualization_reference