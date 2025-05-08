# ClimateGPT User Guide

Welcome to ClimateGPT! This guide will help you get started and make the most of this powerful climate data analysis system.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Command-Line Interface](#command-line-interface)
3. [Query Types](#query-types)
4. [Example Queries](#example-queries)
5. [Visualizations](#visualizations)
6. [Forecasting](#forecasting)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Features](#advanced-features)
9. [FAQ](#faq)

## Getting Started

### Installation

Follow these steps to set up ClimateGPT on your system:

1. **Prerequisites**:
   - Python 3.9 or higher
   - SQLite3 (included with Python)
   - Git

2. **Clone the Repository**:
   ```bash
   git clone https://github.com/newsconsole/GMU_DAEN_2025_01_D.git
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

### Starting the System

The ClimateGPT system consists of multiple servers and a unified client. You'll need to:

1. **Start the Servers**:
   
   Start the emissions server:
   ```bash
   cd emissions_server
   python start_server.py
   ```
   
   In separate terminal windows, start the other servers (if needed):
   ```bash
   cd sea_level_server
   python start_server.py
   
   cd wildfires_server
   python start_server.py
   ```

2. **Start the Unified Client**:
   ```bash
   cd unified_client
   python start_client.py
   ```

This will launch the interactive command-line interface, connecting to all available servers.

## Command-Line Interface

The ClimateGPT CLI provides an interactive interface to access all climate data analysis capabilities.

### Basic Commands

- **Natural Language Queries**: Just type your question about climate data
- `help` - Display help information and example queries
- `stats` - Show server statistics (database tables, rows, etc.)
- `servers` - List available climate servers and their capabilities
- `purge` - Clear the server's in-memory cache
- `clear` - Clear the screen
- `exit` or `quit` - Exit the application

### Command Examples

```
> help
[Help information will be displayed]

> stats
[Server statistics will be displayed]

> servers
[Available servers will be listed]

> What was the total CO2 emission trend from 2010 to 2020?
[Query results will be displayed]
```

## Query Types

ClimateGPT supports three main types of queries:

### 1. Database Queries

Questions about specific climate data in the database.

**Examples:**
- "What was the total CO2 emission trend from 2010 to 2020?"
- "Compare emissions between California and Texas from 2015 to 2020"
- "Which sectors had the highest emissions in 2019?"

Database queries typically return:
- A data table with results
- A visualization (where appropriate)
- Insights explaining the data

### 2. Forecasting Queries

Questions about future projections based on historical data.

**Examples:**
- "Forecast CO2 emissions for the next 10 years"
- "Predict methane emissions through 2035"
- "Forecast transportation emissions in California through 2030"

Forecasting queries typically return:
- Projected values with confidence intervals
- A line chart visualization
- Analysis of forecast reliability

### 3. General Knowledge Queries

Questions about climate concepts, definitions, and general information.

**Examples:**
- "What is climate change?"
- "How does global warming affect biodiversity?"
- "What is the Paris Climate Agreement?"

General knowledge queries return comprehensive text responses without database access.

## Example Queries

Here are some example queries grouped by topic:

### Emissions Queries

- "What was the total CO2 emission trend in the US from 2010 to 2020?"
- "Which greenhouse gas had the largest increase between 2000-2020?"
- "Show me the top 5 states by CO2 emissions in 2019"
- "How have industrial emissions changed compared to transportation since 1990?"

### Sea Level Queries

- "What is the global sea level rise rate in the last decade?"
- "Compare sea level changes in the Atlantic and Pacific oceans"
- "Show coastal regions most affected by sea level rise"
- "What is the projected sea level rise by 2050?"

### Wildfire Queries

- "How has the frequency of wildfires changed since 2000?"
- "Which US states had the most acres burned by wildfires in the last 5 years?"
- "Show the correlation between temperature and wildfire occurrence"
- "Compare wildfire seasons in California from 2018 to 2022"

## Visualizations

ClimateGPT automatically generates appropriate visualizations based on your query. The system selects the best visualization type for your data:

### Line Charts

Used for trends over time, like emissions changes over years.


### Bar Charts

Used for comparing values across categories, like emissions by state.


### Pie Charts

Used for showing proportions, like the breakdown of emissions by sector.


### Forecast Charts

Special charts showing projections with confidence intervals.


## Forecasting

ClimateGPT has powerful forecasting capabilities that allow you to project climate trends into the future.

### How Forecasting Works

1. The system analyzes historical data patterns using ARIMA time series modeling
2. It generates projections with statistical confidence intervals
3. It provides reliability metrics for the forecast
4. It creates visualizations showing both historical data and projections

### Tips for Effective Forecasts

- Use specific timeframes: "Forecast through 2035" is better than "Forecast for the future"
- Specify the data of interest: "Forecast CO2 emissions" is better than "Forecast emissions"
- For regional forecasts, specify the region: "Forecast California emissions" 
- For sector-specific forecasts, specify the sector: "Forecast transportation emissions"

### Forecast Limitations

- Forecasts become less reliable the further into the future they go
- Confidence intervals widen with distance from historical data
- Unexpected policy changes or technologies can impact actual outcomes
- Complex systems may have non-linear behaviors that are difficult to predict

## Troubleshooting

### Common Issues

#### Connection Problems

**Issue**: "Could not connect to server" or similar error

**Solution**: 
- Make sure all servers are running in separate terminal windows
- Check for error messages in the server terminal windows
- Verify the server URLs in `server_registry.json` are correct (default: http://127.0.0.1:8000, etc.)
- Make sure no other applications are using the same ports

#### Slow Responses

**Issue**: Queries take a long time to process

**Solution**:
- For complex queries, some processing time is normal
- Try purging the cache to clear any stuck requests (`purge` command)
- Check if the ClimateGPT API is experiencing delays
- Check your internet connection (required for the ClimateGPT API)

#### Visualization Errors

**Issue**: Visualizations don't display

**Solution**:
- Make sure matplotlib is installed: `pip install matplotlib`
- Check for error messages in the client output
- Try a different query that produces a visualization
- Check file permissions if visualization files aren't saving

#### No Results Found

**Issue**: "No results found" or empty results

**Solution**:
- Check that your query references data that exists in the database
- Verify the date range (our data covers 1990-2022)
- Try reformulating your query to be more specific
- Use the `stats` command to see available data ranges

#### Python Environment Issues

**Issue**: ImportError or ModuleNotFoundError 

**Solution**:
- Make sure you've activated your virtual environment
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check for compatibility issues between packages
- Try running `pip list` to see installed packages

## Advanced Features

### Query Caching

ClimateGPT caches query results for improved performance. If you run the same or similar queries multiple times, responses will be faster after the first execution.

To clear the cache:
```
> purge
Cache purged successfully
```

### Multi-Step Queries

You can ask complex, multi-part questions that require multiple processing steps:

**Example**:
```
> Calculate the annual percentage change in CO2 emissions for California from 2010 to 2020, and compare it with the national average
```

The system will:
1. Retrieve California emissions data
2. Calculate percentage changes
3. Retrieve national emissions data
4. Calculate national percentage changes
5. Compare the two datasets
6. Generate insights and visualizations

### Server Selection

You can see which specialized servers are available:
```
> servers
```

The system intelligently routes your query to the appropriate server based on the content, but you can also specify a server:
```
> @sea-level What is the current rate of sea level rise?
```

## FAQ

### How current is the data?

Our emissions database includes data from 1990 through 2022. Sea level data spans from 1900 to the present, and wildfire data covers 2000 to the present.

### How accurate are the forecasts?

Forecasts are based on statistical models using historical data. They include confidence intervals that show the range of possible outcomes. Accuracy typically decreases the further into the future you look.

### Can I export the results?

Currently, visualizations are saved as image files in the current directory. 

### What data sources does ClimateGPT use?

Our emissions data is compiled from EPA greenhouse gas inventories, international sources, and standardized climate datasets. Sea level data comes from satellite measurements and tide gauges. Wildfire data is sourced from national fire agencies and satellite observations.

### How do I update the system?

To update to the latest version:
```bash
git pull
pip install -r requirements.txt
```

### How do I run multiple servers at once?

You'll need to open multiple terminal windows or use a terminal multiplexer like tmux or screen. Start each server in a separate window:

```bash
# Terminal 1
cd emissions_server
python start_server.py

# Terminal 2
cd sea_level_server
python start_server.py

# Terminal 3
cd wildfires_server
python start_server.py

# Terminal 4
cd unified_client
python start_client.py
```

### Where can I find more help?

- Check our [comprehensive documentation](DOCUMENTATION.md)
- View the [technical architecture](ARCHITECTURE.md)
- For developers, see the [development guide](DEVELOPMENT.md)

---
