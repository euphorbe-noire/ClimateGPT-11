# src/utils/visualization.py
"""
Visualization module for WildfireGPT.

This module analyzes query results to determine visualization suitability and
generates visualization specifications that can be rendered by the client.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Union

# Import visualization templates
from src.utils.visualization_templates import get_plot_code

# Set up logging
logger = logging.getLogger('visualization')

class VisualizationError(Exception):
    """Exception raised for errors in the visualization module."""
    pass

def is_visualizable(columns: List[str], data: List[List[Any]]) -> bool:
    """
    Determine if the query result is suitable for visualization.
    
    Args:
        columns: List of column names
        data: List of data rows
        
    Returns:
        Boolean indicating if data can be visualized
    """
    # Need at least some data to visualize
    if not data or not columns:
        return False
    
    # Need at least 2 columns for meaningful visualization
    if len(columns) < 2:
        return False
    
    # Check if we have enough rows for a visualization
    if len(data) < 2:
        # Special case: Single row might be suitable for a pie chart if we have multiple columns
        return len(columns) >= 3
    
    return True

def determine_visualization_type(columns: List[str], data: List[List[Any]], query: str = "", is_forecast: bool = False) -> str:
    """
    Determine the most appropriate visualization type for wildfire data.
    
    Args:
        columns: List of column names
        data: List of data rows
        query: The original query for context (optional)
        is_forecast: Whether this is a forecast visualization
        
    Returns:
        String indicating visualization type (line, bar, pie, scatter, etc.)
    """
    if not columns or not data:
        return "bar"
    
    columns_lower = [col.lower() for col in columns]
    row_count = len(data)
    query_lower = query.lower() if query else ""
    
    # Look for specific column patterns for wildfire data
    has_date = any('date' in col.lower() for col in columns)
    has_time = any('time' in col.lower() for col in columns)
    has_latitude = any('latitude' in col.lower() for col in columns)
    has_longitude = any('longitude' in col.lower() for col in columns)
    has_brightness = any('brightness' in col.lower() for col in columns)
    has_frp = any('frp' in col.lower() for col in columns)
    has_confidence = any('confidence' in col.lower() for col in columns)
    has_satellite = any('satellite' in col.lower() for col in columns)
    has_daynight = any('daynight' in col.lower() for col in columns)
    
    # Detect if this is geographic data that should be plotted on a map
    if has_latitude and has_longitude:
        # For now, fall back to scatter plot since map visualization is complex
        return "scatter"
    
    # Time series patterns
    if has_date:
        if row_count > 7:
            return "line"
        else:
            return "bar"
    
    # Satellite comparisons
    if has_satellite and any(term in query_lower for term in ['compare', 'comparison', 'between']):
        return "bar"
    
    # Day/night distributions
    if has_daynight and any(term in query_lower for term in ['distribution', 'proportion']):
        return "pie"
    
    # Confidence score distributions
    if has_confidence and any(term in query_lower for term in ['distribution', 'breakdown', 'histogram']):
        return "bar"
    
    # FRP or brightness comparisons
    if (has_frp or has_brightness) and row_count > 10:
        return "bar_horizontal"
    
    # Default to bar chart
    return "bar"

def identify_axes(columns: List[str], data: List[List[Any]], viz_type: str = "bar") -> Tuple[int, List[int]]:
    """
    Identify appropriate x-axis and y-axis columns for wildfire data.
    
    Args:
        columns: List of column names
        data: List of data rows
        viz_type: The visualization type (used to make better axis choices)
        
    Returns:
        Tuple containing (x_axis_index, [y_axis_indices])
    """
    columns_lower = [col.lower() for col in columns]
    
    # Find numeric columns (typically for y-axis)
    numeric_cols = []
    for i, col in enumerate(columns):
        if any(i < len(row) and isinstance(row[i], (int, float)) 
              and not isinstance(row[i], bool) for row in data[:min(5, len(data))]):
            numeric_cols.append(i)
    
    # For scatter plots (geographic data)
    if viz_type == "scatter":
        # Look for latitude/longitude
        lat_idx = next((i for i, col in enumerate(columns_lower) if 'latitude' in col), None)
        lon_idx = next((i for i, col in enumerate(columns_lower) if 'longitude' in col), None)
        
        if lat_idx is not None and lon_idx is not None:
            return lon_idx, [lat_idx]  # longitude as x, latitude as y
    
    # For other visualization types
    x_axis_candidates = []
    
    # Priority order for x-axis based on wildfire schema
    if viz_type in ["line", "bar", "bar_horizontal"]:
        x_axis_priorities = [
            'acq_date',                      # Time series should use date
            'satellite',                     # Satellite comparisons
            'daynight',                      # Day/night comparisons
            'confidence',                    # Confidence distributions
            'type',                          # Fire type comparisons
        ]
        
        for priority in x_axis_priorities:
            if priority in columns_lower:
                x_axis_candidates.append(columns_lower.index(priority))
    
    # Find the index of important measure columns - these should be y-axis
    brightness_index = next((i for i, col in enumerate(columns_lower) if 'brightness' in col), -1)
    frp_index = next((i for i, col in enumerate(columns_lower) if 'frp' in col), -1)
    count_index = next((i for i, col in enumerate(columns_lower) if 'count' in col), -1)
    
    # If no candidates yet, use the first non-numeric column
    if not x_axis_candidates:
        for i, col in enumerate(columns):
            if i not in numeric_cols:
                x_axis_candidates.append(i)
                break
    
    # If still no candidates, use the first column
    if not x_axis_candidates:
        x_axis_candidates.append(0)
    
    # Use the first suitable x-axis candidate
    x_axis = x_axis_candidates[0]
    
    # For y-axes, prioritize measure columns
    y_axes = []
    if count_index >= 0 and count_index != x_axis:
        y_axes.append(count_index)
    if brightness_index >= 0 and brightness_index != x_axis:
        y_axes.append(brightness_index)
    if frp_index >= 0 and frp_index != x_axis:
        y_axes.append(frp_index)
    
    # Add other numeric columns as y-axes
    for i in numeric_cols:
        if i != x_axis and i not in y_axes:
            y_axes.append(i)
    
    # If no y-axes found, use all non-x columns
    if not y_axes:
        y_axes = [i for i in range(len(columns)) if i != x_axis]
    
    return x_axis, y_axes

def _get_pie_chart_indices(columns: List[str], data: List[List[Any]]) -> Tuple[int, int]:
    """
    Determine the best columns to use for labels and values in a pie chart
    for wildfire data.
    
    Args:
        columns: List of column names
        data: List of data rows
        
    Returns:
        Tuple of (label_index, value_index)
    """
    columns_lower = [col.lower() for col in columns]
    
    # Try to find the best label column based on wildfire schema
    label_candidates = ['satellite', 'daynight', 'type', 'instrument']
    for candidate in label_candidates:
        if candidate in columns_lower:
            label_index = columns_lower.index(candidate)
            break
    else:
        # If no good label column found, use the first non-numeric column
        for i, col in enumerate(columns):
            if not all(isinstance(row[i], (int, float)) for row in data if i < len(row)):
                label_index = i
                break
        else:
            label_index = 0
    
    # Try to find the best value column
    if 'count' in columns_lower:
        value_index = columns_lower.index('count')
    elif 'brightness' in columns_lower:
        value_index = columns_lower.index('brightness')
    elif 'frp' in columns_lower:
        value_index = columns_lower.index('frp')
    else:
        # Otherwise use the first numeric column
        for i, col in enumerate(columns):
            if all(isinstance(row[i], (int, float)) for row in data[:min(5, len(data))] if i < len(row)):
                value_index = i
                break
        else:
            value_index = min(1, len(columns) - 1)
    
    return label_index, value_index

def _generate_title(columns: List[str], data: List[List[Any]], query: str, viz_type: str) -> str:
    """
    Generate a visualization title for wildfire data.
    
    Args:
        columns: List of column names
        data: List of data rows
        query: Original query string
        viz_type: Type of visualization
        
    Returns:
        Title string
    """
    query_lower = query.lower()
    
    # Extract subject matter
    subjects = []
    if "fire" in query_lower or "wildfire" in query_lower:
        subjects.append("Wildfire Detections")
    elif "brightness" in query_lower:
        subjects.append("Fire Brightness")
    elif "frp" in query_lower:
        subjects.append("Fire Radiative Power")
    elif "confidence" in query_lower:
        subjects.append("Detection Confidence")
    elif "satellite" in query_lower:
        subjects.append("Satellite Detections")
    
    if not subjects:
        subjects = ["Fire Data"]
    
    # Extract time period if mentioned
    date_pattern = r'\b\d{2}-\d{2}-\d{4}\b'
    dates = re.findall(date_pattern, query)
    year_pattern = r'\b20\d{2}\b'
    years = re.findall(year_pattern, query)
    
    time_range = ""
    if dates:
        if len(dates) >= 2:
            time_range = f" from {dates[0]} to {dates[-1]}"
        else:
            time_range = f" on {dates[0]}"
    elif years:
        if len(years) >= 2:
            time_range = f" from {years[0]} to {years[-1]}"
        else:
            time_range = f" in {years[0]}"
    
    # Extract intent
    if any(term in query_lower for term in ['trend', 'over time', 'temporal', 'daily', 'monthly']):
        intent = "Trend Analysis"
    elif any(term in query_lower for term in ['compare', 'comparison', 'versus', 'vs']):
        intent = "Comparison"
    elif any(term in query_lower for term in ['distribution', 'breakdown', 'proportion']):
        intent = "Distribution"
    elif any(term in query_lower for term in ['map', 'location', 'geographic', 'spatial']):
        intent = "Geographic Distribution"
    else:
        intent = "Analysis"
    
    # Build the title
    return f"{subjects[0]} {intent}{time_range}"

def generate_visualization_spec(columns: List[str], data: List[List[Any]], query: str, is_forecast: bool = False) -> Dict[str, Any]:
    """
    Generate a visualization specification based on query results for wildfire data.
    
    Args:
        columns: List of column names
        data: List of data rows
        query: Original query string for context
        is_forecast: Whether this is a forecast visualization
        
    Returns:
        Dictionary with visualization specification
    """
    if not is_visualizable(columns, data):
        raise VisualizationError("Data is not suitable for visualization")
    
    # Determine visualization type
    viz_type = determine_visualization_type(columns, data, query, is_forecast)
    
    # Identify appropriate axes
    x_axis, y_axes = identify_axes(columns, data, viz_type)
    
    # Generate a title
    title = _generate_title(columns, data, query, viz_type)
    
    # Create the specification
    spec = {
        "type": viz_type,
        "title": title,
        "x_axis": {
            "index": x_axis,
            "label": columns[x_axis]
        },
        "y_axes": [{"index": idx, "label": columns[idx]} for idx in y_axes],
        "data": data,
        "columns": columns
    }
    
    # Add type-specific configurations
    if viz_type == "pie":
        label_index, value_index = _get_pie_chart_indices(columns, data)
        spec["label_index"] = label_index
        spec["value_index"] = value_index
    
    return spec

def get_visualization_for_results(result_data: Dict[str, Any], query: str, forecast_metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Process query results to generate a visualization if appropriate.
    
    Args:
        result_data: Query result data
        query: Original user query
        forecast_metadata: Optional metadata for forecast visualizations
        
    Returns:
        Visualization specification or None if visualization is not appropriate
    """
    try:
        if not result_data or "columns" not in result_data or "data" not in result_data:
            return None
        
        columns = result_data["columns"]
        data = result_data["data"]
        
        if not is_visualizable(columns, data):
            return None
        
        # Generate the visualization specification
        viz_spec = generate_visualization_spec(columns, data, query)
        
        # Generate plot code for the client using the templates
        viz_spec["plot_code"] = get_plot_code(viz_spec)
        
        return viz_spec
    except Exception as e:
        logger.error(f"Error generating visualization: {str(e)}")
        return None