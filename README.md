# ClimateGPT - LLM-Powered Climate Data Analysis

This repository contains a modular, LLM-powered version of the ClimateGPT system that allows users to query climate data and get climate information using natural language. The system features enhanced MCP (Model Context Protocol) integration for powerful tool-based interactions.

## System Architecture

The system consists of these main components:

1. **Multiple MCP Servers**: Specialized servers for different climate domains (Emissions, Sea Level, Wildfires)
2. **FastAPI Middleware**: REST API layers that handle HTTP requests for each server
3. **Unified Client**: A command-line interface with intelligent query routing
4. **Router Module**: Routes queries to the appropriate specialized server based on content

```
                                        ┌─────────────────────┐
                                   ┌───▶│ Emissions MCP Server│
                                   │    └─────────────────────┘
┌─────────────┐    Query    ┌──────┴───┐
│  Unified    │───Routing──▶│  Router  │    ┌─────────────────────┐
│   Client    │◀────────────|  Module  │───▶│ Sea Level MCP Server│
└─────────────┘             └──────┬───┘    └─────────────────────┘
                                   │
                                   │    ┌─────────────────────┐
                                   └───▶│ Wildfires MCP Server│
                                        └─────────────────────┘
```

Each specialized server handles domain-specific climate data and analysis, while the router intelligently directs queries to the most appropriate server. The unified client provides a consistent interface regardless of which backend server processes the request.

## Key Features

- **Natural Language Queries**: Ask questions in plain English about climate data and topics
- **MCP Tool Framework**: Leverages structured tool-based architecture for more predictable and robust query processing
- **LLM-Powered Analysis**: Uses ClimateGPT API for query understanding, classification, and insight generation
- **Hybrid Answers**: Combines database results with climate knowledge for comprehensive responses
- **Automatic SQL Generation**: No need to write SQL - the LLM translates natural language to database queries
- **Interactive CLI Interface**: User-friendly command-line tool with rich formatting and visualization
- **ARIMA-Based Forecasting**: Statistical time series forecasting with confidence intervals in the emissions server
- **Multi-Server Ecosystem**: Unified client can connect to specialized servers (Emissions, Sea Level, Wildfires)
- **In-Memory Caching**: Performance optimization with query result and insight caching

## Setup Instructions

### 1. Prerequisites

- Python 3.9 or higher (required for type annotation features)
- SQLite3 (included with Python)
- Git

### 2. Clone the Repository

```bash
git clone https://github.com/newsconsole/GMU_DAEN_2025_01_D.git
cd climategpt
```

### 3. Create and Activate a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Running the System

#### Start all (a) Server(s)

```bash
# Start the emissions server
cd emissions_server
python start_server.py

# Or start the sea level data server
cd sea_level_server
python start_server.py

# Or start the wildfires server
cd wildfires_server
python start_server.py
```

#### Start the Unified Client (in a separate terminal)

```bash
cd unified_client
python start_client.py
```

## Using the System

### CLI Commands

The interactive CLI supports the following commands:

- **Climate Questions**: Ask any climate-related question
- **Database Queries**: Ask about emissions data in the database
- **Forecasting Queries**: Request future projections based on historical data
- `help` - Display help and example queries
- `stats` - Show server statistics (database tables, rows, etc.)
- `servers` - List available climate servers and their capabilities
- `purge` - Clear the server's in-memory cache for query results and insights
- `clear` - Clear the screen
- `exit` or `quit` - Exit the application

### Example Queries

```
What is climate change?
How much CO2 was emitted globally from 2010 to 2020?
Which greenhouse gas showed the most significant increase over the past decade?
Compare emissions between California and Texas from 2015 to 2020
What sectors had the highest emissions in 2020?
Forecast CO2 emissions for the next 10 years
Predict methane emissions through 2035
```

## Data Coverage

The system includes specialized databases for different climate aspects:

### Emissions Server
- **Time Period**: 1990 to 2022
- **Greenhouse Gases**: CO2, CH4, N2O, HFCs, PFCs, SF6, and others
- **Geography**: 63 regions including US states and territories
- **Sectors**: Transportation, Industrial, Energy, Agriculture, and more

### Sea Level Server
- **Time Period**: 1900 to present
- **Data Types**: Global mean sea level, regional variations, rates of change

### Wildfires Server
- **Time Period**: 2000 to present
- **Geography**: Global wildfire occurrences with regional focus
- **Metrics**: Frequency, area burned, intensity, and duration

## How It Works

The ClimateGPT system leverages the MCP architecture to:

1. **Process Queries via Tools**: Each capability is encapsulated as a tool with clear inputs/outputs
2. **Execute Structured Plans**: Multi-step plans for handling complex queries
3. **Generate Optimized SQL**: Create database queries from natural language with schema awareness
4. **Provide Visualizations**: Automatically generate appropriate visualizations based on data patterns
5. **Generate Insights**: Provide meaningful analysis of data results through the ClimateGPT API
6. **Forecast Future Trends**: Use ARIMA time series modeling to project climate metrics

When a user submits a query through the unified client:
1. The router.py module analyzes the query content and selects the appropriate specialized server
2. The query is sent to the chosen server via HTTP
3. The server uses the ClimateGPT API to classify the query and generate an execution plan
4. For database queries, SQL is generated and executed against the SQLite database
5. For forecasting queries, ARIMA models analyze historical data to predict future trends
6. Visualization code is generated on the server and executed on the client
7. Results, insights, and visualizations are returned to the client for display

## Project Structure

```
.
├── README.md                     # This File
├── docs/                         # Detailed documentation directory
│   ├── ARCHITECTURE.md           # Technical architecture details
│   ├── DATABASE_GUIDE.md         # Database documentation
│   ├── DEVELOPMENT.md            # Developer-focused guide
│   ├── DOCUMENTATION.md          # Comprehensive system documentation
│   └── USER_GUIDE.md             # User-focused guide
├── emissions_server/             # Greenhouse gas emissions server
│   ├── __init__.py
│   ├── app.py                    # FastAPI server with RESTful endpoints
│   ├── logs/                     # Server log directory
│   │   └── emissions_server.log
│   ├── requirements.txt          # Server-specific dependencies
│   ├── src/
│   │   ├── __init__.py
│   │   ├── config.py             # Configuration settings
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── ClimateGPT.db     # Emissions SQLite database
│   │   │   └── Emissions.sql     # Database schema definition
│   │   ├── mcp_server/           # MCP server implementation
│   │   │   ├── __init__.py
│   │   │   ├── cache_utils.py    # Memory cache implementation
│   │   │   ├── db_access.py      # Database interaction
│   │   │   ├── insight_generator.py # Insight generation
│   │   │   ├── query_check.py    # Query validation
│   │   │   ├── query_classifier.py # Query classification
│   │   │   ├── query_executor.py # Query execution
│   │   │   ├── query_processor.py # Query processing
│   │   │   ├── query_utils.py    # Utility functions for queries
│   │   │   ├── retry_utils.py    # Retry mechanism
│   │   │   ├── schema_tools.py   # Schema access tools
│   │   │   └── server.py         # MCP server core
│   │   └── utils/                # Utility functions
│   │       ├── __init__.py
│   │       ├── arima_forecaster.py # Time series forecasting
│   │       ├── forecast_detector.py # Detect forecast queries
│   │       ├── forecast_executor.py # Execute forecasts
│   │       ├── logging_setup.py  # Logging configuration
│   │       ├── visualization_templates.py # Visualization templates
│   │       └── visualization.py  # Visualization generation
│   └── start_server.py           # Server startup script
├── sea_level_server/             # Sea level data server
│   ├── __init__.py
│   ├── app.py                    # FastAPI server for sea level data
│   ├── logs/                     # Server log directory
│   │   └── sea_level_server.log
│   ├── requirements.txt          # Server-specific dependencies
│   ├── src/
│   │   ├── __init__.py
│   │   ├── config.py             # Configuration settings
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   └── Sea_Level_data.db # Sea level SQLite database
│   │   ├── mcp_server/           # MCP implementation for sea level data
│   │   │   ├── __init__.py
│   │   │   ├── cache_utils.py
│   │   │   ├── db_access.py
│   │   │   ├── insight_generator.py
│   │   │   ├── query_check.py
│   │   │   ├── query_classifier.py
│   │   │   ├── query_executor.py
│   │   │   ├── query_processor.py
│   │   │   ├── query_utils.py
│   │   │   ├── retry_utils.py
│   │   │   ├── schema_tools.py
│   │   │   ├── server.py
│   │   │   └── visualization_generator.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── logging_setup.py
│   └── start_server.py           # Sea level server startup script
├── Wildfires_server/             # Wildfire data server
│   ├── __init__.py
│   ├── app.py                    # FastAPI server for wildfire data
│   ├── logs/                     # Server log directory
│   │   └── Wildfires_server.log
│   ├── requirements.txt          # Server-specific dependencies
│   ├── src/
│   │   ├── __init__.py
│   │   ├── config.py             # Configuration settings
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── Emissions.sql
│   │   │   └── fire_data.db      # Wildfires SQLite database
│   │   ├── mcp_server/           # MCP implementation for wildfire data
│   │   │   ├── __init__.py
│   │   │   ├── cache_utils.py
│   │   │   ├── db_access.py
│   │   │   ├── insight_generator.py
│   │   │   ├── query_check.py
│   │   │   ├── query_classifier.py
│   │   │   ├── query_executor.py
│   │   │   ├── query_processor.py
│   │   │   ├── query_utils.py
│   │   │   ├── retry_utils.py
│   │   │   ├── schema_tools.py
│   │   │   └── server.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── arima_forecaster.py
│   │       ├── forecast_detector.py
│   │       ├── forecast_executor.py
│   │       ├── logging_setup.py
│   │       ├── visualization_templates.py
│   │       └── visualization.py
│   └── start_server.py           # Wildfires server startup script
├── unified_client/              # Cross-server client interface
│   ├── cli.py                   # Rich interactive CLI
│   ├── config.py                # Client configuration
│   ├── logging_setup.py         # Client logging
│   ├── logs/                    # Client log directory
│   │   └── climate_client.log
│   ├── requirements.txt         # Client-specific dependencies
│   ├── router.py                # Query routing intelligence
│   ├── server_registry.json     # Server registration and capabilities
│   └── start_client.py          # Client startup script
├── climate_visualization.png    # Generated visualization file
├── climatemcp.log               # Main system log
├── project_structure.txt        # Current file
└── pyproject.toml               # Python project configuration
```

## Troubleshooting

### Common Issues

1. **Connection Refused Error**:
   - Make sure the relevant server is running (default: http://127.0.0.1:8000)
   - Check for any startup errors in the terminal

2. **Database Not Found**:
   - Verify the database path in the server's `src/config.py`
   - Make sure the file exists and has appropriate permissions
   - Default paths: `src/database/ClimateGPT.db`, `src/database/Sea_Level_data.db`, or `src/database/fire_data.db`

3. **ClimateGPT API Authentication Issues**:
   - Check the API credentials in `src/config.py` (CLIMATEGPT_USER, CLIMATEGPT_PASSWORD)
   - Verify the API URLs (CLIMATEGPT_API_URL, CLIMATEGPT_BACKUP_API_URL)
   - The system relies on the ClimateGPT API for query classification and insight generation

4. **Server Won't Start**:
   - Check log files for errors (server log: `climatemcp.log` in server root, client log: `logs/climate_client.log`)
   - Ensure all dependencies are installed
   - Try starting components individually for more detailed error messages

5. **MCP Communication Errors**:
   - Verify that the server implementation includes the required MCP endpoints
   - Check server logs for execution errors in tool calls

6. **Visualization Not Rendering**:
   - Make sure matplotlib is installed (`pip install matplotlib`)
   - The CLI generates visualizations on the client side using code provided by the server
   - Check permissions for saving visualization files

## Development and Documentation

The ClimateGPT system includes comprehensive documentation to help you understand, use, and extend the system:

- [DOCUMENTATION.md](DOCUMENTATION.md) - Comprehensive system documentation
- [USER_GUIDE.md](USER_GUIDE.md) - Guide for end users
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture details
- [DEVELOPMENT.md](DEVELOPMENT.md) - Guide for developers

### Extending the System

To add new features or servers, see the [Developer Guide](DEVELOPMENT.md) which includes:

- Adding new specialized servers
- Creating new tools within the MCP framework
- Extending the database schema
- Modifying the visualization system
