# Meshtastic Bluetooth Controller

A Python application for Bluetooth Low Energy (BLE) communication with Heltec V3 Meshtastic devices on Raspberry Pi 5. This project provides an interactive menu interface for configuring message frequency, monitoring battery levels, and managing node-to-node communication.

![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi-5-red?style=flat-square&logo=raspberry-pi)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Meshtastic](https://img.shields.io/badge/Meshtastic-Compatible-green?style=flat-square)
![Heltec V3](https://img.shields.io/badge/Heltec-V3-orange?style=flat-square)

## Features

- 🔗 **BLE Communication**: Connect to Heltec V3 devices via Bluetooth Low Energy
- 📱 **Interactive Menu**: User-friendly command-line interface
- ⚡ **Configurable Frequency**: Set custom message sending intervals
- 🔋 **Battery Monitoring**: Real-time battery level reporting
- 🏷️ **Node Management**: Configure source and destination node names
- 🔍 **Device Scanning**: Automatic BLE device discovery
- 🐍 **Virtual Environment**: Isolated Python environment with automatic setup
- 📝 **Configuration Persistence**: Settings saved to JSON file
- 📊 **Comprehensive Logging**: Detailed logging for debugging

## Hardware Requirements

### Primary Device
- **Raspberry Pi 5** (recommended)
  - Other Raspberry Pi models may work but are not officially supported
  - Ensure Bluetooth is enabled and working

### Meshtastic Device
- **Heltec WiFi LoRa 32 V3** (ESP32-S3 based)
  - Must have Meshtastic firmware installed
  - Bluetooth must be enabled in device settings

### Optional
- UPS/Battery pack for Raspberry Pi (for portable operation)

## Software Requirements

- **Operating System**: Raspberry Pi OS (Bookworm recommended)
- **Python**: 3.9 or higher
- **Bluetooth**: BlueZ stack with working BLE support

## Quick Start

### 1. Clone or Download

```bash
# If using git
git clone <repository-url>
cd Meshtastic

# Or download and extract the files to a directory
```

### 2. First-Time Setup

```bash
# Make the startup script executable
chmod +x start.sh

# Run setup (installs dependencies, creates virtual environment)
./start.sh --setup
```

### 3. Run the Application

```bash
# Start the application
./start.sh
```

## Installation Guide

### Prerequisites Installation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3 python3-pip python3-venv bluez bluetooth

# Ensure Bluetooth service is running
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Add user to bluetooth group (logout/login required after this)
sudo usermod -a -G bluetooth $USER
```

### Project Setup

1. **Download Project Files**
   ```bash
   # Create project directory
   mkdir ~/meshtastic-bluetooth
   cd ~/meshtastic-bluetooth
   
   # Copy all project files to this directory
   ```

2. **Configure Permissions**
   ```bash
   # Make startup script executable
   chmod +x start.sh
   ```

3. **Initial Setup**
   ```bash
   # Run comprehensive setup
   ./start.sh --setup
   ```

4. **Verify Installation**
   ```bash
   # Check system requirements
   ./start.sh --check
   ```

## Usage Guide

### Starting the Application

```bash
./start.sh
```

### Menu Options

1. **Set message frequency** - Configure how often messages are sent (in seconds)
2. **Set node names** - Configure source and destination node names
3. **Set BLE address** - Specify device address or use auto-scan
4. **Scan for BLE devices** - Discover available Meshtastic devices
5. **Start/Stop messaging** - Toggle automatic message transmission
6. **View device battery level** - Check current battery status
7. **Send test message** - Send a custom message immediately
8. **View connection status** - Display connection and configuration details
9. **Exit** - Close the application

### Configuration

Settings are automatically saved to `config.json`:

```json
{
  "message_frequency": 60,
  "from_node": "HeltecV3_1",
  "to_node": "HeltecV3_2", 
  "ble_address": null,
  "auto_scan": true
}
```

### Automatic Messaging

When enabled, the application sends periodic messages with:
- Source and destination node names
- Message counter
- Current battery level percentage
- Timestamp

Example message format:
```
[HeltecV3_1→HeltecV3_2] Auto message #5 from HeltecV3_1 | Battery: 87.3%
```

## Troubleshooting

### Common Issues

**Bluetooth Connection Failed**
```bash
# Check Bluetooth status
sudo systemctl status bluetooth

# Restart Bluetooth service
sudo systemctl restart bluetooth

# Verify user permissions
groups | grep bluetooth
```

**Device Not Found**
- Ensure Heltec V3 has Meshtastic firmware installed
- Verify Bluetooth is enabled on the Meshtastic device
- Try manual device scanning from the menu
- Check device is in range (< 10 meters recommended)

**Permission Denied Errors**
```bash
# Add user to bluetooth group
sudo usermod -a -G bluetooth $USER

# Logout and login again, then retry
```

**Python Import Errors**
```bash
# Reinstall dependencies
./start.sh --setup

# Or manually activate venv and install
source venv/bin/activate
pip install -r requirements.txt
```

### Raspberry Pi 5 Specific Notes

- **Bluetooth Performance**: Pi 5 has significantly improved Bluetooth performance
- **Power Management**: Consider using a UPS for mobile applications
- **GPIO Access**: Ensure user has GPIO permissions if using hardware features
- **WiFi Interference**: 2.4GHz WiFi may interfere with Bluetooth; consider using 5GHz WiFi

### Debug Mode

Enable detailed logging by modifying the main.py file:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Project Structure

```
meshtastic-bluetooth/
├── main.py              # Main application with menu interface
├── meshtastic_comm.py   # Bluetooth communication handler
├── start.sh             # Startup script with venv management
├── requirements.txt     # Python dependencies
├── config.json          # Configuration file
├── README.md            # This file
├── .github/
│   └── copilot-instructions.md  # Project documentation
└── venv/                # Virtual environment (created by script)
```

## Dependencies

### Python Packages
- **meshtastic** (>=2.7.0) - Official Meshtastic Python API
- **bleak** (>=0.21.0) - Bluetooth Low Energy platform integration
- **psutil** (>=5.9.0) - System and process utilities

### System Dependencies
- **BlueZ** - Linux Bluetooth protocol stack
- **Python 3.9+** - Core Python interpreter
- **pip** - Python package manager

## Advanced Configuration

### Custom BLE Settings

Modify `meshtastic_comm.py` to adjust BLE parameters:

```python
# Connection timeout (seconds)
timeout=30

# Auto-reconnection attempts
retry_attempts=3

# Message send interval
default_frequency=60
```

### Logging Configuration

Customize logging in `main.py`:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('meshtastic.log'),
        logging.StreamHandler()
    ]
)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source. Please check the repository for specific license terms.

## Support

For issues and questions:

1. Check this README and troubleshooting section
2. Review the [Meshtastic documentation](https://meshtastic.org/docs/)
3. Check [Raspberry Pi forums](https://www.raspberrypi.org/forums/) for Pi-specific issues
4. Open an issue in the project repository

## Acknowledgments

- [Meshtastic Project](https://meshtastic.org/) - For the excellent mesh networking platform
- [Heltec Automation](https://heltec.org/) - For the V3 hardware platform  
- [Raspberry Pi Foundation](https://www.raspberrypi.org/) - For the Pi 5 platform
- Python community - For the excellent libraries and tools

## Changelog

### v1.0.0
- Initial release with full BLE communication support
- Interactive menu interface
- Automatic virtual environment setup
- Raspberry Pi 5 optimization
- Battery monitoring integration
- Configurable message frequency
- Persistent configuration storage