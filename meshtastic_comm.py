import time
import threading
import logging
import psutil
from typing import Optional, Dict, Any, Callable, List
import meshtastic
import meshtastic.serial_interface
import serial.tools.list_ports
from pubsub import pub

# Sensor support removed - no external sensors connected

logger = logging.getLogger(__name__)

class MeshtasticComm:
    def __init__(self, logger_instance=None,
                 serial_port: Optional[str] = None, 
                 from_node: str = "Node1", 
                 to_node: str = "Node2", 
                 frequency: int = 60):
        """
        Initialize Meshtastic communication handler
        
        Args:
            serial_port: Serial port path (e.g., /dev/ttyUSB0)
            from_node: Name of the sender node
            to_node: Name of the recipient node  
            frequency: Message sending frequency in seconds
        """
        self.serial_port = serial_port
        self.from_node = from_node
        self.to_node = to_node
        self.frequency = frequency
        self.interface = None
        self.connected = False
        self.messaging_thread = None
        self.stop_messaging_flag = threading.Event()
        self.last_battery_level = None
        self.device_info = {}
        
        # Subscribe to Meshtastic events
        pub.subscribe(self._on_receive, "meshtastic.receive")
        pub.subscribe(self._on_connection, "meshtastic.connection.established")
        
    def scan_for_devices(self) -> List[Dict[str, str]]:
        """
        Scan for available Meshtastic devices via USB/Serial ports
        
        Returns:
            List of device dictionaries with 'name' and 'port' keys
        """
        logger.info("Scanning for USB/Serial devices...")
        
        try:
            ports = serial.tools.list_ports.comports()
            devices = []
            
            for port in ports:
                # Look for common Heltec/ESP32 USB identifiers
                if any(keyword in (port.description or '').lower() for keyword in 
                      ['cp210x', 'ch340', 'ch341', 'ftdi', 'usb serial', 'esp32', 'heltec']):
                    device_info = {
                        'name': f"{port.description or 'USB Serial'} ({port.device})",
                        'port': port.device
                    }
                    devices.append(device_info)
                    logger.debug(f"Found device: {device_info['name']}")
            
            # If no specific devices found, show all serial ports
            if not devices:
                for port in ports:
                    device_info = {
                        'name': f"{port.description or 'Serial Port'} ({port.device})",
                        'port': port.device
                    }
                    devices.append(device_info)
                    logger.debug(f"Found port: {device_info['name']}")
            
            logger.info(f"Found {len(devices)} serial device(s)")
            return devices
            
        except Exception as e:
            logger.error(f"Error scanning for devices: {e}")
            return []
        
    def test_connection(self, serial_port: Optional[str] = None) -> bool:
        """
        Test USB/Serial connection without waiting for full configuration
        
        Args:
            serial_port: Optional serial port to test (uses instance port if None)
            
        Returns:
            bool: True if basic USB connection works, False otherwise
        """
        import logging as test_logging
        
        try:
            test_port = serial_port or self.serial_port
            logger.debug(f"Testing USB connection to: {test_port}")
            
            # Temporarily suppress meshtastic logging to reduce noise
            meshtastic_logger = test_logging.getLogger('meshtastic')
            original_level = meshtastic_logger.level
            meshtastic_logger.setLevel(test_logging.ERROR)
            
            # Create a simple Serial interface for testing
            try:
                test_interface = meshtastic.serial_interface.SerialInterface(
                    devPath=test_port,
                    debugOut=None,
                    noProto=True,  # Skip protocol initialization for speed
                    noNodes=True   # Skip node discovery for speed
                )
                
                # If we get here, USB connection is working
                logger.debug("USB connection test successful")
                
                # Clean up test interface
                if test_interface:
                    try:
                        test_interface.close()
                    except:
                        pass
                        
                return True
                
            except Exception as e:
                logger.error(f"USB connection test failed: {e}")
                return False
                
            finally:
                # Restore original logging level
                meshtastic_logger.setLevel(original_level)
            
        except KeyboardInterrupt:
            logger.info("Connection test interrupted by user")
            return False
        except Exception as e:
            logger.error(f"USB connection test setup failed: {e}")
            return False

    def connect(self, serial_port: Optional[str] = None, 
                from_node: Optional[str] = None, 
                to_node: Optional[str] = None,
                to_node_id: Optional[str] = None) -> bool:
        """
        Connect to Meshtastic device via USB/Serial
        
        Args:
            serial_port: Serial port path (e.g., /dev/ttyUSB0)
            from_node: Source node name/ID
            to_node: Destination node name/ID
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Store connection parameters
            if serial_port:
                self.serial_port = serial_port
            if from_node:
                self.from_node = from_node
            if to_node:
                self.to_node = to_node
            if to_node_id:
                self.to_node_id = to_node_id
            
            if not self.serial_port:
                logger.error("No serial port specified")
                return False
            
            logger.info(f"Connecting to Meshtastic device at {self.serial_port}...")
            
            # Check if port is available before attempting connection
            if not self._is_port_available(self.serial_port):
                logger.error(f"Port {self.serial_port} is not available or already in use")
                return False
            
            # Close existing connection if any
            if self.interface:
                try:
                    self.interface.close()
                except:
                    pass
                self.interface = None
                # Give the port time to be released
                import time
                time.sleep(1)
            
            # Create Serial interface
            self.interface = meshtastic.serial_interface.SerialInterface(
                devPath=self.serial_port,
                debugOut=None
            )
            
            if self.interface:
                self.connected = True
                logger.info(f"Successfully connected to {self.serial_port}")
                return True
            else:
                logger.error("Failed to create Serial interface")
                return False
                
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the Meshtastic device"""
        try:
            self.stop_messaging()
            
            if self.interface:
                logger.info("Disconnecting from Meshtastic device...")
                self.interface.close()
                self.interface = None
                self.connected = False
                # Give extra time for port cleanup
                import time
                time.sleep(1)
                logger.info("Disconnected successfully")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            self.connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to device"""
        connected = self.connected and self.interface is not None
        logger.debug(f"Connection check: connected={self.connected}, interface_exists={self.interface is not None}, result={connected}")
        return connected
    
    def _update_device_info(self):
        """Update device information from the connected device"""
        try:
            if self.interface and hasattr(self.interface, 'myInfo'):
                self.device_info = {
                    'node_num': getattr(self.interface.myInfo, 'my_node_num', None),
                    'hw_model': None,
                    'firmware_version': None
                }
                
                # Get hardware model if available
                if hasattr(self.interface, 'nodes') and self.interface.nodes:
                    for node in self.interface.nodes.values():
                        if node.get('num') == self.device_info['node_num']:
                            if 'user' in node and 'hwModel' in node['user']:
                                self.device_info['hw_model'] = node['user']['hwModel']
                            break
                
                logger.info(f"Device info updated: {self.device_info}")
        except Exception as e:
            logger.error(f"Error updating device info: {e}")
    
    def get_battery_level(self) -> Optional[float]:
        """
        Get the current battery level of the device
        
        Returns:
            Optional[float]: Battery level percentage, None if unavailable
        """
        try:
            if not self.is_connected():
                return None
            
            # Try to get battery level from device telemetry
            if hasattr(self.interface, 'nodes') and self.interface.nodes:
                my_node_num = getattr(self.interface.myInfo, 'my_node_num', None)
                if my_node_num and my_node_num in self.interface.nodesByNum:
                    node = self.interface.nodesByNum[my_node_num]
                    if 'deviceMetrics' in node:
                        metrics = node['deviceMetrics']
                        if 'batteryLevel' in metrics:
                            self.last_battery_level = metrics['batteryLevel']
                            return self.last_battery_level
            
            # Fallback: use system battery info (for Pi with UPS)
            battery = psutil.sensors_battery()
            if battery:
                self.last_battery_level = battery.percent
                return self.last_battery_level
            
            return self.last_battery_level
            
        except Exception as e:
            logger.error(f"Error getting battery level: {e}")
            return self.last_battery_level
    
    def get_device_telemetry(self) -> Dict[str, Any]:
        """
        Get comprehensive device telemetry data from Heltec V3
        
        Returns:
            Dict containing various telemetry metrics
        """
        telemetry = {
            'battery_level': None,
            'voltage': None,
            'channel_utilization': None,
            'air_util_tx': None,
            'uptime_seconds': None,
            'memory_free': None,
            'signal_strength': None,
            'snr': None,
            'rssi': None,
            'hw_model': None,
            'firmware_version': None,
            'region': None,
            'modem_preset': None
        }
        
        try:
            if not self.is_connected():
                return telemetry
            
            # Get device metrics from the local node
            if hasattr(self.interface, 'nodes') and self.interface.nodes:
                my_node_num = getattr(self.interface.myInfo, 'my_node_num', None)
                if my_node_num and my_node_num in self.interface.nodesByNum:
                    node = self.interface.nodesByNum[my_node_num]
                    
                    # Device metrics (battery, voltage, etc.)
                    if 'deviceMetrics' in node:
                        metrics = node['deviceMetrics']
                        telemetry['battery_level'] = metrics.get('batteryLevel')
                        telemetry['voltage'] = metrics.get('voltage')
                        telemetry['channel_utilization'] = metrics.get('channelUtilization')
                        telemetry['air_util_tx'] = metrics.get('airUtilTx')
                        telemetry['uptime_seconds'] = metrics.get('uptimeSeconds')
                    
                    # User info (hardware model, etc.)
                    if 'user' in node:
                        user_info = node['user']
                        telemetry['hw_model'] = user_info.get('hwModel', 'Unknown')
                        
                    # Position info might include signal data
                    if 'position' in node:
                        pos_info = node['position']
                        telemetry['signal_strength'] = pos_info.get('rxSnr')
                        telemetry['rssi'] = pos_info.get('rxRssi')
            
            # Get radio configuration
            if hasattr(self.interface, 'radioConfig'):
                radio_config = self.interface.radioConfig
                if hasattr(radio_config, 'preferences'):
                    prefs = radio_config.preferences
                    telemetry['region'] = getattr(prefs, 'region', 'Unknown')
                    telemetry['modem_preset'] = getattr(prefs, 'modemPreset', 'Unknown')
                    
            # Get firmware version from interface info
            if hasattr(self.interface, 'myInfo'):
                my_info = self.interface.myInfo
                if hasattr(my_info, 'firmware_version'):
                    telemetry['firmware_version'] = my_info.firmware_version
                    
        except Exception as e:
            logger.error(f"Error getting device telemetry: {e}")
            
        return telemetry
    
    def get_interesting_data(self) -> str:
        """
        Generate an interesting data string with various Heltec V3 metrics
        
        Returns:
            Formatted string with interesting device data
        """
        try:
            telemetry = self.get_device_telemetry()
            dht_data = self.read_dht22_sensor()
            
            data_parts = []
            
            # Battery and power
            if telemetry['battery_level'] is not None:
                data_parts.append(f"🔋{telemetry['battery_level']:.1f}%")
            if telemetry['voltage'] is not None:
                data_parts.append(f"⚡{telemetry['voltage']:.2f}V")
                
            # Environmental sensors not connected - skipping
                
            # Radio metrics
            if telemetry['channel_utilization'] is not None:
                data_parts.append(f"📻{telemetry['channel_utilization']:.1f}%")
            if telemetry['air_util_tx'] is not None:
                data_parts.append(f"📡{telemetry['air_util_tx']:.1f}%")
                
            # Signal strength
            if telemetry['rssi'] is not None:
                data_parts.append(f"📶{telemetry['rssi']}dBm")
            if telemetry['snr'] is not None:
                data_parts.append(f"🎯{telemetry['snr']:.1f}dB")
                
            # Uptime (converted to human readable)
            if telemetry['uptime_seconds'] is not None:
                uptime_hours = telemetry['uptime_seconds'] / 3600
                if uptime_hours < 24:
                    data_parts.append(f"⏱️{uptime_hours:.1f}h")
                else:
                    uptime_days = uptime_hours / 24
                    data_parts.append(f"⏱️{uptime_days:.1f}d")
                    
            # Hardware info (occasionally)
            import random
            if random.randint(1, 10) == 1:  # 10% chance to include hardware info
                if telemetry['hw_model']:
                    data_parts.append(f"💻{telemetry['hw_model']}")
                if telemetry['region']:
                    data_parts.append(f"🌍{telemetry['region']}")
                    
            return " | " + " ".join(data_parts) if data_parts else ""
            
        except Exception as e:
            logger.error(f"Error generating interesting data: {e}")
            return ""
    
    def send_message(self, message: str, include_battery: bool = True, include_sensors: bool = True, private: bool = True, include_telemetry: bool = False) -> bool:
        """
        Send a message via the Meshtastic device
        
        Args:
            message: Message text to send
            include_battery: Whether to include battery level in message
            include_sensors: Whether to include DHT22 sensor data in message
            private: If True, send as private message to to_node; if False, broadcast publicly
            include_telemetry: Whether to include comprehensive device telemetry
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        logger.debug(f"Attempting to send message: '{message}' (include_battery={include_battery})")
        try:
            if not self.is_connected():
                logger.warning("Not connected to device, attempting to reconnect...")
                # Try to reconnect using existing settings
                if self.serial_port:
                    success = self.connect(self.serial_port, self.from_node, self.to_node, self.frequency)
                    if not success:
                        logger.error("Cannot send message: reconnection failed")
                        return False
                    logger.info("Reconnected successfully")
                else:
                    logger.error("Cannot send message: no device port configured")
                    return False
            
            logger.debug(f"Interface status: {self.interface is not None}")
            
            # Prepare message with battery info if requested
            if private:
                # For private messages, don't include routing info in the message text
                full_message = message
            else:
                # For public messages, include routing info
                full_message = f"[{self.from_node}→{self.to_node}] {message}"
            
            # Add sensor data to message
            if include_telemetry:
                # Use comprehensive telemetry data
                interesting_data = self.get_interesting_data()
                if interesting_data:
                    full_message += interesting_data
            else:
                # Use basic sensor data (backwards compatibility)
                sensor_data = []
                if include_battery:
                    battery_level = self.get_battery_level()
                    if battery_level is not None:
                        sensor_data.append(f"Battery: {battery_level:.1f}%")
                        
                if include_sensors:
                    # No external sensors connected
                    pass
                        
                if sensor_data:
                    full_message += f" | {' | '.join(sensor_data)}"
            
            # Send the message
            if private and self.to_node:
                # Send private message to specific node
                logger.debug(f"Sending private message to {self.to_node}: '{full_message}'")
                
                # Use configured node ID if available, otherwise try to discover
                destination_id = getattr(self, 'to_node_id', None)
                if not destination_id:
                    destination_id = self._get_node_id_by_name(self.to_node)
                    
                if destination_id:
                    # Convert node ID format for Meshtastic library
                    original_id = destination_id
                    if isinstance(destination_id, str):
                        if destination_id.startswith('!'):
                            # Convert hex string to integer (remove the '!' prefix)
                            hex_id = destination_id[1:]  # Remove '!' prefix
                            try:
                                destination_id = int(hex_id, 16)
                                logger.debug(f"Converted node ID from !{hex_id} to decimal {destination_id}")
                            except ValueError as e:
                                logger.error(f"Invalid hex node ID format {original_id}: {e}")
                                destination_id = None
                        elif destination_id.isdigit():
                            # Already a decimal string, convert to int
                            destination_id = int(destination_id)
                            logger.debug(f"Using decimal node number: {destination_id}")
                        else:
                            # Try as hex without prefix
                            try:
                                destination_id = int(destination_id, 16)
                                logger.debug(f"Converted hex string {original_id} to decimal {destination_id}")
                            except ValueError as e:
                                logger.error(f"Invalid node ID format {original_id}: {e}")
                                destination_id = None
                    
                    if destination_id:
                        self.interface.sendText(full_message, destinationId=destination_id)
                        logger.info(f"Private message sent to {self.to_node} (ID: {destination_id}): {full_message}")
                else:
                    # Fallback to broadcast if can't find specific node
                    logger.warning(f"Could not find node ID for {self.to_node}, sending as broadcast")
                    self.interface.sendText(full_message)
                    logger.info(f"Broadcast message sent: {full_message}")
            else:
                # Send public broadcast message
                logger.debug(f"Sending broadcast message: '{full_message}'")
                self.interface.sendText(full_message)
                logger.info(f"Broadcast message sent: {full_message}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            logger.debug(f"Message send failure - interface: {self.interface}, connected: {self.connected}")
            return False
    
    def _get_node_id_by_name(self, node_name: str) -> Optional[str]:
        """
        Get node ID by node name from the mesh network
        
        Args:
            node_name: The display name of the node to find
            
        Returns:
            Node ID string if found, None otherwise
        """
        try:
            if not self.interface or not hasattr(self.interface, 'nodes'):
                return None
                
            # Search through connected nodes for matching name
            for node_id, node_info in self.interface.nodes.items():
                if hasattr(node_info, 'user') and node_info.user:
                    # Check both longName and shortName
                    if (hasattr(node_info.user, 'longName') and node_info.user.longName == node_name) or \
                       (hasattr(node_info.user, 'shortName') and node_info.user.shortName == node_name):
                        logger.debug(f"Found node {node_name} with ID {node_id}")
                        return node_id
                        
            logger.debug(f"Node {node_name} not found in network")
            return None
            
        except Exception as e:
            logger.error(f"Error finding node ID for {node_name}: {e}")
            return None
    
    def _is_port_available(self, port_path: str) -> bool:
        """
        Check if a serial port is available for use
        
        Args:
            port_path: Path to the serial port (e.g., /dev/ttyUSB0)
            
        Returns:
            bool: True if port is available, False if in use or inaccessible
        """
        try:
            import serial
            # Try to open the port briefly to check availability
            with serial.Serial(port_path, timeout=1) as test_port:
                logger.debug(f"Port {port_path} is available")
                return True
        except serial.SerialException as e:
            if "could not open port" in str(e).lower() or "resource temporarily unavailable" in str(e).lower():
                logger.warning(f"Port {port_path} is already in use: {e}")
                return False
            else:
                logger.error(f"Error checking port {port_path}: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error checking port {port_path}: {e}")
            return False
    
    def read_dht22_sensor(self, pin: int = 4) -> Dict[str, Optional[float]]:
        """
        DHT22 sensor not connected - returns zero values
        
        Returns:
            Dictionary with 'temperature' and 'humidity' keys set to 0.0
        """
        # No DHT22 sensor connected, return zero values
        result = {'temperature': 0.0, 'humidity': 0.0}
        logger.debug("No DHT22 sensor connected - returning zero values")
        return result
    
    def start_messaging(self):
        """Start periodic messaging in a background thread"""
        if self.messaging_thread and self.messaging_thread.is_alive():
            logger.warning("Messaging thread is already running")
            return
        
        self.stop_messaging_flag.clear()
        self.messaging_thread = threading.Thread(
            target=self._messaging_loop,
            name="MeshtasticMessaging",
            daemon=True
        )
        self.messaging_thread.start()
        logger.info("Started periodic messaging")
    
    def stop_messaging(self):
        """Stop periodic messaging"""
        if self.messaging_thread and self.messaging_thread.is_alive():
            self.stop_messaging_flag.set()
            self.messaging_thread.join(timeout=5)
            logger.info("Stopped periodic messaging")
    
    def _messaging_loop(self):
        """Background loop for periodic messaging"""
        logger.info(f"Starting messaging loop with frequency {self.frequency}s")
        message_count = 0
        
        while not self.stop_messaging_flag.is_set():
            try:
                logger.debug(f"Messaging loop iteration {message_count + 1}")
                if self.is_connected():
                    message_count += 1
                    message = f"Auto message #{message_count} from {self.from_node}"
                    logger.debug(f"Preparing to send periodic message: {message}")
                    
                    success = self.send_message(message)
                    if success:
                        logger.info(f"Periodic message #{message_count} sent successfully")
                    else:
                        logger.error(f"Failed to send periodic message #{message_count}")
                else:
                    logger.warning("Cannot send periodic message: not connected")
                    logger.debug(f"Connection status details: interface={self.interface}, connected={self.connected}")
                
                # Wait for the specified frequency or until stop signal
                logger.debug(f"Waiting {self.frequency} seconds until next message")
                if self.stop_messaging_flag.wait(timeout=self.frequency):
                    logger.info("Stop signal received, exiting messaging loop")
                    break  # Stop signal received
                    
            except Exception as e:
                logger.error(f"Error in messaging loop: {e}", exc_info=True)
                # Wait a bit before retrying
                logger.debug("Waiting 10 seconds before retry due to error")
                if self.stop_messaging_flag.wait(timeout=10):
                    break
        
        logger.info("Messaging loop ended")
    
    def set_frequency(self, frequency: int):
        """
        Set the messaging frequency
        
        Args:
            frequency: New frequency in seconds
        """
        self.frequency = frequency
        logger.info(f"Messaging frequency updated to {frequency} seconds")
    
    def set_node_names(self, from_node: str, to_node: str):
        """
        Set the node names for messaging
        
        Args:
            from_node: Name of the sender node
            to_node: Name of the recipient node
        """
        self.from_node = from_node
        self.to_node = to_node
        logger.info(f"Node names updated: {from_node} -> {to_node}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get detailed connection status
        
        Returns:
            Dict containing connection status information
        """
        status = {
            'connected': self.connected,
            'ble_address': self.ble_address,
            'messaging_active': self.messaging_thread and self.messaging_thread.is_alive(),
            'frequency': self.frequency,
            'from_node': self.from_node,
            'to_node': self.to_node,
            'last_battery_level': self.last_battery_level
        }
        return status
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        Get device information
        
        Returns:
            Dict containing device information
        """
        return self.device_info.copy()
    
    def _on_receive(self, packet, interface):
        """Handle received packets"""
        try:
            logger.info(f"Received packet: {packet}")
            # Add any custom packet handling here
        except Exception as e:
            logger.error(f"Error handling received packet: {e}")
    
    def _on_connection(self, interface, topic=pub.AUTO_TOPIC):
        """Handle connection events"""
        try:
            logger.info("Meshtastic connection established")
            self._update_device_info()
        except Exception as e:
            logger.error(f"Error handling connection event: {e}")
    
    @staticmethod
    def scan_devices():
        """
        Scan for available Meshtastic BLE devices
        
        Returns:
            List of available BLE devices
        """
        try:
            logger.info("Scanning for BLE devices...")
            devices = meshtastic.ble_interface.BLEInterface.scan()
            logger.info(f"Found {len(devices)} BLE devices")
            return devices
        except Exception as e:
            logger.error(f"Error scanning for BLE devices: {e}")
            return []