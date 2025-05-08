#!/usr/bin/env python
"""
Startup script for Climate Client.

This script starts the command-line interface to interact with the Climate Server.
"""

import os
import sys
import argparse

def main():
    """Start the client component."""
    parser = argparse.ArgumentParser(description="Start Climate Client")
    parser.add_argument("--server", help="Climate Server URL", default=None)
    args = parser.parse_args()
    
    # Set environment variables if provided via CLI
    if args.server:
        os.environ["CLIMATE_CLIENT_API_URL"] = args.server
    
    # Start the CLI
    from cli import main as cli_main
    return cli_main()

if __name__ == "__main__":
    sys.exit(main())