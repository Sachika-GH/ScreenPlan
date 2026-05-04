#!/usr/bin/env python3
"""Simple runner for ScreenPlan backend."""
from app import app
from config import SERVER_HOST, SERVER_PORT, DEBUG

if __name__ == "__main__":
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG)
