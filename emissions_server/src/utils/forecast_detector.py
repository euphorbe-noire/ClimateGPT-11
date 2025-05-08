"""
Forecast detection module for ClimateGPT.

This module analyzes user queries to identify when they are requesting
emissions forecasts or predictions for future years.
"""

import re
from typing import Tuple, Dict, Any, Optional

def is_forecast_query(query: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Determine if a query is requesting a forecast or prediction.
    
    Args:
        query: User's natural language query
        
    Returns:
        Tuple containing:
        - Boolean indicating if this is a forecast query
        - Dictionary with forecast parameters if it is a forecast query, None otherwise
    """
# Convert to lowercase for easier pattern matching
    query_lower = query.lower().strip()
    
    # Check if query explicitly asks for forecast/prediction
    forecast_keywords = ["forecast", "predict", "projection", "future trend", "future emission"]
    is_forecast = any(query_lower.startswith(keyword) for keyword in ["forecast", "predict"]) or \
                 any(keyword in query_lower for keyword in forecast_keywords)
    
    if not is_forecast:
        return False, None
    
    # Extract forecast parameters
    forecast_params = {}
    
    # Try to determine forecast horizon (number of years to forecast)
    year_matches = re.findall(r'(\d{4})', query)
    future_years = [y for y in year_matches if int(y) > 2022]  # Assuming database ends at 2022
    
    # Default forecast horizon is 10 years if not specified
    forecast_params['forecast_years'] = 10
    
    if future_years:
        # If specific future years are mentioned, forecast to the furthest one
        max_year = max(future_years)
        forecast_params['forecast_years'] = int(max_year) - 2022  # Assuming database ends at 2022
    elif 'next' in query_lower:
        # Look for phrases like "next 20 years"
        horizon_match = re.search(r'next\s+(\d+)\s+years?', query_lower)
        if horizon_match:
            forecast_params['forecast_years'] = int(horizon_match.group(1))
    elif 'till' in query_lower or 'until' in query_lower or 'through' in query_lower:
        # Look for phrases like "until 2035" or "through 2040"
        year_pattern = r'(?:till|until|through)\s+(\d{4})'
        year_match = re.search(year_pattern, query_lower)
        if year_match:
            end_year = int(year_match.group(1))
            if end_year > 2022:  # Only consider future years
                forecast_params['forecast_years'] = end_year - 2022
    
    # Try to determine what to forecast (which emission type, region, etc.)
    emission_types = {
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
    
    forecast_params['emission_type'] = 'Total Greenhouse Gas'  # Default
    for key, value in emission_types.items():
        if key in query_lower:
            forecast_params['emission_type'] = value
            break
    
    # Look for specific regions
    regions = {
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
    
    # Look for regions using word boundaries to avoid partial matches
    forecast_params['region'] = None  # Default to global/no specific region
    for key, value in regions.items():
    # Use word boundaries to avoid partial matches (e.g., "in" matching "Indiana")
        if re.search(r'\b' + re.escape(key) + r'\b', query_lower):
            forecast_params['region'] = value
            break
    
    # Look for sectors
    sectors = {
    'transportation': 'Transportation',
    'transport': 'Transportation',
    'electric power': 'Electric Power',
    'energy': 'Energy',
    'industry': 'Industry',
    'industrial': 'Industrial',
    'industrial processes': 'Industrial Processes',
    'agriculture': 'Agriculture',
    'commercial': 'Commercial',
    'residential': 'Residential',
    'waste': 'Waste',
    'forestry': 'Forestry',
    'lulucf': 'LULUCF',
    'land use change and forestry': 'LULUCF'
}
    
    forecast_params['sector'] = None  # Default to no specific sector
    for key, value in sectors.items():
        if key in query_lower:
            forecast_params['sector'] = value
            break

    # Ensure forecast years is at least 1
    if forecast_params['forecast_years'] < 1:
        forecast_params['forecast_years'] = 10  # Default to 10 years
    
    return True, forecast_params