# Meshtastic Monitor Dashboard

A real-time GUI monitoring dashboard for Meshtastic mesh networks on Raspberry Pi. Monitor telemetry, nodes, messages, and network statistics while sending encrypted private telemetry reports to selected nodes.

![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-Compatible-red?style=flat-square&logo=raspberry-pi)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Meshtastic](https://img.shields.io/badge/Meshtastic-2.5.0+-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

## Features

### 📊 Real-Time Monitoring
- **Device Telemetry**: Battery level, voltage, channel utilization, air utilization, uptime
- **Environment Sensors**: Temperature, humidity, barometric pressure (when available)
- **Mesh Nodes**: Live list with SNR values and last-heard timestamps
- **Network Statistics**: Total nodes, online nodes, packet counts, message counts
- **LoRa Traffic Feed**: Color-coded real-time message feed

### 🚀 Auto-Send Telemetry
- **Scheduled Reporting**: Automatically send telemetry reports at configurable intervals
- **Node Selection**: Choose specific nodes to receive reports via intuitive GUI
- **Private Messages**: Uses encrypted Direct Messages (DM) - only recipients can decrypt
- **Configuration Persistence**: Settings saved across sessions

### 🛡️ Security
- **PKC Encryption**: Automatic Public Key Cryptography for DMs (firmware 2.5.0+)
- **Channel Encryption**: Supports AES128/AES256 channel-based encryption
- **No Spam**: Private messages don't clutter public channels

### 🎨 User Interface
- **Dark Theme**: Easy on the eyes for long monitoring sessions
- **Live Updates**: Real-time refresh without performance impact
- **Click-to-Select**: Intuitive node selection with visual feedback
- **Countdown Timer**: Shows time until next auto-send

## Hardware Requirements

### Raspberry Pi
- **Raspberry Pi 5** (recommended)
- Raspberry Pi 4/3 (compatible)
- **USB Port**: For serial connection to Meshtastic device

### Meshtastic Device
- **Heltec WiFi LoRa 32 V3** (tested)
- Other Meshtastic-compatible devices with USB serial support
- **Firmware**: v2.5.0 or higher (for PKC encryption features)

## Software Requirements

- **Operating System**: Raspberry Pi OS (Bookworm/Bullseye)
- **Python**: 3.9 or higher
- **Packages**: tkinter (usually included), meshtastic, pypubsub

## Installation

### 1. Clone Repository

```

### 2. Install Dependencies

```bash
# Ensure tkinter is installed (usually pre-installed on Raspberry Pi OS)
sudo apt-get install python3-tk

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python packages
pip install meshtastic pypubsub
```

### 3. Connect Device

```bash
# Connect Heltec V3 via USB cable
# Device should appear as /dev/ttyUSB0 (or similar)

# Check connection
ls -l /dev/ttyUSB*

# Add user to dialout group if needed
sudo usermod -a -G dialout $USER
# (logout/login required after this)
```

## Quick Start

### Running the Monitor

```bash
# Activate virtual environment
source venv/bin/activate

# Run the monitor dashboard
python mesh_monitor.py
```

Or use the convenience script:

```bash
# Make executable (first time only)
chmod +x start.sh

# Run with virtual environment activation
./start.sh
```

## Using the Dashboard

### Main Interface

The dashboard is divided into four main sections:

1. **Top Left - Device Telemetry**
   - Real-time battery, voltage, and utilization metrics
   - Environment sensor readings (temperature, humidity, pressure)

2. **Bottom Left - Mesh Nodes**
   - Live list of all nodes on the mesh
   - SNR values and last-heard timestamps
   - Automatically updates as nodes are discovered

3. **Top Right - Network Statistics**
   - Total nodes, packets sent/received
   - Message counts

4. **Bottom Right - Auto-Send Control**
   - Enable/disable automatic telemetry reports
   - Configure sending interval
   - Select recipient nodes
   - Test send button

5. **Bottom - LoRa Traffic Feed**
   - Real-time message log with color coding
   - Shows all mesh traffic including your sent messages

### Sending Telemetry Reports

1. **Wait for nodes to appear** in the Mesh Nodes list
2. **Click "Select Nodes"** button
3. **Click nodes to toggle selection** (they'll highlight green)
4. **Click "Save Selection"** to confirm
5. **Set your desired interval** in seconds (minimum 30)
6. **Enable "Auto-Send"** checkbox
7. **Monitor the countdown** - telemetry will be sent automatically

### Test Before Auto-Send

Use the **"Test Send Now"** button to immediately send a telemetry report to your selected nodes and verify it's working.

## Configuration Files

### monitor_config.json

Automatically created on first save. Stores:
- `auto_send_enabled`: Whether auto-send is active
- `auto_send_interval`: Seconds between sends
- `selected_nodes`: List of node IDs to receive reports

Example:
```json
{
  "auto_send_enabled": true,
  "auto_send_interval": 300,
  "selected_nodes": ["!a1b2c3d4", "!e5f6g7h8"]
}
```

## Telemetry Configuration

### Setting Telemetry Intervals

Use the included `set_telemetry.py` script to configure device telemetry broadcast intervals:

```bash
source venv/bin/activate
python set_telemetry.py
```

This sets both environment and device telemetry intervals to 60 seconds.

## Security & Privacy

### Encryption

**Direct Messages (Auto-Send)**:
- Uses PKC (Public Key Cryptography) automatically on firmware 2.5.0+
- Only the selected recipient can decrypt messages
- Messages are signed to verify sender identity
- No private data visible to other mesh participants

**Channel Messages**:
- Use the primary channel's PSK (Pre-Shared Key)
- All nodes on the channel can decrypt if they have the PSK
- Change PSK for enhanced privacy

### Best Practices

- ✅ Keep firmware updated (2.5.0+ recommended)
- ✅ Use Direct Messages for sensitive telemetry
- ✅ Change default channel PSK on primary channel
- ✅ Don't send telemetry more frequently than needed
- ✅ Monitor your air utilization percentage

## Troubleshooting

### Connection Issues

**Device Not Connecting**
```bash
# Check USB connection
ls -l /dev/ttyUSB*

# Verify permissions
sudo usermod -a -G dialout $USER
# Logout/login required

# Try different USB port
# Check USB cable quality
```

**GUI Not Starting**
```bash
# Ensure tkinter is installed
sudo apt-get install python3-tk

# Check X11 display
echo $DISPLAY  # Should show :0 or similar

# If using SSH, enable X11 forwarding
ssh -X user@raspberrypi
```

**ImportError: No module named 'meshtastic'**
```bash
# Activate virtual environment first
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Performance Issues

**Slow GUI Updates**
- Close other applications to free memory
- Reduce auto-send frequency
- Check system load: `htop`

**High Air Utilization**
- Increase auto-send interval (minimum 30 seconds recommended)
- Reduce number of recipients
- Check other devices on mesh

### Common Errors

**"Permission denied: '/dev/ttyUSB0'"**
```bash
sudo usermod -a -G dialout $USER
# Logout and login again
```

**"No nodes appearing"**
- Wait 30-60 seconds for initial discovery
- Ensure other nodes are powered on and in range
- Check device firmware version compatibility

## Project Structure

```
Meshtastic/
├── mesh_monitor.py          # Main GUI dashboard application
├── set_telemetry.py        # Telemetry configuration utility
├── start.sh                # Convenience startup script
├── requirements.txt        # Python dependencies
├── monitor_config.json     # Auto-send configuration (auto-created)
├── README.md               # This file
└── venv/                   # Virtual environment (create locally)
```

## Files Description

### mesh_monitor.py
Main dashboard application with GUI interface. Monitors mesh network in real-time and manages auto-send telemetry feature.

### set_telemetry.py
Utility script to configure device telemetry broadcast intervals (environment and device metrics).

### start.sh
Bash script that activates virtual environment and launches mesh_monitor.py. Makes running the application easier.

### requirements.txt
Lists Python package dependencies:
- `meshtastic` - Official Meshtastic Python API
- `pypubsub` - Publish-subscribe messaging library

### monitor_config.json
Auto-generated configuration file storing auto-send settings and selected nodes. Created on first save operation.

## Dependencies

### Python Packages
- **meshtastic** - Meshtastic device communication
- **pypubsub** - Event-driven messaging
- **tkinter** - GUI framework (pre-installed on most systems)

### System Requirements
- **Python 3.9+** - Core interpreter
- **USB Serial drivers** - For device connection
- **X11 Display** - For GUI (available on Raspberry Pi OS desktop)

# Message send interval
default_frequency=60
```

## Tips & Best Practices

### Optimal Settings

**Auto-Send Interval**:
- Minimum: 30 seconds
- Recommended: 300 seconds (5 minutes)
- Consider mesh size and traffic

**Node Selection**:
- Select only nodes that need your telemetry
- Fewer recipients = lower air utilization
- Test with one node first

**Monitoring**:
- Watch air utilization % - keep under 10%
- Monitor channel utilization
- Check SNR values regularly

### Power Management

**For Battery Operation**:
- Increase telemetry intervals
- Reduce screen brightness
- Consider scheduled operation only

**For Always-On**:
- Use powered USB hub if connecting multiple devices
- Monitor Raspberry Pi temperature
- Ensure adequate ventilation

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Test thoroughly on Raspberry Pi
4. Commit with clear messages
5. Open a Pull Request

## License

This project is provided as-is for use with Meshtastic devices. See LICENSE file for details.

## Support & Resources

**Documentation**:
- [Meshtastic Official Docs](https://meshtastic.org/docs/)
- [Meshtastic Python API](https://python.meshtastic.org/)
- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)

**Community**:
- [Meshtastic Discord](https://discord.gg/meshtastic)
- [Meshtastic Forum](https://meshtastic.discourse.group/)

**Troubleshooting**:
- Check GitHub issues for known problems
- Review Meshtastic firmware compatibility
- Verify Python version compatibility

## Acknowledgments

- **Meshtastic Project** - Excellent mesh networking platform and Python API
- **Heltec Automation** - Quality LoRa hardware
- **Raspberry Pi Foundation** - Reliable computing platform
- **Python Community** - Robust libraries and tools

## Changelog

### v2.0.0 (Current)
- Complete GUI dashboard with real-time monitoring
- Auto-send telemetry with encrypted Direct Messages
- Node selection interface with persistence
- Network statistics and LoRa traffic feed
- Environment sensor support
- PKC encryption support (firmware 2.5.0+)
- USB serial connection (removed BLE dependency)
- Dark theme GUI optimized for long sessions

### v1.0.0 (Legacy)
- BLE communication support
- CLI menu interface
- Basic telemetry monitoring

---

**Made for the Meshtastic community 📡**