#!/usr/bin/env python3
"""
Meshtastic Terminal Monitor
A lightweight terminal-based monitoring and auto-send program for Raspberry Pi Zero 2 W
"""

import os
import sys
import time
import json
import threading
import logging
import signal
from datetime import datetime
from typing import Optional, Dict, List
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

class MeshtasticTerminal:
    def __init__(self):
        # Setup logging
        self.log_file = 'mesh_terminal.log'
        self.setup_logging()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.interface = None
        self.connected = False
        self.telemetry_history = []
        self.nodes_data = {}
        self.stats = {
            'packets_rx': 0,
            'packets_tx': 0,
            'messages_seen': 0,
            'nodes_discovered': 0
        }
        self.latest_snr = None
        self.latest_rssi = None
        
        # Auto-send configuration
        self.config_file = 'terminal_config.json'
        self.auto_send_enabled = False
        self.auto_send_interval = 60  # seconds
        self.selected_nodes = []
        self.last_send_time = 0
        
        # Load config
        self.load_config()
        
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C and termination signals gracefully"""
        print("\n\n🛑 Shutting down gracefully...")
        self.logger.info("Received shutdown signal, exiting gracefully")
        if self.interface:
            try:
                self.interface.close()
                self.logger.info("Closed interface connection")
            except Exception as e:
                self.logger.error(f"Error closing interface: {e}")
        print("✅ Goodbye!")
        sys.exit(0)
        
    def setup_logging(self):
        """Setup file and console logging"""
        # Create logger
        self.logger = logging.getLogger('MeshtasticTerminal')
        self.logger.setLevel(logging.DEBUG)
        
        # File handler - detailed logging
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # Add handler
        self.logger.addHandler(fh)
        self.logger.info("="*60)
        self.logger.info("Meshtastic Terminal Monitor Started")
        self.logger.info("="*60)
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.auto_send_enabled = config.get('auto_send_enabled', False)
                    self.auto_send_interval = config.get('auto_send_interval', 60)
                    self.selected_nodes = config.get('selected_nodes', [])
                    msg = f"Loaded config: {len(self.selected_nodes)} nodes selected, auto_send={self.auto_send_enabled}"
                    print(f"✅ {msg}")
                    self.logger.info(msg)
            else:
                self.logger.info("No config file found, using defaults")
        except Exception as e:
            msg = f"Error loading config: {e}"
            print(f"⚠️  {msg}")
            self.logger.error(msg)
            
    def save_config(self):
        """Save configuration to JSON file"""
        try:
            config = {
                'auto_send_enabled': self.auto_send_enabled,
                'auto_send_interval': self.auto_send_interval,
                'selected_nodes': self.selected_nodes
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.logger.info(f"Saved config: {len(self.selected_nodes)} nodes, interval={self.auto_send_interval}s")
        except Exception as e:
            msg = f"Error saving config: {e}"
            print(f"⚠️  {msg}")
            self.logger.error(msg)
    
    def clear_usb_port_lock(self):
        """Clear any stale locks on USB port before connecting"""
        try:
            import serial
            import glob
            # Find USB ports
            ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
            for port in ports:
                try:
                    # Open and immediately close to clear any stale locks
                    s = serial.Serial(port, timeout=1)
                    s.close()
                    self.logger.debug(f"Cleared lock on {port}")
                except:
                    pass  # Port might be in use or not accessible
        except Exception as e:
            self.logger.debug(f"Port lock clear attempt: {e}")
            
    def connect_device(self):
        """Connect to Meshtastic device with retry and Pi Zero 2 W error resilience"""
        retry_count = 0
        max_retries = 10
        retry_delay = 5
        
        while retry_count < max_retries:
            try:
                if retry_count > 0:
                    print(f"🔄 Retry {retry_count}/{max_retries} in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                
                print("📡 Connecting to device via USB...")
                
                # Clear any stale port locks before attempting connection
                self.clear_usb_port_lock()
                
                # Suppress meshtastic library's protobuf parsing errors for Pi Zero 2 W
                import logging as stdlib_logging
                meshtastic_logger = stdlib_logging.getLogger('meshtastic')
                meshtastic_logger.setLevel(stdlib_logging.CRITICAL)
                
                self.interface = meshtastic.serial_interface.SerialInterface()
                
                # Subscribe to message events
                pub.subscribe(self.on_receive, "meshtastic.receive")
                pub.subscribe(self.on_connection, "meshtastic.connection.established")
                
                # Pi Zero 2 W needs extra time to stabilize USB connection
                print("⏳ Waiting for device to stabilize...")
                time.sleep(5)
                
                self.connected = True
                print("✅ Connected successfully!")
                
                # Get local node info
                try:
                    if hasattr(self.interface, 'myInfo') and self.interface.myInfo:
                        my_node = self.interface.myInfo.get('user', {})
                        long_name = my_node.get('longName', 'Unknown')
                        node_num = self.interface.myInfo.get('num')
                        node_id = f"!{node_num:08x}" if node_num else 'N/A'
                        print(f"📱 Local Node: {long_name} ({node_id})")
                except Exception:
                    pass
                
                return  # Success, exit retry loop
                    
            except Exception as e:
                error_str = str(e)
                # Check if it's a protobuf parsing error - these are non-fatal on Pi Zero 2 W
                if 'protobuf' in error_str.lower() or 'ParseFromString' in error_str:
                    print(f"⚠️  Protobuf parsing errors detected (common on Pi Zero 2 W)")
                    print("⏳ Continuing - waiting for stable connection...")
                    time.sleep(10)
                    # Try to continue despite protobuf errors
                    if self.interface:
                        try:
                            pub.subscribe(self.on_receive, "meshtastic.receive")
                            pub.subscribe(self.on_connection, "meshtastic.connection.established")
                            self.connected = True
                            print("✅ Connection established - monitoring active")
                            return
                        except:
                            pass
                
                print(f"❌ Connection failed: {e}")
                retry_count += 1
                self.connected = False
        
        # If we get here, all retries failed
        print(f"\n❌ Failed to connect after {max_retries} attempts")
        print("Please check:")
        print("  - Device is plugged in via USB")
        print("  - Device is powered on")
        print("  - USB cable supports data transfer")
        print("  - User has permissions (try: sudo usermod -a -G dialout $USER)")
        time.sleep(5)
            
    def on_connection(self, interface, topic=pub.AUTO_TOPIC):
        """Called when connection is established"""
        self.logger.info("Connection established via pubsub")
        
    def on_node_updated(self, node, interface):
        """Called when a node is discovered or updated"""
        try:
            node_num = node.get('num')
            if node_num:
                node_id = f"!{node_num:08x}"
                user = node.get('user', {})
                long_name = user.get('longName', 'Unknown')
                
                # Check if this is a new node
                if node_id not in self.nodes_data:
                    self.stats['nodes_discovered'] += 1
                    self.logger.info(f"NEW NODE discovered: {long_name} ({node_id})")
                
                self.nodes_data[node_id] = {
                    'name': long_name,
                    'id': node_id,
                    'last_update': datetime.now().strftime('%H:%M:%S')
                }
        except Exception as e:
            self.logger.error(f"Error in on_node_updated: {e}")
        
    def on_receive(self, packet, interface):
        """Called when a packet is received"""
        try:
            from_id = packet.get('fromId', 'Unknown')
            decoded = packet.get('decoded', {})
            portnum = decoded.get('portnum', 'UNKNOWN')
            
            self.stats['packets_rx'] += 1
            
            # Get signal strength
            snr = packet.get('rxSnr')
            rssi = packet.get('rxRssi')
            
            if isinstance(snr, (int, float)):
                self.latest_snr = snr
            if isinstance(rssi, (int, float)):
                self.latest_rssi = rssi
            
            # Track signal strength per node
            if from_id and from_id != 'Unknown':
                if from_id not in self.nodes_data:
                    self.nodes_data[from_id] = {}
                if isinstance(snr, (int, float)):
                    self.nodes_data[from_id]['last_snr'] = snr
                if isinstance(rssi, (int, float)):
                    self.nodes_data[from_id]['last_rssi'] = rssi
            
            # Log packet details
            self.logger.debug(f"RX: {portnum} from {from_id} | SNR: {snr} | RSSI: {rssi}")
            
            # Process telemetry
            if portnum == 'TELEMETRY_APP':
                self.process_telemetry(packet)
            elif portnum == 'TEXT_MESSAGE_APP':
                self.stats['messages_seen'] += 1
                text = decoded.get('text', '')
                self.logger.info(f"TEXT_MSG from {from_id}: {text[:50]}")
                
        except Exception as e:
            self.logger.error(f"Error in on_receive: {e}")
            
    def process_telemetry(self, packet):
        """Process telemetry data"""
        try:
            decoded = packet.get('decoded', {})
            payload = decoded.get('telemetry', {})
            
            # Device metrics
            if 'deviceMetrics' in payload:
                dm = payload['deviceMetrics']
                telemetry_data = {
                    'time': time.time(),
                    'battery': dm.get('batteryLevel'),
                    'voltage': dm.get('voltage'),
                    'channel_util': dm.get('channelUtilization'),
                    'air_util': dm.get('airUtilTx')
                }
                
                if self.telemetry_history and (time.time() - self.telemetry_history[-1].get('time', 0)) < 5:
                    self.telemetry_history[-1].update(telemetry_data)
                else:
                    self.telemetry_history.append(telemetry_data)
            
            # Environment metrics
            if 'environmentMetrics' in payload:
                em = payload['environmentMetrics']
                env_data = {
                    'time': time.time(),
                    'temperature': em.get('temperature'),
                    'humidity': em.get('relativeHumidity'),
                    'pressure': em.get('barometricPressure')
                }
                
                if self.telemetry_history and (time.time() - self.telemetry_history[-1].get('time', 0)) < 5:
                    self.telemetry_history[-1].update(env_data)
                else:
                    self.telemetry_history.append(env_data)
                    
        except Exception as e:
            pass
            
    def get_telemetry_message(self, dest_node_id: Optional[str] = None) -> str:
        """Generate telemetry message"""
        lines = [f"⏰ {datetime.now().strftime('%H:%M:%S')}"]
        
        # Get hop count
        if dest_node_id and self.interface and self.interface.nodes:
            for node in self.interface.nodes.values():
                node_num = node.get('num')
                if node_num and f"!{node_num:08x}" == dest_node_id:
                    hops_away = node.get('hopsAway', 0)
                    if hops_away is not None and hops_away > 0:
                        lines.append(f"🔗 Hops: {hops_away}")
                    break
        
        has_sensor_data = False
        if self.telemetry_history:
            latest = self.telemetry_history[-1]
            
            # BME280 sensors
            temp = latest.get('temperature')
            if temp is not None:
                temp_f = (temp * 9/5) + 32
                lines.append(f"🌡️ {temp_f:.1f}°F")
                has_sensor_data = True
                
            humidity = latest.get('humidity')
            if humidity is not None:
                lines.append(f"💧 {humidity:.1f}%")
                has_sensor_data = True
                
            pressure = latest.get('pressure')
            if pressure is not None:
                lines.append(f"🔘 {pressure:.1f}hPa")
                has_sensor_data = True
            
            # Signal strength
            if self.latest_snr is not None:
                lines.append(f"📶 SNR: {self.latest_snr:.1f}dB")
            if self.latest_rssi is not None:
                lines.append(f"📡 RSSI: {self.latest_rssi}dBm")
            
            # Battery & power
            battery = latest.get('battery')
            if battery is not None:
                if battery == 101:
                    lines.append("🔋 PWR")
                else:
                    lines.append(f"🔋 {battery}%")
                    
            voltage = latest.get('voltage')
            if voltage is not None:
                lines.append(f"⚡ {voltage:.2f}V")
            
            # Network utilization
            channel_util = latest.get('channel_util')
            if channel_util is not None:
                lines.append(f"📻 CH:{channel_util:.1f}%")
                
            air_util = latest.get('air_util')
            if air_util is not None:
                lines.append(f"🌐 Air:{air_util:.1f}%")
        
        # Node count
        if self.interface and self.interface.nodes:
            lines.append(f"👥 {len(self.interface.nodes)}")
        
        # Prepend NoT if no sensor telemetry data
        if not has_sensor_data:
            lines.insert(0, "NoT")
        
        return " | ".join(lines)
        
    def send_telemetry(self):
        """Send telemetry to selected nodes"""
        if not self.connected or not self.interface:
            msg = "Not connected to device"
            print(f"❌ {msg}")
            self.logger.warning(f"Send failed: {msg}")
            return False
            
        if not self.selected_nodes:
            msg = "No nodes selected"
            print(f"❌ {msg}")
            self.logger.warning(f"Send failed: {msg}")
            return False
        
        try:
            sent_count = 0
            for node_id in self.selected_nodes:
                message = self.get_telemetry_message(dest_node_id=node_id)
                
                # Check if node is still online
                node_info = self.get_node_info(node_id)
                if node_info:
                    last_heard = node_info.get('lastHeard', 0)
                    if last_heard:
                        age = time.time() - last_heard
                        age_str = f"{int(age/60)} min ago" if age > 60 else f"{int(age)} sec ago"
                        self.logger.info(f"Sending to {node_id} (last seen {age_str})")
                
                self.interface.sendText(message, destinationId=node_id, wantAck=True)
                self.stats['packets_tx'] += 1
                sent_count += 1
                self.logger.info(f"TX to {node_id}: {message}")
            
            self.last_send_time = time.time()
            msg = f"Sent telemetry to {sent_count} nodes"
            print(f"✅ {msg}")
            self.logger.info(msg)
            self.logger.info("NOTE: Messages use PKC encryption (fw 2.5.0+). Key exchange happens automatically.")
            return True
        except Exception as e:
            msg = f"Error sending telemetry: {e}"
            print(f"❌ {msg}")
            self.logger.error(msg, exc_info=True)
            return False
            
    def get_node_info(self, node_id: str) -> Optional[Dict]:
        """Get node information by ID"""
        if not self.interface or not hasattr(self.interface, 'nodes'):
            return None
        for node in self.interface.nodes.values():
            node_num = node.get('num')
            if node_num and f"!{node_num:08x}" == node_id:
                return node
        return None
            
    def auto_send_worker(self):
        """Background worker for auto-send"""
        while True:
            if self.auto_send_enabled and self.connected:
                elapsed = time.time() - self.last_send_time
                
                if elapsed >= self.auto_send_interval:
                    self.send_telemetry()
            time.sleep(1)
    
    def display_auto_send_status(self):
        """Display status during auto-send mode"""
        self.clear_screen()
        self.print_header()
        
        print("🔄 AUTO-SEND MODE ACTIVE")
        print("=" * 60)
        
        # Show sensor data if available
        if self.telemetry_history:
            latest = self.telemetry_history[-1]
            temp = latest.get('temperature')
            humidity = latest.get('humidity')
            pressure = latest.get('pressure')
            
            if temp is not None or humidity is not None or pressure is not None:
                print("\n🌡️  LOCAL SENSOR DATA:")
                if temp is not None:
                    temp_f = (temp * 9/5) + 32
                    print(f"   Temperature: {temp_f:.1f}°F ({temp:.1f}°C)")
                if humidity is not None:
                    print(f"   Humidity: {humidity:.1f}%")
                if pressure is not None:
                    print(f"   Pressure: {pressure:.1f} hPa")
            else:
                print("\n⚠️  No BME280 sensor detected")
            
            # Device metrics
            battery = latest.get('battery')
            voltage = latest.get('voltage')
            if battery is not None or voltage is not None:
                print("\n🔋 DEVICE STATUS:")
                if battery is not None:
                    if battery == 101:
                        print("   Power: USB/Solar")
                    else:
                        print(f"   Battery: {battery}%")
                if voltage is not None:
                    print(f"   Voltage: {voltage:.2f}V")
        
        # Show target nodes
        if self.selected_nodes:
            print(f"\n📡 TARGET NODES ({len(self.selected_nodes)}):")
            print("-" * 60)
            
            for node_id in self.selected_nodes:
                node_info = self.get_node_info(node_id)
                if node_info:
                    name = node_info.get('user', {}).get('longName', 'Unknown')
                    last_heard = node_info.get('lastHeard', 0)
                    
                    # Calculate time since last heard
                    if last_heard:
                        age = time.time() - last_heard
                        if age < 60:
                            age_str = f"{int(age)}s ago"
                        elif age < 3600:
                            age_str = f"{int(age/60)}m ago"
                        else:
                            age_str = f"{int(age/3600)}h ago"
                    else:
                        age_str = "Never"
                    
                    # Get signal strength
                    snr = node_info.get('snr')
                    rssi = node_info.get('deviceMetrics', {}).get('airUtilTx', 0)  # Try device metrics
                    
                    # Display node info
                    print(f"\n  {name} ({node_id})")
                    print(f"  └─ Last heard: {age_str}")
                    
                    # Show signal if we have recent data
                    if node_id in self.nodes_data and 'last_snr' in self.nodes_data[node_id]:
                        snr = self.nodes_data[node_id].get('last_snr')
                        rssi = self.nodes_data[node_id].get('last_rssi')
                        if snr is not None:
                            print(f"  └─ SNR: {snr:.1f} dB")
                        if rssi is not None:
                            print(f"  └─ RSSI: {rssi} dBm")
                else:
                    print(f"\n  {node_id}")
                    print(f"  └─ Status: Not found in database")
        
        # Show countdown
        elapsed = time.time() - self.last_send_time
        remaining = max(0, int(self.auto_send_interval - elapsed))
        print(f"\n⏱️  Next send in: {remaining} seconds")
        print("\n💡 Press (M) for Menu | Ctrl+C to Exit")
        print("=" * 60)
            
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name != 'nt' else 'cls')
        
    def print_header(self):
        """Print application header"""
        print("=" * 60)
        print("    MESHTASTIC TERMINAL MONITOR")
        print("=" * 60)
        if self.connected:
            print("Status: ✅ Connected")
        else:
            print("Status: ❌ Disconnected")
        print(f"Packets RX: {self.stats['packets_rx']} | TX: {self.stats['packets_tx']} | Nodes: {self.stats['nodes_discovered']}")
        print(f"Log file: {self.log_file}")
        print("=" * 60)
        print()
        
    def show_telemetry(self):
        """Display current telemetry"""
        self.clear_screen()
        self.print_header()
        
        print("📊 CURRENT TELEMETRY (Local Device)")
        print("-" * 60)
        
        try:
            if self.telemetry_history:
                latest = self.telemetry_history[-1]
                
                # Environment sensors (BME280)
                temp = latest.get('temperature')
                humidity = latest.get('humidity')
                pressure = latest.get('pressure')
                
                if temp is not None or humidity is not None or pressure is not None:
                    print("\n🌡️  ENVIRONMENT SENSORS (BME280):")
                    if temp is not None:
                        temp_f = (temp * 9/5) + 32
                        print(f"   Temperature: {temp_f:.1f}°F ({temp:.1f}°C)")
                    if humidity is not None:
                        print(f"   Humidity: {humidity:.1f}%")
                    if pressure is not None:
                        print(f"   Pressure: {pressure:.1f} hPa")
                else:
                    print("\n⚠️  No BME280 sensor data available")
                    print("   (Device may not have BME280 sensor attached)")
                
                # Device metrics
                print("\n🔋 DEVICE METRICS:")
                battery = latest.get('battery')
                if battery is not None:
                    if battery == 101:
                        print("   Battery: Powered (USB/Solar)")
                    else:
                        print(f"   Battery: {battery}%")
                
                voltage = latest.get('voltage')
                if voltage is not None:
                    print(f"   Voltage: {voltage:.2f}V")
                
                channel_util = latest.get('channel_util')
                if channel_util is not None:
                    print(f"   Channel Utilization: {channel_util:.1f}%")
                
                air_util = latest.get('air_util')
                if air_util is not None:
                    print(f"   Air Utilization TX: {air_util:.1f}%")
            else:
                print("No telemetry data available yet...")
                print("Waiting for device to broadcast telemetry...")
        except Exception as e:
            print(f"Error displaying telemetry: {e}")
            self.logger.error(f"Error in show_telemetry: {e}", exc_info=True)
        
        print()
        try:
            raw_input = input("Press Enter to continue...")
        except (KeyboardInterrupt, EOFError):
            pass
        except Exception as e:
            print(f"Input error: {e}")
            time.sleep(1)
        
    def show_nodes(self):
        """Display mesh nodes"""
        try:
            self.clear_screen()
            self.print_header()
            
            print("👥 MESH NODES")
            print("-" * 60)
            
            try:
                if self.interface and hasattr(self.interface, 'nodes') and self.interface.nodes:
                    # Create a snapshot to avoid race conditions
                    nodes_snapshot = list(self.interface.nodes.values())
                    
                    for node in nodes_snapshot:
                        try:
                            user = node.get('user', {})
                            long_name = user.get('longName', 'Unknown')
                            node_num = node.get('num')
                            node_id = f"!{node_num:08x}" if node_num else 'N/A'
                            snr = node.get('snr', 'N/A')
                            hops = node.get('hopsAway', 0)
                            
                            snr_str = f"{snr:.1f}dB" if isinstance(snr, (int, float)) else 'N/A'
                            
                            last_heard = node.get('lastHeard')
                            if last_heard:
                                last_heard_str = datetime.fromtimestamp(last_heard).strftime('%H:%M:%S')
                            else:
                                last_heard_str = 'Never'
                            
                            selected = "✓" if node_id in self.selected_nodes else " "
                            print(f"[{selected}] {long_name} ({node_id})")
                            print(f"    SNR: {snr_str} | Hops: {hops} | Last: {last_heard_str}")
                            print()
                        except Exception as e:
                            continue
                else:
                    print("No nodes available yet...")
            except Exception as e:
                print(f"Error accessing nodes: {e}")
            
            print()
            try:
                raw_input = input("Press Enter to continue...")
            except (KeyboardInterrupt, EOFError):
                pass
            except Exception as e:
                print(f"Input error: {e}")
                time.sleep(1)
        except Exception as e:
            print(f"Critical error in show_nodes: {e}")
            time.sleep(2)
        
    def select_nodes(self):
        """Select nodes for auto-send"""
        self.logger.info("Entering select_nodes function")
        while True:
            try:
                self.clear_screen()
                self.print_header()
                
                print("📝 SELECT NODES FOR AUTO-SEND")
                print("-" * 60)
                
                try:
                    if not self.interface or not hasattr(self.interface, 'nodes') or not self.interface.nodes:
                        print("No nodes available yet...")
                        self.logger.warning("No nodes available in select_nodes")
                        try:
                            input("\nPress Enter to continue...")
                        except (KeyboardInterrupt, EOFError):
                            pass
                        return
                    
                    # Create snapshot to avoid race conditions
                    self.logger.debug(f"Creating snapshot of {len(self.interface.nodes)} nodes")
                    nodes_snapshot = list(self.interface.nodes.values())
                    nodes_list = []
                    idx = 1
                    
                    for node in nodes_snapshot:
                        try:
                            user = node.get('user', {})
                            long_name = user.get('longName', 'Unknown')
                            node_num = node.get('num')
                            
                            if node_num is None:
                                self.logger.warning(f"Node with no num: {user}")
                                continue
                                
                            node_id = f"!{node_num:08x}"
                            
                            selected = "✓" if node_id in self.selected_nodes else " "
                            print(f"{idx}. [{selected}] {long_name} ({node_id})")
                            nodes_list.append(node_id)
                            idx += 1
                        except Exception as e:
                            self.logger.error(f"Error processing node in select_nodes: {e}")
                            continue
                    
                    self.logger.debug(f"Displayed {len(nodes_list)} nodes")
                    
                    print()
                    print("A. Select All")
                    print("C. Clear All")
                    print("S. Save and Return")
                    print("Q. Cancel and Return")
                    print()
                    
                    try:
                        choice = input("Enter number to toggle, or letter: ").strip().upper()
                    except (KeyboardInterrupt, EOFError):
                        self.logger.info("User cancelled node selection")
                        return
                    except Exception as e:
                        self.logger.error(f"Input error in select_nodes: {e}")
                        return
                    
                    if choice == 'Q':
                        self.logger.info("User quit node selection")
                        return
                    elif choice == 'S':
                        self.save_config()
                        print(f"✅ Saved {len(self.selected_nodes)} selected nodes")
                        time.sleep(1)
                        return
                    elif choice == 'A':
                        self.selected_nodes = nodes_list.copy()
                        self.logger.info(f"Selected all {len(nodes_list)} nodes")
                    elif choice == 'C':
                        self.selected_nodes = []
                        self.logger.info("Cleared all selected nodes")
                    elif choice.isdigit():
                        idx = int(choice) - 1
                        if 0 <= idx < len(nodes_list):
                            node_id = nodes_list[idx]
                            if node_id in self.selected_nodes:
                                self.selected_nodes.remove(node_id)
                                self.logger.info(f"Deselected node {node_id}")
                            else:
                                self.selected_nodes.append(node_id)
                                self.logger.info(f"Selected node {node_id}")
                except Exception as e:
                    msg = f"Error in node selection inner loop: {e}"
                    print(f"❌ {msg}")
                    self.logger.error(msg, exc_info=True)
                    time.sleep(2)
                    return
            except Exception as e:
                msg = f"Critical error in select_nodes: {e}"
                print(f"❌ {msg}")
                self.logger.error(msg, exc_info=True)
                time.sleep(2)
                return
                        
    def configure_auto_send(self):
        """Configure auto-send settings"""
        while True:
            try:
                self.clear_screen()
                self.print_header()
                
                print("🚀 AUTO-SEND CONFIGURATION")
                print("-" * 60)
                print(f"Status: {'✅ ENABLED' if self.auto_send_enabled else '❌ DISABLED'}")
                print(f"Interval: {self.auto_send_interval} seconds")
                print(f"Selected Nodes: {len(self.selected_nodes)}")
                
                # Show selected nodes
                if self.selected_nodes:
                    print("\n📋 Sending to:")
                    for node_id in self.selected_nodes:
                        # Find node name
                        node_name = "Unknown"
                        if self.interface and hasattr(self.interface, 'nodes') and self.interface.nodes:
                            for node in self.interface.nodes.values():
                                node_num = node.get('num')
                                if node_num and f"!{node_num:08x}" == node_id:
                                    node_name = node.get('user', {}).get('longName', 'Unknown')
                                    break
                        print(f"  • {node_name} ({node_id})")
                
                if self.auto_send_enabled:
                    elapsed = time.time() - self.last_send_time
                    remaining = max(0, self.auto_send_interval - elapsed)
                    print(f"\n⏱️  Next send in: {int(remaining)} seconds")
                
                print()
                print("1. Toggle Enable/Disable")
                print("2. Set Interval")
                print("3. Select Nodes")
                print("4. Test Send Now")
                print("5. Return to Main Menu")
                print()
                
                choice = input("Enter choice: ").strip()
                self.logger.info(f"Auto-send menu choice: {choice}")
                
                if choice == '1':
                    self.auto_send_enabled = not self.auto_send_enabled
                    self.save_config()
                    msg = f"Auto-send {'ENABLED' if self.auto_send_enabled else 'DISABLED'}"
                    print(msg)
                    self.logger.info(msg)
                    time.sleep(1)
                elif choice == '2':
                    try:
                        interval = int(input("Enter interval in seconds (min 30): "))
                        if interval >= 30:
                            self.auto_send_interval = interval
                            self.save_config()
                            msg = f"Interval set to {interval} seconds"
                            print(f"✅ {msg}")
                            self.logger.info(msg)
                        else:
                            print("❌ Interval must be at least 30 seconds")
                        time.sleep(1)
                    except ValueError:
                        print("❌ Invalid number")
                        time.sleep(1)
                elif choice == '3':
                    self.select_nodes()
                elif choice == '4':
                    self.send_telemetry()
                    time.sleep(2)
                elif choice == '5':
                    return
            except Exception as e:
                self.logger.error(f"Error in configure_auto_send: {e}", exc_info=True)
                print(f"Error: {e}")
                time.sleep(2)
                
    def manage_keys(self):
        """Manage encryption keys"""
        self.clear_screen()
        self.print_header()
        
        print("🔐 ENCRYPTION & MESSAGE DELIVERY")
        print("-" * 60)
        print()
        print("✅ NO KEYS NEEDED - Direct Messages automatically use PKC!")
        print()
        print("📱 How It Works:")
        print("   • Each device has automatic public/private key pair")
        print("   • Messages encrypted with recipient's public key")
        print("   • Only recipient can decrypt with their private key")
        print("   • Key exchange happens automatically on first contact")
        print("   • Requires firmware 2.5.0 or newer on both devices")
        print()
        print("❌ Common Reasons Messages Aren't Received:")
        print()
        print("   1. FIRMWARE VERSION")
        print("      • Both devices need firmware 2.5.0+ for PKC")
        print("      • Check: Settings > Radio Configuration > Device")
        print()
        print("   2. RECIPIENT OFFLINE/SLEEPING")
        print("      • Check 'Last Heard' time in node selection")
        print("      • Device may be in deep sleep mode")
        print()
        print("   3. OUT OF RANGE")
        print("      • Recipient beyond radio range")
        print("      • No multi-hop route available")
        print("      • Check hop count (default max: 3)")
        print()
        print("   4. KEY EXCHANGE NOT YET COMPLETED")
        print("      • Happens automatically when nodes first communicate")
        print("      • May take a few messages to establish")
        print()
        print(f"   5. CHECK LOG FILE: {self.log_file}")
        print("      • See if messages are being sent successfully")
        print("      • Check for error messages")
        print()
        print("💡 TIP: Try sending a test message and check the log for details")
        print()
        input("Press Enter to continue...")
        
    def main_menu(self):
        """Display main menu"""
        # Start auto-send worker in background
        worker_thread = threading.Thread(target=self.auto_send_worker, daemon=True)
        worker_thread.start()
        
        while True:
            self.clear_screen()
            self.print_header()
            
            print("MAIN MENU")
            print("-" * 60)
            print("1. View Current Telemetry")
            print("2. Configure Auto-Send")
            print("3. Send Telemetry Now")
            print("4. Manage Encryption Keys")
            print("5. Exit")
            print()
            
            choice = input("Enter choice: ").strip()
            
            if choice == '1':
                self.show_telemetry()
            elif choice == '2':
                self.configure_auto_send()
            elif choice == '3':
                self.send_telemetry()
                time.sleep(2)
            elif choice == '4':
                self.manage_keys()
            elif choice == '5':
                print("\nExiting...")
                sys.exit(0)
                
    def auto_start_countdown(self):
        """10 second countdown to auto-start"""
        print("=" * 60)
        print("    MESHTASTIC TERMINAL MONITOR - AUTO START")
        print("=" * 60)
        print()
        print("Auto-starting with saved configuration...")
        
        if self.auto_send_enabled:
            print(f"✅ Auto-send: ENABLED ({self.auto_send_interval}s interval)")
            print(f"📝 Selected nodes: {len(self.selected_nodes)}")
            
            # Show which nodes will receive messages
            if self.selected_nodes and self.interface and hasattr(self.interface, 'nodes'):
                print("\n📋 Sending to:")
                for node_id in self.selected_nodes:
                    print(f"  • {node_id}")
        else:
            print("⏸️  Auto-send: DISABLED")
        
        print()
        import select
        for i in range(10, 0, -1):
            print(f"Starting in {i} seconds... (Press X to eXit autostart)", end='\r')
            # Check for 'x' key press with 1 second timeout
            if select.select([sys.stdin], [], [], 1)[0]:
                key = sys.stdin.read(1).strip().upper()
                if key == 'X':
                    raise KeyboardInterrupt  # Use existing cancel mechanism
            else:
                time.sleep(0)  # select already waited 1 second
        print()
        
def main():
    terminal = MeshtasticTerminal()
    
    # Try auto-start countdown
    try:
        terminal.auto_start_countdown()
        auto_started = True
    except KeyboardInterrupt:
        print("\n\nAuto-start cancelled. Entering menu...")
        auto_started = False
        time.sleep(1)
    
    # Connect to device
    terminal.connect_device()
    
    if not terminal.connected:
        print("\n⚠️  Running in disconnected mode (will keep trying in background)")
        # Start background reconnection thread
        def reconnect_worker():
            while not terminal.connected:
                time.sleep(30)
                print("\n🔄 Attempting reconnection...")
                terminal.connect_device()
        
        reconnect_thread = threading.Thread(target=reconnect_worker, daemon=True)
        reconnect_thread.start()
    
    # If auto-started and auto-send is enabled, run with M key to enter menu
    if auto_started and terminal.auto_send_enabled:
        terminal.logger.info("Running in auto-send background mode")
        
        # Start auto-send worker thread
        worker_thread = threading.Thread(target=terminal.auto_send_worker, daemon=True)
        worker_thread.start()
        terminal.logger.info("Auto-send worker thread started")
        
        # Send immediately on startup
        terminal.clear_screen()
        terminal.print_header()
        print("\n📤 Sending initial telemetry...")
        terminal.send_telemetry()
        time.sleep(2)
        
        # Display loop with status updates
        try:
            import select
            last_display = 0
            display_interval = 10  # Update every 10 seconds
            
            while True:
                # Update display every 10 seconds
                if time.time() - last_display >= display_interval:
                    terminal.display_auto_send_status()
                    last_display = time.time()
                
                # Check for 'M' key press with short timeout
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    key = sys.stdin.readline().strip().upper()
                    if key == 'M':
                        terminal.logger.info("User pressed M to enter menu")
                        print("\nEntering menu...")
                        time.sleep(1)
                        break
                
                time.sleep(0.5)
        except KeyboardInterrupt:
            # Ctrl+C will be handled by signal handler
            pass
    
    # Show main menu
    terminal.main_menu()

if __name__ == "__main__":
    main()
