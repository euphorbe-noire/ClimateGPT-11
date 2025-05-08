"""
Visualization generation module for Sea Level data with the new schema.

This module handles the generation of data visualizations for sea level data.
"""

import json
import logging
import os
import tempfile
import base64
import importlib.util
import sys
import requests
import seaborn
from typing import Dict, Any, List, Optional

# For visualization code execution in a controlled environment
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io
import re
import traceback
from src.config import VISUALIZATION_LLM_API_URL, VISUALIZATION_LLM_API_KEY

# Set up logging with more verbose output
logger = logging.getLogger('visualization_generator')
logger.setLevel(logging.DEBUG)  # Set to DEBUG for maximum details

def generate_visualization_code(query: str, data: Dict[str, Any]) -> str:
    """
    Generate Python code for visualizing sea level data using a code-generating LLM.
    
    Args:
        query: The original user query
        data: Dictionary with columns and data arrays
        
    Returns:
        Python code for visualization
    """
    logger.info(f"Starting visualization generation for query: {query[:50]}...")
    
    if not data or "columns" not in data or "data" not in data:
        logger.warning("No data available for visualization")
        return None
        
    # Convert data to a format that's easier to describe to the LLM
    columns = data["columns"]
    rows = data["data"]
    
    logger.info(f"Data has {len(rows)} rows and {len(columns)} columns")
    
    # Create a proper DataFrame first
    try:
        df = pd.DataFrame(rows, columns=columns)
        # Limit to 10 rows for the sample
        data_sample = df.head(10)
        # Convert to string representation
        data_sample_str = data_sample.to_string(index=False)
    except Exception as e:
        logger.warning(f"Error creating DataFrame: {str(e)}")
        # Fallback to simple string representation
        data_sample_str = f"Columns: {columns}\nSample rows (first 5):\n"
        for i in range(min(5, len(rows))):
            data_sample_str += str(rows[i]) + "\n"
    
    # Create the prompt with the data sample
    prompt = f"""
    Generate a Python visualization for the following sea level data based on this query: "{query}"

    Data (DataFrame):
    {data_sample_str}

    Total rows: {len(rows)}
    Columns: {', '.join(columns)}

    This data uses the following schema:
    - ID: Unique identifier for each measurement
    - Country: Country name (e.g., "World")
    - Unit: Measurement unit (e.g., "Millimeters")
    - Source: Data source organization
    - Region: Specific sea or ocean region (e.g., "Baltic Sea", "North Sea")
    - Date: Date of the measurement in YYYY-MM-DD format
    - Sea_Level_Change: The sea level measurement value

    Requirements:
    1. Use matplotlib, pandas, and seaborn to create a clear, informative visualization
    2. Include appropriate labels, title, and legend
    3. Use a blue color scheme appropriate for sea level/ocean data
    4. Apply best practices for the specific type of visualization needed
    5. Ensure the code is complete and can run independently with the provided data
    6. Add annotations or trend lines for important trends
    7. The code should create just ONE visualization that best answers the query
    8. Store the final plot in a variable called 'fig'
    9. Use the plt.tight_layout() function before saving
    10. Don't show the plot, just save it to a bytes buffer
    11. Make sure to parse dates correctly
    12. If there are multiple regions, use different colors for each region
    13. Make sure to handle 'Sea_Level_Change' as the measurement value column

    Return ONLY the Python code with no explanations.

    Example:
    ```python
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns
    import numpy as np
    import io
    from matplotlib.dates import DateFormatter
    import matplotlib.dates as mdates

    # Data is already provided as a DataFrame
    # Convert Date to datetime if not already
    if 'Date' in data.columns and data['Date'].dtype != 'datetime64[ns]':
        data['Date'] = pd.to_datetime(data['Date'])

    # Create visualization
    plt.figure(figsize=(10, 6))
    
    # Plot by region with different colors
    if 'Region' in data.columns:
        for region in data['Region'].unique():
            region_data = data[data['Region'] == region]
            plt.plot(region_data['Date'], region_data['Sea_Level_Change'], 
                    marker='o', label=region, linewidth=2)
    else:
        plt.plot(data['Date'], data['Sea_Level_Change'], marker='o', linewidth=2)
    
    plt.title('Sea Level Change Over Time', fontsize=15)
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Sea Level Change (mm)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.xticks(rotation=45)
    
    # Format date axis
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    
    
    plt.tight_layout()

    # Store the figure
    fig = plt.gcf()

    # No plt.show() needed
"""
    
    try:
        # Request code from the LLM API
        logger.info("Sending visualization request to LLM API")
        logger.info(f"API URL: {VISUALIZATION_LLM_API_URL}")
        logger.debug(f"Using API key: {VISUALIZATION_LLM_API_KEY[:5]}...{VISUALIZATION_LLM_API_KEY[-5:]}")
        
        # Format payload for LLM - Fix: Ensure prompt is a string
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 1500,
                "temperature": 0.3,
                "return_full_text": False
            }
        }
        
        # Use API key authentication
        headers = {"Authorization": f"Bearer {VISUALIZATION_LLM_API_KEY}"}
        
        logger.debug("Sending API request with payload")
        
        try:
            response = requests.post(
                VISUALIZATION_LLM_API_URL,
                json=payload,
                headers=headers,
                timeout=60  # Longer timeout for model inference
            )
            
            logger.info(f"API response status code: {response.status_code}")
            
            if response.status_code != 200:
                # Fix: Use str(response.text) instead of directly including response.text in f-string
                logger.error(f"API error: {response.status_code} - {str(response.text)[:200]}")
                if response.status_code == 401:
                    logger.error("Authentication error - check your API key")
                elif response.status_code == 403:
                    logger.error("Permission denied - you may not have model access yet")
                elif response.status_code == 429:
                    logger.error("Rate limit exceeded")
                return None
                
            response.raise_for_status()
            
            # Extract the code from the response
            result = response.json()
            logger.debug(f"API response type: {type(result)}")
            # Fix: Properly convert result to string for debug logging
            logger.debug(f"API response content: {json.dumps(result)[:200] if isinstance(result, (dict, list)) else str(result)[:200]}...")
            
            # Handle different response formats from API
            content = ""
            if isinstance(result, list) and len(result) > 0:
                if "generated_text" in result[0]:
                    content = result[0]["generated_text"]
                else:
                    content = str(result[0])
            elif isinstance(result, dict):
                if "generated_text" in result:
                    content = result["generated_text"]
                else:
                    content = json.dumps(result)  # Fix: Convert dict to string
            else:
                content = str(result)
                
            logger.debug(f"Extracted content: {content[:200]}...")
                
            # Extract only the Python code between triple backticks
            code_match = re.search(r'```python\s*(.*?)\s*```', content, re.DOTALL)
            if code_match:
                code = code_match.group(1)
                logger.info("Successfully extracted code from API response")
                logger.debug(f"Code snippet: {code[:200]}...")
            else:
                # If no code block, try to use the entire content as code
                logger.warning("No code block found in API response, using entire content")
                code = content
                
            logger.info("Successfully generated visualization code")
            return code
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error generating visualization code: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def execute_visualization_code(code: str, data: Dict[str, Any]) -> Optional[bytes]:
    """
    Execute the generated visualization code safely and return the visualization.
    
    Args:
        code: Python code to execute
        data: Dictionary with columns and data arrays
        
    Returns:
        Bytes containing the visualization image or None if failed
    """
    if not code:
        logger.error("No code provided to execute")
        return None
        
    logger.info("Executing visualization code")
    logger.debug(f"Code to execute: {code[:200]}...")
    
    try:
        # Create a DataFrame from the data first
        df = pd.DataFrame(data["data"], columns=data["columns"])
    # Create a controlled globals environment
        globals_dict = {
            'plt': plt,
            'pd': pd,
            'np': np,
            'sns': None,  # Will import if needed
            'io': io,
            'mdates': None,  # Will import if needed
            'DateFormatter': None,  # Will import if needed
            'data': df
        }
    
        # Check if code needs seaborn and import if needed
        if 'seaborn' in code or 'sns' in code:
            try:
                import seaborn as sns
                globals_dict['sns'] = sns
                logger.info("Imported seaborn for visualization")
            except ImportError:
                logger.warning("Seaborn not available, visualization might be affected")
    
        # Check if code needs matplotlib.dates and import if needed
        if 'matplotlib.dates' in code or 'mdates' in code:
            try:
                import matplotlib.dates as mdates
                from matplotlib.dates import DateFormatter
                globals_dict['mdates'] = mdates
                globals_dict['DateFormatter'] = DateFormatter
                logger.info("Imported matplotlib.dates for visualization")
            except ImportError:
                logger.warning("matplotlib.dates not available, visualization might be affected")
    

        # Create a buffer to save the image
        buf = io.BytesIO()
        
        # Add buffer to globals
        globals_dict['buf'] = buf
        
        # Execute code in controlled environment
        logger.info("Executing code in controlled environment")
        exec(code, globals_dict)
        
        # Check if the code generated a figure
        if 'fig' in globals_dict:
            # Save the figure to the buffer
            logger.info("Figure created, saving to buffer")
            globals_dict['fig'].savefig(buf, format='png', dpi=100)
            buf.seek(0)
            
            # Return the image bytes
            logger.info("Successfully created visualization")
            return buf.getvalue()
        else:
            logger.warning("Visualization code did not create a 'fig' variable")
            if plt.get_fignums():
                logger.info("Figure found using plt.gcf(), saving to buffer")
                plt.savefig(buf, format='png', dpi=100)
                buf.seek(0)
                plt.close('all')
                return buf.getvalue()
            return None
            
    except Exception as e:
        logger.error(f"Error executing visualization code: {str(e)}")
        logger.error(traceback.format_exc())
        return None
    finally:
        plt.close('all')  # Ensure all figures are closed to free memory

def create_fallback_visualization(query: str, data: Dict[str, Any]) -> Optional[bytes]:
    """
    Create a simple fallback visualization when LLM code generation fails.
    
    Args:
        query: The user query
        data: The data to visualize
        
    Returns:
        Visualization as bytes
    """
    try:
        logger.info("Creating fallback visualization")
        
        # Fix: Convert data to DataFrame with proper error handling
        try:
            df = pd.DataFrame(data["data"], columns=data["columns"])
        except Exception as e:
            logger.error(f"Error creating DataFrame: {str(e)}")
            # Create a simple error message as an image
            plt.figure(figsize=(8, 6))
            plt.text(0.5, 0.5, f"Could not create visualization: Data format error", 
                    horizontalalignment='center', verticalalignment='center', fontsize=14)
            plt.axis('off')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            plt.close('all')
            return buf.getvalue()
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Make sure we have the expected columns
        if 'Date' not in df.columns or 'Sea_Level_Change' not in df.columns:
            logger.warning(f"Expected columns not found. Available columns: {df.columns}")
            # If we don't have the expected columns, create a simple visualization
            plt.bar(range(len(df)), df[df.columns[-1]], color='#1f77b4')
            plt.title(f'Sea Level Data Visualization', fontsize=15)
            plt.xlabel('Index', fontsize=12)
            plt.ylabel('Value', fontsize=12)
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            plt.close('all')
            return buf.getvalue()
        
        # Try to convert date column to datetime if it's not already
        if df['Date'].dtype != 'datetime64[ns]':
            try:
                df['Date'] = pd.to_datetime(df['Date'])
            except:
                logger.warning("Could not convert Date column to datetime")
                
        # Check if we have multiple regions
        if 'Region' in df.columns and len(df['Region'].unique()) > 1:
            # Create a plot by region
            for region in df['Region'].unique():
                region_data = df[df['Region'] == region]
                plt.plot(region_data['Date'], region_data['Sea_Level_Change'], 
                         marker='o', label=region, linewidth=2)
            plt.legend()
            plt.title('Sea Level Change by Region', fontsize=15)
        else:
            # Create a simple time series plot
            plt.plot(df['Date'], df['Sea_Level_Change'], marker='o', color='#1f77b4')
            plt.title('Sea Level Change Over Time', fontsize=15)
            
        # Add trend line if possible
        try:
            # If dates are converted to datetime, convert to ordinal for trend line
            if df['Date'].dtype == 'datetime64[ns]':
                import matplotlib.dates as mdates
                x = mdates.date2num(df['Date'])
            else:
                x = range(len(df))
            
            z = np.polyfit(x, df['Sea_Level_Change'], 1)
            p = np.poly1d(z)
            
            if df['Date'].dtype == 'datetime64[ns]':
                plt.plot(df['Date'], p(x), "r--", alpha=0.8)
            else:
                plt.plot(df['Date'], p(range(len(df))), "r--", alpha=0.8)
            
            # Add trend annotation
            trend_direction = "rising" if z[0] > 0 else "falling"
            plt.annotate(f"Trend: {z[0]:.4f} mm/period ({trend_direction})", 
                         xy=(0.05, 0.95), 
                         xycoords='axes fraction',
                         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8))
        except Exception as e:
            logger.warning(f"Could not add trend line: {str(e)}")
        
        # Set appropriate labels
        plt.xlabel('Date', fontsize=12)
        # Get unit from data if available
        unit = "mm"
        if 'Unit' in df.columns and len(df['Unit'].unique()) == 1:
            unit = df['Unit'].iloc[0]
            if isinstance(unit, str) and unit.lower() == "millimeters":
                unit = "mm"
        plt.ylabel(f'Sea Level Change ({unit})', fontsize=12)
        
        # Format date axis if possible
        if df['Date'].dtype == 'datetime64[ns]':
            try:
                import matplotlib.dates as mdates
                # Determine appropriate date format based on date range
                date_range = (df['Date'].max() - df['Date'].min()).days
                
                if date_range > 365 * 10:  # > 10 years
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
                    plt.gca().xaxis.set_major_locator(mdates.YearLocator(2))
                elif date_range > 365 * 2:  # > 2 years
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=3))
                else:
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    plt.gca().xaxis.set_major_locator(mdates.MonthLocator())
                
                plt.xticks(rotation=45)
            except Exception as e:
                logger.warning(f"Could not format date axis: {str(e)}")
        
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close('all')
        
        logger.info("Successfully created fallback visualization")
        return buf.getvalue()
        
    except Exception as e:
        logger.error(f"Error creating fallback visualization: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def create_visualization(query: str, data: Dict[str, Any]) -> Optional[bytes]:
    """
    Generate and execute visualization code for sea level data.
    
    Args:
        query: The original user query
        data: Dictionary with columns and data arrays
        
    Returns:
        Bytes containing the visualization image or None if failed
    """
    # Fix: Add input validation and better error handling
    if not data:
        logger.error("No data provided for visualization")
        return None
        
    # Check if data has the expected structure
    if not isinstance(data, dict) or "columns" not in data or "data" not in data:
        logger.error(f"Invalid data format: {type(data)}")
        try:
            # Try to convert data to expected format if possible
            if isinstance(data, dict) and any(isinstance(v, list) for v in data.values()):
                # Data might be in a different format, try to adapt
                columns = list(data.keys())
                # Get the length of the first list
                first_key = next(k for k in data.keys() if isinstance(data[k], list))
                rows = []
                for i in range(len(data[first_key])):
                    row = [data[col][i] if isinstance(data[col], list) and i < len(data[col]) else None 
                           for col in columns]
                    rows.append(row)
                data = {"columns": columns, "data": rows}
            else:
                logger.error(f"Cannot convert data to required format: {type(data)}")
                return None
        except Exception as e:
            logger.error(f"Error adapting data format: {str(e)}")
            return None
    
    # Try the LLM code generation approach
    code = generate_visualization_code(query, data)
    
    if not code:
        logger.warning("Code generation failed, using fallback")
        return create_fallback_visualization(query, data)
    
    # Execute the code to create the visualization
    result = execute_visualization_code(code, data)
    
    if not result:
        logger.warning("Code execution failed, using fallback")
        return create_fallback_visualization(query, data)
        
    return result