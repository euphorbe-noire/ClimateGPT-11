#!/usr/bin/env python
"""
Interactive CLI for ClimateGPT.
This script provides a command-line interface to interact with the ClimateGPT system via FastAPI,
allowing users to enter natural language queries, view results, and visualize data.
"""

import os
import sys
import time
import re
import json
import logging
import tempfile
import subprocess
import platform
import base64
from typing import Dict, Any, Optional, List, Union

# Third-party imports
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.progress import Progress
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML

# Local application imports
from config import (
    CLI_API_URL, CLI_TABLE_ROW_LIMIT, CLI_REQUEST_TIMEOUT,
    CLI_BANNER_STYLE, CLI_MAX_RETRIES, CLI_RETRY_DELAY,
    LOG_LEVEL, LOG_FILE
)
from router import ClimateRouter

# Set up logging
def setup_logging(logger_name='climate_client'):
    """Set up logging configuration for the client."""
    # Parse log level string to logging constant
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create directory for log file if it doesn't exist
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(level)
    
    # Console handler - use a higher level for console to reduce clutter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
    
    # Create formatters and add to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logging('cli')

# Set up rich console for prettier output
console = Console()

# Create a prompt style similar to Rich's style
prompt_style = Style.from_dict({
    'prompt': 'bold green',
})

# Create a prompt session with history
prompt_history = InMemoryHistory()
prompt_session = PromptSession(history=prompt_history)

class ClimateGPTClient:
    """Client for interacting with the ClimateGPT API."""
    
    def __init__(self, api_url: str = CLI_API_URL, timeout: int = CLI_REQUEST_TIMEOUT):
        self.api_url = api_url
        self.timeout = timeout
        logger.info(f"Initialized client with API URL: {api_url}")
        
    def check_server_status(self) -> bool:
        """Check if the FastAPI server is running."""
        logger.info("Checking server status")
        return self._make_request("get", "/", retries=1) is not None
            
    def get_server_stats(self) -> Optional[Dict[str, Any]]:
        """Get server statistics."""
        logger.info("Requesting server statistics")
        return self._make_request("get", "/stats")
            
    def process_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Process a natural language query."""
        logger.info(f"Processing query: {query[:50]}...")
        data = {"query": query}
        console.print("[dim]Sending query to server...[/dim]")
        return self._make_request("post", "/query", json=data)
    
    def get_visualization(self, result_data: Dict[str, Any], query: str) -> Optional[Dict[str, Any]]:
        """Request visualization for result data."""
        logger.info("Requesting visualization for results")
        data = {"result_data": result_data, "query": query}
        console.print("[dim]Generating visualization...[/dim]")
        return self._make_request("post", "/visualization", json=data)
    
    def purge_cache(self) -> Optional[Dict[str, Any]]:
        """Purge all cached data on the server."""
        console.print("[dim]Purging server cache...[/dim]")
        return self._make_request("post", "/cache/purge")
    
    def _make_request(self, method: str, endpoint: str, retries: int = CLI_MAX_RETRIES, **kwargs) -> Optional[Dict[str, Any]]:
        """Make an HTTP request to the API with retry capability."""
        url = f"{self.api_url}{endpoint}"
        logger.debug(f"Making {method.upper()} request to {url}")
        
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
            
        for attempt in range(retries):
            try:
                response = getattr(requests, method.lower())(url, **kwargs)
                
                if response.status_code == 200:
                    logger.debug(f"Request successful: {endpoint}")
                    return response.json()
                    
                logger.warning(f"Server returned status {response.status_code} for {endpoint}")
                console.print(f"[bold red]Error:[/bold red] Server returned status {response.status_code}")
                if attempt < retries - 1:
                    delay = CLI_RETRY_DELAY * (attempt + 1)
                    logger.info(f"Retrying in {delay} seconds (Attempt {attempt+1}/{retries})")
                    console.print(f"Retrying in {delay} seconds... (Attempt {attempt + 1}/{retries})")
                    time.sleep(delay)
                    
            except requests.exceptions.RequestException as e:
                error_type = e.__class__.__name__
                logger.error(f"Network error ({error_type}): {str(e)}")
                console.print(f"[bold red]Network error:[/bold red] {error_type}")
                
                if attempt < retries - 1:
                    delay = CLI_RETRY_DELAY * (attempt + 1)
                    logger.info(f"Retrying in {delay} seconds (Attempt {attempt+1}/{retries})")
                    console.print(f"Retrying in {delay} seconds... (Attempt {attempt + 1}/{retries})")
                    time.sleep(delay)
        
        logger.error(f"Request failed after {retries} attempts: {endpoint}")
        return None


class ClimateGPTCLI:
    """Interactive command-line interface for ClimateGPT."""
    
    def __init__(self):
        logger.info("Initializing CLI")
        self.router = ClimateRouter()
        self.client = ClimateGPTClient()
        self.commands = {
        'help': self.show_help,
        'exit': self.exit_cli,
        'quit': self.exit_cli,
        'clear': self.clear_screen,
        'stats': self.show_stats,
        'purge': self.purge_cache,
        'servers': self.list_servers  
    }
    
    def start(self) -> int:
        """Start the interactive CLI."""
        logger.info("Starting CLI")
        self.show_banner()
        
        # Check if at least one server is available instead of checking a single server
        server_available = False
        
        # Try connecting to the main emissions server first (usually the primary one)
        if "emissions_server" in self.router.registry:
            server_info = self.router.registry["emissions_server"]
            client = ClimateGPTClient(api_url=server_info.get("url", ""))
            if client.check_server_status():
                server_available = True
                logger.info(f"Successfully connected to emissions_server at {server_info.get('url')}")
                console.print(f"\n[green]Successfully connected to Emissions Server at {server_info.get('url')}[/green]")
        if "sea_level_server" in self.router.registry:
            server_info = self.router.registry["sea_level_server"]
            client = ClimateGPTClient(api_url=server_info.get("url", ""))
            if client.check_server_status():
                server_available = True
                logger.info(f"Successfully connected to Sea Level Server at {server_info.get('url')}")
                console.print(f"\n[green]Successfully connected to Sea Level Server at {server_info.get('url')}[/green]")
        if "fire_data_server" in self.router.registry:
            server_info = self.router.registry["fire_data_server"]
            client = ClimateGPTClient(api_url=server_info.get("url", ""))
            if client.check_server_status():
                server_available = True
                logger.info(f"Successfully connected to Wildfires Server at {server_info.get('url')}")
                console.print(f"\n[green]Successfully connected to Wildfires Server at {server_info.get('url')}[/green]\n")
        
        if not server_available:
            logger.warning("Could not connect to primary server, but will continue with limited functionality")
            console.print("\n[bold yellow]Warning:[/bold yellow] Could not connect to primary climate server.")
            console.print("Limited functionality may be available through other servers or the general knowledge API.\n")
            console.print("Use the 'servers' command to see available servers.\n")
        
        self.command_loop()
        return 0
    
    def command_loop(self) -> None:
        """Run the main command loop with improved input handling."""
        logger.info("Entering command loop")
        while True:
            try:
                # Use prompt_toolkit for input with history support
                user_input = prompt_session.prompt(
                    HTML('<ansigreen><b>Enter your climate question:</b></ansigreen> '),
                    style=prompt_style
                )
                
                if not user_input.strip():
                    continue
                    
                logger.info(f"Received input: {user_input[:50]}...")
                
                if user_input.strip().lower() in self.commands:
                    logger.debug(f"Executing command: {user_input.strip().lower()}")
                    self.commands[user_input.strip().lower()]()
                elif user_input.strip():
                    self.handle_query(user_input)
                    
            except KeyboardInterrupt:
                logger.info("Operation cancelled by keyboard interrupt")
                console.print("\n\n[bold yellow]Operation cancelled by user[/bold yellow]")
            except Exception as e:
                logger.error(f"Error in command loop: {str(e)}", exc_info=True)
                console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
    
    def handle_query(self, query: str) -> None:
        """Process a user query and display results using the router."""
        logger.info(f"Handling query: {query[:50]}...")
        start_time = time.time()
        
        with Progress() as progress:
            task = progress.add_task("[green]Processing query...", total=None)
            
            # Use the router instead of direct client
            result = self.router.process_query(query)
            
            progress.update(task, completed=True)
            
            if result is None:
                logger.warning("Received empty result from router")
                return
            
            # Check if there was an error in routing or processing
            if result.get("error") is not None:
                logger.warning(f"Query error: {result['error']}")
                console.print(f"\n[bold red]Error:[/bold red] {result['error']}")
                if result.get("message"):
                    console.print(f"[dim]{result['message']}[/dim]")
                return
            
            # Display results based on query type and response format
            self.display_query_results(result, query)
            
        execution_time = result.get("execution_time", time.time() - start_time)
        logger.info(f"Query processed in {execution_time:.2f} seconds")
        console.print(f"\n[dim]Query processed in {execution_time:.2f} seconds[/dim]\n")
    
    def display_query_results(self, result: Dict[str, Any], query: str) -> None:
        """Display query results in appropriate format."""
        if result.get("error") is not None:
            logger.warning(f"Query error: {result['error']}")
            console.print(f"\n[bold red]Error:[/bold red] {result['error']}")
            if result.get("message"):
                console.print(f"[dim]{result['message']}[/dim]")
            return
        
        if result.get("sql"):
            logger.info("Displaying database query results")
            self.display_db_query_results(result, query)
        else:
            logger.info("Displaying knowledge query results")
            self.display_knowledge_query_results(result)
    
    def display_db_query_results(self, result: Dict[str, Any], query: str) -> None:
        """Display database query results."""
        # Display SQL query if available
        if result.get("sql"):
            logger.debug(f"SQL query: {result['sql'][:100]}...")
            console.print("\n[bold blue]SQL Query:[/bold blue]")
            # Ensure the SQL query is properly formatted and not truncated
            sql_query = result["sql"]
            # Format SQL for better readability
            sql_query = self.format_sql_query(sql_query)
            syntax = Syntax(sql_query, "sql", theme="monokai", line_numbers=True, word_wrap=True)
            console.print(syntax)
        
        # Display plan if available
        if result.get("plan") and "steps" in result["plan"]:
            steps = result["plan"]["steps"]
            if len(steps) > 1:  # Only show plan for multi-step queries
                logger.debug(f"Multi-step plan with {len(steps)} steps")
                console.print("\n[bold blue]Execution Plan:[/bold blue]")
                for i, step in enumerate(steps):
                    step_id = step.get("id", f"Step {i+1}")
                    description = step.get("description", "No description")
                    console.print(f"[blue]{step_id}:[/blue] {description}")
                    # Display the SQL for each step
                    if step.get("sql"):
                        step_sql = self.format_sql_query(step["sql"])
                        step_syntax = Syntax(step_sql, "sql", theme="monokai", line_numbers=True, word_wrap=True)
                        console.print(step_syntax)
        
        # Display data results if available
        result_data = result.get("result", {})
        if result_data and "columns" in result_data and "data" in result_data:
            row_count = len(result_data["data"])
            logger.info(f"Query returned {row_count} rows")
            console.print("\n[bold blue]Query Results:[/bold blue]")
            self.show_table(result_data["columns"], result_data["data"])
        elif result_data and result_data.get("message"):
            console.print(f"\n[yellow]{result_data['message']}[/yellow]")
        
        # Display insights if available
        if result.get("insight"):
            logger.debug("Displaying insights")
            console.print("\n[bold green]Climate Data Insights:[/bold green]")
            console.print(Panel(Markdown(result["insight"]), border_style="green"))
        
        # Handle visualization if available
        if result.get("visualization"):
            logger.debug("Handling visualization data")
            self.handle_visualization(result["visualization"], query)

    def handle_visualization(self, visualization: Dict[str, Any], query: str) -> None:
        """Handle visualization data from the server."""
        if isinstance(visualization, str):
            try:
                logger.info("Processing base64 visualization string")
                image_data = base64.b64decode(visualization)
            
                # Save to file
                image_path = 'climate_visualization.png'
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                
                console.print(f"[green]Visualization saved to: {image_path}[/green]")
                # Try to open the image with the default viewer
                self.open_image_with_default_app(image_path)
                return
            except Exception as e:
                logger.error(f"Error processing base64 visualization: {str(e)}")
                console.print("[yellow]Could not process visualization data.[/yellow]")
                return
        viz_type = visualization.get("type", "unknown")
        title = visualization.get("title", "Data Visualization")
        
        logger.info(f"Processing visualization of type: {viz_type}")
        console.print(f"\n[bold green]Data Visualization:[/bold green] {title}")
        
        # Check if we have plotting code
        if "plot_code" in visualization:
            self.render_visualization(visualization["plot_code"])
        else:
            # If no plot code but we have data, request visualization from server
            if "data" in visualization and "columns" in visualization:
                logger.info("No plot code provided, requesting from server")
                console.print("[dim]Generating visualization...[/dim]")
                result_data = {"columns": visualization["columns"], "data": visualization["data"]}
                viz_result = self.client.get_visualization(result_data, query)
                
                if viz_result and "plot_code" in viz_result:
                    self.render_visualization(viz_result["plot_code"])
                else:
                    logger.warning("Failed to generate visualization from server")
                    console.print("[yellow]Could not generate visualization for these results.[/yellow]")
    
    def render_visualization(self, plot_code: str) -> None:
        """Render visualization using matplotlib."""
        logger.info("Rendering visualization")
        
        try:
            # Create a temporary file for the plotting code
            with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as temp_file:
                temp_file.write(plot_code)
                temp_file_path = temp_file.name
            
            # Check if matplotlib is installed
            try:
                import matplotlib
                console.print("[dim]Rendering visualization...[/dim]")
                
                # Try to execute the plot code
                process = subprocess.Popen(
                    [sys.executable, temp_file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    logger.error(f"Error executing plot code: {stderr.decode('utf-8')}")
                    console.print("[bold red]Error rendering visualization.[/bold red]")
                    console.print(f"[dim]{stderr.decode('utf-8')}[/dim]")
                else:
                    # Visualization should be shown in a new window by matplotlib
                    image_path = 'climate_visualization.png'
                    if os.path.exists(image_path):
                        console.print(f"[green]Visualization saved to: {image_path}[/green]")
                        # Try to open the image with the default viewer
                        self.open_image_with_default_app(image_path)
                    else:
                        console.print("[yellow]Visualization rendered but not saved.[/yellow]")
                
            except ImportError:
                logger.warning("Matplotlib not installed")
                console.print("\n[yellow]Matplotlib not installed. Cannot render visualization.[/yellow]")
                console.print("[dim]To install Matplotlib, run: pip install matplotlib[/dim]")
                
                # Instead of rendering, show the plot code
                console.print("\n[bold blue]Visualization Code:[/bold blue]")
                syntax = Syntax(plot_code, "python", theme="monokai", line_numbers=True, word_wrap=True)
                console.print(syntax)
        
        except Exception as e:
            logger.error(f"Error rendering visualization: {str(e)}", exc_info=True)
            console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        
        finally:
            # Clean up the temporary file
            try:
                if 'temp_file_path' in locals():
                    os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Error removing temporary file: {str(e)}")
    
    def open_image_with_default_app(self, image_path: str) -> None:
        """Open an image with the default application based on platform."""
        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.call(('open', image_path))
            elif platform.system() == 'Windows':  # Windows
                os.startfile(image_path)
            else:  # Linux/Unix
                subprocess.call(('xdg-open', image_path))
                
            logger.info(f"Opened image with default viewer: {image_path}")
        except Exception as e:
            logger.warning(f"Could not open image with default viewer: {str(e)}")
            console.print(f"[dim]Image saved but could not be opened automatically.[/dim]")

    def format_sql_query(self, sql: str) -> str:
        """Format SQL query for better readability."""
        logger.debug("Formatting SQL query")
        # Basic SQL formatting - split by keywords and add newlines
        keywords = ["SELECT", "FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY", 
                    "LIMIT", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", 
                    "OUTER JOIN", "ON", "AND", "OR", "UNION", "INTERSECT", "EXCEPT"]
        
        # Replace keywords with newline + keyword
        formatted_sql = sql
        for keyword in keywords:
            # Only add newlines for stand-alone keywords (not substrings)
            formatted_sql = re.sub(r'(?i)\b' + keyword + r'\b', '\n' + keyword, formatted_sql)
        
        # Remove any leading newline
        formatted_sql = formatted_sql.lstrip('\n')
        
        # Add indentation for readability
        lines = formatted_sql.split('\n')
        indent_level = 0
        for i in range(len(lines)):
            # Add indentation
            lines[i] = '  ' * indent_level + lines[i]
            
            # Count opening and closing parentheses for next line's indentation
            open_parens = lines[i].count('(')
            close_parens = lines[i].count(')')
            indent_level += open_parens - close_parens
            indent_level = max(0, indent_level)  # Ensure indent level doesn't go negative
        
        return '\n'.join(lines)
    
    def display_knowledge_query_results(self, result: Dict[str, Any]) -> None:
        """Display knowledge query results."""
        result_data = result.get("result", {})
        if result_data and result_data.get("answer"):
            logger.debug("Displaying answer")
            console.print("\n[bold green]ClimateGPT Response:[/bold green]")
            console.print(Panel(Markdown(result_data["answer"]), border_style="green"))
        else:
            logger.warning("No answer provided for knowledge query")
            console.print("\n[yellow]No answer was provided for your query.[/yellow]")
    
    def show_banner(self) -> None:
        """Display welcome banner with instructions."""
        logger.debug("Displaying welcome banner")
        banner = """
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                                                                   ║
    ║                 ClimateGPT Interactive Console                    ║
    ║                                                                   ║
    ║   Ask questions about climate data or general climate topics      ║
    ║   Queries are automatically routed to specialized servers         ║
    ║   Type 'servers' to see available climate servers                 ║
    ║   Type 'exit', 'quit', or press Ctrl+C to exit                    ║
    ║   Type 'help' for example queries                                 ║
    ║                                                                   ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """
        console.print(Panel(banner, border_style=CLI_BANNER_STYLE))
    
    def show_help(self) -> None:
        """Display help information and example queries."""
        logger.info("Showing help information")
        help_text = """
    # ClimateGPT Query Guide

    ## Multi-Server Architecture

    This client can route queries to multiple specialized climate servers:

    - Queries about emissions data, trends, and forecasts go to the Emissions server
    - Queries about global sea level changes, trends, and forecasts go to the Sea Level server
    - Queries about wildfires, trends, and forecasts go to the Wildfires server
    - General climate knowledge questions are answered directly

    ## Example Database Queries for the Emissions Server:

    - "What was the total emissions generated by various sectors over the years"
    - "What was the total CO2 emission trend from 2010 to 2020?"
    - "Which greenhouse gas showed the most significant increase over the past decade?"
    - "Compare emissions between California and Texas from 2015 to 2020"
    - "What sectors had the highest emissions growth rate from 2015 to 2020?"
    - "Show methane emissions trend over the last decade"

    ## Example Database Queries for the Sea Level Server:

    - "What is the trend in sea level rise over the last 10 years?"
    - "Show me the sea level measurements from 2010 to 2020"
    - "What was the average sea level in 2015?"
    - "Calculate the rate of sea level rise per year"
    - "Show sea level anomalies over time"
    - "Compare sea level rise before and after 2000"

    ## Example Database Queries for the Wildfires Server:

    - "Show the number of active fires detected on 2015-01-30"
    - "What is the average brightness of fires in California region"
    - "Compare fire detections between Aqua and Terra satellites"
    - "Show high-confidence fire detections with confidence > 90"
    - "What is the distribution of day vs night fire detections?"
    - "Find the hottest fires (highest brightness) in January 2015"
    - "Show temporal trend of fire detections over the last month"

    ## Example Visualization Queries
    
    - "Show the proportion of emissions by fuel type in 2019"
    - "Plot the yearly trend of emissions from the Energy sector from 1990 to 2022"
    - "What are the top 5 states by CO2 emissions in 2019?"
    - "Plot the geographic distribution of fires"
    - "Show daily fire count trend for January 2015"
    - "Create a bar chart comparing satellite detection counts"
    - "Show the pie chart of day vs night fire detections"
    
    ## Example Forecast Queries:

    Begin your query with "Forecast" or "Predict" to use the ARIMA forecasting feature:
    
    - "Forecast CO2 emissions for the next 10 years"
    - "Forecast emissions generated by the state of California for the next 5 years"
    - "Predict methane emissions through 2035"
    - "Forecast US energy sector emissions for the next decade"
    - "Predict transportation emissions in California through 2040"

    ## Example General Knowledge Queries:

    - "What is climate change?"
    - "How does global warming affect biodiversity?"
    - "What are the main causes of greenhouse gas emissions?"
    - "How can individuals reduce their carbon footprint?"
    - "What is the Paris Climate Agreement?"
    - "What causes sea level rise?"
    - "How does global warming affect sea levels?"
    - "What are the projections for future sea level rise?"
    - "How do sea levels impact coastal communities?"
    - "What is thermal expansion of oceans?"
    - "What is MODIS?"
    - "How does satellite fire detection work?"
    - "What is Fire Radiative Power (FRP)?"
    - "What does the confidence score mean in fire detection?"
    - "What's the difference between Aqua and Terra satellites?"

    ## Commands:

    - servers: List available climate servers and their capabilities
    - help: Display this help information
    - exit, quit: Exit the program
    - clear: Clear the screen
    - stats: Show server statistics (when connected to supporting servers)
    - purge: Clear a server's query cache (when connected to supporting servers)
    """
        console.print(Markdown(help_text))

    def show_table(self, columns: List[str], data: List[List[Any]], row_limit: int = CLI_TABLE_ROW_LIMIT) -> None:
        """Display data as a rich formatted table."""
        if not data or not columns:
            logger.warning("No data found for table display")
            console.print("\n[bold red]No data found matching your query.[/bold red]\n")
            return
        
        logger.debug(f"Displaying table with {len(columns)} columns and {len(data)} rows")
        table = Table(show_header=True, header_style="bold green")
        
        for column in columns:
            table.add_column(str(column))
        
        for i, row in enumerate(data):
            if i >= row_limit:
                break
            table.add_row(*[str(x) for x in row])
        
        console.print(table)
        
        total_rows = len(data)
        if total_rows > row_limit:
            logger.info(f"Showing {row_limit} of {total_rows} rows")
            console.print(f"\n[dim]Showing {row_limit} of {total_rows} rows[/dim]")
    
    def show_stats(self) -> None:
        """Get and display statistics from all available servers."""
        logger.info("Requesting server statistics")
        
        # Check if registry is empty
        if not self.router.registry:
            console.print("\n[bold yellow]No servers configured in registry[/bold yellow]")
            return
        
        # Create a table for server overview
        overview_table = Table(title="Server Overview", show_header=True)
        overview_table.add_column("Server", style="cyan")
        overview_table.add_column("Status", style="green")
        overview_table.add_column("Requests", justify="right")
        overview_table.add_column("Success Rate", justify="right")
        
        # Track if we found any servers with stats
        found_stats = False
        
        # Process each server
        for server_name, server_info in self.router.registry.items():
            # Skip the general knowledge API which doesn't provide detailed stats
            if server_name == "climategpt_api":
                overview_table.add_row(server_name, "[blue]API Gateway[/blue]", "-", "-")
                continue
                
            server_url = server_info.get("url", "")
            if not server_url:
                overview_table.add_row(server_name, "[yellow]No URL[/yellow]", "-", "-")
                continue
                
            # Get statistics for this server
            client = ClimateGPTClient(api_url=server_url)
            stats = client.get_server_stats()
            
            if not stats:
                overview_table.add_row(server_name, "[red]Offline[/red]", "-", "-")
                continue
                
            # Mark that we found at least one server with stats
            found_stats = True
            
            # Get server stats for overview
            server_stats = stats.get("stats", {}).get("server", {})
            total_requests = server_stats.get("total_requests", 0)
            successful = server_stats.get("successful_queries", 0)
            
            # Calculate success rate
            success_rate = "0%" if total_requests == 0 else f"{(successful / total_requests) * 100:.1f}%"
            
            # Add to overview table
            overview_table.add_row(
                server_name, 
                "[green]Online[/green]", 
                str(total_requests),
                success_rate
            )
            
            # Display detailed server statistics
            console.print(f"\n[bold blue]{server_name} Statistics:[/bold blue]")
            
            console.print(Panel.fit(
                f"Total Requests: {total_requests}\n"
                f"Successful Queries: {successful}\n"
                f"Failed Queries: {server_stats.get('failed_queries', 0)}\n"
                f"Database Queries: {server_stats.get('db_queries', 0)}\n"
                f"Knowledge Queries: {server_stats.get('knowledge_queries', 0)}\n"
                f"Visualization Requests: {server_stats.get('visualization_requests', 0)}",
                title="API Server",
                border_style="blue"
            ))
            
            # Display database statistics if available
            db_stats = stats.get("stats", {}).get("database", {})
            if db_stats and isinstance(db_stats, dict):
                db_table = Table(title="Database Tables")
                db_table.add_column("Table", style="cyan")
                db_table.add_column("Rows", justify="right")
                db_table.add_column("Columns", justify="right")
                
                for table_name, table_data in db_stats.items():
                    if isinstance(table_data, dict) and "error" not in table_data:
                        db_table.add_row(
                            table_name,
                            str(table_data.get('rows', 'N/A')),
                            str(table_data.get('columns', 'N/A'))
                        )
                
                if db_table.row_count > 0:
                    console.print(db_table)
                    
                # Show year range for Emissions table if available
                if "Emissions" in db_stats and "year_range" in db_stats["Emissions"]:
                    min_year, max_year = db_stats["Emissions"]["year_range"]
                    console.print(f"[blue]Data Coverage: {min_year} to {max_year}[/blue]")
        
        # Display server overview
        console.print("\n")
        console.print(overview_table)
        
        # If no statistics were found from any server
        if not found_stats:
            console.print("\n[bold yellow]Could not retrieve statistics from any servers[/bold yellow]")
            
    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        logger.debug("Clearing screen")
        os.system('cls' if os.name == 'nt' else 'clear')
        self.show_banner()
    
    def exit_cli(self) -> None:
        """Exit the CLI."""
        logger.info("Exiting CLI")
        console.print("\n[bold]Goodbye![/bold]\n")
        sys.exit(0)

    def purge_cache(self) -> None:
        """Purge all cached data across all available servers."""
        logger.info("Purging cache across all servers")
        
        if not self.router.registry:
            console.print("\n[bold yellow]No servers configured in registry[/bold yellow]")
            return
        
        # Track results for each server
        results = {}
        
        with Progress() as progress:
            task = progress.add_task("[green]Purging cache across all servers...", total=len(self.router.registry))
            
            # Iterate through all servers in the registry
            for server_name, server_info in self.router.registry.items():
                # Skip the general knowledge API as it typically doesn't have a cache
                if server_name == "climategpt_api":
                    progress.update(task, advance=1)
                    continue
                    
                # Create a temporary client for this server
                server_url = server_info.get("url", "")
                if not server_url:
                    results[server_name] = {"status": "error", "message": "No URL configured"}
                    progress.update(task, advance=1)
                    continue
                    
                client = ClimateGPTClient(api_url=server_url)
                
                try:
                    # Attempt to purge cache for this server
                    logger.info(f"Purging cache for {server_name} at {server_url}")
                    result = client.purge_cache()
                    
                    if result is None:
                        results[server_name] = {"status": "error", "message": "No response from server"}
                    else:
                        results[server_name] = result
                        
                except Exception as e:
                    logger.error(f"Error purging cache for {server_name}: {str(e)}")
                    results[server_name] = {"status": "error", "message": str(e)}
                    
                progress.update(task, advance=1)
        
        # Display summary of results
        table = Table(title="Cache Purge Results")
        table.add_column("Server", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Message")
        
        success_count = 0
        for server_name, result in results.items():
            status = result.get("status", "unknown")
            message = result.get("message", "No message provided")
            
            if status == "success":
                status_style = "green"
                success_count += 1
            else:
                status_style = "red"
                
            table.add_row(server_name, f"[{status_style}]{status}[/{status_style}]", message)
        
        console.print(table)
        
        # Summary message
        if success_count == 0:
            console.print("\n[bold red]Failed to purge cache on any servers.[/bold red]")
        elif success_count == len(results):
            console.print(f"\n[bold green]Successfully purged cache on all {success_count} servers.[/bold green]")
        else:
            console.print(f"\n[bold yellow]Purged cache on {success_count} of {len(results)} servers.[/bold yellow]")
                
    def list_servers(self) -> None:
        """Display information about available servers."""
        logger.info("Displaying server information")
        
        # Create a table of servers and capabilities
        table = Table(show_header=True, header_style="bold green")
        table.add_column("Server")
        table.add_column("Description")
        table.add_column("Capabilities")
        table.add_column("URL")
        
        # Add servers from the router registry
        for server_name, server_info in self.router.registry.items():
            if server_name == "climategpt_api":
                # Skip the API entry as it's the fallback
                continue
                
            capabilities = ", ".join(server_info.get("capabilities", []))
            description = server_info.get("description", "")
            url = server_info.get("url", "")
            
            table.add_row(server_name, description, capabilities, url)
        
        # Add the fallback general knowledge API
        if "climategpt_api" in self.router.registry:
            api_info = self.router.registry["climategpt_api"]
            table.add_row(
                "climategpt_api", 
                api_info.get("description", "General knowledge API"),
                "General climate knowledge",
                "(API Endpoint)"
            )
        
        console.print("\n[bold blue]Available Climate Servers:[/bold blue]")
        console.print(table)
        console.print("\n[dim]Queries are automatically routed to the appropriate server[/dim]\n")


def main() -> int:
    """Main function for the interactive CLI."""
    try:
        logger.info("Starting Climate Client")
        cli = ClimateGPTCLI()
        return cli.start()
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        console.print(f"\n[bold red]Critical error:[/bold red] {str(e)}\n")
        console.print("Please check the log file for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())