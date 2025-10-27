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
        "custom_message": "[{timestamp}] Battery: {battery}%"
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

def display_menu():
    """Display the simplified main menu"""
    config = load_config()
    
    print("\n" + "=" * 50)
    print("       MESHTASTIC USB CONTROLLER")
    print("=" * 50)
    
    # Display current device info
    device_info = "Not Connected"
    if config.get('last_connected_device') and config.get('device_name'):
        device_info = f"{config['device_name']} ({config['last_connected_device']})"
    elif config.get('serial_port'):
        device_info = config['serial_port']
    
    print(f"Connected Device: {device_info}")
    print(f"Message Frequency: {config['message_frequency']} seconds")
    print(f"Target Node: {config['to_node']}")
    
    print("\nOptions:")
    print("  1. Pair / Change Device")
    print("  2. Test Connection")
    print("  3. Configure Message")
    print("  4. Start Messaging")
    print("  5. Debug & Diagnostics")
    print("  6. Exit")
    print("=" * 50)
    
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
                        print(f"\n✓ Device paired: {selected_device['name']}")
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
                print(f"\n✓ Device port set: {new_port}")
                logger.info(f"Manual device port set: {new_port}")
            else:
                print("Invalid serial port format. Should start with /dev/")
                
    except Exception as e:
        error_msg = f"Error in device pairing: {str(e)}"
        print(f"\n✗ {error_msg}")
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
            print("\\n✗ No device paired. Please pair a device first.")
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
            print("\\n\\n⚠️ Connection test cancelled by user")
            print("The connection attempt was interrupted.")
            return
        
        if success:
            print("\n\u2713 Connection test PASSED!")
            print("• USB/Serial connection established successfully")
            print("• Device is reachable and responding")
            print("• Ready for messaging operations")
        else:
            print("\n✗ Connection test FAILED!")
            print("• Could not establish Bluetooth connection")
            print("\nTroubleshooting:")
            print("  - Ensure device is powered on and nearby")
            print("  - Check device is within Bluetooth range (<10m)")
            print("  - Verify BLE address is correct")
            print("  - Make sure no other apps are using the device")
            print("  - Try the 'Debug & Diagnostics' menu for more info")
            
    except Exception as e:
        error_msg = f"Error testing connection: {str(e)}"
        print(f"\n✗ {error_msg}")
        logger.error(error_msg)
        
    input("\nPress Enter to continue...")

def configure_message():
    """Configure message settings (frequency and target node)"""
    try:
        print("\n" + "=" * 40)
        print("      MESSAGE CONFIGURATION")
        print("=" * 40)
        
        config = load_config()
        
        # Add default custom message if not present
        if 'custom_message' not in config:
            config['custom_message'] = "[{timestamp}] Battery: {battery}%"
        
        print(f"\nCurrent settings:")
        print(f"  Frequency: {config['message_frequency']} seconds")
        print(f"  Target Node: {config['to_node']}")
        if config.get('to_node_id'):
            print(f"  Target Node ID: {config['to_node_id']}")
        print(f"  Message Template: {config['custom_message']}")
        print(f"  Private Messages: {'Yes' if config.get('private_messages', True) else 'No (Broadcast)'}")
        
        print("\nWhat would you like to change?")
        print("1. Message frequency")
        print("2. Target node name")
        print("3. Target node ID")
        print("4. Privacy settings (private vs broadcast)")
        print("5. Back to main menu")
        
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
                        print(f"✓ Frequency set to {freq} seconds")
                        break
                    else:
                        print("Frequency must be between 10 and 3600 seconds.")
                except ValueError:
                    print("Please enter a valid number.")
        
        elif choice == '2':
            to_node = input(f"\\nTarget node name (current: {config['to_node']}): ").strip()
            if to_node:
                config['to_node'] = to_node
                print(f"✓ Target node set to {to_node}")
                
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
            print("\\n✓ Configuration saved successfully!")
            
    except Exception as e:
        error_msg = f"Error configuring message: {str(e)}"
        print(f"\\n✗ {error_msg}")
        logger.error(error_msg)
        
    input("\nPress Enter to continue...")

def start_messaging():
    """Start the messaging service"""
    try:
        config = load_config()
        serial_port = config.get('last_connected_device') or config.get('serial_port')
        
        if not serial_port:
            print("\n✗ No device paired. Please pair a device first.")
            input("\nPress Enter to continue...")
            return
        
        device_name = config.get('device_name', 'Unknown')
        print(f"\nStarting messaging with {device_name}...")
        print(f"Frequency: Every {config['message_frequency']} seconds")
        print(f"Target Node: {config['to_node']}")
        print("\nConnecting to device...")
        
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
            print("\n✓ Connected successfully!")
            print("Starting message transmission...")
            
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
                        
                        # Use custom message template with error handling
                        custom_template = config.get('custom_message', "[{timestamp}] Battery: {battery}%")
                        try:
                            message = custom_template.format(
                                timestamp=timestamp,
                                battery=battery,
                                to_node=config['to_node']
                            )
                        except (KeyError, ValueError) as e:
                            # Fallback to default message if template is invalid
                            logger.warning(f"Invalid message template: {e}. Using default.")
                            message = f"[{timestamp}] Battery: {battery}%"
                        
                        private_mode = config.get('private_messages', True)
                        # Send simple message since sensor data is already included in the template
                        success = comm.send_message(message, include_battery=False, include_sensors=False, private=private_mode)
                        if success:
                            print(f"✓ Message sent: {message}")
                        else:
                            print("✗ Failed to send message")
                        
                        time.sleep(config['message_frequency'])
                        
                except KeyboardInterrupt:
                    print("\n\nStopping messaging...")
                    comm.disconnect()
                    
            print(f"\nStarting periodic messaging every {config['message_frequency']} seconds...")
            print("Press Ctrl+C to stop messaging and return to menu")
            
            messaging_thread = threading.Thread(target=messaging_loop, daemon=True)
            messaging_thread.start()
            
            # Wait for user interrupt
            try:
                messaging_thread.join()
            except KeyboardInterrupt:
                print("\n\nMessaging stopped by user.")
                comm.stop_messaging()  # Stop messaging but keep connection alive
        else:
            print("\n✗ Failed to connect to device")
            print("Try using Test Connection option first to diagnose issues.")
            
    except Exception as e:
        error_msg = f"Error starting messaging: {str(e)}"
        print(f"\n✗ {error_msg}")
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
                print(f"\n✓ Found {len(devices)} serial devices:")
                for i, device in enumerate(devices, 1):
                    print(f"  {i}. {device['name']}")
            else:
                print("\n✗ No serial devices found")
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
            print("\n✗ No device configured. Please pair a device first.")
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
                print("\\n✓ CONNECTION TEST SUCCESSFUL!")
                print("• USB/Serial connection established")
                print("• Device is responding")
                print("• Ready for messaging operations")
            else:
                print("\n✗ CONNECTION TEST FAILED!")
                print("• Could not establish connection")
                print("• Check device power and range")
                print("• Verify BLE address is correct")
                
        finally:
            # Restore logging level
            meshtastic_logger.setLevel(original_level)
            
    except Exception as e:
        print(f"\n✗ Test error: {e}")
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
                print(f"  {file}: {size} bytes ✓")
            else:
                print(f"  {file}: MISSING ✗")
                
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
        while True:
            display_menu()
            choice = input("\\nEnter your choice (1-6): ").strip()
            
            if choice == '1':
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

if __name__ == "__main__":
    main()