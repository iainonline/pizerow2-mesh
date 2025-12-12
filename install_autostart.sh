#!/bin/bash

# Installation script for Meshtastic autostart service

echo "Installing Meshtastic Monitor autostart service..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "Please do not run as root. Run as your regular user."
    exit 1
fi

# Copy service file to systemd directory
sudo cp meshtastic.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable the service
sudo systemctl enable meshtastic.service

echo ""
echo "Installation complete!"
echo ""
echo "Available commands:"
echo "  sudo systemctl start meshtastic    - Start the service now"
echo "  sudo systemctl stop meshtastic     - Stop the service"
echo "  sudo systemctl status meshtastic   - Check service status"
echo "  sudo systemctl disable meshtastic  - Disable autostart"
echo "  journalctl -u meshtastic -f        - View live logs"
echo ""
echo "The service will automatically start on next boot."
echo "To start it now, run: sudo systemctl start meshtastic"
