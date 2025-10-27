# Meshtastic Bluetooth Communication Project

This project creates a Python application for Bluetooth communication with Heltec V3 Meshtastic devices on Raspberry Pi 5.

## Project Features
- Bluetooth Low Energy (BLE) communication with Meshtastic devices
- Interactive menu for configuring message frequency
- Battery level monitoring and transmission
- Configurable node names (from/to)
- Virtual environment with startup script
- Raspberry Pi 5 optimized

## Key Components
- `main.py`: Main application with menu interface
- `meshtastic_comm.py`: Bluetooth communication handler
- `start.sh`: Startup script with virtual environment activation
- `requirements.txt`: Python dependencies
- `config.json`: Configuration storage for node settings

## Development Notes
- Use the official Meshtastic Python API for device communication
- Implement proper error handling for Bluetooth connectivity
- Ensure compatibility with Raspberry Pi 5's Bluetooth stack
- Follow Meshtastic protocol standards for message formatting