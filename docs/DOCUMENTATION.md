# ClimateGPT Documentation

This documentation provides a comprehensive overview of the ClimateGPT system architecture, components, and workflows.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Component Overview](#component-overview)
3. [Data Flow](#data-flow)
4. [Server Components](#server-components)
5. [Client Component](#client-component)
6. [MCP Architecture](#mcp-architecture)
7. [Database Schema](#database-schema)
8. [API Reference](#api-reference)
9. [Development Guide](#development-guide)

## System Architecture

ClimateGPT is built on a modular, multi-server architecture with a central router component:

```
                                         ┌─────────────────────┐
                                    ┌───▶│ Emissions MCP Server│
                                    │    └─────────────────────┘
┌─────────────┐    Query    ┌──────┴───┐
│  Unified    │───Routing──▶│  Router  │    ┌─────────────────────┐
│   Client    │◀─────────────  Module  │───▶│ Sea Level MCP Server│
└─────────────┘             └──────┬───┘    └─────────────────────┘
                                    │
                                    │    ┌─────────────────────┐
                                    └───▶│ Wildfires MCP Server│
                                         └─────────────────────┘
```

### Key Architectural Features

- **Microservices Design**: Each data domain has its own specialized server
- **Centralized Routing**: The router dynamically directs queries to the appropriate server
- **MCP Protocol**: All servers implement the Model Context Protocol for tool-based interactions
- **Unified Client**: A single CLI interface connects to all servers through the router

## Component Overview

### Server Components

1. **Emissions Server**: Processes greenhouse gas emissions data and forecasts
   - Database: SQLite (`ClimateGPT.db`)
   - Primary Tables: Emissions, Greenhouse_Gases, Sectors, Geography, Fuels
   - Special Feature: ARIMA-based emissions forecasting

2. **Sea Level Server**: Analyzes sea level rise data
   - Database: SQLite (`Sea_Level_data.db`)
   - Primary Feature: Trend analysis for sea level changes

3. **Wildfires Server**: Processes wildfire occurrence and impact data
   - Database: SQLite (`fire_data.db`) 
   - Primary Feature: Spatial and temporal wildfire pattern analysis

### Client Component

- **Unified Client**: Interactive CLI that connects to all specialized servers
  - Includes the router module for query classification and routing
  - Rich text formatting for query results and visualizations
  - Matplotlib integration for client-side visualization rendering

### Support Components

- **ClimateGPT API**: External LLM API used for:
  - Query classification
  - SQL generation
  - Insight generation
  - Plan creation and execution

## Data Flow

A typical query in ClimateGPT follows this flow:

1. **Query Entry**: User enters a natural language query in the unified client
2. **Query Routing**: 
   - Router analyzes the query content
   - Router selects the appropriate specialized server
3. **Query Processing**:
   - Selected server receives the query via HTTP
   - Server uses ClimateGPT API to classify the query
   - Server generates an execution plan via MCP
4. **Data Retrieval**:
   - For database queries, SQL is generated and executed
   - For forecasts, ARIMA models analyze data and project trends
   - For general knowledge, the ClimateGPT API provides the answer
5. **Result Enhancement**:
   - Server generates insights about the results
   - Server creates visualization code if appropriate
6. **Response Display**:
   - Results are sent back through the router to the client
   - Client displays formatted results, insights, and renders visualizations

## Server Components

Each server follows a similar structure:

```
server/
├── app.py                  # FastAPI server with RESTful endpoints
├── start_server.py         # Server startup script
├── src/
│   ├── config.py           # Configuration settings
│   ├── database/           # SQLite database and schema
│   ├── mcp_server/         # MCP implementation
│   │   ├── server.py       # MCP server core
│   │   ├── db_access.py    # Database interaction
│   │   ├── query_processor.py # Query processing logic
│   │   ├── query_executor.py  # Execute database queries
│   │   ├── query_classifier.py # Classify query type
│   │   └── ...             # Other processing modules
│   └── utils/              # Utility functions
│       ├── logging_setup.py # Logging configuration
│       ├── visualization.py # Visualization generation
│       └── ...             # Other utilities
```

### Key Server Components

#### FastAPI Server (app.py)

The FastAPI server provides RESTful endpoints:

- `/query` - Process natural language queries
- `/stats` - Get server statistics and database information
- `/visualization` - Generate visualizations for data
- `/cache/purge` - Clear the query and insight cache

#### MCP Server (server.py)

The MCP server implements the Model Context Protocol with tools:

- `query-database` - Generate and execute SQL queries
- `get-database-stats` - Get database statistics
- `generate-insights` - Create insights for query results
- `create-visualization` - Generate visualization code

## Client Component

The unified client consists of:

```
unified_client/
├── cli.py                  # Interactive CLI
├── config.py               # Client configuration
├── router.py               # Query routing logic
├── server_registry.json    # Server registration
└── start_client.py         # Client startup script
```

### Router Module

The router is central to the system's functionality:

```python
# Simplified router logic
def process_query(query: str) -> Dict[str, Any]:
    """Route a query to the appropriate server."""
    # Select server based on query content
    server_name, server_config = select_server(query)
    
    # Send query to selected server
    response = query_server(server_name, server_config, query)
    
    return response

def select_server(query: str) -> Tuple[str, Dict[str, Any]]:
    """Select the appropriate server for this query."""
    # Use ClimateGPT to determine best server
    payload = {
        "model": "/cache/climategpt_8b_latest",
        "messages": [
            {"role": "system", "content": "You route climate queries to specialized servers."},
            {"role": "user", "content": f"Query: {query}"}
        ]
    }
    
    # Process the response to determine server
    # ...
```

### Server Registry

The server registry (`server_registry.json`) defines the available servers:

```json
{
  "emissions_server": {
    "url": "http://127.0.0.1:8000",
    "description": "Climate emissions data analytics and forecasting server",
    "capabilities": ["database_queries", "general_knowledge", "forecasting"],
    "keywords": ["emission", "carbon", "greenhouse", "ghg", "co2", "methane"]
  },
  "sea_level_server": {
    "url": "http://127.0.0.1:8001",
    "description": "Sea level rise data and analysis",
    "capabilities": ["database_queries", "trends"],
    "keywords": ["sea level", "ocean", "coastal", "flooding"]
  },
  "wildfires_server": {
    "url": "http://127.0.0.1:8002",
    "description": "Wildfire occurrence and impact analysis",
    "capabilities": ["database_queries", "spatial_analysis"],
    "keywords": ["fire", "wildfire", "burn", "forest fire"]
  }
}
```

## MCP Architecture

ClimateGPT leverages the Model Context Protocol (MCP) architecture for all servers. This tool-based approach provides several advantages:

### Tool Framework

Each capability is encapsulated as a discrete tool with:
- Clear input schema
- Defined output format
- Specific functionality

### Execution Engine

The MCP execution engine:
1. Plans multi-step processes for complex queries
2. Handles variable resolution between steps
3. Manages error recovery
4. Provides execution context

### Tool Examples

**Database Query Tool:**
```python
@server.call_tool()
async def handle_database_query(query: str) -> list[types.TextContent]:
    """Handle database query execution and results analysis."""
    # Process query using LLM-powered processor
    result = process_query(query)
    
    # Format results for response
    if result.get("type") == "database":
        # Format database results
        response_parts = [
            types.TextContent(type="text", text=f"SQL Query:\n{result.get('sql', '')}"),
            types.TextContent(type="text", text=f"Results:\n{format_results(result)}"),
            types.TextContent(type="text", text=f"Insights:\n{result.get('insights', '')}")
        ]
    else:
        # Format general knowledge response
        response_parts = [
            types.TextContent(type="text", text=result.get("answer", ""))
        ]
        
    return response_parts
```

## Database Schema

### Emissions Database Schema

The Emissions database contains the following tables:

#### Greenhouse_Gases Table
```sql
CREATE TABLE Greenhouse_Gases (
    ghg_id INTEGER PRIMARY KEY,
    ghg_name TEXT NOT NULL,
    ghg_category TEXT
);
```

#### Sectors Table
```sql
CREATE TABLE Sectors (
    sector_id INTEGER PRIMARY KEY,
    sector TEXT NOT NULL,
    subsector TEXT,
    category TEXT,
    sub_category_1 TEXT,
    sub_category_2 TEXT,
    sub_category_3 TEXT,
    sub_category_4 TEXT,
    sub_category_5 TEXT,
    dataset_type TEXT NOT NULL
);
```

#### Fuels Table
```sql
CREATE TABLE Fuels (
    fuel_id INTEGER PRIMARY KEY,
    fuel1 TEXT NOT NULL,
    fuel2 TEXT
);
```

#### Geography Table
```sql
CREATE TABLE Geography (
    geo_id INTEGER PRIMARY KEY,
    geo_ref TEXT NOT NULL
);
```

#### Emissions Table (Fact Table)
```sql
CREATE TABLE Emissions (
    emission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    ghg_id INTEGER,
    sector_id INTEGER,
    fuel_id INTEGER,
    geo_id INTEGER,
    emissions REAL NOT NULL,
    FOREIGN KEY (ghg_id) REFERENCES Greenhouse_Gases (ghg_id),
    FOREIGN KEY (sector_id) REFERENCES Sectors (sector_id),
    FOREIGN KEY (fuel_id) REFERENCES Fuels (fuel_id),
    FOREIGN KEY (geo_id) REFERENCES Geography (geo_id)
);
```

## API Reference

### Emissions Server API

#### Query Endpoint
```
POST /query
Content-Type: application/json

{
  "query": "What was the total CO2 emission trend from 2010 to 2020?"
}
```

Response:
```json
{
  "sql": "SELECT e.year, SUM(e.emissions) as total_emissions...",
  "result": {
    "columns": ["year", "total_emissions"],
    "data": [[2010, 5.2], [2011, 5.3], ...]
  },
  "insight": "CO2 emissions showed a steady increase from 2010 to 2020...",
  "visualization": {
    "type": "line",
    "title": "CO2 Emissions Trend (2010-2020)",
    "plot_code": "import matplotlib.pyplot as plt..."
  },
  "execution_time": 0.45
}
```

#### Statistics Endpoint
```
GET /stats
```

Response:
```json
{
  "status": "running",
  "message": "Server statistics",
  "version": "0.1.0",
  "stats": {
    "server": {
      "total_requests": 150,
      "successful_queries": 142,
      "failed_queries": 8
    },
    "database": {
      "Emissions": {
        "rows": 24500,
        "columns": 6,
        "year_range": [1990, 2022]
      },
      "Greenhouse_Gases": {
        "rows": 6,
        "columns": 3
      }
    }
  }
}
```

## Development Guide

### Setting Up a Development Environment

1. **Prerequisites**:
   - Python 3.9+
   - SQLite3
   - Git

2. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/climategpt.git
   cd climategpt
   ```

3. **Create a Virtual Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running in Development Mode

1. **Start a Server**:
   ```bash
   cd emissions_server
   python start_server.py
   ```

2. **Start the Client**:
   ```bash
   cd unified_client
   python start_client.py
   ```

### Adding a New Server

To add a new specialized server:

1. **Create a Server Directory**:
   ```bash
   mkdir new_server
   cd new_server
   ```

2. **Copy Basic Structure**:
   - Copy app.py, start_server.py from an existing server
   - Create src/ directory with config.py, database/, mcp_server/, and utils/

3. **Update Server Registry**:
   - Add your new server to server_registry.json

4. **Implement MCP Server**:
   - Create your specialized database schema
   - Implement the MCP server with appropriate tools
   - Add specialized processing logic

### Code Style Guidelines

- Follow PEP 8 for Python code styling
- Use type hints for function parameters and return values
- Document all functions, classes, and modules
- Write tests for new functionality

### Testing Guidelines

- Unit tests should be placed in a tests/ directory
- Run tests with pytest
- Aim for at least 80% code coverage
- Include both unit and integration tests

---

## Further Reading

- [README.md](README.md) - Overview and general information
- [USER_GUIDE.md](USER_GUIDE.md) - User-focused documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture details
- [DEVELOPMENT.md](DEVELOPMENT.md) - Developer-focused guide