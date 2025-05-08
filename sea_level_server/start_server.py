#!/usr/bin/env python
"""
Startup script for Sea Level Server.
"""
import os
import sys
import argparse
import traceback

def main():
    """Start the Sea Level Server component."""
    parser = argparse.ArgumentParser(description="Start Sea Level Server")
    parser.add_argument("--host", help="API server host", default="127.0.0.1")
    parser.add_argument("--port", type=int, help="API server port", default=8001)
    args = parser.parse_args()
    
    # Set environment variables for sea level server
    os.environ["CLIMATE_SERVER_API_HOST"] = args.host
    os.environ["CLIMATE_SERVER_API_PORT"] = str(args.port)
    os.environ["CLIMATE_SERVER_DB_PATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                                      "src/database/Sea_Level_data.db")
    
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
        
        print(f"Starting Sea Level Server on {config.API_HOST}:{config.API_PORT}...")
        
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
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())