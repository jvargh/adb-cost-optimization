"""
Entry point for running the scanner as a module.
Allows execution via: python -m dbx_discovery
"""

from .cli import main

if __name__ == "__main__":
    main()
