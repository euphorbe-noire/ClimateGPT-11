# climate_server/app.py
#!/usr/bin/env python
"""
FastAPI server for ClimateGPT.

This script provides a RESTful API interface to interact with the ClimateGPT system,
allowing clients to submit natural language queries and receive responses.
"""

# Standard library imports
import os
import sys
import time
import logging
import base64

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Third-party imports
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
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
    description="API for querying climate data and knowledge",
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
    visualization: Optional[str] = None  # Base64 encoded image
    error: Optional[str] = None
    message: Optional[str] = None
    execution_time: Optional[float] = None
    plan: Optional[Dict[str, Any]] = None

class StatusResponse(BaseModel):
    status: str
    message: str
    version: str
    stats: Optional[Dict[str, Any]] = None

# Track server statistics
SERVER_STATS = {
    "total_requests": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "db_queries": 0,
    "knowledge_queries": 0,
}

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
    """
    Process a natural language query and return results.
    
    This endpoint handles both database queries and general knowledge questions
    using ClimateGPT for classification, planning, and insight generation.
    """
    start_time = time.time()
    
    # Update server stats
    SERVER_STATS["total_requests"] += 1
    
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
            SERVER_STATS["knowledge_queries"] += 1
            SERVER_STATS["successful_queries"] += 1
            
            return QueryResponse(
                result={"answer": result.get("answer", "")},
                execution_time=time.time() - start_time
            )
        
        elif result.get("type") == "database":
            SERVER_STATS["db_queries"] += 1
            
            if "error" in result:
                SERVER_STATS["failed_queries"] += 1
                return QueryResponse(
                    error=result["error"],
                    message="Database query execution failed",
                    execution_time=time.time() - start_time
                )
            
            # Success case
            SERVER_STATS["successful_queries"] += 1
            
            # Extract SQL if available
            plan = result.get("plan", {})
            final_sql = ""
            
            if plan and "steps" in plan and plan["steps"]:
                final_step = plan["steps"][-1]
                final_sql = final_step.get("sql", "")
                
            
            return QueryResponse(
                sql=final_sql,
                result=result.get("results", {}),
                insight=result.get("insights", ""),
                visualization=result.get("visualization"),  # Include visualization if available
                plan=result.get("plan"),
                execution_time=time.time() - start_time
            )
        
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
    # Include the visualization cache
    visualization_cache = query_processor.visualization_cache
    
    # Clear the caches
    query_count = query_cache.size()
    insight_count = insight_cache.size()
    visualization_count = visualization_cache.size()
    
    query_cache.clear()
    insight_cache.clear()
    visualization_cache.clear()
    
    return StatusResponse(
        status="success",
        message=f"Cache purged successfully. Cleared {query_count} queries, {insight_count} insights, and {visualization_count} visualizations.",
        version="0.1.0"
    )
# Add this new endpoint to your app.py file
@app.post("/visualize")
async def generate_visualization(request: dict):
    """Generate a visualization for the provided data."""
    logger.info("Visualization endpoint called")
    
    if not request:
        logger.error("Empty request received")
        return {"error": "Empty request"}
        
    if "data" not in request:
        logger.error("Request missing data field")
        return {"error": "Request missing data field"}
    
    try:
        query = request.get("query", "Visualize the data")
        data = request.get("data")
        
        logger.info(f"Visualization request for query: {query}")
        logger.info(f"Data structure: {type(data)}")
        
        if isinstance(data, dict):
            logger.info(f"Data keys: {list(data.keys())}")
        
        # Import the visualization generator
        from src.mcp_server.visualization_generator import create_visualization
        
        # Generate the visualization
        logger.info("Calling create_visualization function")
        visualization_bytes = create_visualization(query, data)
        
        if visualization_bytes:
            logger.info(f"Visualization generated, size: {len(visualization_bytes)} bytes")
            # Convert to base64 for transmission
            visualization = base64.b64encode(visualization_bytes).decode('utf-8')
            return {"visualization": visualization}
        else:
            logger.error("create_visualization returned None")
            return {"error": "Failed to generate visualization"}
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in visualization generation: {error_msg}", exc_info=True)
        return {"error": f"Visualization error: {error_msg}"}
    
@app.post("/visualize")
async def generate_visualization(request: dict):
    """Generate a visualization for the provided data."""
    logger.info("Visualization endpoint called")
    
    if not request:
        logger.error("Empty request received")
        return {"error": "Empty request"}
        
    if "data" not in request:
        logger.error("Request missing data field")
        return {"error": "Request missing data field"}
    
    try:
        query = request.get("query", "Visualize the data")
        data = request.get("data")
        
        logger.info(f"Visualization request for query: {query}")
        logger.info(f"Data structure: {type(data)}")
        
        if isinstance(data, dict):
            logger.info(f"Data keys: {list(data.keys())}")
        
        # Import the visualization generator
        from src.mcp_server.visualization_generator import create_visualization
        
        # Generate the visualization
        logger.info("Calling create_visualization function")
        visualization_bytes = create_visualization(query, data)
        
        if visualization_bytes:
            logger.info(f"Visualization generated, size: {len(visualization_bytes)} bytes")
            # Convert to base64 for transmission
            visualization = base64.b64encode(visualization_bytes).decode('utf-8')
            return {"visualization": visualization}
        else:
            logger.error("create_visualization returned None")
            return {"error": "Failed to generate visualization"}
            
    except Exception as e:
        logger.error(f"Error in visualization generation: {str(e)}", exc_info=True)
        return {"error": f"Visualization error: {str(e)}"}
    
if __name__ == "__main__":
    # Start the FastAPI server
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)