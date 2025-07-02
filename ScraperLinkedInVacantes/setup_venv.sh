#!/bin/bash
# Script to set up Python virtual environment and install dependencies for the LinkedIn scraper

set -e

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

echo "Virtual environment setup complete. Activate with: source venv/bin/activate" 