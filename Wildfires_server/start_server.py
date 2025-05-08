#!/usr/bin/env python
"""
Startup script for Climate Server with debugging.

This script starts the FastAPI server and provides detailed error information.
"""

import os
import sys
import argparse
import traceback

def main():
    """Start the server component with detailed debugging."""
    parser = argparse.ArgumentParser(description="Start Climate Server")
    parser.add_argument("--host", help="API server host", default=None)
    parser.add_argument("--port", type=int, help="API server port", default=None)
    args = parser.parse_args()
    
    # Set environment variables if provided via CLI
    if args.host:
        os.environ["CLIMATE_SERVER_API_HOST"] = args.host
    if args.port:
        os.environ["CLIMATE_SERVER_API_PORT"] = str(args.port)
    
    # Set up paths properly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)  # Add climate_server to path
    
    # Print debugging information
    print("Python version:", sys.version)
    print("Current directory:", os.getcwd())
    print("Script directory:", current_dir)
    print("Python path:", sys.path)
    
    try:
        print("\nTrying to import src.config...")
        import src.config as config
        print("Successfully imported src.config")
        
        print(f"Starting Climate Server on {config.API_HOST}:{config.API_PORT}...")
        
        print("\nTrying to import app...")
        try:
            import app
            print("Successfully imported app")
            
            print("\nTrying to import uvicorn...")
            import uvicorn
            print("Successfully imported uvicorn")
            
            print("\nTrying to run uvicorn...")
            uvicorn.run(app.app, host=config.API_HOST, port=config.API_PORT)
        except Exception as e:
            print(f"Error while importing app: {str(e)}")
            print("\nDetailed traceback:")
            traceback.print_exc()
            return 1
    except ImportError as e:
        print(f"Import error: {str(e)}")
        print("\nDetailed traceback:")
        traceback.print_exc()
        
        # Try to identify which import is causing the issue
        try:
            print("\nTesting imports one by one:")
            
            try:
                import src
                print("- Successfully imported 'src'")
            except ImportError as e:
                print(f"- Failed to import 'src': {str(e)}")
            
            try:
                from src import config
                print("- Successfully imported 'src.config'")
            except ImportError as e:
                print(f"- Failed to import 'src.config': {str(e)}")
            
            try:
                from src.utils import logging_setup
                print("- Successfully imported 'src.utils.logging_setup'")
            except ImportError as e:
                print(f"- Failed to import 'src.utils.logging_setup': {str(e)}")
            
            try:
                from src.mcp_server import query_processor
                print("- Successfully imported 'src.mcp_server.query_processor'")
            except ImportError as e:
                print(f"- Failed to import 'src.mcp_server.query_processor': {str(e)}")
                
        except Exception as e:
            print(f"Error during import testing: {str(e)}")
        
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())