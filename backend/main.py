"""
Convenience entrypoint for the Smart Bug Analyzer backend.

Run from the backend folder:
    uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""

from app.main import app

__all__ = ["app"]
