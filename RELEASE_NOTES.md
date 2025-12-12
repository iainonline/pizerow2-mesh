# Meshtastic Terminal Monitor - Release Notes

## v1.7 (December 12, 2025)

### 🐛 Bug Fixes
- **Fixed ChatBot Timeout**: Replaced signal-based timeout with thread-safe timeout mechanism
  - Resolved "signal only works in main thread" error
  - ChatBot now properly responds to messages in background threads
- **Improved Error Logging**: Enhanced telemetry error messages to show actual exception details
  - Changed from generic "get" error to detailed exception type and message
  - Better debugging information for troubleshooting

### 🔧 Improvements
- **Simplified Channel Filtering**: Removed LongFast (channel 0) filter
  - ChatBot now responds on all channels
  - Only responds to selected nodes (configured in terminal_config.json)
  - Prevents unwanted spam while allowing flexibility
- **Thread-Safe Timeout**: Implemented threading-based timeout for LLM generation
  - Works correctly in callback threads
  - Prevents indefinite hangs during response generation
  - Returns friendly timeout message after 30 seconds

### 📝 Configuration
- ChatBot now exclusively responds to nodes in `selected_nodes` list
- All other nodes are silently ignored
- No rate limiting needed for non-selected nodes

---

## v1.6 (Previous Release)

# Meshtastic Monitor Dashboard v2.0.0

## Release Summary

This release represents a complete rewrite of the Meshtastic monitoring application, transitioning from a BLE-based CLI tool to a comprehensive USB-connected GUI dashboard.

## What's New

### Major Changes
- **Complete GUI Dashboard**: Real-time monitoring interface with tkinter
- **USB Serial Connection**: Replaced BLE with more reliable USB serial communication
- **Auto-Send Telemetry**: Scheduled encrypted telemetry reports to selected nodes
- **PKC Encryption**: Support for Public Key Cryptography (firmware 2.5.0+)
- **Node Selection Interface**: Easy click-to-toggle node selection
- **Configuration Persistence**: Settings saved across sessions

### Features
- 📊 Real-time device telemetry (battery, voltage, utilization)
- 🌡️ Environment sensor display (temperature, humidity, pressure)
- 📡 Live mesh nodes list with SNR and timestamps
- 📈 Network statistics tracking
- 💬 Color-coded LoRa traffic feed
- 🔒 Private Direct Messages (no channel spam)
- ⏱️ Configurable auto-send intervals
- 💾 JSON configuration persistence

## Files Included

### Core Application
- `mesh_monitor.py` (35KB) - Main GUI dashboard application
- `set_telemetry.py` (1.7KB) - Utility to configure device telemetry intervals

### Configuration & Setup
- `start.sh` (1.2KB) - Convenience startup script with venv activation
- `requirements.txt` (33B) - Python dependencies (meshtastic, pypubsub)
- `README.md` (12KB) - Comprehensive documentation

### Auto-Generated
- `monitor_config.json` - Created on first save, stores auto-send settings

## Removed Files

The following legacy files have been removed:
- `main.py` - Old CLI menu interface
- `meshtastic_comm.py` - Legacy BLE communication handler
- `test_connection.py` - Old connection testing utility
- `test_system.py` - Legacy system test script
- `config.json` - Old configuration format
- `meshtastic.spec` - PyInstaller spec (no longer needed)

## Installation

```bash
# Clone repository
git clone https://github.com/yourusername/Meshtastic.git
cd Meshtastic

# Install system dependencies (if needed)
sudo apt-get install python3-tk

# Run with automatic venv setup
chmod +x start.sh
./start.sh
```

## Upgrade Notes

### From v1.x

1. **Connection Method**: Now uses USB serial instead of BLE
   - Connect device via USB cable
   - No Bluetooth pairing required
   - More reliable connection

2. **Configuration**: New configuration format
   - Old `config.json` can be deleted
   - New `monitor_config.json` created automatically

3. **Dependencies**: Simplified requirements
   - No longer needs `bleak` for BLE
   - No longer needs `psutil`
   - Removed `Adafruit_DHT` dependency

4. **User Interface**: Complete redesign
   - GUI instead of CLI menu
   - Real-time updates instead of polling
   - Visual node selection

## System Requirements

- **Hardware**: Raspberry Pi 3/4/5 (or any Linux system with USB)
- **OS**: Raspberry Pi OS (Bullseye/Bookworm) or similar
- **Python**: 3.9 or higher
- **Display**: X11 display required for GUI
- **USB**: USB port for device connection

## Known Issues

- None currently identified

## Upgrade Path

To upgrade from v1.x:

```bash
cd Meshtastic
git pull
rm -f config.json  # Remove old config
source venv/bin/activate
pip install -r requirements.txt  # Update dependencies
./start.sh
```

## Breaking Changes

- BLE connection no longer supported (use USB serial)
- CLI menu interface removed (replaced with GUI)
- Old `config.json` format not compatible
- Command-line arguments no longer supported

## Compatibility

- **Firmware**: Tested with Meshtastic 2.3.0 - 2.5.x
- **Devices**: Heltec V3, T-Beam, and other USB-capable devices
- **Python**: Requires 3.9+ (3.11 recommended)
- **Operating Systems**: Linux (Raspberry Pi OS, Ubuntu, Debian)

## Support

- Documentation: See README.md
- Issues: GitHub issues page
- Community: Meshtastic Discord/Forum

## Changelog

### v2.0.0 (2025-12-05)
- Complete rewrite with GUI interface
- USB serial connection replacing BLE
- Auto-send telemetry feature
- PKC encryption support
- Node selection with persistence
- Real-time monitoring dashboard
- Configuration persistence
- Simplified dependencies
- Improved documentation

### v1.0.0 (Legacy)
- BLE communication
- CLI menu interface
- Basic telemetry monitoring

---

**Built for the Meshtastic community 📡**
