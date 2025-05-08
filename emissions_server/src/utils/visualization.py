# src/utils/visualization.py
"""
Visualization module for ClimateGPT.

This module analyzes query results to determine visualization suitability and
generates visualization specifications that can be rendered by the client.
"""

import logging
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
    Determine the most appropriate visualization type for climate data,
    with special handling for negative values and forecasts.
    
    Args:
        columns: List of column names
        data: List of data rows
        query: The original query for context (optional)
        is_forecast: Whether this is a forecast visualization
        
    Returns:
        String indicating visualization type (line, bar, pie, etc.)
    """

    # If this is explicitly a forecast, use forecast_line type
    if is_forecast:
        return "forecast_line"    # Make sure we have data to work with
    
    if not columns or not data:
        return "bar"  # Default when data is insufficient
    
    # Convert column names to lowercase for easier comparison
    columns_lower = [col.lower() for col in columns]
    
    # Count of rows and columns
    row_count = len(data)
    col_count = len(columns)
    
    # Look for specific column patterns from our schema
    has_year = any('year' in col.lower() for col in columns)
    has_emissions = any('emissions' in col.lower() for col in columns)
    has_region = any(col in ['region_name', 'geo_ref', 'state'] for col in columns_lower)
    has_ghg = any(col in ['ghg_name', 'ghg_category'] for col in columns_lower)
    has_sector = any(col in ['sector', 'subsector', 'category'] for col in columns_lower)
    has_fuel = any(col in ['fuel1', 'fuel2'] for col in columns_lower)
    
    # Detect numeric columns (mainly for emissions values)
    numeric_cols = []
    for i, col in enumerate(columns):
        # Check first few rows to determine if column is numeric
        if any(i < len(row) and isinstance(row[i], (int, float)) 
              and not isinstance(row[i], bool) for row in data[:min(5, len(data))]):
            numeric_cols.append(i)
    
    # Check for negative values in numeric columns
    has_negative_values = False
    for i in numeric_cols:
        for row in data:
            if i < len(row) and isinstance(row[i], (int, float)) and row[i] < 0:
                has_negative_values = True
                break
        if has_negative_values:
            break
    
    # Extract query intent
    query_lower = query.lower() if query else ""
    
    # Look for intent keywords in the query
    trend_keywords = ['trend', 'over time', 'change', 'evolution', 'history', 'series', 'since']
    comparison_keywords = ['compare', 'comparison', 'versus', 'vs', 'between', 'difference']
    distribution_keywords = ['distribution', 'breakdown', 'proportion', 'percentage', 'share', 'split']
    ranking_keywords = ['ranking', 'rank', 'top', 'highest', 'lowest']
    
    # Check for query intents - force exact matching to avoid false positives
    has_trend_intent = any(keyword in query_lower for keyword in trend_keywords)
    has_comparison_intent = any(keyword in query_lower for keyword in comparison_keywords)
    has_distribution_intent = any(keyword in query_lower for keyword in distribution_keywords)
    has_ranking_intent = any(keyword in query_lower for keyword in ranking_keywords)
    
    # ==== DECISION LOGIC ====
    
    # 1. Time Series Patterns - Emissions over time
    if has_year and numeric_cols:
        # Multi-year analysis with trend intent strongly suggests line chart
        if has_trend_intent:
            return "line"
        # Comparison of specific years might be better as bars
        elif has_comparison_intent and row_count <= 10:
            return "bar"
        # Default to line for time series with many points
        elif row_count > 7:
            return "line"
        # Few time points are better as bar charts
        else:
            return "bar"
    
    # 2. Geographic Comparisons - Emissions by region
    if has_region and numeric_cols:
        # Many regions work better with horizontal bars
        if row_count > 8:
            return "bar_horizontal"
        # Few regions can use standard bars
        else:
            return "bar"
    
    # 3. Sectoral Distributions - Emissions by sector
    if has_sector and numeric_cols:
        # Distribution of sectors for pie chart - BUT only if no negative values
        if has_distribution_intent and row_count <= 7 and not has_negative_values:
            return "pie"
        # If there are negative values, we should use bars instead
        elif has_distribution_intent and has_negative_values:
            return "bar"
        # Rankings of many sectors work better as horizontal bars
        elif (has_ranking_intent or has_comparison_intent) and row_count > 7:
            return "bar_horizontal"
        # Few sectors can use standard bars
        else:
            return "bar"
    
    # 4. GHG Type Breakdown - Distribution of greenhouse gases
    if has_ghg and numeric_cols:
        # GHG distribution works well as pie chart when explicitly asked - BUT only if no negative values
        if has_distribution_intent and row_count <= 7 and not has_negative_values:
            return "pie"
        # If there are negative values, we should use bars instead
        elif has_distribution_intent and has_negative_values:
            return "bar"
        # Default to bar for GHG comparisons
        else:
            return "bar"
    
    # 5. Fuel Type Analysis
    if has_fuel and numeric_cols:
        # Fuel type distribution works well with pie charts - BUT only if no negative values
        if has_distribution_intent and row_count <= 7 and not has_negative_values:
            return "pie"
        # If there are negative values, we should use bars instead
        elif has_distribution_intent and has_negative_values:
            return "bar"
        # Default to bar for fuel comparisons
        else:
            return "bar"
    
    # 6. Special case: Single row with multiple numeric columns suggests pie chart
    if row_count == 1 and len(numeric_cols) >= 2 and has_distribution_intent and not has_negative_values:
        return "pie"
    
    # 7. Many categories (such as full lists of regions, sectors, etc.)
    if row_count > 10 and len(numeric_cols) >= 1:
        return "bar_horizontal"  # Horizontal bars work best for many categories
    
    # Default to bar chart as it's the most versatile
    return "bar"

def identify_axes(columns: List[str], data: List[List[Any]], viz_type: str = "bar") -> Tuple[int, List[int]]:
    """
    Identify appropriate x-axis and y-axis columns based on chart type
    and climate database schema knowledge.
    
    Args:
        columns: List of column names
        data: List of data rows
        viz_type: The visualization type (used to make better axis choices)
        
    Returns:
        Tuple containing (x_axis_index, [y_axis_indices])
    """
    # Convert column names to lowercase for easier comparison
    columns_lower = [col.lower() for col in columns]
    
    # Find numeric columns (typically for y-axis)
    numeric_cols = []
    for i, col in enumerate(columns):
        # Check if column contains numeric data
        if any(i < len(row) and isinstance(row[i], (int, float)) 
              and not isinstance(row[i], bool) for row in data[:min(5, len(data))]):
            numeric_cols.append(i)
    
    # For all visualization types, we want a sensible x-axis
    x_axis_candidates = []
    
    # Based on the schema, prioritize different columns for x-axis depending on viz_type
    if viz_type in ["line", "bar", "bar_horizontal"]:
        # Priority order for x-axis based on climate schema
        x_axis_priorities = [
            'year',                                      # Time series should use year
            'region_name', 'geo_ref', 'state',          # Geographic comparisons
            'sector', 'category', 'subsector',          # Sector comparisons
            'ghg_name', 'ghg_category',                # GHG type comparisons
            'fuel1'                                     # Fuel type comparisons
        ]
        
        # Try to find the best x-axis column in order of priority
        for priority in x_axis_priorities:
            if priority.lower() in columns_lower:
                x_axis_candidates.append(columns_lower.index(priority.lower()))
                
    # Find the index of 'emissions' column - this should almost always be a y-axis
    emissions_index = -1
    if 'emissions' in columns_lower:
        emissions_index = columns_lower.index('emissions')
    
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
    
    # For y-axes, prioritize emissions column if present
    y_axes = []
    if emissions_index >= 0 and emissions_index != x_axis:
        y_axes.append(emissions_index)
    
    # Add other numeric columns as y-axes
    for i in numeric_cols:
        if i != x_axis and i not in y_axes:
            y_axes.append(i)
    
    # If no y-axes found, use all non-x columns
    if not y_axes:
        y_axes = [i for i in range(len(columns)) if i != x_axis]
        
    # For pie charts, special handling may be needed but this is now handled in _get_pie_chart_indices
    
    return x_axis, y_axes

def _get_pie_chart_indices(columns: List[str], data: List[List[Any]]) -> Tuple[int, int]:
    """
    Determine the best columns to use for labels and values in a pie chart
    based on the schema knowledge.
    
    Args:
        columns: List of column names
        data: List of data rows
        
    Returns:
        Tuple of (label_index, value_index)
    """
    # Convert column names to lowercase for comparison
    columns_lower = [col.lower() for col in columns]
    
    # Try to find the best label column based on climate schema
    label_candidates = ['ghg_name', 'sector', 'region_name', 'fuel1', 'state']
    for candidate in label_candidates:
        if candidate.lower() in columns_lower:
            label_index = columns_lower.index(candidate.lower())
            break
    else:
        # If no good label column found, use the first non-numeric column
        for i, col in enumerate(columns):
            # Check if column is non-numeric
            if not all(isinstance(row[i], (int, float)) for row in data if i < len(row)):
                label_index = i
                break
        else:
            # Fallback to first column if everything else fails
            label_index = 0
    
    # Try to find the best value column - emissions is the preferred choice
    if 'emissions' in columns_lower:
        value_index = columns_lower.index('emissions')
    else:
        # Otherwise use the first numeric column
        for i, col in enumerate(columns):
            # Check if column is numeric
            if all(isinstance(row[i], (int, float)) for row in data[:min(5, len(data))] if i < len(row)):
                value_index = i
                break
        else:
            # Fallback to second column if everything else fails
            value_index = min(1, len(columns) - 1)
    
    return label_index, value_index

import re
from typing import List, Dict, Any, Optional

def _generate_title(columns: List[str], data: List[List[Any]], query: str, viz_type: str) -> str:
    """
    Generate a visualization title using an enhanced rule-based approach
    incorporating EPA GHG Inventory terminology.
    
    Args:
        columns: List of column names
        data: List of data rows
        query: Original query string
        viz_type: Type of visualization
        
    Returns:
        Title string
    """
    # Convert query to lowercase for easier matching
    query_lower = query.lower()
    
    # Dictionary mapping normalized terms to display terms for greenhouse gases
    ghg_mapping = {
        "co2": "CO₂",
        "carbon dioxide": "CO₂",
        "ch4": "CH₄",
        "methane": "CH₄",
        "n2o": "N₂O",
        "nitrous oxide": "N₂O",
        "greenhouse gas": "Greenhouse Gas",
        "ghg": "Greenhouse Gas",
        "hydrofluorocarbons": "HFCs",
        "hfcs": "HFCs",
        "perfluorocarbons": "PFCs",
        "pfcs": "PFCs",
        "sulfur hexafluoride": "SF₆",
        "sf6": "SF₆",
        "nitrogen trifluoride": "NF₃",
        "nf3": "NF₃",
        "fluorinated": "Fluorinated Gas",
        "co2e": "CO₂e",
        "co2 equivalent": "CO₂e"
    }
    
    # IPCC Sectors from the metadata
    ipcc_sector_mapping = {
        "energy": "Energy",
        "industrial processes": "Industrial Processes",
        "agriculture": "Agriculture",
        "waste": "Waste",
        "land-use change": "Land-Use Change",
        "forestry": "Forestry",
        "lulucf": "LULUCF",
        "land use change and forestry": "LULUCF"
    }
    
    # Economic sectors from the metadata
    econ_sector_mapping = {
        "transportation": "Transportation",
        "electric power": "Electric Power",
        "industry": "Industry",
        "agriculture": "Agriculture",
        "commercial": "Commercial",
        "residential": "Residential",
        "u.s. territories": "U.S. Territories"
    }
    
    # Categories and subcategories from the metadata
    category_mapping = {
        "fossil fuel combustion": "Fossil Fuel Combustion",
        "fugitive": "Fugitive Emissions",
        "incineration of waste": "Waste Incineration",
        "chemical industry": "Chemical Industry",
        "metal industry": "Metal Industry", 
        "mineral industry": "Mineral Industry",
        "electronics industry": "Electronics Industry",
        "substitution of ozone depleting substances": "ODS Substitution",
        "agricultural soil management": "Agricultural Soil Management",
        "enteric fermentation": "Enteric Fermentation",
        "manure management": "Manure Management",
        "rice cultivation": "Rice Cultivation",
        "field burning": "Field Burning",
        "solid waste disposal": "Solid Waste Disposal",
        "landfills": "Landfills",
        "wastewater treatment": "Wastewater Treatment",
        "composting": "Composting"
    }
    
    # Fuel types from the metadata
    fuel_mapping = {
        "coal": "Coal",
        "natural gas": "Natural Gas",
        "petroleum": "Petroleum",
        "biomass": "Biomass",
        "fossil fuel": "Fossil Fuel"
    }
    
    # States and territories for geography
    geo_mapping = {
        "alabama": "Alabama", "al": "Alabama",
        "alaska": "Alaska", "ak": "Alaska", 
        "arizona": "Arizona", "az": "Arizona",
        "arkansas": "Arkansas", "ar": "Arkansas",
        "california": "California", "ca": "California",
        "colorado": "Colorado", "co": "Colorado",
        "connecticut": "Connecticut", "ct": "Connecticut",
        "delaware": "Delaware", "de": "Delaware",
        "florida": "Florida", "fl": "Florida",
        "georgia": "Georgia", "ga": "Georgia",
        "hawaii": "Hawaii", "hi": "Hawaii",
        "idaho": "Idaho", "id": "Idaho",
        "illinois": "Illinois", "il": "Illinois",
        "indiana": "Indiana", "in": "Indiana",
        "iowa": "Iowa", "ia": "Iowa",
        "kansas": "Kansas", "ks": "Kansas",
        "kentucky": "Kentucky", "ky": "Kentucky",
        "louisiana": "Louisiana", "la": "Louisiana",
        "maine": "Maine", "me": "Maine",
        "maryland": "Maryland", "md": "Maryland",
        "massachusetts": "Massachusetts", "ma": "Massachusetts",
        "michigan": "Michigan", "mi": "Michigan",
        "minnesota": "Minnesota", "mn": "Minnesota",
        "mississippi": "Mississippi", "ms": "Mississippi",
        "missouri": "Missouri", "mo": "Missouri",
        "montana": "Montana", "mt": "Montana",
        "nebraska": "Nebraska", "ne": "Nebraska",
        "nevada": "Nevada", "nv": "Nevada",
        "new hampshire": "New Hampshire", "nh": "New Hampshire",
        "new jersey": "New Jersey", "nj": "New Jersey",
        "new mexico": "New Mexico", "nm": "New Mexico",
        "new york": "New York", "ny": "New York",
        "north carolina": "North Carolina", "nc": "North Carolina",
        "north dakota": "North Dakota", "nd": "North Dakota",
        "ohio": "Ohio", "oh": "Ohio",
        "oklahoma": "Oklahoma", "ok": "Oklahoma",
        "oregon": "Oregon", "or": "Oregon",
        "pennsylvania": "Pennsylvania", "pa": "Pennsylvania",
        "rhode island": "Rhode Island", "ri": "Rhode Island",
        "south carolina": "South Carolina", "sc": "South Carolina",
        "south dakota": "South Dakota", "sd": "South Dakota",
        "tennessee": "Tennessee", "tn": "Tennessee",
        "texas": "Texas", "tx": "Texas",
        "utah": "Utah", "ut": "Utah",
        "vermont": "Vermont", "vt": "Vermont",
        "virginia": "Virginia", "va": "Virginia",
        "washington": "Washington", "wa": "Washington",
        "west virginia": "West Virginia", "wv": "West Virginia",
        "wisconsin": "Wisconsin", "wi": "Wisconsin",
        "wyoming": "Wyoming", "wy": "Wyoming",
        "district of columbia": "D.C.", "dc": "D.C.",
        "territories": "U.S. Territories",
        "us territories": "U.S. Territories",
        "federal offshore": "Federal Offshore",
        "national": "National",
        "united states": "U.S.",
        "us": "U.S.",
        "usa": "U.S."
    }
    
    # Extract time period using regex for years
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', query)
    
    time_range = ""
    if len(years) >= 2:
        years.sort()
        time_range = f"from {years[0]} to {years[-1]}"
    elif len(years) == 1:
        time_range = f"in {years[0]}"
    elif "over time" in query_lower or "trend" in query_lower:
        time_range = "over time"
    
    # Extract subject matter - prioritize GHGs, then sectors, then fuels
    subjects = []
    
    # First check for GHG terms
    for term, display in ghg_mapping.items():
        if term in query_lower:
            if display not in subjects:
                subjects.append(display)
    
    # If no GHG terms, check for IPCC sectors
    if not subjects:
        for term, display in ipcc_sector_mapping.items():
            if term in query_lower:
                if display not in subjects:
                    subjects.append(f"{display} Emissions")
    
    # If still no subjects, check for economic sectors
    if not subjects:
        for term, display in econ_sector_mapping.items():
            if term in query_lower:
                if display not in subjects:
                    subjects.append(f"{display} Emissions")
    
    # If still no subjects, check for categories
    if not subjects:
        for term, display in category_mapping.items():
            if term in query_lower:
                if display not in subjects:
                    subjects.append(f"{display} Emissions")
    
    # If still no subjects, check for fuel terms
    if not subjects:
        for term, display in fuel_mapping.items():
            if term in query_lower:
                if display not in subjects:
                    subjects.append(f"{display} Emissions")
    
    # Default to emissions if no subject found
    if not subjects:
        subjects = ["Emissions"]
    
    # Extract geographic scope
    locations = []
    for term, display in geo_mapping.items():
        # Use word boundaries to avoid partial matches (e.g., "in" matching "Indiana")
        if re.search(r'\b' + re.escape(term) + r'\b', query_lower):
            if display not in locations:
                locations.append(display)
    
    # Determine visualization intent (trend, comparison, distribution)
    intent = None
    
    # Trend-related terms
    trend_terms = ["trend", "time series", "over time", "historical", "change", "evolution", 
                 "increase", "decrease", "growing", "declining", "annual", "yearly"]
    for term in trend_terms:
        if term in query_lower:
            intent = "Trend"
            break
    
    # Comparison-related terms
    if not intent:
        comparison_terms = ["compare", "comparison", "versus", "vs", "between", "difference", 
                          "relative", "against", "contrast"]
        for term in comparison_terms:
            if term in query_lower:
                intent = "Comparison"
                break
    
    # Distribution-related terms
    if not intent:
        distribution_terms = ["distribution", "breakdown", "proportion", "percentage", 
                            "share", "split", "composition", "makeup", "allocation"]
        for term in distribution_terms:
            if term in query_lower:
                intent = "Distribution"
                break
    
    # If intent not determined from terminology, use visualization type
    if not intent:
        if viz_type == "line":
            intent = "Trend"
        elif viz_type in ["bar", "bar_horizontal"]:
            intent = "Comparison"
        elif viz_type == "pie":
            intent = "Distribution"
        else:
            intent = "Analysis"  # Default for other visualization types
    
    # Construct title with all components
    title_parts = []
    
    # Add subject (limit to two for readability)
    if subjects:
        title_parts.append(", ".join(subjects[:2]))
    
    # Add intent
    if intent:
        title_parts.append(intent)
    
    # Add location (limit to two for readability)
    if locations:
        title_parts.append("for " + ", ".join(locations[:2]))
    
    # Add time range
    if time_range:
        title_parts.append(time_range)
    
    # Assemble the final title
    if title_parts:
        return " ".join(title_parts)
    
    # Fallback to simpler title based on columns if no meaningful parts found
    x_axis, y_axes = identify_axes(columns, data)
    return f"{columns[y_axes[0]]} by {columns[x_axis]}"

def generate_visualization_spec(columns: List[str], data: List[List[Any]], query: str, is_forecast: bool = False) -> Dict[str, Any]:
    """
    Generate a visualization specification based on query results and schema knowledge.
    
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
    
    # Determine visualization type using our schema-aware function
    viz_type = determine_visualization_type(columns, data, query, is_forecast)
    
    # Identify appropriate axes based on schema knowledge
    x_axis, y_axes = identify_axes(columns, data, viz_type)
    
    # Generate a title based on columns and data
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
        # Determine best columns for pie chart based on schema
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
        
        # Special case for forecasts - we may already have a visualization
        if forecast_metadata and forecast_metadata.get("is_forecast", False):
            # If there's already a plot_code in the result_data, use it
            if "plot_code" in result_data:
                return {
                    "type": "forecast_line",
                    "title": "Emissions Forecast",
                    "data": data,
                    "columns": columns,
                    "plot_code": result_data["plot_code"]
                }
        
        if not is_visualizable(columns, data):
            return None
        
        # Check if this is a forecast (has a 'type' column with 'Forecast' values)
        is_forecast = False
        if 'type' in columns:
            type_idx = columns.index('type')
            is_forecast = any(row[type_idx] == 'Forecast' for row in data if len(row) > type_idx)
        
        # Generate the visualization specification
        viz_spec = generate_visualization_spec(columns, data, query, is_forecast)
        
        # Generate plot code for the client using the templates
        viz_spec["plot_code"] = get_plot_code(viz_spec)
        
        return viz_spec
    except Exception as e:
        logger.error(f"Error generating visualization: {str(e)}")
        return None