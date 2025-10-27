#!/bin/bash

# Meshtastic Bluetooth Controller Startup Script
# Optimized for Raspberry Pi 5 with Heltec V3 devices

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_VERSION="3.11"  # Recommended for Raspberry Pi 5
LOG_FILE="$SCRIPT_DIR/meshtastic_app.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "[ERROR] $1" >> "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "[SUCCESS] $1" >> "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "[WARNING] $1" >> "$LOG_FILE"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check if running on Raspberry Pi
    if [ -f /proc/device-tree/model ]; then
        MODEL=$(cat /proc/device-tree/model)
        if [[ $MODEL == *"Raspberry Pi"* ]]; then
            log_success "Running on Raspberry Pi: $MODEL"
        else
            log_warning "Not detected as Raspberry Pi, but continuing anyway"
        fi
    fi
    
    # Check Python version
    if command_exists python3; then
        PYTHON_VER=$(python3 --version 2>&1 | awk '{print $2}')
        log "Found Python version: $PYTHON_VER"
        
        # Check if Python 3.9+ is available
        if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"; then
            log_success "Python version is compatible"
        else
            log_error "Python 3.9+ is required. Found: $PYTHON_VER"
            exit 1
        fi
    else
        log_error "Python 3 is not installed"
        exit 1
    fi
    
    # Check if pip is available
    if ! command_exists pip3; then
        log_error "pip3 is not installed. Please install with: sudo apt update && sudo apt install python3-pip"
        exit 1
    fi
    
    # Check Bluetooth availability
    if command_exists bluetoothctl; then
        BT_STATUS=$(systemctl is-active bluetooth 2>/dev/null || echo "inactive")
        if [ "$BT_STATUS" = "active" ]; then
            log_success "Bluetooth service is running"
        else
            log_warning "Bluetooth service is not active. Attempting to start..."
            if sudo systemctl start bluetooth; then
                log_success "Bluetooth service started"
            else
                log_error "Failed to start Bluetooth service"
                exit 1
            fi
        fi
    else
        log_error "Bluetooth tools not found. Please install with: sudo apt update && sudo apt install bluez"
        exit 1
    fi
    
    # Check if user is in bluetooth group
    if groups | grep -q bluetooth; then
        log_success "User is in bluetooth group"
    else
        log_warning "User is not in bluetooth group. Adding user to bluetooth group..."
        sudo usermod -a -G bluetooth "$USER"
        log_warning "Please log out and log back in, then run this script again"
        exit 1
    fi
}

# Function to setup virtual environment
setup_venv() {
    log "Setting up Python virtual environment..."
    
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating virtual environment at $VENV_DIR"
        python3 -m venv "$VENV_DIR"
        log_success "Virtual environment created"
    else
        log "Virtual environment already exists at $VENV_DIR"
    fi
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    log_success "Virtual environment activated"
    
    # Upgrade pip
    log "Upgrading pip..."
    pip install --upgrade pip
    
    # Install requirements
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        log "Installing Python dependencies..."
        pip install -r "$SCRIPT_DIR/requirements.txt"
        log_success "Dependencies installed successfully"
    else
        log_error "requirements.txt not found in $SCRIPT_DIR"
        exit 1
    fi
}

# Function to check Bluetooth permissions and setup
setup_bluetooth() {
    log "Setting up Bluetooth permissions..."
    
    # Check if bluetoothctl is accessible
    if bluetoothctl show >/dev/null 2>&1; then
        log_success "Bluetooth controller accessible"
    else
        log_error "Cannot access Bluetooth controller. Check permissions and service status"
        exit 1
    fi
    
    # Enable Bluetooth if not enabled
    if bluetoothctl show | grep -q "Powered: yes"; then
        log_success "Bluetooth is powered on"
    else
        log "Powering on Bluetooth..."
        bluetoothctl power on
        sleep 2
        log_success "Bluetooth powered on"
    fi
    
    # Make device discoverable (optional)
    bluetoothctl discoverable on >/dev/null 2>&1 || true
}

# Function to start the application
start_application() {
    log "Starting Meshtastic Bluetooth Controller..."
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Change to script directory
    cd "$SCRIPT_DIR"
    
    # Start the application
    python main.py
}

# Function to display usage information
show_usage() {
    echo "Meshtastic Bluetooth Controller - Startup Script"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --setup     Run setup only (create venv, install dependencies)"
    echo "  --check     Check system requirements only"
    echo "  --help      Show this help message"
    echo ""
    echo "Default behavior: Run setup and start application"
    echo ""
    echo "For first-time setup on Raspberry Pi 5:"
    echo "1. Run: chmod +x start.sh"
    echo "2. Run: ./start.sh --setup"
    echo "3. Run: ./start.sh"
}

# Main execution
main() {
    log "=== Meshtastic Bluetooth Controller Startup ==="
    log "Script directory: $SCRIPT_DIR"
    log "Virtual environment: $VENV_DIR"
    log "Log file: $LOG_FILE"
    
    case "${1:-}" in
        --setup)
            check_requirements
            setup_venv
            setup_bluetooth
            log_success "Setup completed successfully!"
            ;;
        --check)
            check_requirements
            log_success "System requirements check completed!"
            ;;
        --help)
            show_usage
            ;;
        "")
            check_requirements
            setup_venv
            setup_bluetooth
            start_application
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Trap Ctrl+C and cleanup
cleanup() {
    log ""
    log "Received interrupt signal. Cleaning up..."
    exit 0
}

trap cleanup INT TERM

# Run main function
main "$@"