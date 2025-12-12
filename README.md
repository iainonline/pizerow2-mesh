# Meshtastic Terminal Monitor v2.0

A lightweight terminal-based monitoring application with AI ChatBot for Meshtastic mesh networks on Raspberry Pi. Perfect for headless operation on Raspberry Pi 5/4/3. Monitor telemetry, send encrypted direct messages to selected nodes, track mesh network activity, and interact with an intelligent AI assistant over the mesh.

![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-Compatible-red?style=flat-square&logo=raspberry-pi)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Meshtastic](https://img.shields.io/badge/Meshtastic-2.5.0+-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

## Features

### 🤖 AI ChatBot (Enhanced in v2.0!)
- **TinyLlama 1.1B**: Fast, efficient on-device AI running on Raspberry Pi 5
- **Direct Messages Only**: Responds only to DMs (not channel broadcasts)
- **Universal Access**: Responds to all nodes on the mesh
- **Rate Limiting**: 50 messages/hour for non-selected nodes, unlimited for selected nodes
- **Auto-Enabled**: ChatBot loads automatically on startup
- **Smart Splitting**: Long responses split into 200-char messages automatically
- **Flicker-Free Display**: Smooth dashboard updates using cursor positioning
- **Live Status**: Dashboard shows "💭 Thinking..." in green during AI processing
- **Concise Responses**: Optimized for 500 char responses (2-3 messages)
- **Mesh Personality**: MeshBot identifies as a bot running on the mesh network
- **Customizable Greeting**: Set your own welcome message
- **Commands**: CHATBOTON/CHATBOTOFF from selected nodes only

### 📊 Real-Time Dashboard
- **Two-Column Layout**: Main content on left, message panel on right
- **Active Mesh Network**: Top 5 most recently heard nodes (last 30 minutes)
- **Signal Metrics**: Live SNR and RSSI for each active node
- **Text Message Panel**: Boxed display with last 10 messages, timestamps, sender details, and signal strength
- **Real-Time Activity Feed**: Last 20 packets in/out with timestamps
- **Device Telemetry**: Battery level, voltage, channel utilization, air utilization
- **Environment Sensors**: Fresh temperature, humidity, barometric pressure readings
- **Network Statistics**: Total nodes, packet RX/TX counts
- **Dedicated Activity Log**: mesh_activity.log for detailed analysis

### 🚀 Auto-Send Telemetry
- **Fresh Sensor Readings**: Triggers BME280 reading before each send
- **Real-Time Data**: Temperature/humidity/pressure in every message (not 30-min intervals)
- **Immediate Send**: Sends telemetry immediately on startup
- **Scheduled Reporting**: Automatically send telemetry at configurable intervals (minimum 30 seconds)
- **Node Selection**: Choose specific nodes to receive encrypted direct messages
- **Live Status Display**: Updates every 10 seconds showing:
  - Top 5 active mesh nodes with signal strength
  - Text message panel (boxed, top right) with last 10 messages
  - Local sensor data (temperature, humidity, pressure)
  - Device status (battery, voltage)
  - Target node information (name, last heard, signal strength)
  - Recent activity feed (last 20 packets)
  - Countdown to next send
- **Configuration Persistence**: Settings saved across sessions

### 🛡️ Security
- **PKC Encryption**: Automatic Public Key Cryptography for Direct Messages (firmware 2.5.0+)
- **Private Messaging**: Recipients see messages in their DM inbox
- **No Manual Keys**: Key exchange happens automatically

### 💻 Terminal Interface
- **Dashboard Layout**: Active nodes at top, activity feed below
- **Numbered Menu Navigation**: Simple 1-5 option menus
- **Auto-Start Mode**: 10-second countdown with X key to cancel
- **Background Operation**: M key to access menu anytime
- **Graceful Shutdown**: Ctrl+C for clean exit
- **Headless Optimized**: No GUI dependencies, perfect for SSH access
- **Automatic Port Clearing**: Resolves USB port lock issues automatically

## Hardware Requirements

### Raspberry Pi
- **Raspberry Pi 5/4/3** (recommended - tested and fully working)
- **USB Port**: For serial connection to Meshtastic device
- Raspberry Pi Zero 2 W (limited - USB compatibility issues with Meshtastic Python library)

### Meshtastic Device
- **Heltec WiFi LoRa 32 V3** (tested)
- Other Meshtastic-compatible devices with USB serial support
- **Firmware**: v2.5.0 or higher (for PKC encryption features)
- **Optional**: BME280 sensor for environment telemetry

## Software Requirements

- **Operating System**: Raspberry Pi OS (Bookworm/Bullseye)
- **Python**: 3.9 or higher
- **Packages**: meshtastic, pypubsub, llama-cpp-python
- **Disk Space**: ~650MB for TinyLlama model

## Installation

### Quick Install on Raspberry Pi 5/4/3

```bash
# 0. Install git if not present
sudo apt-get update
sudo apt-get install -y git

# 1. Clone the repository (using HTTPS - no SSH keys needed)
cd ~
git clone https://github.com/iainonline/pizerow2-mesh.git Meshtastic
cd Meshtastic

# 2. Create Python virtual environment
python3 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install requirements (includes llama-cpp-python for ChatBot)
pip install -r requirements.txt

# 5. Download TinyLlama model (required for ChatBot)
python download_model.py

# 6. Make start script executable (optional)
chmod +x start_terminal.sh
```

### Connect Meshtastic Device

```bash
# Connect Heltec V3 (or other device) via USB cable
# Device should appear as /dev/ttyUSB0 (or similar)

# Check connection
ls -l /dev/ttyUSB*

# Add user to dialout group if needed
sudo usermod -a -G dialout $USER
# (logout/login required after this)
```

## Quick Start

### Running the Terminal Monitor

```bash
# Option 1: Use the start script
./start_terminal.sh

# Option 2: Run directly
source venv/bin/activate
python mesh_terminal.py
```

The program will:
1. Load saved configuration (if exists)
2. Show 10-second countdown (press X to cancel autostart)
3. Connect to Meshtastic device via USB
4. Send telemetry immediately on startup
5. Enter auto-send mode (or manual menu if cancelled)

## Using the Terminal Monitor

### Auto-Send Mode

When auto-send is enabled, the display updates every 10 seconds showing:

- **Active Mesh Nodes**: Top 5 most recently heard nodes with signal strength
- **Text Message Panel**: Last 10 received messages (boxed, top right)
- **Sent Messages Panel**: Last 2 sent messages with timestamps
- **ChatBot Status**: Shows "ENABLED ✅" or "💭 Thinking..." when processing
- **Local Sensor Data**: Temperature, humidity, pressure (if BME280 present)
- **Device Status**: Battery level, voltage
- **Target Nodes**: Name, last heard time, signal strength (SNR/RSSI)
- **Recent Activity**: Last 20 packets in/out
- **Countdown**: Time remaining until next send

**Controls**:
- Press **M** then Enter to access menu
- Press **S** then Enter to send message
- Press **Ctrl+C** to exit gracefully

### Main Menu

When in menu mode (or after pressing M), you'll see numbered options:

1. **View Current Telemetry**
   - Shows local device telemetry
   - Environment sensors (BME280) if available
   - Device metrics (battery, voltage, utilization)

2. **Configure Auto-Send**
   - Toggle auto-send on/off
   - Set interval (minimum 30 seconds, recommended 60+)
   - Select target nodes
   - Test send immediately

3. **Send Telemetry Now**
   - Immediately send to all selected nodes
   - Useful for testing

4. **Manage Encryption Keys**
   - Information about PKC encryption
   - Troubleshooting guide for Direct Messages

5. **View Command Words**
   - Documentation for all keyword commands
   - Shows STOP, START, FREQ, RADIOCHECK, WEATHERCHECK, KEYWORDS, CHATBOTON, CHATBOTOFF
   - Explains command format and responses

6. **Configure ChatBot**
   - Toggle ChatBot on/off
   - Change model path
   - Customize greeting message
   - View ChatBot status

7. **Start Auto-Send**
   - Begins auto-send dashboard mode
   - Live updates every 10 seconds
   - Press M for menu, S to send message

8. **Stop Auto-Send**
   - Stops automatic sending
   - Returns to main menu

9. **View Dashboard**
   - View-only dashboard (no auto-send)
   - See current status snapshot

9. **Exit**
   - Gracefully close the application

### Selecting Target Nodes

In "Configure Auto-Send" menu, choose "Select Nodes":
- View list of all discovered nodes
- Enter node number to toggle selection
- Selected nodes marked with ✅
- Press Enter (blank) when done

### Interactive Message Interface

Access message interface from auto-send dashboard by pressing **S**:

**Features**:
- View all nodes with message counts
- Open conversation view with any node
- Send messages directly from conversation
- See full message history per node
- Real-time message updates
- Clear conversation history

**Navigation**:
- Press **N** to select a node number
- Enter number to view conversation
- Press **R** to reply in conversation view
- Press **B** to go back
- Press **C** to clear conversation

### Keyword Commands

Target nodes can send commands to control your station:

**Available Commands**:
- `STOP` - Pause automatic telemetry sending
- `START` - Resume automatic telemetry sending  
- `FREQ##` - Change send interval (30-3600 seconds)
  - Example: `FREQ60` sets interval to 60 seconds
- `RADIOCHECK` - Request signal strength information
  - Response includes SNR, RSSI, and age of last signal
- `WEATHERCHECK` - Request current telemetry/weather data
  - Response includes temperature, humidity, pressure if available
- `KEYWORDS` - Request list of all available commands
- `CHATBOTON` - Enable AI ChatBot (selected nodes only)
- `CHATBOTOFF` - Disable AI ChatBot (selected nodes only)

**Command Features**:
- Only accepted from selected target nodes
- Automatic responses sent without user intervention
- All commands and responses logged
- View command help in menu option 5

### ChatBot Usage

The AI ChatBot responds to direct messages (DMs) that are not keyword commands:

**Features**:
- **DM Only**: Responds only to direct messages, ignores channel broadcasts
- Responds to **all nodes** on the mesh (not just selected ones)
- Rate limiting: 50 messages per hour for non-selected nodes
- Selected nodes have unlimited access
- Automatic message splitting (200 char Meshtastic limit)
- Responses limited to 500 chars total (2-3 messages)
- Shows "💭 Thinking..." in green on dashboard during processing
- Flicker-free dashboard updates for smooth user experience

**Example Conversation**:
```
User: "What time is it?"
Bot: "I don't have access to real-time data, but you can check your device clock."

User: "Tell me about mesh networks"
Bot: "Mesh networks are decentralized wireless networks where nodes relay data for each other..."
```

**Rate Limit Response**:
```
⚠️ Rate limit: 50 msg/hour. Please wait.
```

### Message Format

Messages sent contain available data:

**With Sensor Data**:
```
⏰ 18:45:30 | 🌡️ 78.5°F | 💧 52.3% | 🔘 924.9hPa | 📶 SNR: 6.5dB | 📡 RSSI: -42dBm | 🔋 96% | ⚡ 4.14V | 📻 CH:5.1% | 🌐 Air:1.2% | 👥 100
```

**Without Sensor Data** (NoT = No Telemetry):
```
NoT | ⏰ 18:45:30 | 📶 SNR: 7.0dB | 📡 RSSI: -46dBm | 🔋 96% | ⚡ 4.14V | 📻 CH:13.3% | 🌐 Air:1.1% | 👥 100
```

### Message Delivery

Messages are sent as **encrypted Direct Messages (DMs)** to selected nodes:
- Recipients see messages in their **Direct Messages inbox** (not main channel)
- Uses PKC (Public Key Cryptography) - firmware 2.5.0+
- Key exchange happens automatically - no manual setup needed
- Check **DM tab** on recipient devices to see messages

### Viewing Sent Messages and Activity

**Main Debug Log** (`mesh_terminal.log`):
```bash
tail -f mesh_terminal.log
```
Shows:
- Connection status and errors
- All packet RX/TX details
- Telemetry sends with full message content
- Node discoveries with signal strength
- Debug information and stack traces

**Activity Log** (`mesh_activity.log`):
```bash
tail -f mesh_activity.log
```
Shows clean timestamped activity feed:
- `📥 TELEMETRY from Yang SNR:6.2` (incoming packets)
- `📤 Telemetry to Yang` (outgoing messages)
- Perfect for analyzing mesh traffic patterns
- Last 20 items also displayed on screen

## Configuration Files

### terminal_config.json

Automatically created when you save settings. Stores:
- `auto_send_enabled`: Whether auto-send is active
- `auto_send_interval`: Seconds between sends (minimum 30)
- `selected_nodes`: List of node IDs to receive reports

Example:
```json
{
  "auto_send_enabled": true,
  "auto_send_interval": 60,
  "selected_nodes": ["!9e757a8c", "!9e761374"]
}
```

## Security & Privacy

### Encryption

**Direct Messages (DM)**:
- Uses PKC (Public Key Cryptography) automatically on firmware 2.5.0+
- Only the selected recipient can decrypt messages
- Messages are signed to verify sender identity
- No manual key management required
- No private data visible to other mesh participants

### Best Practices

- ✅ Keep firmware updated (2.5.0+ for PKC)
- ✅ Use recommended intervals (60+ seconds)
- ✅ Check log file for troubleshooting
- ✅ Monitor air utilization percentage (keep under 10%)
- ✅ Verify recipients check their DM inbox

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

**"Resource temporarily unavailable" / Port Lock Error**
The application now automatically clears stale USB port locks before connecting. This fixes the common error:
```
[Errno 11] Could not exclusively lock port /dev/ttyUSB0: Resource temporarily unavailable
```

The automatic port clearing happens on every connection attempt, so no manual intervention is needed. If you still experience issues:
```bash
# Manually check for processes using the port
sudo fuser -v /dev/ttyUSB0

# Kill specific process if needed
sudo kill -9 <PID>
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

## Known Issues & TODO

### Pi Zero 2 W USB Compatibility
⚠️ **USB Serial Issues**: The Pi Zero 2 W's USB implementation has compatibility issues with Meshtastic protobuf streams, causing intermittent parsing errors. 

**Workaround**: Use Raspberry Pi 5/4/3 for USB serial connections (tested and working).

**Future Enhancement**: Implement Bluetooth Low Energy (BLE) connection support as an alternative to USB for Pi Zero 2 W compatibility.

## Acknowledgments

- **Meshtastic Project** - Excellent mesh networking platform and Python API
- **Heltec Automation** - Quality LoRa hardware
- **Raspberry Pi Foundation** - Reliable computing platform
- **Python Community** - Robust libraries and tools

## Changelog

### v2.0 (Current - Enhanced ChatBot & Display)
- **Direct Message Only ChatBot** - Responds only to DMs, not channel broadcasts
- **Flicker-Free Dashboard** - ANSI cursor positioning eliminates screen flicker
- **Green Thinking Indicator** - "💭 Thinking..." displayed in green during AI processing
- **Optimized Responses** - ChatBot now targets 500 char responses for faster mesh delivery
- **Enhanced Personality** - MeshBot identifies as a mesh-native assistant
- **Correct Message Order** - Incoming messages stored before ChatBot processes
- **Universal ChatBot Access** - All nodes can interact with ChatBot (with rate limiting)
- **Keyword Commands Protected** - Only selected nodes can use keyword commands
- **Improved Logging** - Shows toId field for better DM tracking
- **Better Error Handling** - More robust message processing

### v1.7 (Terminal Launcher & Service)
- **Terminal Auto-Launch** - Maximized window automatically on startup
- **Systemd Service** - System integration for auto-start at boot
- **Dedicated Launcher** - `launch_maximized.sh` starts terminal in full screen
- **Improved Startup** - Auto-start script launches in new maximized terminal
- **Better Service Management** - Easy enable/disable/restart with systemctl
- **Clean Output** - Terminal optimized for visibility and monitoring

**New Files**:
- `launch_maximized.sh` - Maximized terminal launcher for better visibility
- Updated `meshtastic.service` - System service with maximized terminal integration
- Updated `start_terminal.sh` - Integrated with maximized terminal launcher

### v1.6 (Terminal Launcher & Service)
- **Terminal Auto-Launch** - Maximized window automatically on startup
- **Systemd Service** - System integration for auto-start at boot
- **Dedicated Launcher** - `launch_maximized.sh` starts terminal in full screen
- **Improved Startup** - Auto-start script launches in new maximized terminal
- **Better Service Management** - Easy enable/disable/restart with systemctl
- **Clean Output** - Terminal optimized for visibility and monitoring

**New Files**:
- `launch_maximized.sh` - Maximized terminal launcher for better visibility
- Updated `meshtastic.service` - System service with maximized terminal integration
- Updated `start_terminal.sh` - Integrated with maximized terminal launcher

### v1.5 (Enhanced Reliability)
- **Improved ChatBot Error Handling** - Better recovery from processing failures
- **Enhanced Message Processing** - More robust keyword command detection
- **Better Rate Limiting** - Clearer feedback when limits reached
- **Optimized Dashboard Updates** - Smoother real-time display refresh
- **Message History Fixes** - Proper tracking of sent messages

### v1.4 (AI ChatBot Integration)
- **TinyLlama AI ChatBot** - On-device AI responses over mesh
- **Smart Rate Limiting** - 50 msg/hour for non-selected nodes
- **Auto Message Splitting** - 200-char chunk management
- **Thinking Indicator** - Visual feedback during AI processing
- **CHATBOTON/OFF Commands** - Remote ChatBot control

### v1.3 (Enhanced Messaging)
- **Interactive Message Interface** - View conversations with any node
- **Sent Message Tracking** - Dashboard displays last 10 sent messages
- **Enhanced Keyword Commands** - Added WEATHERCHECK and KEYWORDS commands
- **Command Help Screen** - Detailed documentation for all command words
- **Improved Menu Navigation** - Better keyboard input handling
- **Message Conversation View** - Full conversation history with each node
- **Real-Time Updates** - Message displays update automatically
- **Enhanced Dashboard** - Shows both received and sent messages

**New Keyword Commands**:
- `WEATHERCHECK` - Requests current telemetry/weather data
- `KEYWORDS` - Lists all available commands

### v1.2 (Dashboard Edition)
- **Dashboard Layout** - Active nodes at top, scrolling activity below
- **Live Mesh Network View** - Top 5 most recently heard nodes (last 30 minutes)
- **Real-Time Activity Feed** - Last 20 packets with timestamps in continuous scroll
- **Dedicated Activity Log** - mesh_activity.log for traffic analysis
- **Fresh Sensor Readings** - Triggers BME280 reading before each send
- **Real-Time Telemetry** - Temp/humidity/pressure every minute (not 30-min intervals)
- **Signal Metrics** - Live SNR and RSSI for all active nodes
- **Automatic USB Port Lock Clearing** - Fixes "Resource temporarily unavailable" errors
- **Enhanced Stability** - No manual intervention needed for port locks

### v1.1 (Terminal Edition)
- **Terminal-based interface** - No GUI dependencies, perfect for headless operation
- **Enhanced auto-send display** - Live updates every 10 seconds
- **Immediate send on startup** - No waiting for first telemetry
- **Comprehensive logging** - All activity to mesh_terminal.log
- **M key menu access** - Enter menu anytime during auto-send
- **X key autostart cancel** - 10-second countdown with option to cancel
- **Graceful shutdown** - Ctrl+C exits cleanly
- **Signal strength tracking** - Per-node SNR/RSSI in real-time
- **PKC Direct Messages** - Automatic encryption (firmware 2.5.0+)
- **Configuration persistence** - Settings saved to terminal_config.json

### v1.0 (Legacy - BLE CLI)
- BLE communication support
- CLI menu interface
- Basic telemetry monitoring

---

**Made for the Meshtastic community 📡**
**Optimized for Raspberry Pi 5/4/3 with USB connectivity**