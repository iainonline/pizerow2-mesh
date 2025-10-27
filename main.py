#!/usr/bin/env python3
"""
Meshtastic USB Controller
Simplified interface for Raspberry Pi 5 and Heltec V3 devices
"""

import os
import sys
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from meshtastic_comm import MeshtasticComm

# Configure logging with reduced console output but detailed file logging
log_file = os.path.join(os.path.dirname(__file__), 'meshtastic_app.log')

# Create a custom console formatter that shows less verbose output
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# File handler for detailed logging
file_handler = logging.FileHandler(log_file, mode='a')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_formatter)

# Console handler for minimal output (only INFO and above)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(console_formatter)

# Configure root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Suppress verbose logging from other modules to console
logging.getLogger('meshtastic').setLevel(logging.WARNING)
logging.getLogger('bleak').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

def load_config() -> Dict[str, Any]:
    """Load configuration from file or create default config"""
    config_file = "config.json"
    
    # Default configuration
    default_config = {
        "serial_port": "",
        "device_name": "",
        "last_connected_device": "",
        "to_node": "yang",
        "message_frequency": 60,
        "private_messages": True,
        "to_node_id": 2658499212,  # Decimal node ID for yang
        "custom_message": "[{timestamp}] Battery: {battery} Uptime: {uptime}",
        "telemetry_mode": False,  # Enable comprehensive device telemetry
        "message_templates": {
            "basic": "[{timestamp}] Battery: {battery}",
            "detailed": "[{timestamp}] Battery: {battery} Voltage: {voltage} Channel: {channel_util}",
            "radio": "[{timestamp}] Battery: {battery} Channel: {channel_util} RSSI: {rssi}",
            "full": "[{timestamp}] Battery: {battery} Voltage: {voltage} Channel: {channel_util} Uptime: {uptime}"
        },
        "auto_start": True,
        "auto_start_delay": 10
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Update with any missing default keys
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return default_config
    else:
        save_config(default_config)
        return default_config

def save_config(config: Dict[str, Any]):
    """Save configuration to file"""
    try:
        with open("config.json", 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Configuration saved")
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def display_main_menu(config):
    """Display the main application menu with improved layout"""
    print("\n" + "=" * 60)
    print("                MESHTASTIC USB CONTROLLER")
    print("                   Raspberry Pi Edition")
    print("=" * 60)
    
    # Status section
    print("\nTelemetry: CURRENT STATUS:")
    print("-" * 30)
    
    # Device info
    device_info = get_device_display_info(config)
    if device_info:
        print(f"Device: Device: {device_info[:50]}..." if len(device_info) > 50 else f"Device: Device: {device_info}")
        print(f"Target: Target: {config['to_node']} (ID: {config.get('to_node_id', 'auto')})")
        print(f"Uptime:  Frequency: Every {config['message_frequency']} seconds")
        print(f"Mode: Mode: {'Private' if config.get('private_messages', True) else 'Broadcast'}")
    else:
        print("Error: No device configured - Setup required")
    
    print("\nActions: QUICK ACTIONS:")
    print("-" * 30)
    if device_info:
        print("  Start [S] Start Messaging (Quick Start)")
        print("  Config [C] Configure Settings")
    print("  Setup [D] Device Setup")
    print("  Test [T] Test Connection")
    
    print("\nConfig:  MAIN MENU:")
    print("-" * 30)
    print("  1.  Device Management")
    print("  2.  Connection Test")
    print("  3.  Message Configuration")
    print("  4.  Run Program (with message log)")
    print("  5.  Diagnostics & Logs")
    print("  6.  Exit Application")
    print("\n" + "=" * 60)
    
    # Show helpful hints
    if device_info:
        print("Tip: Tip: Press 'S' for quick start or choose a number (1-6)")
    else:
        print("Tip: Tip: Start with option 1 to configure your device")
    
def pair_or_change_device():
    """Scan for and pair with a Meshtastic device"""
    try:
        print("\n" + "=" * 40)
        print("         DEVICE PAIRING")
        print("=" * 40)
        
        config = load_config()
        current_device = config.get('last_connected_device', 'None')
        device_name = config.get('device_name', '')
        
        if current_device != 'None' and device_name:
            print(f"Current device: {device_name} ({current_device})")
        else:
            print("Current device: None")
        
        print("\n1. Scan for USB/Serial devices")
        print("2. Enter serial port manually")
        print("3. Cancel")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            print("\nScanning for Meshtastic devices...")
            logger.info("Starting device scan")
            
            comm = MeshtasticComm(logger)
            devices = comm.scan_for_devices()
            
            if devices:
                print("\nFound devices:")
                for i, device in enumerate(devices, 1):
                    print(f"  {i}. {device['name']}")
                
                try:
                    device_choice = int(input("\nSelect device (number): ")) - 1
                    if 0 <= device_choice < len(devices):
                        selected_device = devices[device_choice]
                        config['serial_port'] = selected_device['port']
                        config['last_connected_device'] = selected_device['port']
                        config['device_name'] = selected_device['name']
                        # Remove old BLE config
                        if 'ble_address' in config:
                            config['ble_address'] = ""
                        save_config(config)
                        print(f"\nSuccess Device paired: {selected_device['name']}")
                        print(f"Port: {selected_device['port']}")
                        logger.info(f"Device paired: {selected_device['name']} ({selected_device['port']})")
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Invalid input.")
            else:
                print("\nNo Meshtastic devices found.")
                
        elif choice == '2':
            new_port = input("\nEnter serial port (e.g., /dev/ttyUSB0): ").strip()
            if new_port and new_port.startswith('/dev/'):
                config['serial_port'] = new_port
                config['last_connected_device'] = new_port
                config['device_name'] = f"Manual_{new_port.split('/')[-1]}"
                # Remove old BLE config
                if 'ble_address' in config:
                    config['ble_address'] = ""
                save_config(config)
                print(f"\nSuccess Device port set: {new_port}")
                logger.info(f"Manual device port set: {new_port}")
            else:
                print("Invalid serial port format. Should start with /dev/")
                
    except Exception as e:
        error_msg = f"Error in device pairing: {str(e)}"
        print(f"\nError {error_msg}")
        logger.error(error_msg)
        
    input("\\nPress Enter to continue...")

def cleanup_meshtastic_processes():
    """Kill any existing Meshtastic processes that might be using the serial port"""
    try:
        import subprocess
        import psutil
        
        # Look for Python processes that might be using Meshtastic
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] == 'python3' and proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if ('meshtastic' in cmdline.lower() and 
                        'main.py' not in cmdline and  # Don't kill ourselves
                        proc.pid != os.getpid()):
                        logger.info(f"Found existing Meshtastic process (PID {proc.info['pid']}), terminating...")
                        proc.terminate()
                        proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
                
        # Also try to kill any meshtastic CLI processes
        try:
            subprocess.run(['pkill', '-f', 'meshtastic'], capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
    except Exception as e:
        logger.debug(f"Error during process cleanup: {e}")

def test_connection():
    """Test connection to the paired device"""
    try:
        config = load_config()
        serial_port = config.get('last_connected_device') or config.get('serial_port')
        
        if not serial_port:
            print("\\nError No device paired. Please pair a device first.")
            input("\\nPress Enter to continue...")
            return
            
        device_name = config.get('device_name', 'Unknown')
        print(f"\\nTesting connection to {device_name}...")
        print(f"Serial Port: {serial_port}")
        print("Testing USB connectivity...")
        print("Press Ctrl+C to cancel if it takes too long")
        
        logger.info(f"Testing USB connection to {serial_port}")
        
        # Clean up any processes that might be using the port
        cleanup_meshtastic_processes()
        
        comm = MeshtasticComm(logger)
        try:
            success = comm.test_connection(serial_port)
        except KeyboardInterrupt:
            print("\\n\\nWarning: Connection test cancelled by user")
            print("The connection attempt was interrupted.")
            return
        
        if success:
            print("\n\u2713 Connection test PASSED!")
            print("- USB/Serial connection established successfully")
            print("- Device is reachable and responding")
            print("- Ready for messaging operations")
        else:
            print("\nError Connection test FAILED!")
            print("- Could not establish Bluetooth connection")
            print("\nTroubleshooting:")
            print("  - Ensure device is powered on and nearby")
            print("  - Check device is within Bluetooth range (<10m)")
            print("  - Verify BLE address is correct")
            print("  - Make sure no other apps are using the device")
            print("  - Try the 'Debug & Diagnostics' menu for more info")
            
    except Exception as e:
        error_msg = f"Error testing connection: {str(e)}"
        print(f"\nError {error_msg}")
        logger.error(error_msg)
        
    input("\nPress Enter to continue...")

def configure_message():
    """Configure message settings with improved interface"""
    while True:
        config = load_config()
        
        # Add default custom message if not present
        if 'custom_message' not in config:
            config['custom_message'] = "[{timestamp}] Battery: {battery}"
        
        print("\n" + "=" * 50)
        print("         MESSAGE CONFIGURATION")
        print("=" * 50)
        
        print("\nCURRENT SETTINGS:")
        print("-" * 25)
        print(f"Target Node: {config['to_node']}")
        print(f"Node ID: {config.get('to_node_id', 'Auto-detect')}")
        print(f"Frequency: Every {config['message_frequency']} seconds")
        print(f"Mode: {'Private' if config.get('private_messages', True) else 'Broadcast'}")
        print(f"Template: {config['custom_message']}")
        
        print("\nCONFIGURATION OPTIONS:")
        print("-" * 30)
        print("  1. Change message frequency")
        print("  2. Set target node name")
        print("  3. Configure node ID")
        print("  4. Toggle privacy mode")
        print("  5. Message templates & telemetry")
        print("  6. Back to main menu")
        
        print("\n" + "=" * 50)
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            configure_frequency(config)
        elif choice == '2':
            configure_target_node(config)
        elif choice == '3':
            configure_node_id(config)
        elif choice == '4':
            toggle_privacy_mode(config)
        elif choice == '5':
            configure_telemetry_options(config)
        elif choice == '6':
            break
        else:
            print("\nError: Invalid choice. Please enter 1-6.")
            input("\nPause:  Press Enter to continue...")

def configure_frequency(config):
    """Configure message frequency with validation"""
    print("\nUptime:  MESSAGE FREQUENCY SETUP")
    print("-" * 30)
    print(f"Current: Every {config['message_frequency']} seconds")
    print("\nRecommended settings:")
    print("  - 30s - High frequency (testing)")
    print("  - 60s - Normal (recommended)")
    print("  - 300s - Low frequency (5 min)")
    print("  - 900s - Very low (15 min)")
    
    while True:
        try:
            new_freq = input("\n> Enter frequency in seconds (10-3600): ").strip()
            if not new_freq:
                return
            
            freq = int(new_freq)
            if 10 <= freq <= 3600:
                config['message_frequency'] = freq
                save_config(config)
                print(f"\nSuccess: Frequency set to {freq} seconds")
                
                # Show practical info
                if freq < 60:
                    print("Warning:  High frequency - good for testing")
                elif freq <= 300:
                    print("Success: Good balance of updates and battery life")
                else:
                    print("Battery: Low frequency - maximizes battery life")
                break
            else:
                print("Error: Frequency must be between 10 and 3600 seconds")
        except ValueError:
            print("Error: Please enter a valid number")
    
    input("\nPause:  Press Enter to continue...")

def configure_target_node(config):
    """Configure target node name"""
    print("\nTarget: TARGET NODE SETUP")
    print("-" * 25)
    print(f"Current target: {config['to_node']}")
    
    new_target = input("\n> Enter target node name: ").strip()
    if new_target:
        config['to_node'] = new_target
        save_config(config)
        print(f"\nSuccess: Target node set to '{new_target}'")
    
    input("\nPause:  Press Enter to continue...")

def configure_node_id(config):
    """Configure target node ID with validation"""
    print("\nID: NODE ID CONFIGURATION")
    print("-" * 30)
    print(f"Current ID: {config.get('to_node_id', 'Auto-detect')}")
    print("\nNode ID helps ensure private messages reach the right device.")
    print("\nTip: Examples:")
    print("  - 2658499212 (decimal format)")
    print("  - Leave blank for auto-detection")
    
    node_id_input = input("\n> Enter node ID (or press Enter for auto): ").strip()
    
    if node_id_input:
        try:
            node_id = int(node_id_input)
            config['to_node_id'] = node_id
            save_config(config)
            print(f"\nSuccess: Node ID set to {node_id}")
        except ValueError:
            print("\nError: Invalid node ID. Please enter a decimal number.")
    else:
        if config.get('to_node_id'):
            clear = input("\nQuestion: Clear existing node ID? (y/N): ").strip().lower()
            if clear == 'y':
                config['to_node_id'] = None
                save_config(config)
                print("\nSuccess: Node ID cleared - will use auto-detection")
    
    input("\nPause:  Press Enter to continue...")

def toggle_privacy_mode(config):
    """Toggle between private and broadcast messaging"""
    current_private = config.get('private_messages', True)
    
    print("\nMode: PRIVACY MODE SELECTION")
    print("-" * 30)
    print(f"Current mode: {'Private Private' if current_private else 'Broadcast Broadcast'}")
    
    print("\nOptions: Options:")
    print("  1.  Private Private messages (sent to specific node only)")
    print("  2.  Broadcast Broadcast messages (visible to all nodes)")
    
    choice = input("\n> Choose mode (1/2): ").strip()
    
    if choice == '1':
        config['private_messages'] = True
        save_config(config)
        print("\nSuccess: Private messaging enabled")
        print("Private Messages will be sent only to your target node")
    elif choice == '2':
        config['private_messages'] = False
        save_config(config)
        print("\nBroadcast messaging enabled")
        print("Messages will be visible to all nodes in the mesh")
    
    input("\nPause:  Press Enter to continue...")

def configure_telemetry_options(config):
    """Configure message templates and telemetry options"""
    print("\nTELEMETRY & MESSAGE TEMPLATES")
    print("-" * 40)
    
    # Ensure template structure exists
    if 'message_templates' not in config:
        config['message_templates'] = {
            "basic": "[{timestamp}] Battery: {battery}%",
            "detailed": "[{timestamp}] Battery: {battery}% Voltage: {voltage}V | Channel: {channel_util}%",
            "radio": "[{timestamp}] Battery: {battery}% Channel: {channel_util}% RSSI: {rssi}dBm",
            "full": "[{timestamp}] Battery: {battery}% Voltage: {voltage}V Channel: {channel_util}% Uptime: {uptime}"
        }
    
    current_mode = "Enhanced" if config.get('telemetry_mode', False) else "Basic"
    print(f"Current mode: {current_mode}")
    print(f"Active template: {config.get('custom_message', 'Default')}")
    
    print("\nTEMPLATE OPTIONS:")
    print("-" * 25)
    templates = config['message_templates']
    for i, (name, template) in enumerate(templates.items(), 1):
        print(f"  {i}. {name.title()}: {template}")
    
    print("\nConfig:  ADVANCED OPTIONS:")
    print("-" * 25)
    print(f"  5.  Toggle telemetry mode (current: {current_mode})")
    print("  6.  Custom template editor")
    print("  7.  Preview message with current data")
    print("  8.  Back to configuration menu")
    
    choice = input("\n> Select option (1-8): ").strip()
    
    if choice in ['1', '2', '3', '4']:
        template_names = list(templates.keys())
        selected_name = template_names[int(choice) - 1]
        selected_template = templates[selected_name]
        
        config['custom_message'] = selected_template
        config['telemetry_mode'] = (selected_name in ['detailed', 'radio', 'full'])
        save_config(config)
        
        print(f"\nSuccess: Template set to '{selected_name.title()}'")
        print(f"Telemetry mode: {'Enabled' if config['telemetry_mode'] else 'Disabled'}")
        
    elif choice == '5':
        config['telemetry_mode'] = not config.get('telemetry_mode', False)
        save_config(config)
        new_mode = "Enhanced" if config['telemetry_mode'] else "Basic"
        print(f"\nSuccess: Telemetry mode: {new_mode}")
        
    elif choice == '6':
        print("\nEditor CUSTOM TEMPLATE EDITOR")
        print("-" * 30)
        print("Available variables:")
        print("  {timestamp} - Message time (HH:MM:SS)")
        print("  {battery} - Battery percentage")
        print("  {uptime} - Device uptime (auto-format: minutes/hours/days)")
        
        current = config.get('custom_message', '')
        print(f"\nCurrent: {current}")
        
        new_template = input("\nEnter new template (or press Enter to cancel): ").strip()
        if new_template:
            config['custom_message'] = new_template
            config['telemetry_mode'] = True  # Enable telemetry for custom templates
            save_config(config)
            print("\nSuccess: Custom template saved!")
            
    elif choice == '7':
        preview_message_with_data(config)
        
    input("\nPause:  Press Enter to continue...")

def preview_message_with_data(config):
    """Preview what a message would look like with current data"""
    print("\nPreview MESSAGE PREVIEW")
    print("-" * 20)
    
    try:
        # Create sample data
        from datetime import datetime
        sample_data = {
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'battery': 87.3,
            'uptime': '2.3h'
        }
        
        template = config.get('custom_message', '[{timestamp}] Battery: {battery}')
        
        try:
            preview = template.format(**sample_data)
            print(f"Template: {template}")
            print(f"Preview:  {preview}")
            
            print(f"\nTelemetry: Data includes:")
            if config.get('telemetry_mode', False):
                print("  Success: Timestamp, battery percentage, and device uptime")
                print("  Time: Simple, clean message format")
            else:
                print("  - Basic battery and timestamp only")
                print("  Info: Enable telemetry mode for uptime data")
                
        except KeyError as e:
            print(f"Warning:  Template error: Variable {e} not available")
            print("Available variables listed in custom template editor")
            
    except Exception as e:
        print(f"Error: Preview error: {e}")

def old_configure_message():
    """Legacy configure message function - keeping for reference"""
    try:
        config = load_config()
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            while True:
                try:
                    new_freq = input(f"\nEnter frequency in seconds (10-3600, current: {config['message_frequency']}): ")
                    if not new_freq.strip():
                        break
                    freq = int(new_freq)
                    if 10 <= freq <= 3600:
                        config['message_frequency'] = freq
                        print(f"Success Frequency set to {freq} seconds")
                        break
                    else:
                        print("Frequency must be between 10 and 3600 seconds.")
                except ValueError:
                    print("Please enter a valid number.")
        
        elif choice == '2':
            to_node = input(f"\\nTarget node name (current: {config['to_node']}): ").strip()
            if to_node:
                config['to_node'] = to_node
                print(f"Success Target node set to {to_node}")
                
        elif choice == '3':
            # Configure node ID for private messaging
            current_node_id = config.get('to_node_id', '')
            print("\\nFor private messaging, you can specify the exact node ID:")
            print("Supported formats: !9e765a8 (hex with !), 9e765a8 (hex), or 166159784 (decimal)")
            print(f"Current to_node_id: {current_node_id if current_node_id else 'Not set (will auto-discover)'}")
            to_node_id = input("To node ID (or press Enter to skip): ").strip()
            if to_node_id:
                if not to_node_id.startswith('!'):
                    to_node_id = '!' + to_node_id
                config['to_node_id'] = to_node_id
                print(f"\u2713 To node ID set to {to_node_id}")
            elif to_node_id == '' and current_node_id:
                # User pressed Enter but there was a previous value - ask if they want to clear it
                clear = input(f"Clear existing node ID? (y/N): ").strip().lower()
                if clear == 'y':
                    config['to_node_id'] = ''
                    print("\u2713 Node ID cleared (will use auto-discovery)")
                
        elif choice == '4':
            print("\nMessage Privacy Settings:")
            print("1. Private messages (sent directly to specific node)")
            print("2. Broadcast messages (visible to all nodes in mesh)")
            current_setting = "Private" if config.get('private_messages', True) else "Broadcast"
            print(f"Current: {current_setting}")
            
            privacy_choice = input("\nChoose (1 for private, 2 for broadcast): ").strip()
            if privacy_choice == '1':
                config['private_messages'] = True
                print("\u2713 Set to private messages (direct node-to-node)")
            elif privacy_choice == '2':
                config['private_messages'] = False
                print("\u2713 Set to broadcast messages (visible to entire mesh)")
        
        if choice in ['1', '2', '3', '4']:
            save_config(config)
            private_str = "private" if config.get('private_messages', True) else "broadcast"
            logger.info(f"Message configuration updated: freq={config['message_frequency']}s, target={config['to_node']}, node_id={config.get('to_node_id', 'auto')}, mode={private_str}")
            print("\\nSuccess Configuration saved successfully!")
            
    except Exception as e:
        error_msg = f"Error configuring message: {str(e)}"
        print(f"\\nError {error_msg}")
        logger.error(error_msg)
        
    input("\nPress Enter to continue...")

def start_messaging():
    """Start the messaging service with improved interface"""
    try:
        config = load_config()
        serial_port = config.get('last_connected_device') or config.get('serial_port')
        
        if not serial_port:
            print("\n" + "=" * 50)
            print("            Error: SETUP REQUIRED")
            print("=" * 50)
            print("\nSetup No device configured yet!")
            print("\nTip: Quick setup options:")
            print("  1. Return to main menu and use 'Device Management'")
            print("  2. Use auto-detect to find your device")
            
            choice = input("\n> Run auto-detect now? (y/N): ").strip().lower()
            if choice == 'y':
                auto_detect_devices()
                # Try again with updated config
                config = load_config()
                serial_port = config.get('serial_port')
                if not serial_port:
                    return
            else:
                return
        
        # Pre-flight check
        print("\n" + "=" * 60)
        print("              Start STARTING MESSAGING SERVICE")
        print("=" * 60)
        
        device_info = get_device_display_info(config)
        print(f"\nTelemetry: MISSION PARAMETERS:")
        print("-" * 25)
        print(f"Device: Device: {device_info[:35]}..." if len(device_info) > 35 else f"Device: Device: {device_info}")
        print(f"Port: Port: {serial_port}")
        print(f"Target: Target: {config['to_node']}")
        if config.get('to_node_id'):
            print(f"ID: Node ID: {config['to_node_id']}")
        print(f"Uptime:  Interval: Every {config['message_frequency']} seconds")
        print(f"Mode: Mode: {'Private Private' if config.get('private_messages', True) else 'Broadcast Broadcast'}")
        print(f"Template: Format: [timestamp] Battery: percentage%")
        
        print("\nLoading CONNECTING...")
        print("-" * 20)
        
        logger.info(f"Starting messaging service - Device: {serial_port}, Frequency: {config['message_frequency']}s")
        
        comm = MeshtasticComm(logger)
        
        # Try to connect with retry logic built into the comm class
        print("Establishing connection (this may take 10-30 seconds)...")
        success = comm.connect(
            serial_port=serial_port,
            from_node="local",  # Use generic from_node
            to_node=config['to_node'],
            to_node_id=config.get('to_node_id')
        )
        
        if success:
            print("\nSuccess Connected successfully!")
            print("\n" + "=" * 60)
            print("              Device: MESHTASTIC MESSAGING ACTIVE")
            print("=" * 60)
            print(f"Target: Target: {config['to_node']} (ID: {config.get('to_node_id', 'auto')})")
            print(f"Uptime:  Frequency: Every {config['message_frequency']} seconds")
            print(f"Mode: Mode: {'Private messaging' if config.get('private_messages', True) else 'Broadcast'}")
            print(f"Template: Template: {config.get('custom_message', 'Default')}")
            print("\nMESSAGE LOG:")
            print("-" * 60)
            
            # Start messaging in a separate thread
            def messaging_loop():
                try:
                    while True:
                        # Get timestamp
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        # Get battery level
                        battery_level = comm.get_battery_level()
                        battery = battery_level if battery_level else 0
                        
                        # Get enhanced telemetry data if enabled
                        telemetry_mode = config.get('telemetry_mode', False)
                        message_data = {'timestamp': timestamp, 'battery': battery}
                        
                        if telemetry_mode:
                            # Get comprehensive device telemetry
                            device_telemetry = comm.get_device_telemetry()
                            
                            # Add only uptime data for simple messaging
                            uptime_seconds = device_telemetry.get('uptime_seconds', 0) or 0
                            if uptime_seconds < 3600:
                                uptime_str = f"{uptime_seconds / 60:.0f}m"
                            elif uptime_seconds < 86400:
                                uptime_str = f"{uptime_seconds / 3600:.1f}h"
                            else:
                                uptime_str = f"{uptime_seconds / 86400:.1f}d"
                            
                            message_data.update({
                                'uptime': uptime_str
                            })
                        
                        # Use custom message template with error handling
                        custom_template = config.get('custom_message', "[{timestamp}] Battery: {battery}")
                        try:
                            message = custom_template.format(**message_data)
                        except (KeyError, ValueError) as e:
                            # Fallback to default message if template is invalid
                            logger.warning(f"Invalid message template: {e}. Using default.")
                            message = f"[{timestamp}] Battery: {battery}%"
                        
                        private_mode = config.get('private_messages', True)
                        # Send message with telemetry if enabled
                        success = comm.send_message(
                            message, 
                            include_battery=False, 
                            include_sensors=False, 
                            include_telemetry=telemetry_mode,
                            private=private_mode
                        )
                        
                        # Enhanced logging with timestamp and status
                        log_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        target_info = f"to {config['to_node']}" if private_mode else "(broadcast)"
                        
                        if success:
                            print(f"[{log_timestamp}] SENT {target_info}: {message}")
                            logger.info(f"Message sent to {config['to_node']}: {message}")
                        else:
                            print(f"[{log_timestamp}] FAILED {target_info}: {message}")
                            logger.error(f"Failed to send message to {config['to_node']}: {message}")
                        
                        time.sleep(config['message_frequency'])
                        
                except KeyboardInterrupt:
                    print("\n\nStopping messaging...")
                    comm.disconnect()
                    
            # Show initial status
            first_message_time = datetime.now() + timedelta(seconds=5)
            print(f"Starting in 5 seconds... First message at {first_message_time.strftime('%H:%M:%S')}")
            print("\nPress Ctrl+C to stop and return to menu\n")
            time.sleep(5)  # Give user time to read the setup
            
            messaging_thread = threading.Thread(target=messaging_loop, daemon=True)
            messaging_thread.start()
            
            # Wait for user interrupt
            try:
                messaging_thread.join()
            except KeyboardInterrupt:
                print("\n\nMessaging stopped by user.")
                comm.stop_messaging()  # Stop messaging but keep connection alive
        else:
            print("\nError Failed to connect to device")
            print("Try using Test Connection option first to diagnose issues.")
            
    except Exception as e:
        error_msg = f"Error starting messaging: {str(e)}"
        print(f"\nError {error_msg}")
        logger.error(error_msg, exc_info=True)
        
    input("\nPress Enter to continue...")

def debug_menu():
    """Display and handle debug menu options"""
    while True:
        print("\n=== Debug & Diagnostics ===")
        print("1. Show System Information")
        print("2. Show Configuration Details")
        print("3. Test USB/Serial Scanning")
        print("4. Show Recent Logs")
        print("5. Test Connection (Verbose)")
        print("6. Check Python Environment")
        print("0. Back to Main Menu")
        
        try:
            choice = input("\nSelect option (0-6): ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                show_system_info()
            elif choice == '2':
                show_config_details()
            elif choice == '3':
                test_usb_scanning()
            elif choice == '4':
                show_recent_logs()
            elif choice == '5':
                test_connection_verbose()
            elif choice == '6':
                check_python_environment()
            else:
                print("Invalid option. Please try again.")
                
        except KeyboardInterrupt:
            print("\n\nReturning to main menu...")
            break
        except Exception as e:
            print(f"\nDebug menu error: {e}")

def show_system_info():
    """Display system information for debugging"""
    try:
        import platform
        import psutil
        import subprocess
        
        print("\n" + "=" * 40)
        print("        SYSTEM INFORMATION")
        print("=" * 40)
        
        # System info
        print(f"\nOperating System: {platform.system()} {platform.release()}")
        print(f"Python Version: {platform.python_version()}")
        print(f"Architecture: {platform.machine()}")
        
        # Memory info
        memory = psutil.virtual_memory()
        print(f"\nMemory:")
        print(f"  Total: {memory.total // (1024**3)} GB")
        print(f"  Available: {memory.available // (1024**3)} GB")
        print(f"  Used: {memory.percent}%")
        
        # USB Serial info
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"\\nUSB Serial Devices:")
                usb_lines = [line.strip() for line in result.stdout.split('\\n') 
                           if any(keyword in line.lower() for keyword in ['serial', 'cp210', 'ch340', 'ch341', 'ftdi'])]
                if usb_lines:
                    for line in usb_lines[:5]:  # Show first 5 matches
                        print(f"  {line}")
                else:
                    print("  No USB serial adapters detected")
            else:
                print("\\nUSB: Unable to check devices")
        except:
            print("\\nUSB: lsusb not available")
            
    except Exception as e:
        print(f"\nError getting system info: {e}")
        logger.error(f"Error in show_system_info: {e}")

def show_config_details():
    """Show detailed configuration information"""
    try:
        config = load_config()
        
        print("\n" + "=" * 40)
        print("      CONFIGURATION DETAILS")
        print("=" * 40)
        
        print(f"\nCurrent Configuration:")
        for key, value in config.items():
            print(f"  {key}: {value}")
        
        # File info
        import os
        config_path = "config.json"
        if os.path.exists(config_path):
            stat = os.stat(config_path)
            print(f"\nConfig File Info:")
            print(f"  Path: {os.path.abspath(config_path)}")
            print(f"  Size: {stat.st_size} bytes")
            print(f"  Modified: {time.ctime(stat.st_mtime)}")
        
        # Log file info
        log_path = "meshtastic_app.log"
        if os.path.exists(log_path):
            stat = os.stat(log_path)
            print(f"\nLog File Info:")
            print(f"  Path: {os.path.abspath(log_path)}")
            print(f"  Size: {stat.st_size} bytes")
            print(f"  Modified: {time.ctime(stat.st_mtime)}")
            
    except Exception as e:
        print(f"\nError getting config details: {e}")
        logger.error(f"Error in show_config_details: {e}")

def test_usb_scanning():
    """Test USB/Serial scanning functionality with verbose output"""
    try:
        print("\n" + "=" * 40)
        print("       USB/SERIAL SCAN TEST")
        print("=" * 40)
        
        print("\nTesting USB/Serial scanning capability...")
        print("This will scan for all serial ports and identify potential Meshtastic devices")
        
        # Temporarily enable more verbose logging
        import logging
        meshtastic_logger = logging.getLogger('meshtastic')
        original_mesh_level = meshtastic_logger.level
        
        try:
            print("\nStarting scan...")
            logger.info("Starting USB/Serial scan test")
            
            # Create a temporary comm instance for testing
            test_comm = MeshtasticComm()
            devices = test_comm.scan_for_devices()
            
            if devices:
                print(f"\nSuccess Found {len(devices)} serial devices:")
                for i, device in enumerate(devices, 1):
                    print(f"  {i}. {device['name']}")
            else:
                print("\nError No serial devices found")
                print("This could mean:")
                print("  - No Meshtastic devices are connected via USB")
                print("  - Device drivers not installed")
                print("  - USB cable issues")
                print("  - Device not powered on")
                
        finally:
            # Restore original logging levels
            meshtastic_logger.setLevel(original_mesh_level)
            
    except Exception as e:
        print(f"\nError during USB/Serial scan test: {e}")
        logger.error(f"Error in test_usb_scanning: {e}", exc_info=True)

def show_recent_logs():
    """Show recent log entries"""
    try:
        print("\n" + "=" * 40)
        print("        RECENT LOG ENTRIES")
        print("=" * 40)
        
        log_path = "meshtastic_app.log"
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                lines = f.readlines()
                # Show last 20 lines
                recent_lines = lines[-20:] if len(lines) > 20 else lines
                
                print(f"\nLast {len(recent_lines)} log entries:")
                print("-" * 60)
                for line in recent_lines:
                    print(line.strip())
        else:
            print("\nNo log file found at meshtastic_app.log")
            
    except Exception as e:
        print(f"\nError reading log file: {e}")
        logger.error(f"Error in show_recent_logs: {e}")

def test_connection_verbose():
    """Test connection with verbose debugging output"""
    try:
        config = load_config()
        ble_address = config.get('ble_address')
        
        if not ble_address:
            print("\nError No device configured. Please pair a device first.")
            return
            
        print("\n" + "=" * 40)
        print("      VERBOSE CONNECTION TEST")
        print("=" * 40)
        
        device_name = config.get('device_name', 'Unknown')
        print(f"\nTesting connection to: {device_name}")
        print(f"BLE Address: {ble_address}")
        print(f"Timeout: 15 seconds")
        
        # Enable verbose logging temporarily
        import logging
        meshtastic_logger = logging.getLogger('meshtastic')
        original_level = meshtastic_logger.level
        
        try:
            print("\nStarting connection test...")
            start_time = time.time()
            
            # Set to INFO level to see more details
            meshtastic_logger.setLevel(logging.INFO)
            
            comm = MeshtasticComm(logger)
            success = comm.test_connection(ble_address)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\nTest completed in {duration:.2f} seconds")
            
            if success:
                print("\\nSuccess CONNECTION TEST SUCCESSFUL!")
                print("- USB/Serial connection established")
                print("- Device is responding")
                print("- Ready for messaging operations")
            else:
                print("\nError CONNECTION TEST FAILED!")
                print("- Could not establish connection")
                print("- Check device power and range")
                print("- Verify BLE address is correct")
                
        finally:
            # Restore logging level
            meshtastic_logger.setLevel(original_level)
            
    except Exception as e:
        print(f"\nError Test error: {e}")
        logger.error(f"Error in test_connection_verbose: {e}", exc_info=True)

def check_python_environment():
    """Check Python environment and dependencies"""
    try:
        print("\n" + "=" * 40)
        print("      PYTHON ENVIRONMENT")
        print("=" * 40)
        
        import sys
        print(f"\nPython executable: {sys.executable}")
        print(f"Python version: {sys.version}")
        print(f"Python path: {sys.path[0]}")
        
        # Check key dependencies
        dependencies = [
            'meshtastic',
            'bleak', 
            'psutil',
            'pypubsub'
        ]
        
        print(f"\nDependency versions:")
        for dep in dependencies:
            try:
                module = __import__(dep)
                version = getattr(module, '__version__', 'Unknown')
                print(f"  {dep}: {version}")
            except ImportError:
                print(f"  {dep}: NOT INSTALLED")
            except Exception as e:
                print(f"  {dep}: Error - {e}")
        
        # Check working directory
        print(f"\nWorking directory: {os.getcwd()}")
        
        # List key files
        key_files = ['main.py', 'meshtastic_comm.py', 'config.json', 'requirements.txt']
        print(f"\nKey files:")
        for file in key_files:
            if os.path.exists(file):
                size = os.path.getsize(file)
                print(f"  {file}: {size} bytes Success")
            else:
                print(f"  {file}: MISSING Error")
                
    except Exception as e:
        print(f"\nError checking Python environment: {e}")
        logger.error(f"Error in check_python_environment: {e}")

def main():
    """Main application loop"""
    logger.info("=== Starting Meshtastic USB Controller ===")
    logger.info(f"Log file location: {log_file}")
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"Python version: {sys.version}")
    
    print("Welcome to Meshtastic USB Controller!")
    print("Optimized for Raspberry Pi 5 and Heltec V3 devices")
    print(f"Detailed logs: {log_file}")
    
    try:
        config = load_config()
        
        # Auto-start functionality
        if config.get('auto_start', True) and config.get('serial_port'):
            auto_delay = config.get('auto_start_delay', 10)
            print(f"\nAUTO-START ENABLED")
            print(f"Will automatically start messaging in {auto_delay} seconds...")
            print("Press Ctrl+C to access menu instead")
            
            try:
                # Simple countdown with interrupt
                for remaining in range(auto_delay, 0, -1):
                    print(f"\rStarting in {remaining:2d} seconds... (Ctrl+C to cancel)", end='', flush=True)
                    time.sleep(1)
                
                print("\n\nAuto-starting messaging service...")
                start_messaging()
                return
                
            except KeyboardInterrupt:
                print("\n\nAuto-start cancelled. Showing menu...")
        
        # Regular menu loop
        while True:
            config = load_config()
            display_main_menu(config)
            choice = input("\nEnter your choice (1-6, or S/C/D/T): ").strip().upper()
            
            # Handle quick actions
            if choice == 'S':
                start_messaging()
            elif choice == 'C':
                configure_message()
            elif choice == 'D':
                pair_or_change_device()
            elif choice == 'T':
                test_connection()
            # Handle numbered options
            elif choice == '1':
                pair_or_change_device()
            elif choice == '2':
                test_connection()
            elif choice == '3':
                configure_message()
            elif choice == '4':
                start_messaging()
            elif choice == '5':
                debug_menu()
            elif choice == '6':
                logger.info("User requested exit")
                break
            else:
                print("Invalid choice. Please try again.")
    
    except KeyboardInterrupt:
        print("\n\nReceived interrupt signal. Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Goodbye!")

def auto_detect_devices():
    """Auto-detect available Meshtastic devices"""
    print("\nDetecting: AUTO-DETECTING DEVICES...")
    print("-" * 30)
    
    try:
        import meshtastic_comm
        devices = meshtastic_comm.scan_devices()
        
        if devices:
            print(f"\nSuccess: Found {len(devices)} device(s):")
            for i, device in enumerate(devices, 1):
                print(f"  {i}. {device}")
            
            if len(devices) == 1:
                # Auto-select single device
                config = load_config()
                config['serial_port'] = devices[0]
                config['device_name'] = f"Device on {devices[0]}"
                save_config(config)
                print(f"\nSuccess: Automatically configured: {devices[0]}")
            else:
                # Let user choose
                choice = input(f"\n> Select device (1-{len(devices)}): ").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(devices):
                        config = load_config()
                        config['serial_port'] = devices[idx]
                        config['device_name'] = f"Device on {devices[idx]}"
                        save_config(config)
                        print(f"\nSuccess: Configured: {devices[idx]}")
                except ValueError:
                    print("Error: Invalid selection")
        else:
            print("\nError: No Meshtastic devices found")
            print("Tip: Make sure your device is connected via USB")
            
    except Exception as e:
        print(f"\nError: Auto-detection failed: {e}")
        logger.error(f"Auto-detection error: {e}")

def get_device_display_info(config):
    """Get formatted device display information"""
    if config.get('device_name'):
        return config['device_name']
    elif config.get('serial_port'):
        return f"Device on {config['serial_port']}"
    else:
        return None

def display_menu():
    """Legacy display menu function - redirects to improved version"""
    display_main_menu(load_config())

if __name__ == "__main__":
    main()