"""
Forecast execution module for ClimateGPT.

This module handles the creation of time series forecasts based on 
emissions data, orchestrating data retrieval, model training and visualization.
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

from src.mcp_server.db_access import execute_query
from src.utils.arima_forecaster import (
    generate_forecast, 
    format_forecast_explanation,
    generate_forecast_plot_code,
    ForecastError
)

# Set up logging
logger = logging.getLogger('forecast_executor')

# In forecast_executor.py

def build_forecast_query(forecast_params: Dict[str, Any]) -> str:
    """
    Build an enhanced SQL query to retrieve historical data with more features
    based on EPA's GHG inventory structure.
    
    Args:
        forecast_params: Dictionary with forecast parameters
        
    Returns:
        SQL query string
    """
    region = forecast_params.get('region')
    emission_type = forecast_params.get('emission_type')

    # Add these in build_forecast_query function
    print(f"DEBUG - Region value received: {region}")
    print(f"DEBUG - Emission type received: {emission_type}")
    
    # Enhanced query with more predictive features based on EPA data structure
    sql = """
    SELECT 
        e.year, 
        SUM(e.emissions) as total_emissions,
        
        -- Energy sector emissions by key categories
        SUM(CASE WHEN s.sector = 'Energy' AND s.subsector = 'Fossil Fuel Combustion' 
            THEN e.emissions ELSE 0 END) as fossil_fuel_emissions,
            
        SUM(CASE WHEN s.sector = 'Energy' AND s.subsector = 'Fugitive' 
            THEN e.emissions ELSE 0 END) as fugitive_emissions,
        
        -- Key sector emissions based on EPA categories
        SUM(CASE WHEN s.category = 'Transportation' 
            THEN e.emissions ELSE 0 END) as transportation_emissions,
            
        SUM(CASE WHEN s.sector = 'Industrial Processes'
            THEN e.emissions ELSE 0 END) as industrial_process_emissions,
            
        SUM(CASE WHEN s.sector = 'Agriculture'
            THEN e.emissions ELSE 0 END) as agriculture_emissions,
            
        -- Major fuel types 
        SUM(CASE WHEN f.fuel1 = 'Coal' THEN e.emissions ELSE 0 END) as coal_emissions,
        SUM(CASE WHEN f.fuel1 = 'Natural Gas' THEN e.emissions ELSE 0 END) as natural_gas_emissions,
        SUM(CASE WHEN f.fuel1 = 'Petroleum' THEN e.emissions ELSE 0 END) as petroleum_emissions
    FROM Emissions e
    JOIN Sectors s ON e.sector_id = s.sector_id
    JOIN Fuels f ON e.fuel_id = f.fuel_id
    JOIN Greenhouse_Gases gg ON e.ghg_id = gg.ghg_id
    """
    
    # Add conditional joins and where clauses
    where_clauses = []

    print(f"DEBUG - Where clauses before assembly: {where_clauses}")

    
    if emission_type and emission_type != 'Total Greenhouse Gas':
        where_clauses.append(f"gg.ghg_name = '{emission_type}'")
    
    if region:
        sql += "\nJOIN Geography g ON e.geo_id = g.geo_id"
        where_clauses.append(f"g.region_name = '{region}'")
    
    # Add where clauses
    if where_clauses:
        sql += "\nWHERE " + " AND ".join(where_clauses)
    
    # Finish the query with grouping by year
    sql += """
    GROUP BY e.year
    ORDER BY e.year
    """
    # After SQL query is fully constructed
    print(f"DEBUG - Final SQL query: {sql}")
    
    return sql

def execute_forecast(forecast_params: Dict[str, Any], original_query: str) -> Dict[str, Any]:
    """Execute forecast with enhanced multi-feature approach."""
    
    # Build enhanced query with more features
    sql_query = build_forecast_query(forecast_params)
    
    # Execute query
    df_result = execute_query(sql_query)

    # Add this at the beginning of execute_forecast in forecast_executor.py
    print(f"DEBUG - Forecast parameters: {forecast_params}")
    print(f"DEBUG - Region parameter: {forecast_params.get('region')}")
    
    # Check if we have data
    if df_result.empty or len(df_result) < 5:
        # Try a more generic query if specific parameters returned no data
        if forecast_params.get('region'):
            logger.info("Attempting more generic query without region filter")
            generic_params = forecast_params.copy()
            generic_params.pop('region', None)
            sql_query = build_forecast_query(generic_params)
            df_result = execute_query(sql_query)
    
    # Check if we still don't have enough data
    if df_result.empty or len(df_result) < 5:
        return {
            "type": "error",
            "error": "Insufficient historical data for forecasting. Need at least 5 years of data."
        }
    
    try:
        # Generate forecast using enhanced approach
        forecast_years = forecast_params.get('forecast_years', 10)
        forecast_data = generate_forecast(df_result, forecast_years)
        
        # Add historical data to forecast_data to ensure it's available for the explanation
        forecast_data['historical_data'] = {
            'years': df_result['year'].tolist(),
            'values': df_result['total_emissions'].tolist()
        }
        
        # Format the results for visualization system
        columns = ["year", "emissions", "type", "lower_ci", "upper_ci"]
        
        data = []
        # Add historical data
        for i, year in enumerate(df_result['year'].values):
            data.append([
                int(year), 
                float(df_result['total_emissions'].values[i]),
                "Historical",
                None,  # No CI for historical data
                None   # No CI for historical data
            ])
        
        # Add forecast data
        for i, year in enumerate(forecast_data['forecast']['years']):
            data.append([
                int(year), 
                forecast_data['forecast']['values'][i],
                "Forecast",
                forecast_data['forecast']['lower_ci'][i],
                forecast_data['forecast']['upper_ci'][i]
            ])
        
        # Create a title for the forecast visualization
        region_text = f"for {forecast_params.get('region')}" if forecast_params.get('region') else ""
        emission_text = forecast_params.get('emission_type', 'Total Greenhouse Gas')
        title = f"{emission_text} Emissions {region_text} Forecast"
        
        # Generate more descriptive insights using the formatted explanation
        insights = format_forecast_explanation(forecast_data)
        
        # Prepare standard result format with forecast data
        result = {
            "type": "database",
            "results": {
                "columns": columns,
                "data": data
            },
            "insights": insights,
            "sql": sql_query,
            "forecast_metadata": {
                "is_forecast": True,
                "forecast_years": forecast_years,
                "metrics": forecast_data.get('metrics', {}),
                "model_info": forecast_data.get('model_info', {})
            }
        }
        
        # Generate visualization code
        visualization_code = generate_forecast_plot_code(data, columns, title, forecast_data)
        
        # Add visualization to result
        result["visualization"] = {
            "type": "forecast_line",
            "title": title,
            "data": data,
            "columns": columns,
            "plot_code": visualization_code
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error executing forecast: {str(e)}")
        return {
            "type": "error",
            "error": f"Error generating forecast: {str(e)}"
        }