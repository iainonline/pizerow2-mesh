#!/usr/bin/env python3
"""
Real-time Meshtastic Monitor Dashboard
Displays telemetry, nodes, messages, and network statistics in a GUI
Connects to Heltec V3 via USB (read-only, no configuration changes)
"""

import sys
import time
import json
import os
from datetime import datetime
from collections import deque
from typing import Optional, Dict, Any, List
import threading

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
except ImportError:
    print("Error: tkinter not found. Install with: sudo apt-get install python3-tk")
    sys.exit(1)

try:
    import meshtastic
    import meshtastic.serial_interface
    from meshtastic.protobuf import mesh_pb2, portnums_pb2, telemetry_pb2
    from pubsub import pub
except ImportError as e:
    print(f"Error: Missing required packages. Run: pip install meshtastic pubsub")
    sys.exit(1)


class MeshtasticMonitor:
    """Real-time GUI monitor for Meshtastic devices"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Meshtastic Monitor - Real-Time Dashboard")
        self.root.geometry("1200x800")
        self.root.configure(bg='#2b2b2b')
        
        # Configuration file
        self.config_file = os.path.join(os.path.dirname(__file__), 'monitor_config.json')
        
        # Data storage
        self.interface: Optional[Any] = None
        self.connected = False
        self.nodes_data: Dict[str, Dict] = {}
        self.messages = deque(maxlen=100)
        self.telemetry_history = deque(maxlen=50)
        self.stats = {
            'packets_rx': 0,
            'packets_tx': 0,
            'messages_seen': 0
        }
        
        # Auto-send configuration
        self.auto_send_enabled = False
        self.auto_send_interval = 300  # seconds (5 minutes default)
        self.selected_nodes: List[str] = []
        self.last_auto_send = 0
        
        # Signal strength tracking (for telemetry messages)
        self.latest_snr: Optional[float] = None
        self.latest_rssi: Optional[int] = None
        
        # Load configuration
        self.load_config()
        
        # Setup GUI
        self.setup_gui()
        
        # Subscribe to Meshtastic events
        pub.subscribe(self.on_receive, "meshtastic.receive")
        pub.subscribe(self.on_connection, "meshtastic.connection.established")
        pub.subscribe(self.on_node_updated, "meshtastic.node.updated")
        
        # Start connection in separate thread
        self.connection_thread = threading.Thread(target=self.connect_to_device, daemon=True)
        self.connection_thread.start()
        
        # Start UI update loop
        self.update_ui()
        
        # Start auto-send check loop
        self.check_auto_send()
        
    def setup_gui(self):
        """Create the GUI layout"""
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#2b2b2b', foreground='white', font=('Arial', 10))
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground='#4CAF50')
        style.configure('Status.TLabel', font=('Arial', 11), foreground='#FFC107')
        style.configure('TFrame', background='#2b2b2b')
        style.configure('Card.TFrame', background='#363636', relief='raised')
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # === TOP SECTION: Status and Device Info ===
        top_frame = ttk.Frame(main_frame, style='Card.TFrame', padding="10")
        top_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(top_frame, text="🔗 Connection Status:", style='Header.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.status_label = ttk.Label(top_frame, text="Connecting...", style='Status.TLabel')
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        self.device_info_label = ttk.Label(top_frame, text="Device: N/A", style='TLabel')
        self.device_info_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        # === LEFT COLUMN: Telemetry ===
        telemetry_frame = ttk.LabelFrame(main_frame, text=" 📊 Device Telemetry ", padding="10")
        telemetry_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        telemetry_frame.configure(relief='ridge', borderwidth=2)
        
        self.battery_label = ttk.Label(telemetry_frame, text="🔋 Battery: N/A", style='TLabel')
        self.battery_label.pack(anchor=tk.W, pady=2)
        
        self.voltage_label = ttk.Label(telemetry_frame, text="⚡ Voltage: N/A", style='TLabel')
        self.voltage_label.pack(anchor=tk.W, pady=2)
        
        self.channel_util_label = ttk.Label(telemetry_frame, text="📡 Channel Util: N/A", style='TLabel')
        self.channel_util_label.pack(anchor=tk.W, pady=2)
        
        self.air_util_label = ttk.Label(telemetry_frame, text="📶 Air Util TX: N/A", style='TLabel')
        self.air_util_label.pack(anchor=tk.W, pady=2)
        
        self.uptime_label = ttk.Label(telemetry_frame, text="⏱️  Uptime: N/A", style='TLabel')
        self.uptime_label.pack(anchor=tk.W, pady=2)
        
        ttk.Separator(telemetry_frame, orient='horizontal').pack(fill='x', pady=10)
        
        self.temp_label = ttk.Label(telemetry_frame, text="🌡️  Temperature: N/A", style='TLabel')
        self.temp_label.pack(anchor=tk.W, pady=2)
        
        self.humidity_label = ttk.Label(telemetry_frame, text="💧 Humidity: N/A", style='TLabel')
        self.humidity_label.pack(anchor=tk.W, pady=2)
        
        self.pressure_label = ttk.Label(telemetry_frame, text="🌀 Pressure: N/A", style='TLabel')
        self.pressure_label.pack(anchor=tk.W, pady=2)
        
        # === MIDDLE COLUMN: Nodes List ===
        nodes_frame = ttk.LabelFrame(main_frame, text=" 🌐 Mesh Nodes ", padding="10")
        nodes_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        nodes_frame.configure(relief='ridge', borderwidth=2)
        
        # Nodes treeview
        columns = ('Name', 'ID', 'SNR', 'Last Heard')
        self.nodes_tree = ttk.Treeview(nodes_frame, columns=columns, show='headings', height=15)
        self.nodes_tree.heading('Name', text='Name')
        self.nodes_tree.heading('ID', text='Node ID')
        self.nodes_tree.heading('SNR', text='SNR (dB)')
        self.nodes_tree.heading('Last Heard', text='Last Heard')
        
        self.nodes_tree.column('Name', width=150)
        self.nodes_tree.column('ID', width=100)
        self.nodes_tree.column('SNR', width=80)
        self.nodes_tree.column('Last Heard', width=150)
        
        scrollbar = ttk.Scrollbar(nodes_frame, orient='vertical', command=self.nodes_tree.yview)
        self.nodes_tree.configure(yscrollcommand=scrollbar.set)
        
        self.nodes_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # === RIGHT COLUMN: Network Stats & Auto-Send ===
        right_column = ttk.Frame(main_frame)
        right_column.grid(row=1, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        # Network Stats
        stats_frame = ttk.LabelFrame(right_column, text=" 📈 Network Statistics ", padding="10")
        stats_frame.pack(fill='x', pady=(0, 10))
        stats_frame.configure(relief='ridge', borderwidth=2)
        
        self.nodes_online_label = ttk.Label(stats_frame, text="👥 Nodes Online: 0", style='TLabel')
        self.nodes_online_label.pack(anchor=tk.W, pady=2)
        
        self.nodes_total_label = ttk.Label(stats_frame, text="📍 Total Nodes: 0", style='TLabel')
        self.nodes_total_label.pack(anchor=tk.W, pady=2)
        
        self.packets_rx_label = ttk.Label(stats_frame, text="📥 Packets RX: 0", style='TLabel')
        self.packets_rx_label.pack(anchor=tk.W, pady=2)
        
        self.packets_tx_label = ttk.Label(stats_frame, text="📤 Packets TX: 0", style='TLabel')
        self.packets_tx_label.pack(anchor=tk.W, pady=2)
        
        self.messages_label = ttk.Label(stats_frame, text="💬 Messages: 0", style='TLabel')
        self.messages_label.pack(anchor=tk.W, pady=2)
        
        # Auto-Send Telemetry Panel
        auto_send_frame = ttk.LabelFrame(right_column, text=" 🚀 Auto-Send Telemetry ", padding="10")
        auto_send_frame.pack(fill='both', expand=True)
        auto_send_frame.configure(relief='ridge', borderwidth=2)
        
        # Enable/Disable toggle
        self.auto_send_var = tk.BooleanVar(value=self.auto_send_enabled)
        auto_send_check = ttk.Checkbutton(
            auto_send_frame, 
            text="Enable Auto-Send",
            variable=self.auto_send_var,
            command=self.toggle_auto_send
        )
        auto_send_check.pack(anchor=tk.W, pady=5)
        
        # Interval setting
        interval_frame = ttk.Frame(auto_send_frame)
        interval_frame.pack(fill='x', pady=5)
        
        ttk.Label(interval_frame, text="Interval (sec):", style='TLabel').pack(side='left')
        self.interval_var = tk.StringVar(value=str(self.auto_send_interval))
        interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_var, width=10)
        interval_entry.pack(side='left', padx=5)
        
        ttk.Button(interval_frame, text="Set", command=self.set_interval).pack(side='left')
        
        # Selected nodes display
        ttk.Label(auto_send_frame, text="Selected Nodes:", style='TLabel').pack(anchor=tk.W, pady=(10, 2))
        
        self.selected_nodes_text = tk.Text(
            auto_send_frame,
            height=5,
            width=30,
            bg='#1e1e1e',
            fg='#00ff00',
            font=('Courier', 9),
            state='disabled'
        )
        self.selected_nodes_text.pack(fill='x', pady=2)
        
        # Buttons
        button_frame = ttk.Frame(auto_send_frame)
        button_frame.pack(fill='x', pady=5)
        
        ttk.Button(button_frame, text="Select Nodes", command=self.open_node_selector).pack(fill='x', pady=2)
        ttk.Button(button_frame, text="Test Send Now", command=self.send_telemetry_now).pack(fill='x', pady=2)
        
        # Status
        self.auto_send_status = ttk.Label(auto_send_frame, text="Status: Disabled", style='TLabel', foreground='#888888')
        self.auto_send_status.pack(anchor=tk.W, pady=(5, 0))
        
        # Last sent message preview
        ttk.Label(auto_send_frame, text="Last Sent Message:", style='TLabel').pack(anchor=tk.W, pady=(10, 2))
        
        self.last_message_text = tk.Text(
            auto_send_frame,
            height=3,
            width=30,
            bg='#1e1e1e',
            fg='#FFD700',
            font=('Courier', 8),
            state='disabled',
            wrap=tk.WORD
        )
        self.last_message_text.pack(fill='x', pady=2)
        
        # === BOTTOM SECTION: Message Feed ===
        messages_frame = ttk.LabelFrame(main_frame, text=" 📨 LoRa Traffic Feed (Real-Time) ", padding="10")
        messages_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        messages_frame.configure(relief='ridge', borderwidth=2)
        
        self.messages_text = scrolledtext.ScrolledText(
            messages_frame, 
            wrap=tk.WORD, 
            width=100, 
            height=15,
            bg='#1e1e1e',
            fg='#00ff00',
            font=('Courier', 9),
            insertbackground='white'
        )
        self.messages_text.pack(fill='both', expand=True)
        self.messages_text.tag_config('timestamp', foreground='#888888')
        self.messages_text.tag_config('node', foreground='#4CAF50', font=('Courier', 9, 'bold'))
        self.messages_text.tag_config('telemetry', foreground='#2196F3')
        self.messages_text.tag_config('position', foreground='#FFC107')
        self.messages_text.tag_config('message', foreground='#00ff00')
        self.messages_text.tag_config('nodeinfo', foreground='#9C27B0')
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
    def connect_to_device(self):
        """Connect to Meshtastic device via USB"""
        try:
            self.log_message("🔌 Connecting to device on /dev/ttyUSB0...")
            self.interface = meshtastic.serial_interface.SerialInterface('/dev/ttyUSB0')
            self.connected = True
            self.log_message("✅ Connected successfully!")
        except Exception as e:
            self.log_message(f"❌ Connection failed: {e}")
            self.log_message("⚠️  Please check USB connection and try restarting the application.")
            
    def on_connection(self, interface, topic=pub.AUTO_TOPIC):
        """Called when connection is established"""
        self.connected = True
        try:
            if self.interface and self.interface.myInfo:
                my_node = self.interface.myInfo.my_node_num
                node_id = f"!{my_node:08x}"
                long_name = self.interface.getLongName()
                hw_model = "Unknown"
                
                if self.interface.nodes:
                    for node in self.interface.nodes.values():
                        if node.get('num') == my_node:
                            hw_model = node.get('user', {}).get('hwModel', 'Unknown')
                            break
                
                self.root.after(0, self.device_info_label.config, 
                               {'text': f"Device: {long_name} ({node_id}) | Model: {hw_model}"})
                self.log_message(f"📱 Local Node: {long_name} ({node_id})")
        except Exception as e:
            self.log_message(f"⚠️  Error getting device info: {e}")
            
    def on_receive(self, packet, interface):
        """Called when a packet is received"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            from_id = packet.get('fromId', 'Unknown')
            to_id = packet.get('toId', 'Broadcast')
            
            decoded = packet.get('decoded', {})
            portnum = decoded.get('portnum', 'UNKNOWN')
            
            # Update stats
            self.stats['packets_rx'] += 1
            
            # Get and store signal strength
            snr = packet.get('rxSnr')
            rssi = packet.get('rxRssi')
            
            if isinstance(snr, (int, float)):
                self.latest_snr = snr
                snr_str = f"SNR: {snr:.1f}dB"
            else:
                snr_str = ""
                
            if isinstance(rssi, (int, float)):
                self.latest_rssi = rssi
            
            # Process different packet types
            if portnum == 'TEXT_MESSAGE_APP':
                text = decoded.get('text', '')
                self.stats['messages_seen'] += 1
                self.log_message(f"[{timestamp}] 💬 MSG from {from_id}: {text} {snr_str}", 'message')
                
            elif portnum == 'TELEMETRY_APP':
                self.log_message(f"[{timestamp}] 📊 TELEMETRY from {from_id} {snr_str}", 'telemetry')
                self.process_telemetry(packet)
                
            elif portnum == 'POSITION_APP':
                self.log_message(f"[{timestamp}] 📍 POSITION from {from_id} {snr_str}", 'position')
                
            elif portnum == 'NODEINFO_APP':
                self.log_message(f"[{timestamp}] ℹ️  NODEINFO from {from_id} {snr_str}", 'nodeinfo')
                
            else:
                self.log_message(f"[{timestamp}] 📦 {portnum} from {from_id} → {to_id} {snr_str}")
                
        except Exception as e:
            self.log_message(f"⚠️  Error processing packet: {e}")
            
    def on_node_updated(self, node, interface):
        """Called when node database is updated"""
        try:
            node_num = node.get('num')
            if node_num:
                node_id = f"!{node_num:08x}"
                user = node.get('user', {})
                long_name = user.get('longName', 'Unknown')
                
                self.nodes_data[node_id] = {
                    'name': long_name,
                    'id': node_id,
                    'snr': node.get('snr', 'N/A'),
                    'lastHeard': node.get('lastHeard', 0),
                    'node': node
                }
        except Exception as e:
            self.log_message(f"⚠️  Error updating node: {e}")
            
    def process_telemetry(self, packet):
        """Process telemetry data"""
        try:
            decoded = packet.get('decoded', {})
            payload = decoded.get('telemetry', {})
            
            from_id = packet.get('fromId', 'Unknown')
            
            # Device metrics
            if 'deviceMetrics' in payload:
                dm = payload['deviceMetrics']
                battery = dm.get('batteryLevel')
                voltage = dm.get('voltage')
                channel_util = dm.get('channelUtilization')
                air_util = dm.get('airUtilTx')
                uptime = dm.get('uptimeSeconds')
                
                # Store in history (create new entry or update last one)
                telemetry_data = {
                    'time': time.time(),
                    'battery': battery,
                    'voltage': voltage,
                    'channel_util': channel_util,
                    'air_util': air_util
                }
                
                # Check if we have recent telemetry to merge with
                if self.telemetry_history and (time.time() - self.telemetry_history[-1].get('time', 0)) < 5:
                    # Update existing entry
                    self.telemetry_history[-1].update(telemetry_data)
                else:
                    # Create new entry
                    self.telemetry_history.append(telemetry_data)
                
            # Environment metrics
            if 'environmentMetrics' in payload:
                em = payload['environmentMetrics']
                temp = em.get('temperature')
                humidity = em.get('relativeHumidity')
                pressure = em.get('barometricPressure')
                
                # Update GUI labels (convert to Fahrenheit)
                if temp is not None:
                    temp_f = (temp * 9/5) + 32
                    self.root.after(0, self.temp_label.config, 
                                   {'text': f"🌡️  Temperature: {temp_f:.1f}°F"})
                if humidity is not None:
                    self.root.after(0, self.humidity_label.config, 
                                   {'text': f"💧 Humidity: {humidity:.1f}%"})
                if pressure is not None:
                    self.root.after(0, self.pressure_label.config, 
                                   {'text': f"🌀 Pressure: {pressure:.1f} hPa"})
                
                # Store in history (merge with recent device metrics if available)
                env_data = {
                    'time': time.time(),
                    'temperature': temp,
                    'humidity': humidity,
                    'pressure': pressure
                }
                
                # Check if we have recent telemetry to merge with
                if self.telemetry_history and (time.time() - self.telemetry_history[-1].get('time', 0)) < 5:
                    # Update existing entry with environment data
                    self.telemetry_history[-1].update(env_data)
                else:
                    # Create new entry
                    self.telemetry_history.append(env_data)
                    
        except Exception as e:
            self.log_message(f"⚠️  Error processing telemetry: {e}")
            
    def update_ui(self):
        """Update UI elements periodically"""
        try:
            # Update connection status
            if self.connected:
                self.status_label.config(text="✅ Connected", foreground='#4CAF50')
            else:
                self.status_label.config(text="❌ Disconnected", foreground='#F44336')
            
            # Update telemetry display
            if self.telemetry_history:
                latest = self.telemetry_history[-1]
                
                battery = latest.get('battery')
                if battery is not None:
                    if battery == 101:
                        self.battery_label.config(text="🔋 Battery: Powered")
                    else:
                        self.battery_label.config(text=f"🔋 Battery: {battery}%")
                        
                voltage = latest.get('voltage')
                if voltage is not None:
                    self.voltage_label.config(text=f"⚡ Voltage: {voltage:.2f}V")
                    
                channel_util = latest.get('channel_util')
                if channel_util is not None:
                    self.channel_util_label.config(text=f"📡 Channel Util: {channel_util:.1f}%")
                    
                air_util = latest.get('air_util')
                if air_util is not None:
                    self.air_util_label.config(text=f"📶 Air Util TX: {air_util:.1f}%")
            
            # Update nodes list
            if self.interface and self.interface.nodes:
                # Clear existing items
                for item in self.nodes_tree.get_children():
                    self.nodes_tree.delete(item)
                
                # Add updated nodes
                for node in self.interface.nodes.values():
                    user = node.get('user', {})
                    long_name = user.get('longName', 'Unknown')
                    node_num = node.get('num')
                    node_id = f"!{node_num:08x}" if node_num else 'N/A'
                    snr = node.get('snr', 'N/A')
                    snr_str = f"{snr:.1f}" if isinstance(snr, (int, float)) else 'N/A'
                    
                    last_heard = node.get('lastHeard')
                    if last_heard:
                        last_heard_str = datetime.fromtimestamp(last_heard).strftime('%H:%M:%S')
                    else:
                        last_heard_str = 'Never'
                    
                    self.nodes_tree.insert('', 'end', values=(long_name, node_id, snr_str, last_heard_str))
            
            # Update statistics
            nodes_count = len(self.interface.nodes) if self.interface and self.interface.nodes else 0
            self.nodes_online_label.config(text=f"👥 Nodes Online: {nodes_count}")
            self.nodes_total_label.config(text=f"📍 Total Nodes: {nodes_count}")
            self.packets_rx_label.config(text=f"📥 Packets RX: {self.stats['packets_rx']}")
            self.packets_tx_label.config(text=f"📤 Packets TX: {self.stats['packets_tx']}")
            self.messages_label.config(text=f"💬 Messages: {self.stats['messages_seen']}")
            
        except Exception as e:
            print(f"Error updating UI: {e}")
        
        # Schedule next update
        self.root.after(1000, self.update_ui)
        
    def log_message(self, message, tag='default'):
        """Add message to the feed"""
        try:
            self.messages_text.insert(tk.END, message + '\n', tag)
            self.messages_text.see(tk.END)
            
            # Limit buffer size
            lines = int(self.messages_text.index('end-1c').split('.')[0])
            if lines > 500:
                self.messages_text.delete('1.0', '100.0')
        except Exception as e:
            print(f"Error logging message: {e}")
            
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.auto_send_enabled = config.get('auto_send_enabled', False)
                    self.auto_send_interval = config.get('auto_send_interval', 300)
                    self.selected_nodes = config.get('selected_nodes', [])
                    print(f"✅ Loaded config: {len(self.selected_nodes)} nodes selected")
        except Exception as e:
            print(f"⚠️  Error loading config: {e}")
            
    def save_config(self):
        """Save configuration to file"""
        try:
            config = {
                'auto_send_enabled': self.auto_send_enabled,
                'auto_send_interval': self.auto_send_interval,
                'selected_nodes': self.selected_nodes
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.log_message(f"💾 Configuration saved")
        except Exception as e:
            self.log_message(f"⚠️  Error saving config: {e}")
            
    def toggle_auto_send(self):
        """Toggle auto-send feature"""
        self.auto_send_enabled = self.auto_send_var.get()
        if self.auto_send_enabled:
            if not self.selected_nodes:
                messagebox.showwarning("No Nodes Selected", "Please select nodes before enabling auto-send.")
                self.auto_send_var.set(False)
                self.auto_send_enabled = False
                return
            self.auto_send_status.config(text="Status: Enabled ✅", foreground='#4CAF50')
            self.log_message(f"🚀 Auto-send ENABLED (interval: {self.auto_send_interval}s)")
        else:
            self.auto_send_status.config(text="Status: Disabled", foreground='#888888')
            self.log_message("⏸️  Auto-send DISABLED")
        self.save_config()
        
    def set_interval(self):
        """Set auto-send interval"""
        try:
            interval = int(self.interval_var.get())
            if interval < 30:
                messagebox.showerror("Invalid Interval", "Interval must be at least 30 seconds.")
                return
            self.auto_send_interval = interval
            self.save_config()
            self.log_message(f"⏱️  Auto-send interval set to {interval} seconds")
            messagebox.showinfo("Interval Set", f"Auto-send interval set to {interval} seconds.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number.")
            
    def open_node_selector(self):
        """Open dialog to select nodes"""
        if not self.interface or not self.interface.nodes:
            messagebox.showwarning("No Nodes", "No nodes available. Wait for nodes to appear in the mesh.")
            return
            
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Nodes for Auto-Send")
        dialog.geometry("600x500")
        dialog.configure(bg='#2b2b2b')
        
        # Instructions
        instructions = tk.Label(
            dialog,
            text="Click on nodes to select/deselect them for auto-send telemetry.\nRight-click to toggle individual nodes. Selected nodes are highlighted.",
            bg='#2b2b2b',
            fg='#4CAF50',
            font=('Arial', 10, 'bold'),
            justify='center'
        )
        instructions.pack(pady=10)
        
        # Create listbox with checkboxes
        frame = ttk.Frame(dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')
        
        # Listbox with better visibility
        node_listbox = tk.Listbox(
            frame,
            selectmode='multiple',
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 11),
            yscrollcommand=scrollbar.set,
            selectbackground='#4CAF50',
            selectforeground='black',
            activestyle='dotbox',
            height=15
        )
        node_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=node_listbox.yview)
        
        # Populate with nodes
        node_map = {}
        index = 0
        for node in self.interface.nodes.values():
            user = node.get('user', {})
            long_name = user.get('longName', 'Unknown')
            node_num = node.get('num')
            if node_num:
                node_id = f"!{node_num:08x}"
                # Skip our own node
                if node_num == self.interface.myInfo.my_node_num:
                    continue
                display_text = f"{long_name} ({node_id})"
                node_listbox.insert(tk.END, display_text)
                node_map[index] = {'text': display_text, 'id': node_id}
                
                # Select if already in selected_nodes
                if node_id in self.selected_nodes:
                    node_listbox.selection_set(index)
                
                index += 1
        
        # Right-click handler to toggle selection
        def on_right_click(event):
            # Get the index of the clicked item
            index = node_listbox.nearest(event.y)
            if index >= 0:
                # Toggle selection
                if node_listbox.selection_includes(index):
                    node_listbox.selection_clear(index)
                else:
                    node_listbox.selection_set(index)
        
        # Bind right-click
        node_listbox.bind('<Button-3>', on_right_click)
        
        # Also bind regular click for easier single selection
        def on_left_click(event):
            index = node_listbox.nearest(event.y)
            if index >= 0:
                # Toggle selection on left click too
                if node_listbox.selection_includes(index):
                    node_listbox.selection_clear(index)
                else:
                    node_listbox.selection_set(index)
        
        node_listbox.bind('<Button-1>', on_left_click)
        
        # Selection counter
        counter_label = tk.Label(
            dialog,
            text="Selected: 0 nodes",
            bg='#2b2b2b',
            fg='#FFC107',
            font=('Arial', 10)
        )
        counter_label.pack(pady=5)
        
        def update_counter():
            count = len(node_listbox.curselection())
            counter_label.config(text=f"Selected: {count} nodes")
            dialog.after(100, update_counter)
        
        update_counter()
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        def select_all():
            node_listbox.selection_set(0, tk.END)
        
        def clear_all():
            node_listbox.selection_clear(0, tk.END)
        
        def save_selection():
            selected_indices = node_listbox.curselection()
            self.selected_nodes = []
            for idx in selected_indices:
                node_info = node_map.get(idx)
                if node_info:
                    self.selected_nodes.append(node_info['id'])
            
            self.update_selected_nodes_display()
            self.save_config()
            self.log_message(f"📝 Selected {len(self.selected_nodes)} nodes for auto-send")
            messagebox.showinfo("Saved", f"Selected {len(self.selected_nodes)} nodes for auto-send.")
            dialog.destroy()
        
        ttk.Button(button_frame, text="Select All", command=select_all).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Clear All", command=clear_all).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Save Selection", command=save_selection).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
        
    def update_selected_nodes_display(self):
        """Update the selected nodes text display"""
        self.selected_nodes_text.config(state='normal')
        self.selected_nodes_text.delete('1.0', tk.END)
        
        if not self.selected_nodes:
            self.selected_nodes_text.insert('1.0', "No nodes selected")
        else:
            for node_id in self.selected_nodes:
                # Find node name
                node_name = "Unknown"
                if self.interface and self.interface.nodes:
                    for node in self.interface.nodes.values():
                        node_num = node.get('num')
                        if node_num and f"!{node_num:08x}" == node_id:
                            node_name = node.get('user', {}).get('longName', 'Unknown')
                            break
                self.selected_nodes_text.insert(tk.END, f"• {node_name} ({node_id})\n")
        
        self.selected_nodes_text.config(state='disabled')
        
    def get_telemetry_message(self, dest_node_id: Optional[str] = None) -> str:
        """Generate telemetry message with BME280 sensor data priority"""
        lines = [f"⏰ {datetime.now().strftime('%H:%M:%S')}"]
        
        # Get hop count to destination if available
        if dest_node_id and self.interface and self.interface.nodes:
            for node in self.interface.nodes.values():
                node_num = node.get('num')
                if node_num and f"!{node_num:08x}" == dest_node_id:
                    hops_away = node.get('hopsAway', 0)
                    if hops_away is not None and hops_away > 0:
                        lines.append(f"🔗 Hops: {hops_away}")
                    break
        
        # Debug output
        print(f"DEBUG: telemetry_history length: {len(self.telemetry_history)}")
        if self.telemetry_history:
            print(f"DEBUG: Latest entry: {self.telemetry_history[-1]}")
        
        # Check if we have telemetry data
        if self.telemetry_history and len(self.telemetry_history) > 0:
            latest = self.telemetry_history[-1]
            
            # PRIORITY 1: BME280 Environment Sensors
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
            
            # PRIORITY 2: Signal Strength
            # Get SNR from most recent packet (if available)
            if hasattr(self, 'latest_snr') and self.latest_snr is not None:
                lines.append(f"📶 SNR: {self.latest_snr:.1f}dB")
            
            if hasattr(self, 'latest_rssi') and self.latest_rssi is not None:
                lines.append(f"📡 RSSI: {self.latest_rssi}dBm")
            
            # PRIORITY 3: Battery & Power
            battery = latest.get('battery')
            if battery is not None:
                if battery == 101:
                    lines.append("🔋 PWR")
                else:
                    lines.append(f"🔋 {battery}%")
                    
            voltage = latest.get('voltage')
            if voltage is not None:
                lines.append(f"⚡ {voltage:.2f}V")
            
            # PRIORITY 4: Network Utilization
            channel_util = latest.get('channel_util')
            if channel_util is not None:
                lines.append(f"📻 CH:{channel_util:.1f}%")
                
            air_util = latest.get('air_util')
            if air_util is not None:
                lines.append(f"🌐 Air:{air_util:.1f}%")
        
        # Add node count
        if self.interface and self.interface.nodes:
            lines.append(f"👥 {len(self.interface.nodes)}")
        
        return " | ".join(lines)
        
    def send_telemetry_now(self):
        """Send telemetry message immediately (test function)"""
        if not self.connected or not self.interface:
            messagebox.showerror("Not Connected", "Not connected to device.")
            return
            
        if not self.selected_nodes:
            messagebox.showwarning("No Nodes", "No nodes selected for auto-send.")
            return
        
        try:
            last_message = None
            for node_id in self.selected_nodes:
                # Generate message with hop count for this specific node
                message = self.get_telemetry_message(dest_node_id=node_id)
                last_message = message  # Store for display
                
                # Send as direct message (encrypted, only recipient can read)
                self.interface.sendText(message, destinationId=node_id, wantAck=True)
                self.stats['packets_tx'] += 1
                self.log_message(f"📤 Sent private telemetry DM to {node_id}", 'sent')
            
            # Display the last sent message in the GUI
            if last_message:
                self.last_message_text.config(state='normal')
                self.last_message_text.delete('1.0', tk.END)
                self.last_message_text.insert('1.0', last_message)
                self.last_message_text.config(state='disabled')
            
            messagebox.showinfo("Sent", f"Telemetry sent to {len(self.selected_nodes)} nodes.")
        except Exception as e:
            self.log_message(f"❌ Error sending: {e}")
            messagebox.showerror("Send Failed", f"Error: {e}")
            
    def check_auto_send(self):
        """Check if it's time to auto-send telemetry"""
        try:
            current_time = time.time()
            
            if self.auto_send_enabled and self.connected and self.selected_nodes:
                if current_time - self.last_auto_send >= self.auto_send_interval:
                    message = self.get_telemetry_message()
                    
                    for node_id in self.selected_nodes:
                        try:
                            self.interface.sendText(message, destinationId=node_id)
                            self.stats['packets_tx'] += 1
                            self.log_message(f"🚀 Auto-sent telemetry to {node_id}")
                        except Exception as e:
                            self.log_message(f"❌ Auto-send failed to {node_id}: {e}")
                    
                    self.last_auto_send = current_time
                    
                # Update status with countdown
                time_until_next = self.auto_send_interval - (current_time - self.last_auto_send)
                if time_until_next > 0:
                    mins, secs = divmod(int(time_until_next), 60)
                    self.auto_send_status.config(
                        text=f"Status: Enabled ✅ (Next in {mins}m {secs}s)",
                        foreground='#4CAF50'
                    )
            elif self.auto_send_enabled:
                # Update the selected nodes display
                self.update_selected_nodes_display()
                
        except Exception as e:
            self.log_message(f"⚠️  Auto-send check error: {e}")
        
        # Schedule next check (every 5 seconds)
        self.root.after(5000, self.check_auto_send)
    
    def on_closing(self):
        """Clean up on window close"""
        self.log_message("🔌 Closing connection...")
        self.save_config()
        if self.interface:
            try:
                self.interface.close()
            except:
                pass
        self.root.destroy()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = MeshtasticMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
