# climate_server/app.py
#!/usr/bin/env python
"""
FastAPI server for ClimateGPT.

This script provides a RESTful API interface to interact with the ClimateGPT system,
allowing clients to submit natural language queries and receive responses with visualizations.
"""

# Standard library imports
import os
import sys
import time
import logging

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Third-party imports
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

# Local application imports - using absolute imports
import src.config as config
import src.mcp_server.db_access as db_access
import src.mcp_server.query_processor as query_processor
import src.mcp_server.query_check as query_check
import src.utils.logging_setup as logging_setup

# Configure logging
logger = logging_setup.setup_logging('api_server')

# Create FastAPI app
app = FastAPI(
    title="ClimateGPT API",
    description="API for querying climate data and knowledge with visualization support",
    version="0.1.0",
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define request and response models
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    sql: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    insight: Optional[str] = None
    visualization: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None
    execution_time: Optional[float] = None
    plan: Optional[Dict[str, Any]] = None
    
    model_config = {
        "exclude_none": True
    }

class StatusResponse(BaseModel):
    status: str
    message: str
    version: str
    stats: Optional[Dict[str, Any]] = None

class VisualizationRequest(BaseModel):
    result_data: Dict[str, Any]
    query: str

# Track server statistics
SERVER_STATS = {
    "total_requests": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "db_queries": 0,
    "knowledge_queries": 0,
    "visualization_requests": 0,
    "server_selection_requests": 0,
    "tool_usage": {
        "query_processing": 0,
        "database_access": 0,
        "forecast": 0,
        "visualization": 0,
        "insight_generation": 0
    },
    "routing_decisions": {
        "emissions_server": 0,
        "climategpt_api": 0,
        "fallback": 0
    }
}

# Add these helper functions in app.py
def increment_stat(stat_name, increment=1):
    """Increment a top-level statistic."""
    if stat_name in SERVER_STATS:
        SERVER_STATS[stat_name] += increment

def increment_tool_usage(tool_name, increment=1):
    """Increment a tool usage statistic."""
    if tool_name in SERVER_STATS["tool_usage"]:
        SERVER_STATS["tool_usage"][tool_name] += increment

def increment_routing_decision(server_name, increment=1):
    """Increment a routing decision statistic."""
    if server_name in SERVER_STATS["routing_decisions"]:
        SERVER_STATS["routing_decisions"][server_name] += increment
    else:
        SERVER_STATS["routing_decisions"]["fallback"] += increment
        
# API endpoints
@app.get("/", response_model=StatusResponse)
async def root():
    """Get server status and statistics."""
    db_stats = db_access.get_table_stats()
    
    return StatusResponse(
        status="running",
        message="ClimateGPT API is running",
        version="0.1.0",
        stats={
            "server": SERVER_STATS,
            "database": db_stats
        }
    )

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """Process a natural language query and return results."""
    start_time = time.time()
    
    # Update server stats
    increment_stat("total_requests")
    
    # Check if the query is empty
    if not request.query or request.query.strip() == "":
        return _handle_failed_query("Empty query", "Please provide a non-empty query", start_time)
    
    # Validate the query
    is_valid, error_message = query_check.check_query(request.query)
    if not is_valid:
        return _handle_failed_query(error_message, "Invalid query format", start_time)
    
    try:
        # Process the query using our LLM-powered processor
        result = query_processor.process_query(request.query)
        
        # Update stats based on query type and success
        if result.get("type") == "general_knowledge":
            increment_stat("knowledge_queries")
            increment_stat("successful_queries")
            
            # The server used info is already included in the result
            # and stats are already updated in process_query
            
            return QueryResponse(
                result={"answer": result.get("answer", "")},
                execution_time=time.time() - start_time
            )
        
        elif result.get("type") == "database":
            increment_stat("db_queries")
            
            # The server used info is already included in the result
            # and stats are already updated in process_query
            
            if "error" in result:
                increment_stat("failed_queries")
                return QueryResponse(
                    error=result["error"],
                    message="Database query execution failed",
                    execution_time=time.time() - start_time
                )
            
            # Success case
            increment_stat("successful_queries")
            
            # Extract SQL if available
            plan = result.get("plan", {})
            final_sql = ""
            
            if plan and "steps" in plan and plan["steps"]:
                final_step = plan["steps"][-1]
                final_sql = final_step.get("sql", "")
            
            response = QueryResponse(
                sql=final_sql,
                result=result.get("results", {}),
                insight=result.get("insights", ""),
                plan=result.get("plan"),
                execution_time=time.time() - start_time
            )
            
            # Add visualization if available
            if "visualization" in result:
                response.visualization = result["visualization"]
                logger.info(f"Included visualization in response")
            
            return response
        
        else:
            # Error case
            SERVER_STATS["failed_queries"] += 1
            return QueryResponse(
                error=result.get("error", "Unknown error"),
                message="Query processing failed",
                execution_time=time.time() - start_time
            )
            
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return _handle_failed_query(str(e), "An error occurred while processing your query", start_time)

@app.post("/visualization")
async def generate_visualization(request: VisualizationRequest):
    """
    Generate a visualization for provided query results.
    
    This endpoint allows generating visualizations for specific result data
    without needing to reprocess the entire query.
    """
    SERVER_STATS["visualization_requests"] += 1
    
    try:
        from src.utils.visualization import get_visualization_for_results
        
        visualization = get_visualization_for_results(request.result_data, request.query)
        
        if not visualization:
            raise HTTPException(status_code=400, detail="Data not suitable for visualization")
        
        return JSONResponse(content=visualization)
        
    except Exception as e:
        logger.error(f"Error generating visualization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating visualization: {str(e)}")

@app.get("/stats", response_model=StatusResponse)
async def get_stats():
    """Get detailed database statistics."""
    db_stats = db_access.get_table_stats()
    
    return StatusResponse(
        status="running",
        message="Server statistics",
        version="0.1.0",
        stats={
            "server": SERVER_STATS,
            "database": db_stats
        }
    )

def _handle_failed_query(error: str, message: str, start_time: float) -> QueryResponse:
    """Handle failed queries with consistent error reporting and statistics tracking."""
    SERVER_STATS["failed_queries"] += 1
    return QueryResponse(
        error=error,
        message=message,
        execution_time=time.time() - start_time
    )

@app.post("/cache/purge", response_model=StatusResponse)
async def purge_cache():
    """Purge all cached data from the server."""
    logger.info("Purging server cache")
    
    # Import cache instances
    query_cache = query_processor.query_cache
    insight_cache = query_processor.insight_cache
    
    # Clear the caches
    query_count = query_cache.size()
    insight_count = insight_cache.size()
    
    query_cache.clear()
    insight_cache.clear()
    
    return StatusResponse(
        status="success",
        message=f"Cache purged successfully. Cleared {query_count} queries and {insight_count} insights.",
        version="0.1.0"
    )

@app.get("/stats/tools")
async def get_tool_stats():
    """Get detailed statistics about tool usage and routing."""
    return {
        "tool_usage": SERVER_STATS["tool_usage"],
        "routing_decisions": SERVER_STATS["routing_decisions"],
        "server_selection_requests": SERVER_STATS["server_selection_requests"]
    }

if __name__ == "__main__":
    # Start the FastAPI server
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)