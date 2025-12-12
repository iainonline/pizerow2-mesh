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
from datetime import datetime
from typing import Optional, Dict, List
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

class MeshtasticTerminal:
    def __init__(self):
        self.interface = None
        self.connected = False
        self.telemetry_history = []
        self.nodes_data = {}
        self.stats = {
            'packets_rx': 0,
            'packets_tx': 0,
            'messages_seen': 0
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
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.auto_send_enabled = config.get('auto_send_enabled', False)
                    self.auto_send_interval = config.get('auto_send_interval', 60)
                    self.selected_nodes = config.get('selected_nodes', [])
                    print(f"✅ Loaded config: {len(self.selected_nodes)} nodes selected")
        except Exception as e:
            print(f"⚠️  Error loading config: {e}")
            
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
        except Exception as e:
            print(f"⚠️  Error saving config: {e}")
            
    def connect_device(self):
        """Connect to Meshtastic device"""
        try:
            print("📡 Connecting to device via USB...")
            self.interface = meshtastic.serial_interface.SerialInterface()
            
            # Subscribe to message events
            pub.subscribe(self.on_receive, "meshtastic.receive")
            pub.subscribe(self.on_connection, "meshtastic.connection.established")
            
            time.sleep(2)
            self.connected = True
            print("✅ Connected successfully!")
            
            # Get local node info
            if self.interface.myInfo:
                my_node = self.interface.myInfo.get('user', {})
                long_name = my_node.get('longName', 'Unknown')
                node_num = self.interface.myInfo.get('num')
                node_id = f"!{node_num:08x}" if node_num else 'N/A'
                print(f"📱 Local Node: {long_name} ({node_id})")
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            
    def on_connection(self, interface, topic=pub.AUTO_TOPIC):
        """Called when connection is established"""
        print("✅ Connection established")
        
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
            
            # Process telemetry
            if portnum == 'TELEMETRY_APP':
                self.process_telemetry(packet)
            elif portnum == 'TEXT_MESSAGE_APP':
                self.stats['messages_seen'] += 1
                
        except Exception as e:
            pass
            
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
        
        if self.telemetry_history:
            latest = self.telemetry_history[-1]
            
            # BME280 sensors
            temp = latest.get('temperature')
            if temp is not None:
                temp_f = (temp * 9/5) + 32
                lines.append(f"🌡️ {temp_f:.1f}°F")
                
            humidity = latest.get('humidity')
            if humidity is not None:
                lines.append(f"💧 {humidity:.1f}%")
                
            pressure = latest.get('pressure')
            if pressure is not None:
                lines.append(f"🔘 {pressure:.1f}hPa")
            
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
        
        return " | ".join(lines)
        
    def send_telemetry(self):
        """Send telemetry to selected nodes"""
        if not self.connected or not self.interface:
            print("❌ Not connected to device")
            return False
            
        if not self.selected_nodes:
            print("❌ No nodes selected")
            return False
        
        try:
            for node_id in self.selected_nodes:
                message = self.get_telemetry_message(dest_node_id=node_id)
                self.interface.sendText(message, destinationId=node_id, wantAck=True)
                self.stats['packets_tx'] += 1
            
            self.last_send_time = time.time()
            print(f"✅ Sent telemetry to {len(self.selected_nodes)} nodes")
            return True
        except Exception as e:
            print(f"❌ Error sending telemetry: {e}")
            return False
            
    def auto_send_worker(self):
        """Background worker for auto-send"""
        while True:
            if self.auto_send_enabled and self.connected:
                elapsed = time.time() - self.last_send_time
                if elapsed >= self.auto_send_interval:
                    self.send_telemetry()
            time.sleep(1)
            
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
        print(f"Packets RX: {self.stats['packets_rx']} | TX: {self.stats['packets_tx']}")
        print("=" * 60)
        print()
        
    def show_telemetry(self):
        """Display current telemetry"""
        self.clear_screen()
        self.print_header()
        
        print("📊 CURRENT TELEMETRY")
        print("-" * 60)
        
        if self.telemetry_history:
            latest = self.telemetry_history[-1]
            
            temp = latest.get('temperature')
            if temp is not None:
                temp_f = (temp * 9/5) + 32
                print(f"🌡️  Temperature: {temp_f:.1f}°F")
            
            humidity = latest.get('humidity')
            if humidity is not None:
                print(f"💧 Humidity: {humidity:.1f}%")
            
            pressure = latest.get('pressure')
            if pressure is not None:
                print(f"🌀 Pressure: {pressure:.1f} hPa")
            
            battery = latest.get('battery')
            if battery is not None:
                if battery == 101:
                    print("🔋 Battery: Powered")
                else:
                    print(f"🔋 Battery: {battery}%")
            
            voltage = latest.get('voltage')
            if voltage is not None:
                print(f"⚡ Voltage: {voltage:.2f}V")
            
            channel_util = latest.get('channel_util')
            if channel_util is not None:
                print(f"📻 Channel Util: {channel_util:.1f}%")
            
            air_util = latest.get('air_util')
            if air_util is not None:
                print(f"📶 Air Util TX: {air_util:.1f}%")
        else:
            print("No telemetry data available yet...")
        
        print()
        input("Press Enter to continue...")
        
    def show_nodes(self):
        """Display mesh nodes"""
        self.clear_screen()
        self.print_header()
        
        print("👥 MESH NODES")
        print("-" * 60)
        
        if self.interface and self.interface.nodes:
            for node in self.interface.nodes.values():
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
        else:
            print("No nodes available yet...")
        
        print()
        input("Press Enter to continue...")
        
    def select_nodes(self):
        """Select nodes for auto-send"""
        while True:
            self.clear_screen()
            self.print_header()
            
            print("📝 SELECT NODES FOR AUTO-SEND")
            print("-" * 60)
            
            if not self.interface or not self.interface.nodes:
                print("No nodes available yet...")
                input("\nPress Enter to continue...")
                return
            
            nodes_list = []
            idx = 1
            for node in self.interface.nodes.values():
                user = node.get('user', {})
                long_name = user.get('longName', 'Unknown')
                node_num = node.get('num')
                node_id = f"!{node_num:08x}" if node_num else 'N/A'
                
                selected = "✓" if node_id in self.selected_nodes else " "
                print(f"{idx}. [{selected}] {long_name} ({node_id})")
                nodes_list.append(node_id)
                idx += 1
            
            print()
            print("A. Select All")
            print("C. Clear All")
            print("S. Save and Return")
            print("Q. Cancel and Return")
            print()
            
            choice = input("Enter number to toggle, or letter: ").strip().upper()
            
            if choice == 'Q':
                return
            elif choice == 'S':
                self.save_config()
                print(f"✅ Saved {len(self.selected_nodes)} selected nodes")
                time.sleep(1)
                return
            elif choice == 'A':
                self.selected_nodes = nodes_list.copy()
            elif choice == 'C':
                self.selected_nodes = []
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(nodes_list):
                    node_id = nodes_list[idx]
                    if node_id in self.selected_nodes:
                        self.selected_nodes.remove(node_id)
                    else:
                        self.selected_nodes.append(node_id)
                        
    def configure_auto_send(self):
        """Configure auto-send settings"""
        while True:
            self.clear_screen()
            self.print_header()
            
            print("🚀 AUTO-SEND CONFIGURATION")
            print("-" * 60)
            print(f"Status: {'✅ ENABLED' if self.auto_send_enabled else '❌ DISABLED'}")
            print(f"Interval: {self.auto_send_interval} seconds")
            print(f"Selected Nodes: {len(self.selected_nodes)}")
            
            if self.auto_send_enabled:
                elapsed = time.time() - self.last_send_time
                remaining = max(0, self.auto_send_interval - elapsed)
                print(f"Next send in: {int(remaining)} seconds")
            
            print()
            print("1. Toggle Enable/Disable")
            print("2. Set Interval")
            print("3. Select Nodes")
            print("4. Test Send Now")
            print("5. Return to Main Menu")
            print()
            
            choice = input("Enter choice: ").strip()
            
            if choice == '1':
                self.auto_send_enabled = not self.auto_send_enabled
                self.save_config()
                print(f"Auto-send {'ENABLED' if self.auto_send_enabled else 'DISABLED'}")
                time.sleep(1)
            elif choice == '2':
                try:
                    interval = int(input("Enter interval in seconds (min 30): "))
                    if interval >= 30:
                        self.auto_send_interval = interval
                        self.save_config()
                        print(f"✅ Interval set to {interval} seconds")
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
                
    def manage_keys(self):
        """Manage encryption keys"""
        self.clear_screen()
        self.print_header()
        
        print("🔐 ENCRYPTION KEY MANAGEMENT")
        print("-" * 60)
        print()
        print("ℹ️  Direct Messages use PKC (Public Key Cryptography)")
        print("   Firmware 2.5.0+ automatically encrypts DMs")
        print("   No manual key management needed for person-to-person messages")
        print()
        print("For channel encryption, use the Meshtastic mobile app or CLI:")
        print("  meshtastic --set-channel --channel-name MyChannel --psk <base64-key>")
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
            print("2. View Mesh Nodes")
            print("3. Configure Auto-Send")
            print("4. Send Telemetry Now")
            print("5. Manage Encryption Keys")
            print("6. Exit")
            print()
            
            choice = input("Enter choice: ").strip()
            
            if choice == '1':
                self.show_telemetry()
            elif choice == '2':
                self.show_nodes()
            elif choice == '3':
                self.configure_auto_send()
            elif choice == '4':
                self.send_telemetry()
                time.sleep(2)
            elif choice == '5':
                self.manage_keys()
            elif choice == '6':
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
        else:
            print("⏸️  Auto-send: DISABLED")
        
        print()
        for i in range(10, 0, -1):
            print(f"Starting in {i} seconds... (Press Ctrl+C to enter menu)", end='\r')
            time.sleep(1)
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
        print("\n❌ Failed to connect. Please check your device and try again.")
        sys.exit(1)
    
    # If auto-started and auto-send is enabled, just run in background
    if auto_started and terminal.auto_send_enabled:
        print("\n✅ Running in auto-send mode...")
        print("Press Ctrl+C to enter menu")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nEntering menu...")
            time.sleep(1)
    
    # Show main menu
    terminal.main_menu()

if __name__ == "__main__":
    main()
