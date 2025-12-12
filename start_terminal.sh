#!/bin/bash
# Startup script for Meshtastic Terminal Monitor

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Run the terminal monitor
python mesh_terminal.py
