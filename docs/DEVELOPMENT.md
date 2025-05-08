# ClimateGPT Developer Guide

This guide is intended for developers who want to extend, modify, or contribute to the ClimateGPT system.

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Project Structure](#project-structure)
3. [Core Modules](#core-modules)
4. [Adding a New Server](#adding-a-new-server)
5. [Extending Functionality](#extending-functionality)
6. [Testing](#testing)
7. [Deployment](#deployment)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Development Environment Setup

### Prerequisites

- Python 3.9 or higher
- Git
- SQLite3
- A text editor or IDE (VS Code recommended with Python extensions)

### Setting Up Your Development Environment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/newsconsole/GMU_DAEN_2025_01_D.git
   cd climategpt
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables** (create a `.env` file in the project root):
   ```
   CLIMATEGPT_API_URL=https://erasmus.ai/models/climategpt_8b_latest/v1/chat/completions
   CLIMATEGPT_USER=your_username
   CLIMATEGPT_PASSWORD=your_password
   CLIMATE_SERVER_LOG_LEVEL=DEBUG  # Set to DEBUG for development
   ```

5. **Install development tools**:
   ```bash
   pip install black pytest mypy flake8
   ```

## Project Structure

The project follows a modular structure with separate servers and a unified client:

```
.
├── emissions_server/       # Greenhouse gas emissions server
│   ├── app.py              # FastAPI server
│   ├── start_server.py     # Server startup script
│   └── src/                # Server source code
│       ├── config.py       # Configuration
│       ├── database/       # Database files
│       ├── mcp_server/     # MCP implementation
│       └── utils/          # Utility functions
├── sea_level_server/       # Sea level data server
├── wildfires_server/       # Wildfire data server
├── unified_client/         # Client interface
│   ├── cli.py              # CLI implementation
│   ├── router.py           # Query routing logic
│   ├── server_registry.json # Server configuration
│   └── start_client.py     # Client startup script
```

## Core Modules

### FastAPI Server (app.py)

The FastAPI server provides RESTful endpoints and handles HTTP requests. Key functions:

```python
@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    Process a natural language query and return results with visualization if applicable.
    """
    # Implementation...
```

To modify API endpoints, edit this file.

### MCP Server (server.py)

The MCP server implements the Model Context Protocol with tools:

```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """
    Handles tool calls by routing to the appropriate handler function.
    """
    # Implementation...
```

To add new tools, modify this file.

### Query Processor (query_processor.py)

Handles the processing of natural language queries:

```python
def process_query(query: str) -> Dict[str, Any]:
    """
    Process a user query by analyzing intent and executing appropriate actions.
    """
    # Implementation...
```

This is where query classification and execution planning happens.

### Database Access (db_access.py)

Manages database connections and query execution:

```python
def execute_query(sql_query: str) -> pd.DataFrame:
    """
    Execute a SQL query and return results as a pandas DataFrame.
    """
    # Implementation...
```

Modify this for database schema changes or query optimizations.

### Router (router.py)

Handles the routing of queries to specialized servers:

```python
def select_server(query: str) -> Tuple[str, Dict[str, Any]]:
    """
    Select the appropriate server for this query.
    """
    # Implementation...
```

Modify this to change routing logic.

## Adding a New Server

To add a new specialized server to the ClimateGPT ecosystem:

### 1. Create the Server Structure

```bash
mkdir new_server
cd new_server
mkdir -p src/{database,mcp_server,utils}
touch app.py start_server.py
```

### 2. Copy Initial Files

Copy and adapt these files from an existing server:
- app.py - FastAPI server implementation
- start_server.py - Server startup script
- src/config.py - Configuration settings

### 3. Create a Database Schema

Define your SQLite schema in a SQL file:

```sql
-- src/database/new_schema.sql
CREATE TABLE IF NOT EXISTS MainTable (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    value REAL
);
```

### 4. Implement MCP Server

Create an MCP server implementation in `src/mcp_server/server.py`:

```python
from mcp.server import Server
import mcp.types as types

server = Server("new_server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Lists available tools."""
    return [
        types.Tool(
            name="query-database",
            description="Query the specialized database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls."""
    # Tool implementation...
```

### 5. Update the Server Registry

Add your server to `unified_client/server_registry.json`:

```json
{
  "new_server": {
    "url": "http://127.0.0.1:8003",
    "description": "Specialized server for new data domain",
    "capabilities": ["database_queries", "general_knowledge"],
    "keywords": ["keyword1", "keyword2"]
  }
}
```

## Extending Functionality

### Adding a New Tool

To add a new tool to an existing server:

1. Define the tool in `server.py`:

```python
types.Tool(
    name="new-tool",
    description="Description of what the tool does",
    inputSchema={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Parameter description"}
        },
        "required": ["param1"],
    },
)
```

2. Implement the tool handler:

```python
async def handle_new_tool(param1: str) -> list[types.TextContent]:
    """Handle the new tool functionality."""
    # Tool implementation...
    return [types.TextContent(type="text", text="Result")]
```

3. Add the tool to the handler function:

```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls."""
    if name == "new-tool":
        return await handle_new_tool(arguments.get("param1", ""))
    # Other tool handlers...
```

### Adding a New API Endpoint

To add a new endpoint to the FastAPI server:

1. Define the request and response models:

```python
class NewRequest(BaseModel):
    parameter: str

class NewResponse(BaseModel):
    result: str
    status: str
```

2. Implement the endpoint:

```python
@app.post("/new-endpoint", response_model=NewResponse)
async def handle_new_endpoint(request: NewRequest):
    """Handle a new type of request."""
    # Implementation...
    return NewResponse(result="Success", status="completed")
```

## Testing

### Unit Testing

Create tests in a `tests` directory for each component:

```python
# tests/test_query_processor.py
import pytest
from src.mcp_server.query_processor import process_query

def test_process_query():
    """Test that query processing works correctly."""
    result = process_query("What is climate change?")
    assert result is not None
    assert "type" in result
    assert result["type"] in ["general_knowledge", "database"]
```

### Running Tests

Run tests with pytest:

```bash
pytest
```

### Test Coverage

Check test coverage:

```bash
pytest --cov=src
```

## Deployment

### Local Deployment

Run individual servers:

```bash
cd emissions_server
python start_server.py
```

Run the client:

```bash
cd unified_client
python start_client.py
```

### Documentation

Document all functions, classes, and modules:

```python
def function_name(param1: str, param2: int) -> Dict[str, Any]:
    """
    Short description of what the function does.
    
    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When and why this exception is raised
    """
    # Implementation...
```

### Error Handling

Use proper error handling:

```python
try:
    result = potentially_failing_function()
except SpecificException as e:
    logger.error(f"Specific error occurred: {str(e)}")
    # Handle specific exception
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}")
    # Handle general exception
finally:
    # Cleanup code
```

### Logging

Use structured logging:

```python
import logging

logger = logging.getLogger("module_name")

def function():
    logger.info("Starting operation", extra={"operation_id": 123})
    try:
        # Code...
        logger.debug("Intermediate step", extra={"step": "processing"})
    except Exception as e:
        logger.error("Operation failed", exc_info=True, extra={"error_code": 500})
```

## Troubleshooting

### Common Development Issues

#### API Connection Issues

If you can't connect to the API:

1. Check if the server is running
2. Verify the URL in server_registry.json
3. Check for firewall or network issues
4. Look for error messages in the server logs

#### Database Errors

If you encounter database errors:

1. Check if the database file exists
2. Verify permissions on the database file
3. Check SQL syntax in your queries
4. Look for schema migration issues

#### MCP Communication Errors

If MCP tools aren't working:

1. Check if the MCP server is properly initialized
2. Verify tool registration in server.py
3. Check input parameter validation
4. Look for serialization/deserialization issues

### Debugging Techniques

1. **Increase Log Level**: Set `CLIMATE_SERVER_LOG_LEVEL=DEBUG` in your .env file
2. **Use Debugger**: Add breakpoints in your IDE
3. **Print Intermediate Values**: Add debug logging
4. **Check Request/Response**: Use tools like Postman to test API endpoints