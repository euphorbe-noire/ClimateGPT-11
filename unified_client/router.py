"""
Router module for Climate Client using ClimateGPT for server selection.

This module handles routing of queries to appropriate ClimateGPT servers
based on intelligent server selection.
"""

import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple

from config import (
    REGISTRY_PATH, 
    CLIMATEGPT_API_URL,
    CLIMATEGPT_USER,
    CLIMATEGPT_PASSWORD,
    CLIMATEGPT_TIMEOUT,
    CLIMATEGPT_MAX_TOKENS,
    CLIMATEGPT_TEMPERATURE
)

# Set up logging
logger = logging.getLogger('climate_router')

class ClimateRouter:
    """Router for directing queries to appropriate climate servers."""
    
    def __init__(self):
        """Initialize the router by loading the server registry."""
        self.registry = self._load_registry()
        logger.info(f"Loaded server registry with {len(self.registry)} servers")
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load the server registry from the JSON file."""
        try:
            with open(REGISTRY_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading server registry: {str(e)}")
            raise
    
    def select_server(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Use ClimateGPT to select the most appropriate server for this query.
        
        Args:
            query: The user's natural language query
            
        Returns:
            Tuple of (server_name, server_config) for the best matching server
        """
        # Create a description of each server from the registry
        server_descriptions = []
        for server_name, server_config in self.registry.items():
            if server_name == "climategpt_api":
                continue
                
            description = server_config.get("description", "")
            capabilities = server_config.get("capabilities", [])
            schema = server_config.get("schema", {})
            
            server_info = f"Server: {server_name}\n"
            server_info += f"Description: {description}\n"
            server_info += f"Capabilities: {', '.join(capabilities)}\n"
            
            if schema:
                server_info += f"Data tables: {', '.join(schema.get('tables', []))}\n"
                server_info += f"Time range: {schema.get('time_range', '')}\n"
            
            server_descriptions.append(server_info)
        
        # Create a prompt for ClimateGPT
        prompt = f"""
You are assisting a climate data system by selecting the appropriate server to handle a user query.
Based on the query, determine which specialized server would be best, or if the query should be answered directly.

User query: "{query}"

Available servers:
{chr(10).join(server_descriptions)}

If the query requires specialized data access, forecasting, or visualization from one of the described servers, 
select that server. If the query is a general climate knowledge question that doesn't need specific 
data access, respond with "general_knowledge".

Respond with only one of the following options:
{", ".join([name for name in self.registry if name != "climategpt_api"])}
OR
general_knowledge
"""
        
        try:
            # Prepare the payload for the API
            payload = {
                "model": "/cache/climategpt_8b_latest",
                "messages": [
                    {"role": "system", "content": "You are an AI assistant that routes climate queries to the appropriate server."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,  # Lower temperature for more deterministic selection
                "max_tokens": 50     # Only need a short response
            }
            
            # Send request to ClimateGPT API
            response = requests.post(
                CLIMATEGPT_API_URL,
                json=payload,
                auth=(CLIMATEGPT_USER, CLIMATEGPT_PASSWORD),
                timeout=CLIMATEGPT_TIMEOUT
            )
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip().lower()
            
            logger.info(f"ClimateGPT server selection: {content}")
            
            # If response is a server name, return that server
            for server_name in self.registry:
                if server_name.lower() in content:
                    return server_name, self.registry[server_name]
            
            # If response indicates general knowledge, return None
            if "general_knowledge" in content:
                return None, None
                
            # If we couldn't parse the response, default to None
            logger.warning(f"Could not parse server selection response: {content}")
            return None, None
            
        except Exception as e:
            logger.error(f"Error in server selection: {str(e)}")
            return None, None
    
    def query_server(self, server_name: str, server_config: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Send a query to a specific server.
        
        Args:
            server_name: Name of the server to query
            server_config: Configuration for the server
            query: The natural language query
            
        Returns:
            Response from the server
        """
        url = server_config.get("url", "")
        if not url:
            logger.error(f"No URL found for server {server_name}")
            return {"error": f"No URL found for server {server_name}"}
        
        # Append /query endpoint if not included in the URL
        if not url.endswith("/query"):
            url = f"{url}/query"
        
        timeout = server_config.get("timeout", 600)
        
        try:
            logger.info(f"Sending query to {server_name} at {url}")
            response = requests.post(
                url,
                json={"query": query},
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying server {server_name}: {str(e)}")
            return {"error": f"Error communicating with {server_name}: {str(e)}"}
    
    def query_climategpt(self, query: str) -> Dict[str, Any]:
        """
        Send a general knowledge query directly to ClimateGPT API.
        
        Args:
            query: The natural language query
            
        Returns:
            Formatted response from ClimateGPT API
        """
        try:
            logger.info(f"Sending query to ClimateGPT API")
            
            # Prepare the payload for the API
            payload = {
                "model": "/cache/climategpt_8b_latest",
                "messages": [
                    {"role": "system", "content": "You are an AI assistant specialized in climate data analysis."},
                    {"role": "user", "content": query}
                ],
                "temperature": CLIMATEGPT_TEMPERATURE,
                "max_tokens": CLIMATEGPT_MAX_TOKENS
            }
            
            # Send request to ClimateGPT API
            response = requests.post(
                CLIMATEGPT_API_URL,
                json=payload,
                auth=(CLIMATEGPT_USER, CLIMATEGPT_PASSWORD),
                timeout=CLIMATEGPT_TIMEOUT
            )
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Format the response to match the server response format
            return {
                "type": "general_knowledge",
                "result": {"answer": content}
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying ClimateGPT API: {str(e)}")
            return {"error": f"Error communicating with ClimateGPT API: {str(e)}"}
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a user query by routing to the appropriate server.
        
        This is the main entry point that should be called by the CLI.
        
        Args:
            query: The user's natural language query
            
        Returns:
            Response from the appropriate server or ClimateGPT
        """
        # First, use ClimateGPT to select the appropriate server
        server_name, server_config = self.select_server(query)
        
        if server_name and server_config:
            # We found a matching server, send the query there
            return self.query_server(server_name, server_config, query)
        
        # No matching server found, use ClimateGPT for general knowledge
        return self.query_climategpt(query)