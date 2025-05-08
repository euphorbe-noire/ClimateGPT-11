from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
import json
import time
import logging

# Import configuration and utilities directly
from emissions_server.src.config import ERROR_HISTORY_LIMIT
from emissions_server.src.mcp_server.db_access import get_table_stats
from emissions_server.src.mcp_server.query_processor import process_query
from emissions_server.src.mcp_server.query_check import check_query

# Set up simple logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='climatemcp.log',
    filemode='a'
)
logger = logging.getLogger('mcp_server')

server = Server("climatemcp")

# Keep track of successful and failed queries
QUERY_STATS = {
    "total_requests": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "average_response_time": 0,
    "recent_errors": []
}

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Lists available tools."""
    return [
        types.Tool(
            name="query-database",
            description="Generate and execute a SQL query on the climate database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "User's natural language query"}
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get-database-stats",
            description="Get statistics about the climate database.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """
    Handles tool calls by routing to the appropriate handler function.
    
    Args:
        name: Tool name to call
        arguments: Dictionary of arguments for the tool
        
    Returns:
        List of text content responses
    """
    # Update query stats
    QUERY_STATS["total_requests"] += 1
    start_time = time.time()
    
    try:
        # Route to the appropriate handler based on tool name
        if name == "get-database-stats":
            return await handle_database_stats()
            
        elif name == "query-database":
            if not arguments or "query" not in arguments:
                return [types.TextContent(
                    type="text", 
                    text="Error: Invalid tool call or missing query parameter."
                )]
            
            return await handle_database_query(arguments["query"], start_time)
            
        else:
            return [types.TextContent(
                type="text", 
                text="Error: Invalid tool name. Available tools: get-database-stats, query-database"
            )]
            
    except Exception as e:
        # Catch any unexpected errors at the top level
        return handle_generic_error(e, start_time)

async def handle_database_stats() -> list[types.TextContent]:
    """Handle requests for database statistics."""
    stats = get_table_stats()
    
    # Format stats as a string
    stats_text = "### Climate Database Statistics\n\n"
    stats_text += "Table | Rows | Columns\n"
    stats_text += "------|------|--------\n"
    
    for table_name, table_stats in stats.items():
        if isinstance(table_stats, dict) and "error" not in table_stats:
            stats_text += f"{table_name} | {table_stats.get('rows', 'N/A')} | {table_stats.get('columns', 'N/A')}\n"
    
    # Add year range if available
    if "Emissions" in stats and "year_range" in stats["Emissions"]:
        min_year, max_year = stats["Emissions"]["year_range"]
        stats_text += f"\n### Data Coverage\n\nYears: {min_year} to {max_year}\n"
    
    return [types.TextContent(type="text", text=stats_text)]

async def handle_database_query(query: str, start_time: float) -> list[types.TextContent]:
    """Handle database query execution and results analysis."""
    # Log the incoming query
    logger.info(f"Processing query: {query}")
    
    # First check if the query is valid
    is_valid, error_message = check_query(query)
    if not is_valid:
        QUERY_STATS["failed_queries"] += 1
        return [types.TextContent(
            type="text", 
            text=f"Error: {error_message}"
        )]
    
    # Process the query using our LLM-powered processor
    result = process_query(query)
    
    if result.get("type") == "error" or "error" in result:
        QUERY_STATS["failed_queries"] += 1
        return [types.TextContent(
            type="text", 
            text=f"Error: {result.get('error', 'Unknown error')}"
        )]
    
    # Handle different types of results
    if result.get("type") == "general_knowledge":
        QUERY_STATS["successful_queries"] += 1
        update_response_time(start_time)
        
        return [types.TextContent(
            type="text", 
            text=result.get("answer", "No answer provided")
        )]
    
    # Handle database query result
    QUERY_STATS["successful_queries"] += 1
    update_response_time(start_time)
    
    # Get the SQL for display purposes
    plan = result.get("plan", {})
    sql_display = ""
    
    if plan and "steps" in plan and plan["steps"]:
        steps = plan["steps"]
        if len(steps) == 1:
            # Don't truncate the SQL query
            sql_display = f"SQL Query:\n```sql\n{steps[0].get('sql', '')}\n```\n\n"
        else:
            sql_display = "Multi-step query plan:\n"
            for i, step in enumerate(steps):
                sql_display += f"Step {i+1}: {step.get('description', 'No description')}\n"
                # Don't truncate SQL in multi-step queries either
                sql_display += f"```sql\n{step.get('sql', '')}\n```\n\n"
    
    # Format the results
    results_display = ""
    result_data = result.get("results", {})
    if isinstance(result_data, dict) and "data" in result_data and "columns" in result_data:
        row_count = len(result_data["data"])
        results_display = f"Query returned {row_count} rows\n"
        
        # For small result sets, show sample data
        if row_count > 0 and row_count <= 5:
            results_display += "\nSample data:\n```\n"
            # Show column headers
            results_display += " | ".join(result_data["columns"]) + "\n"
            results_display += "-" * (sum(len(col) for col in result_data["columns"]) + (3 * (len(result_data["columns"]) - 1))) + "\n"
            
            # Show rows
            for row in result_data["data"]:
                results_display += " | ".join(str(cell) for cell in row) + "\n"
            results_display += "```\n"
    
    # Include insights
    insights = result.get("insights", "")
    
    # Construct response
    response_parts = []
    
    if sql_display:
        response_parts.append(types.TextContent(type="text", text=sql_display))
    
    if results_display:
        response_parts.append(types.TextContent(type="text", text=results_display))
    
    if insights:
        response_parts.append(types.TextContent(
            type="text", 
            text=f"📊 **Climate Data Insights:**\n\n{insights}"
        ))
    
    if not response_parts:
        response_parts.append(types.TextContent(
            type="text", 
            text="The query was processed but didn't return any results or insights."
        ))
    
    return response_parts

def handle_generic_error(e: Exception, start_time: float) -> list[types.TextContent]:
    """Handle top-level unhandled exceptions."""
    QUERY_STATS["failed_queries"] += 1
    error_code = f"CGP-{hash(str(e)) % 10000:04d}"
    logger.error(f"Top-level error: {str(e)}")
    
    update_response_time(start_time)
    
    return [types.TextContent(
        type="text", 
        text=f"A system error occurred. Please try again later. (Error code: {error_code})"
    )]

def update_response_time(start_time: float) -> None:
    """Update the average response time in stats."""
    end_time = time.time()
    QUERY_STATS["average_response_time"] = (
        (QUERY_STATS["average_response_time"] * (QUERY_STATS["total_requests"] - 1)) + 
        (end_time - start_time)
    ) / QUERY_STATS["total_requests"]

def log_error(query: str, error: str, error_code: str = None) -> None:
    """Log error information and update error stats."""
    error_info = {
        "query": query, 
        "error": error,
        "timestamp": time.time()
    }
    
    if error_code:
        error_info["error_code"] = error_code
        
    QUERY_STATS["recent_errors"].append(error_info)
    
    # Limit the size of recent errors list
    if len(QUERY_STATS["recent_errors"]) > ERROR_HISTORY_LIMIT:
        QUERY_STATS["recent_errors"] = QUERY_STATS["recent_errors"][-ERROR_HISTORY_LIMIT:]

async def main():
    """Main server entry point."""
    logger.info("Starting ClimateMCP server")
    
    try:
        # Check if database is accessible on startup
        stats = get_table_stats()
        logger.info(f"Database statistics: {json.dumps(stats)}")
    except Exception as e:
        logger.error(f"Failed to access database on startup: {str(e)}")
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("Server loaded. Waiting for requests...")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="climatemcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )