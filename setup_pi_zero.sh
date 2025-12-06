#!/bin/bash
#
# Meshtastic Monitor Auto-Setup for Raspberry Pi Zero 2 W
# This script configures a fresh Raspberry Pi OS installation to run the mesh monitor on boot
#

set -e

echo "=========================================="
echo "Meshtastic Monitor Setup"
echo "Raspberry Pi Zero 2 W Configuration"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please do not run as root. Run as pi user."
   exit 1
fi

# Update system
echo "[1/8] Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
echo "[2/8] Installing required packages..."
sudo apt-get install -y python3 python3-pip python3-venv python3-tk git

# Create project directory
echo "[3/8] Setting up project directory..."
INSTALL_DIR="$HOME/MeshtasticController"
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Clone or copy project files
echo "[4/8] Getting project files..."
if [ ! -f "mesh_monitor.py" ]; then
    # If running from USB or download, copy files
    if [ -f "/home/pi/Meshtastic/mesh_monitor.py" ]; then
        cp -r /home/pi/Meshtastic/* "$INSTALL_DIR/"
    else
        # Clone from GitHub
        git clone https://github.com/iainonline/MeshtasticController.git temp_clone
        cp -r temp_clone/* "$INSTALL_DIR/"
        rm -rf temp_clone
    fi
fi

# Create virtual environment
echo "[5/8] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "[6/8] Installing Python packages..."
pip install --upgrade pip
pip install meshtastic pypubsub

# Set up USB permissions
echo "[7/8] Configuring USB permissions..."
sudo usermod -a -G dialout $USER

# Create autostart script
echo "[8/8] Configuring autostart..."

# Create desktop autostart directory
mkdir -p ~/.config/autostart

# Create autostart desktop entry
cat > ~/.config/autostart/meshtastic-monitor.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Meshtastic Monitor
Exec=/home/pi/MeshtasticController/autostart.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Start Meshtastic Monitor on boot
EOF

# Create the autostart wrapper script
cat > "$INSTALL_DIR/autostart.sh" << 'EOF'
#!/bin/bash
# Wait for desktop to load
sleep 10

# Wait for USB device to be available
for i in {1..30}; do
    if [ -e /dev/ttyUSB0 ] || [ -e /dev/ttyACM0 ]; then
        break
    fi
    sleep 1
done

# Start the monitor
cd /home/pi/MeshtasticController
source venv/bin/activate
python mesh_monitor.py
EOF

chmod +x "$INSTALL_DIR/autostart.sh"

# Create manual start script
cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python mesh_monitor.py
EOF

chmod +x "$INSTALL_DIR/start.sh"

# Configure system settings for Pi Zero 2 W
echo ""
echo "Optimizing for Raspberry Pi Zero 2 W..."

# Disable unnecessary services to save resources
sudo systemctl disable bluetooth.service 2>/dev/null || true
sudo systemctl disable hciuart.service 2>/dev/null || true

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Connect your Heltec V3 via USB"
echo "2. Reboot your Pi: sudo reboot"
echo "3. The monitor will start automatically"
echo ""
echo "Manual start: cd $INSTALL_DIR && ./start.sh"
echo ""
echo "⚠️  IMPORTANT: You must reboot for USB permissions to take effect!"
echo ""
