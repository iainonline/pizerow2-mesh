#!/bin/bash

# Meshtastic Monitor Dashboard Startup Script
# Activates virtual environment and runs mesh_monitor.py

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
MAIN_SCRIPT="$SCRIPT_DIR/mesh_monitor.py"

# Change to script directory
cd "$SCRIPT_DIR" || exit 1

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv "$VENV_DIR" || {
        echo "Failed to create virtual environment"
        exit 1
    }
    
    # Activate and install dependencies
    source "$VENV_DIR/bin/activate"
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt || {
        echo "Failed to install dependencies"
        exit 1
    }
    echo "Setup complete!"
else
    # Activate existing virtual environment
    source "$VENV_DIR/bin/activate"
fi

# Check if main script exists
if [ ! -f "$MAIN_SCRIPT" ]; then
    echo "Error: mesh_monitor.py not found in $SCRIPT_DIR"
    exit 1
fi

# Run the monitor
echo "Starting Meshtastic Monitor Dashboard..."
python "$MAIN_SCRIPT"
