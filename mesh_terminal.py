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
import termios
import tty
from datetime import datetime
from typing import Optional, Dict, List
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
from mesh_chatbot import MeshChatBot

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
        
        # Recent activity tracking
        self.recent_activity = []  # List of recent packet activity
        self.max_activity_items = 10  # Keep last 10 items
        
        # Recent text messages tracking
        self.recent_messages = []  # List of recent text messages
        self.max_message_items = 10  # Keep last 10 messages
        
        # Conversation tracking by node
        self.conversations = {}  # {node_id: [{'time': timestamp, 'from': node_id, 'to': node_id, 'text': message, 'direction': 'sent'/'received'}]}
        
        # Message acknowledgment tracking per target node
        self.message_acks = {}  # {node_id: {'last_ack_time': timestamp, 'ack_status': 'ACK'/'NAK'/'PENDING'}}
        
        # Keyword command control
        self.auto_send_paused = False  # STOP/START command control
        self.suppress_output = False  # Suppress console output when in submenus
        
        # Auto-send configuration
        self.config_file = 'terminal_config.json'
        self.auto_send_enabled = False
        self.auto_send_interval = 60  # seconds
        self.selected_nodes = []
        self.last_send_time = 0
        
        # ChatBot initialization
        self.chatbot = None
        self.chatbot_enabled = True  # Enabled by default
        self.chatbot_model_path = "./models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
        self.chatbot_greeting = "Hello. I am MeshBot. How can I help you?"
        self.chatbot_thinking = False  # Flag to indicate LLM is processing
        
        # Rate limiting for non-selected nodes (50 messages per hour)
        self.rate_limit_tracker = {}  # {node_id: {'count': X, 'reset_time': timestamp}}
        
        # Load config
        self.load_config()
        
        # Initialize chatbot if available
        try:
            self.chatbot = MeshChatBot(model_path=self.chatbot_model_path, logger=self.logger)
            if self.chatbot_greeting:
                self.chatbot.set_greeting(self.chatbot_greeting)
            self.logger.info(f"ChatBot initialized: available={self.chatbot.is_available()}")
            
            # Auto-load model if chatbot is enabled by default
            if self.chatbot_enabled and self.chatbot.model_exists():
                self.logger.info("Auto-loading chatbot model on startup...")
                if self.chatbot.load_model():
                    self.logger.info("ChatBot model loaded successfully")
                else:
                    self.logger.warning("Failed to auto-load chatbot model")
                    self.chatbot_enabled = False
        except Exception as e:
            self.logger.warning(f"ChatBot initialization failed: {e}")
            self.chatbot = None
            self.chatbot_enabled = False
        
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
        
        # Setup activity log file
        self.activity_log_file = 'mesh_activity.log'
        self.activity_logger = logging.getLogger('MeshtasticActivity')
        self.activity_logger.setLevel(logging.INFO)
        
        # Activity file handler
        afh = logging.FileHandler(self.activity_log_file)
        afh.setLevel(logging.INFO)
        afh.setFormatter(logging.Formatter(
            '%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # Add handler
        self.activity_logger.addHandler(afh)
        self.activity_logger.info("="*60)
        self.activity_logger.info("Activity Log Started")
        self.activity_logger.info("="*60)
    
    def get_single_key(self, prompt=""):
        """Get a single keypress without requiring Enter"""
        if prompt:
            print(prompt, end='', flush=True)
        
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            key = sys.stdin.read(1)
            print()  # New line after key press
            return key
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def get_line_input(self, prompt=""):
        """Get a full line of input (for text messages, numbers, etc)"""
        # Save current terminal settings
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            # Force terminal into canonical mode for line input
            new_settings = termios.tcgetattr(sys.stdin)
            new_settings[3] = new_settings[3] | termios.ICANON | termios.ECHO
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
            
            if prompt:
                print(prompt, end='', flush=True)
            result = input()
            return result
        finally:
            # Restore original settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.auto_send_enabled = config.get('auto_send_enabled', False)
                    self.auto_send_interval = config.get('auto_send_interval', 60)
                    self.selected_nodes = config.get('selected_nodes', [])
                    self.chatbot_enabled = config.get('chatbot_enabled', True)  # Default to enabled
                    self.chatbot_model_path = config.get('chatbot_model_path', "./models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
                    self.chatbot_greeting = config.get('chatbot_greeting', "Hello. I am MeshBot. How can I help you?")
                    msg = f"Loaded config: {len(self.selected_nodes)} nodes selected, auto_send={self.auto_send_enabled}, chatbot={self.chatbot_enabled}"
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
                'selected_nodes': self.selected_nodes,
                'chatbot_enabled': self.chatbot_enabled,
                'chatbot_model_path': self.chatbot_model_path,
                'chatbot_greeting': self.chatbot_greeting
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
            
            # Add to recent activity
            node_name = from_id
            if from_id and from_id != 'Unknown':
                node_info = self.get_node_info(from_id)
                if node_info:
                    node_name = node_info.get('user', {}).get('shortName') or node_info.get('user', {}).get('longName', from_id)
            
            activity_msg = f"📥 {portnum.replace('_APP', '')} from {node_name}"
            if snr is not None:
                activity_msg += f" SNR:{snr:.1f}"
            self.add_activity(activity_msg)
            
            # Process telemetry
            if portnum == 'TELEMETRY_APP':
                self.process_telemetry(packet)
            elif portnum == 'TEXT_MESSAGE_APP':
                self.stats['messages_seen'] += 1
                text = decoded.get('text', '')
                self.logger.info(f"TEXT_MSG from {from_id}: {text[:50]}")
                
                # Check if this is a keyword command
                text_upper = text.strip().upper()
                keyword_list = ['STOP', 'START', 'RADIOCHECK', 'WEATHERCHECK', 'KEYWORDS', 'CHATBOTON', 'CHATBOTOFF']
                is_keyword = any(text_upper == kw or text_upper.startswith('FREQ') for kw in keyword_list)
                
                # Process keyword commands (only from selected nodes)
                if is_keyword and from_id in self.selected_nodes:
                    self.process_keyword_command(text_upper, from_id)
                
                # Process chatbot messages (from ALL nodes, with rate limiting for non-selected)
                elif not is_keyword and self.chatbot_enabled and self.chatbot and self.chatbot.is_loaded():
                    # Check rate limit for non-selected nodes
                    if from_id not in self.selected_nodes:
                        if not self.check_rate_limit(from_id):
                            self.logger.warning(f"Rate limit exceeded for {from_id}")
                            # Send rate limit notification
                            self.interface.sendText("⚠️ Rate limit: 50 msg/hour. Please wait.", destinationId=from_id, wantAck=False)
                            return
                    
                    # Pass message to chatbot
                    self.logger.info(f"Passing message to chatbot: {text[:50]}")
                    try:
                        self.chatbot_thinking = True
                        response = self.chatbot.generate_response(text)
                        self.chatbot_thinking = False
                        if response:
                            # Split long responses into multiple messages (200 char limit)
                            chunks = self.split_message(response, max_length=200)
                            self.logger.info(f"Split response into {len(chunks)} chunks")
                            
                            for i, chunk in enumerate(chunks):
                                try:
                                    self.interface.sendText(chunk, destinationId=from_id, wantAck=False)
                                    self.logger.info(f"ChatBot response part {i+1}/{len(chunks)} sent: {chunk[:50]}")
                                    
                                    # Store each sent message in conversation
                                    if from_id not in self.conversations:
                                        self.conversations[from_id] = []
                                    self.conversations[from_id].append({
                                        'time': datetime.now().strftime('%H:%M:%S'),
                                        'from': 'local',
                                        'to': from_id,
                                        'text': chunk,
                                        'direction': 'sent'
                                    })
                                    
                                    # Longer delay between messages to avoid interface issues
                                    if i < len(chunks) - 1:
                                        time.sleep(2)
                                except Exception as send_error:
                                    self.logger.error(f"Error sending chunk {i+1}/{len(chunks)}: {send_error}")
                                    # Continue trying to send remaining chunks
                                    time.sleep(2)
                            
                            self.add_activity(f"🤖 Replied to {from_id[:8]} ({len(chunks)} msg)")
                        else:
                            self.chatbot_thinking = False
                            self.logger.warning("ChatBot generated no response")
                    except Exception as e:
                        self.chatbot_thinking = False
                        self.logger.error(f"ChatBot error: {e}", exc_info=True)
                
                # Store the message
                node_name = from_id
                node_info = self.get_node_info(from_id)
                if node_info:
                    node_name = node_info.get('user', {}).get('shortName') or node_info.get('user', {}).get('longName', from_id)
                
                message_entry = {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'from_id': from_id,
                    'from_name': node_name,
                    'text': text,
                    'snr': snr,
                    'rssi': rssi
                }
                self.recent_messages.append(message_entry)
                
                # Keep only last N messages
                if len(self.recent_messages) > self.max_message_items:
                    self.recent_messages.pop(0)
                
                # Add to conversations
                if from_id not in self.conversations:
                    self.conversations[from_id] = []
                self.conversations[from_id].append({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'from': from_id,
                    'to': 'local',
                    'text': text,
                    'direction': 'received',
                    'snr': snr,
                    'rssi': rssi
                })
            elif portnum == 'ROUTING_APP':
                # Handle ACK/NAK responses
                self.handle_routing_response(packet)
                
        except Exception as e:
            self.logger.error(f"Error in on_receive: {e}")
    
    def check_rate_limit(self, node_id):
        """Check if node is within rate limit (50 messages per hour)
        
        Args:
            node_id: Node ID to check
            
        Returns:
            True if within limit, False if exceeded
        """
        current_time = time.time()
        
        # Initialize tracker if not exists
        if node_id not in self.rate_limit_tracker:
            self.rate_limit_tracker[node_id] = {
                'count': 0,
                'reset_time': current_time + 3600  # 1 hour from now
            }
        
        tracker = self.rate_limit_tracker[node_id]
        
        # Reset counter if hour has passed
        if current_time >= tracker['reset_time']:
            tracker['count'] = 0
            tracker['reset_time'] = current_time + 3600
            self.logger.info(f"Rate limit reset for {node_id}")
        
        # Check if under limit (50 per hour)
        if tracker['count'] >= 50:
            remaining = int(tracker['reset_time'] - current_time)
            self.logger.warning(f"Rate limit exceeded for {node_id} ({tracker['count']} msgs). Reset in {remaining}s")
            return False
        
        # Increment counter
        tracker['count'] += 1
        self.logger.debug(f"Rate limit for {node_id}: {tracker['count']}/50")
        return True
    
    def process_keyword_command(self, text, from_id):
        """Process keyword commands from target nodes"""
        try:
            reply_message = None
            
            if text == 'STOP':
                self.auto_send_paused = True
                self.logger.info(f"AUTO-SEND STOPPED by command from {from_id}")
                print(f"\n🛑 AUTO-SEND STOPPED by {from_id}")
                self.add_activity(f"🛑 AUTO-SEND STOPPED by {from_id}")
                reply_message = "✅ AUTO-SEND STOPPED"
            elif text == 'START':
                self.auto_send_paused = False
                self.logger.info(f"AUTO-SEND STARTED by command from {from_id}")
                print(f"\n▶️  AUTO-SEND STARTED by {from_id}")
                self.add_activity(f"▶️  AUTO-SEND STARTED by {from_id}")
                reply_message = "✅ AUTO-SEND STARTED"
            elif text.startswith('FREQ') and len(text) > 4:
                # Parse frequency (e.g., FREQ60, FREQ300)
                try:
                    new_freq = int(text[4:])
                    if 30 <= new_freq <= 3600:  # Limit between 30 seconds and 1 hour
                        old_freq = self.auto_send_interval
                        self.auto_send_interval = new_freq
                        self.save_config()
                        self.logger.info(f"FREQUENCY changed from {old_freq}s to {new_freq}s by {from_id}")
                        print(f"\n⏱️  FREQUENCY changed to {new_freq}s by {from_id}")
                        self.add_activity(f"⏱️  FREQ changed to {new_freq}s by {from_id}")
                        reply_message = f"✅ FREQ set to {new_freq}s (was {old_freq}s)"
                    else:
                        self.logger.warning(f"Invalid frequency {new_freq} from {from_id} (must be 30-3600)")
                        reply_message = f"❌ FREQ must be 30-3600 seconds"
                except ValueError:
                    self.logger.warning(f"Invalid FREQ command from {from_id}: {text}")
                    reply_message = "❌ Invalid FREQ format. Use FREQ## (e.g., FREQ60)"
            elif text == 'RADIOCHECK':
                # Respond with signal strength data
                self.logger.info(f"RADIOCHECK requested by {from_id}")
                print(f"\n📡 RADIOCHECK requested by {from_id}")
                self.add_activity(f"📡 RADIOCHECK from {from_id}")
                
                # Get signal data for requesting node
                node_info = self.get_node_info(from_id)
                if node_info and from_id in self.nodes_data:
                    snr = self.nodes_data[from_id].get('last_snr', 0)
                    rssi = self.nodes_data[from_id].get('last_rssi', 0)
                    last_heard = node_info.get('lastHeard', 0)
                    age = int(time.time() - last_heard) if last_heard else 0
                    
                    reply_message = f"📡 RADIOCHECK: SNR {snr:.1f}dB | RSSI {rssi}dBm | Age {age}s"
                else:
                    reply_message = "📡 RADIOCHECK: No recent signal data available"
            elif text == 'WEATHERCHECK':
                # Respond with telemetry data
                self.logger.info(f"WEATHERCHECK requested by {from_id}")
                print(f"\n🌡️  WEATHERCHECK requested by {from_id}")
                self.add_activity(f"🌡️  WEATHERCHECK from {from_id}")
                
                # Get current telemetry message
                telemetry_msg = self.get_telemetry_message(dest_node_id=from_id)
                if telemetry_msg and telemetry_msg != "No telemetry data available":
                    reply_message = f"🌡️  WEATHERCHECK: {telemetry_msg}"
                else:
                    reply_message = "🌡️  WEATHERCHECK: No telemetry data available"
            elif text == 'KEYWORDS':
                # Respond with list of available keywords
                self.logger.info(f"KEYWORDS requested by {from_id}")
                print(f"\n📋 KEYWORDS requested by {from_id}")
                self.add_activity(f"📋 KEYWORDS from {from_id}")
                chatbot_status = "CHATBOTON CHATBOTOFF" if self.chatbot and self.chatbot.is_available() else ""
                reply_message = f"📋 Available: STOP START FREQ### RADIOCHECK WEATHERCHECK KEYWORDS {chatbot_status}"
            elif text == 'CHATBOTON':
                # Enable chatbot
                if not self.chatbot or not self.chatbot.is_available():
                    reply_message = "❌ ChatBot not available (install llama-cpp-python)"
                elif not self.chatbot.model_exists():
                    reply_message = "❌ ChatBot model not found"
                else:
                    self.logger.info(f"CHATBOTON requested by {from_id}")
                    self.add_activity(f"🤖 CHATBOTON from {from_id}")
                    
                    if self.chatbot_enabled and self.chatbot.is_loaded():
                        reply_message = "⚠️  ChatBot already enabled"
                    else:
                        self.add_activity("Loading chatbot model...")
                        if self.chatbot.load_model():
                            self.chatbot_enabled = True
                            self.save_config()
                            self.add_activity("✅ ChatBot enabled")
                            # Send greeting message
                            greeting = self.chatbot.get_greeting()
                            self.interface.sendText(greeting, destinationId=from_id, wantAck=False)
                            self.add_activity(f"🤖 Sent greeting to {from_id}")
                            reply_message = "✅ CHATBOT ENABLED"
                        else:
                            reply_message = "❌ Failed to load chatbot model"
            elif text == 'CHATBOTOFF':
                # Disable chatbot
                if not self.chatbot:
                    reply_message = "❌ ChatBot not available"
                else:
                    self.logger.info(f"CHATBOTOFF requested by {from_id}")
                    self.add_activity(f"🤖 CHATBOTOFF from {from_id}")
                    
                    if not self.chatbot_enabled:
                        reply_message = "⚠️  ChatBot already disabled"
                    else:
                        self.chatbot.unload_model()
                        self.chatbot_enabled = False
                        self.save_config()
                        self.add_activity("✅ ChatBot disabled")
                        reply_message = "✅ CHATBOT DISABLED"
            
            # Send auto-reply if a response was generated
            if reply_message and self.interface:
                try:
                    self.interface.sendText(reply_message, destinationId=from_id, wantAck=False)
                    self.logger.info(f"Auto-reply sent to {from_id}: {reply_message}")
                    print(f"  ↪️  Replied: {reply_message}")
                    self.add_activity(f"📤 Auto-reply to {from_id}")
                    
                    # Add to conversation
                    if from_id not in self.conversations:
                        self.conversations[from_id] = []
                    self.conversations[from_id].append({
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'from': 'local',
                        'to': from_id,
                        'text': reply_message,
                        'direction': 'sent'
                    })
                except Exception as e:
                    self.logger.error(f"Error sending auto-reply to {from_id}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error processing keyword command: {e}")
    
    def handle_routing_response(self, packet):
        """Handle routing ACK/NAK responses"""
        try:
            decoded = packet.get('decoded', {})
            routing = decoded.get('routing', {})
            error_reason = routing.get('errorReason', 'NONE')
            from_id = packet.get('from')
            
            if from_id:
                from_id = f"!{from_id:08x}"
                
                if error_reason == 'NONE':
                    # ACK received
                    self.message_acks[from_id] = {
                        'last_ack_time': time.time(),
                        'ack_status': 'ACK',
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }
                    self.logger.info(f"Received ACK from {from_id}")
                else:
                    # NAK received
                    self.message_acks[from_id] = {
                        'last_ack_time': time.time(),
                        'ack_status': f'NAK:{error_reason}',
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }
                    self.logger.warning(f"Received NAK from {from_id}: {error_reason}")
        except Exception as e:
            self.logger.error(f"Error handling routing response: {e}")
            
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
    
    def get_current_device_telemetry(self) -> Optional[Dict]:
        """Get current telemetry from local device in interface.nodes"""
        try:
            if self.interface and hasattr(self.interface, 'myInfo') and self.interface.myInfo:
                node_num = self.interface.myInfo.get('num')
                if node_num:
                    node_id = f"!{node_num:08x}"
                    if hasattr(self.interface, 'nodes') and self.interface.nodes and node_id in self.interface.nodes:
                        node = self.interface.nodes[node_id]
                        telemetry = {}
                        
                        # Get device metrics
                        if 'deviceMetrics' in node:
                            dm = node['deviceMetrics']
                            telemetry['battery'] = dm.get('batteryLevel')
                            telemetry['voltage'] = dm.get('voltage')
                            telemetry['channel_util'] = dm.get('channelUtilization')
                            telemetry['air_util'] = dm.get('airUtilTx')
                        
                        # Get environment metrics if available
                        if 'environmentMetrics' in node:
                            em = node['environmentMetrics']
                            telemetry['temperature'] = em.get('temperature')
                            telemetry['humidity'] = em.get('relativeHumidity')
                            telemetry['pressure'] = em.get('barometricPressure')
                        
                        if telemetry:
                            return telemetry
        except Exception as e:
            self.logger.debug(f"Error getting current device telemetry: {e}")
        return None
    
    def split_message(self, text: str, max_length: int = 200) -> List[str]:
        """
        Split a long message into chunks suitable for Meshtastic transmission.
        Tries to split at sentence boundaries when possible.
        
        Args:
            text: The text to split
            max_length: Maximum length per chunk (default 200 for Meshtastic)
            
        Returns:
            List of message chunks
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        remaining = text
        
        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break
            
            # Try to find a sentence boundary within max_length
            chunk = remaining[:max_length]
            
            # Look for sentence endings (. ! ?)
            last_period = max(chunk.rfind('. '), chunk.rfind('! '), chunk.rfind('? '))
            
            if last_period > max_length * 0.5:  # Only split at sentence if it's past halfway
                split_point = last_period + 2  # Include the period and space
            else:
                # Try to split at a space
                last_space = chunk.rfind(' ')
                if last_space > 0:
                    split_point = last_space + 1
                else:
                    # Hard split at max_length
                    split_point = max_length
            
            chunks.append(remaining[:split_point].strip())
            remaining = remaining[split_point:].strip()
        
        return chunks
    
    def add_activity(self, message: str):
        """Add recent activity message with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        display_msg = f"[{timestamp}] {message}"
        self.recent_activity.append(display_msg)
        
        # Write to activity log file
        self.activity_logger.info(message)
        
        # Keep only last N items in memory
        if len(self.recent_activity) > self.max_activity_items:
            self.recent_activity.pop(0)
            
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
        
    def request_fresh_telemetry(self):
        """Request device to read sensors and update telemetry"""
        try:
            if self.interface and hasattr(self.interface, 'sendTelemetry'):
                # Request device to send telemetry (triggers sensor read)
                self.logger.debug("Requesting fresh telemetry from device")
                self.interface.sendTelemetry()
                
                # Wait for device to read sensors and update
                time.sleep(3)
                
                # Fetch updated data from nodes database
                current = self.get_current_device_telemetry()
                if current:
                    self.logger.debug(f"Fresh telemetry received: Temp={current.get('temperature')}, Hum={current.get('humidity')}, Batt={current.get('battery')}")
                    return True
        except Exception as e:
            self.logger.debug(f"Error requesting fresh telemetry: {e}")
        return False
    
    def send_telemetry(self, silent=False):
        """Send telemetry to selected nodes
        
        Args:
            silent: If True, suppress error messages (for background auto-send)
        """
        if not self.connected or not self.interface:
            msg = "Not connected to device"
            if not silent:
                print(f"❌ {msg}")
            self.logger.warning(f"Send failed: {msg}")
            return False
            
        if not self.selected_nodes:
            msg = "No nodes selected"
            if not silent:
                print(f"❌ {msg}")
            self.logger.warning(f"Send failed: {msg}")
            return False
        
        try:
            # Request fresh sensor reading from device
            self.request_fresh_telemetry()
            
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
                
                # Mark message as pending before sending
                self.message_acks[node_id] = {
                    'last_ack_time': time.time(),
                    'ack_status': 'PENDING',
                    'timestamp': datetime.now().strftime('%H:%M:%S')
                }
                
                self.interface.sendText(message, destinationId=node_id, wantAck=True)
                self.stats['packets_tx'] += 1
                sent_count += 1
                self.logger.info(f"TX to {node_id}: {message}")
                
                # Add to activity feed (visible at top of screen)
                node_name = node_info.get('user', {}).get('shortName') if node_info else node_id
                self.add_activity(f"📤 Telemetry to {node_name}")
            
            self.last_send_time = time.time()
            self.logger.info(f"Sent telemetry to {sent_count} nodes")
            self.logger.info("NOTE: Messages use PKC encryption (fw 2.5.0+). Key exchange happens automatically.")
            return True
        except Exception as e:
            msg = f"Error sending telemetry: {e}"
            print(f"❌ {msg}")
            self.logger.error(msg, exc_info=True)
            return False
    
    def send_keyword_info(self):
        """Send keyword command information to target nodes"""
        if not self.connected or not self.interface or not self.selected_nodes:
            return False
        
        try:
            keyword_msg = f"Commands: STOP START FREQ## RADIOCHECK WEATHERCHECK KEYWORDS | Interval: {self.auto_send_interval}s"
            
            for node_id in self.selected_nodes:
                self.interface.sendText(keyword_msg, destinationId=node_id, wantAck=False)
                self.logger.info(f"Sent keyword info to {node_id}")
                time.sleep(0.5)  # Small delay between sends
            
            self.add_activity("📋 Sent keyword info to nodes")
            return True
        except Exception as e:
            self.logger.error(f"Error sending keyword info: {e}")
            return False
    
    def message_interface(self):
        """Interactive message interface to view and send messages"""
        self.suppress_output = True  # Suppress auto-send output while in message interface
        try:
            while True:
                self.clear_screen()
                print("=" * 80)
                print("    💬 MESSAGE INTERFACE")
                print("=" * 80)
                
                # Get all nodes with conversations
                nodes_with_messages = list(self.conversations.keys())
                
                # Add selected nodes even if no messages yet
                all_nodes = set(nodes_with_messages)
                if self.selected_nodes:
                    all_nodes.update(self.selected_nodes)
                
                # Add all known nodes from mesh
                if self.interface and hasattr(self.interface, 'nodes'):
                    for node_id in self.interface.nodes.keys():
                        all_nodes.add(node_id)
                
                node_list = sorted(all_nodes)
                
                if not node_list:
                    print("\n❌ No nodes available")
                    self.get_single_key("\nPress any key to return...")
                    return
                
                # Display nodes with message counts
                print("\n📱 NODES:")
                print("-" * 80)
                for idx, node_id in enumerate(node_list, 1):
                    node_info = self.get_node_info(node_id)
                    node_name = node_info.get('user', {}).get('shortName', node_id[-4:]) if node_info else node_id[-4:]
                    long_name = node_info.get('user', {}).get('longName', '') if node_info else ''
                    
                    msg_count = len(self.conversations.get(node_id, []))
                    unread_indicator = ""
                    if msg_count > 0:
                        unread_indicator = f" ({msg_count} msgs)"
                    
                    # Check if this is a target node
                    target_indicator = " ⭐" if node_id in self.selected_nodes else ""
                    
                    print(f"  {idx}. {node_name:8s} {long_name[:30]:30s}{unread_indicator}{target_indicator}")
                
                print("-" * 80)
                print("\nOptions:")
                print("  [N] - Enter node number to view conversation")
                print("  [B] - Back to dashboard")
                
                choice = self.get_single_key("\nSelect option: ").strip().upper()
                
                if choice == 'B':
                    return
                elif choice == 'N':
                    # Get node number
                    print(f"You pressed: {choice}")
                    num_choice = self.get_line_input("\nEnter node number: ").strip()
                    if num_choice.isdigit():
                        idx = int(num_choice) - 1
                        if 0 <= idx < len(node_list):
                            node_id = node_list[idx]
                            self.logger.info(f"Opening conversation with {node_id}")
                            print(f"\n📖 Opening conversation with node {idx+1}...")
                            time.sleep(0.5)  # Brief pause for user feedback
                            self.view_conversation(node_id)
                        else:
                            print(f"\n❌ Invalid node number. Must be 1-{len(node_list)}")
                            time.sleep(1.5)
                else:
                    print(f"\n❌ Invalid choice: {choice}")
                    time.sleep(1)
        finally:
            self.suppress_output = False  # Restore output when exiting
    
    def view_conversation(self, node_id):
        """View and interact with conversation for a specific node"""
        import select
        import sys
        
        self.logger.info(f"Entering view_conversation for {node_id}")
        last_message_count = -1  # Set to -1 to force initial display
        
        while True:
            # Get current message count to detect new messages
            conversation = self.conversations.get(node_id, [])
            current_message_count = len(conversation)
            
            self.logger.debug(f"Conversation check: current={current_message_count}, last={last_message_count}")
            
            # Only refresh display if message count changed or first time
            if current_message_count != last_message_count:
                self.clear_screen()
                
                node_info = self.get_node_info(node_id)
                node_name = node_info.get('user', {}).get('shortName', node_id[-4:]) if node_info else node_id[-4:]
                long_name = node_info.get('user', {}).get('longName', '') if node_info else ''
                
                print("=" * 80)
                print(f"    💬 CONVERSATION WITH: {node_name} ({long_name})")
                print("=" * 80)
                
                # Show conversation history
                if conversation:
                    print("\n📝 MESSAGE HISTORY:")
                    print("-" * 80)
                    for msg in conversation[-20:]:  # Show last 20 messages
                        time_str = msg['time']
                        text = msg['text']
                        direction = msg['direction']
                        
                        if direction == 'sent':
                            # Messages we sent
                            print(f"[{time_str}] 📤 You: {text}")
                        else:
                            # Messages we received
                            signal_info = ""
                            if msg.get('snr') is not None:
                                signal_info = f" (SNR:{msg['snr']:.1f})"
                            print(f"[{time_str}] 📥 {node_name}{signal_info}: {text}")
                    print("-" * 80)
                else:
                    print("\n📭 No messages in this conversation yet")
                    print("-" * 80)
                
                # Show signal info if available
                if node_info:
                    last_heard = node_info.get('lastHeard', 0)
                    if last_heard:
                        age = time.time() - last_heard
                        age_str = f"{int(age/60)}m ago" if age > 60 else f"{int(age)}s ago"
                        print(f"\n📡 Last heard: {age_str}")
                        
                        if node_id in self.nodes_data:
                            snr = self.nodes_data[node_id].get('last_snr')
                            rssi = self.nodes_data[node_id].get('last_rssi')
                            if snr or rssi:
                                print(f"📶 Signal: SNR {snr:.1f}dB, RSSI {rssi}dBm")
                
                print("\nOptions:")
                print("  [R] - Send Reply")
                print("  [C] - Clear conversation history")
                print("  [B] - Back to node list")
                print("\n💡 Screen auto-refreshes every second for new messages")
                
                last_message_count = current_message_count
            
            # Check for keyboard input with 1 second timeout (use single key for simplicity)
            # Set terminal to cbreak for non-blocking input check
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                if select.select([sys.stdin], [], [], 1.0)[0]:
                    # Restore canonical mode for reading the choice
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    choice = sys.stdin.read(1).upper()
                    
                    if choice == 'B':
                        return
                    elif choice == 'R':
                        self.send_message_to_node(node_id, node_name)
                        # Force refresh after sending
                        last_message_count = -1
                    elif choice == 'C':
                        # Switch to line input for confirmation
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                        confirm = self.get_line_input("\nClear all messages with this node? (yes/no): ").strip().lower()
                        if confirm == 'yes':
                            self.conversations[node_id] = []
                            print("✅ Conversation cleared")
                            last_message_count = -1  # Force refresh
                            time.sleep(1)
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def send_new_message(self, node_list):
        """Send a message to a selected node"""
        self.clear_screen()
        print("=" * 80)
        print("    📤 SEND MESSAGE TO NODE")
        print("=" * 80)
        
        print("\nAvailable nodes:")
        for idx, node_id in enumerate(node_list, 1):
            node_info = self.get_node_info(node_id)
            node_name = node_info.get('user', {}).get('shortName', node_id[-4:]) if node_info else node_id[-4:]
            print(f"  {idx}. {node_name}")
        
        choice = self.get_line_input("\nSelect node number (or B to go back): ").strip()
        
        if choice.upper() == 'B':
            return
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(node_list):
                node_id = node_list[idx]
                node_info = self.get_node_info(node_id)
                node_name = node_info.get('user', {}).get('shortName', node_id[-4:]) if node_info else node_id[-4:]
                self.send_message_to_node(node_id, node_name)
    
    def send_message_to_node(self, node_id, node_name):
        """Send a text message to a specific node"""
        print(f"\n📝 Message to {node_name} (max 200 chars, or 'cancel' to abort):")
        message = self.get_line_input("> ").strip()
        
        if message.lower() == 'cancel' or not message:
            print("❌ Message cancelled")
            time.sleep(1)
            return
        
        if len(message) > 200:
            print("⚠️  Message too long, truncating to 200 characters...")
            message = message[:200]
        
        try:
            self.interface.sendText(message, destinationId=node_id, wantAck=True)
            self.stats['packets_tx'] += 1
            
            # Add to conversation
            if node_id not in self.conversations:
                self.conversations[node_id] = []
            
            self.conversations[node_id].append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'from': 'local',
                'to': node_id,
                'text': message,
                'direction': 'sent'
            })
            
            # Add to activity
            self.add_activity(f"📤 Sent message to {node_name}")
            
            self.logger.info(f"Sent message to {node_id} ({node_name}): {message}")
            print(f"✅ Message sent to {node_name}")
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            self.logger.error(f"Error sending message to {node_id}: {e}")
            time.sleep(2)
            
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
            if self.auto_send_enabled and self.connected and not self.auto_send_paused:
                elapsed = time.time() - self.last_send_time
                
                if elapsed >= self.auto_send_interval:
                    # Silent=True to suppress error messages in background thread
                    self.send_telemetry(silent=True)
            time.sleep(1)
    
    def display_auto_send_status(self):
        """Display status during auto-send mode"""
        self.clear_screen()
        self.print_header()
        
        # Show paused status if applicable
        if self.auto_send_paused:
            print("🛑 AUTO-SEND PAUSED (Send START to resume)")
        else:
            print("🔄 AUTO-SEND MODE ACTIVE")
        
        # Show chatbot status
        if self.chatbot and self.chatbot.is_available():
            if self.chatbot_enabled and self.chatbot.is_loaded():
                if self.chatbot_thinking:
                    print("🤖 ChatBot: ENABLED ✅ | 💭 Thinking...")
                else:
                    print("🤖 ChatBot: ENABLED ✅")
            else:
                print("🤖 ChatBot: OFF")
        
        print("=" * 120)
        
        # Build message panel for right side (40 chars wide)
        message_lines = []
        message_lines.append("")
        message_lines.append("")
        message_lines.append("💬 RECENT MESSAGES (Last 10):")
        message_lines.append("-" * 40)
        
        if self.recent_messages:
            for msg in self.recent_messages[-10:]:  # Last 10 messages
                timestamp = msg['time']
                from_name = msg['from_name'][:8]  # Truncate name
                text = msg['text']
                
                # Message header line with signal
                signal_info = ""
                if msg['snr'] is not None:
                    signal_info = f"SNR:{msg['snr']:.1f}"
                if msg['rssi'] is not None:
                    if signal_info:
                        signal_info += f",{msg['rssi']}dBm"
                    else:
                        signal_info = f"{msg['rssi']}dBm"
                
                header = f"[{timestamp}] {from_name}"
                if signal_info:
                    header += f" {signal_info}"
                
                message_lines.append(f"   {header}")
                
                # Message text - wrap if needed
                max_text_width = 37
                if len(text) <= max_text_width:
                    message_lines.append(f"      {text}")
                else:
                    # Split long messages
                    words = text.split()
                    line = "      "
                    for word in words:
                        if len(line) + len(word) + 1 <= max_text_width + 6:
                            line += word + " "
                        else:
                            message_lines.append(line)
                            line = "      " + word + " "
                    if line.strip():
                        message_lines.append(line)
                
                message_lines.append("")
        else:
            message_lines.append("   No messages yet")
        
        # Add sent messages section
        message_lines.append("")
        message_lines.append("📤 SENT MESSAGES (Last 2):")
        message_lines.append("-" * 40)
        
        # Collect sent messages from all conversations
        sent_msgs = []
        for node_id, conv in self.conversations.items():
            for msg in conv:
                if msg.get('direction') == 'sent':
                    sent_msgs.append({
                        'time': msg['time'],
                        'to': msg['to'],
                        'text': msg['text']
                    })
        
        # Sort by time and get last 2
        sent_msgs.sort(key=lambda x: x['time'])
        recent_sent = sent_msgs[-2:] if len(sent_msgs) > 2 else sent_msgs
        
        if recent_sent:
            for msg in recent_sent:
                timestamp = msg['time']
                to_node = msg['to'][-4:]  # Last 4 chars of node ID
                text = msg['text']
                
                # Message header line
                header = f"[{timestamp}] To:{to_node}"
                message_lines.append(f"   {header}")
                
                # Message text - wrap if needed
                max_text_width = 37
                if len(text) <= max_text_width:
                    message_lines.append(f"      {text}")
                else:
                    # Split long messages
                    words = text.split()
                    line = "      "
                    for word in words:
                        if len(line) + len(word) + 1 <= max_text_width + 6:
                            line += word + " "
                        else:
                            message_lines.append(line)
                            line = "      " + word + " "
                    if line.strip():
                        message_lines.append(line)
                
                message_lines.append("")
        else:
            message_lines.append("   No messages sent yet")
        
        # Show all connected nodes with signal strength
        left_content = []
        if self.interface and hasattr(self.interface, 'nodes') and self.interface.nodes:
            # Filter nodes heard in last 30 minutes
            recent_cutoff = time.time() - 1800  # 30 minutes
            recent_nodes = []
            
            for node_id, node in self.interface.nodes.items():
                last_heard = node.get('lastHeard', 0)
                if last_heard > recent_cutoff:
                    recent_nodes.append((last_heard, node_id, node))
            
            # Sort by last heard (most recent first)
            recent_nodes.sort(reverse=True)
            
            left_content.append(f"\n📡 MESH NETWORK - ACTIVE NODES (Last 30min): {len(recent_nodes)}")
            left_content.append("=" * 75)
            left_content.append(f"{'Node':6s} {'Age':>6s}  {'SNR':>10s}  {'RSSI':>10s}")
            left_content.append("-" * 75)
            
            # Show top 5 most recently seen nodes
            for last_heard, node_id, node in recent_nodes[:5]:
                user = node.get('user', {})
                short_name = user.get('shortName', node_id[-4:])
                
                # Get signal data
                snr = None
                rssi = None
                if node_id in self.nodes_data:
                    snr = self.nodes_data[node_id].get('last_snr')
                    rssi = self.nodes_data[node_id].get('last_rssi')
                
                # Calculate time since last heard
                age = time.time() - last_heard
                if age < 60:
                    age_str = f"{int(age)}s"
                elif age < 3600:
                    age_str = f"{int(age/60)}m"
                else:
                    age_str = f"{int(age/3600)}h"
                
                # Build display line with proper spacing
                snr_str = f"{snr:.1f}dB" if snr is not None else "-"
                rssi_str = f"{rssi}dBm" if rssi is not None else "-"
                left_content.append(f"{short_name:6s} {age_str:>6s}  {snr_str:>10s}  {rssi_str:>10s}")
            
            left_content.append("=" * 75)
        
        # Get current device telemetry from interface.nodes
        current_telemetry = self.get_current_device_telemetry()
        
        # Fall back to telemetry_history if current not available
        if not current_telemetry and self.telemetry_history:
            current_telemetry = self.telemetry_history[-1]
        
        # Show sensor data if available
        if current_telemetry:
            temp = current_telemetry.get('temperature')
            humidity = current_telemetry.get('humidity')
            pressure = current_telemetry.get('pressure')
            
            if temp is not None or humidity is not None or pressure is not None:
                left_content.append("\n🌡️  LOCAL SENSOR DATA:")
                if temp is not None:
                    temp_f = (temp * 9/5) + 32
                    left_content.append(f"   Temperature: {temp_f:.1f}°F ({temp:.1f}°C)")
                if humidity is not None:
                    left_content.append(f"   Humidity: {humidity:.1f}%")
                if pressure is not None:
                    left_content.append(f"   Pressure: {pressure:.1f} hPa")
            
            # Device metrics
            battery = current_telemetry.get('battery')
            voltage = current_telemetry.get('voltage')
            if battery is not None or voltage is not None:
                left_content.append("\n🔋 DEVICE STATUS:")
                if battery is not None:
                    if battery == 101:
                        left_content.append("   Power: USB/Solar")
                    else:
                        left_content.append(f"   Battery: {battery}%")
                if voltage is not None:
                    left_content.append(f"   Voltage: {voltage:.2f}V")
        else:
            left_content.append("\n⚠️  No telemetry data available yet")
        
        # Show target nodes
        if self.selected_nodes:
            left_content.append(f"\n📡 TARGET NODES ({len(self.selected_nodes)}):")
            left_content.append("-" * 75)
            
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
                    left_content.append(f"\n  {name} ({node_id})")
                    left_content.append(f"  └─ Last heard: {age_str}")
                    
                    # Show signal if we have recent data
                    if node_id in self.nodes_data and 'last_snr' in self.nodes_data[node_id]:
                        snr = self.nodes_data[node_id].get('last_snr')
                        rssi = self.nodes_data[node_id].get('last_rssi')
                        if snr is not None:
                            left_content.append(f"  └─ SNR: {snr:.1f} dB")
                        if rssi is not None:
                            left_content.append(f"  └─ RSSI: {rssi} dBm")
                    
                    # Show message acknowledgment status
                    if node_id in self.message_acks:
                        ack_info = self.message_acks[node_id]
                        status = ack_info['ack_status']
                        timestamp = ack_info['timestamp']
                        
                        if status == 'ACK':
                            left_content.append(f"  └─ Last msg: ✅ ACK at {timestamp}")
                        elif status == 'PENDING':
                            left_content.append(f"  └─ Last msg: ⏳ PENDING since {timestamp}")
                        elif status.startswith('NAK'):
                            left_content.append(f"  └─ Last msg: ❌ {status} at {timestamp}")
                    else:
                        left_content.append(f"  └─ Last msg: No messages sent yet")
                else:
                    left_content.append(f"\n  {node_id}")
                    left_content.append(f"  └─ Status: Not found in database")
        
        # Show recent activity
        if self.recent_activity:
            left_content.append(f"\n📊 RECENT ACTIVITY (Last 10):")
            left_content.append("-" * 75)
            # Show all items (continuous scroll)
            for activity in self.recent_activity:
                left_content.append(f"   {activity}")
        
        # Print left content alongside message panel
        max_lines = max(len(left_content), len(message_lines))
        for i in range(max_lines):
            left_line = left_content[i] if i < len(left_content) else ""
            right_line = message_lines[i] if i < len(message_lines) else " " * 40
            print(f"{left_line:<75s}  {right_line}")
        
        # Show countdown or paused status
        if self.auto_send_paused:
            print(f"\n⏱️  AUTO-SEND PAUSED - Send START command to resume")
        else:
            elapsed = time.time() - self.last_send_time
            remaining = max(0, int(self.auto_send_interval - elapsed))
            print(f"\n⏱️  Next send in: {remaining} seconds")
        print("\n💡 Press (M) for Menu | (S) to Send Message | Ctrl+C to Exit")
        print("=" * 120)
            
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
            self.get_single_key("Press any key to continue...")
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
                self.get_single_key("Press any key to continue...")
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
                            self.get_single_key("\nPress any key to continue...")
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
                        choice = self.get_line_input("Enter number to toggle, or letter: ").strip().upper()
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
                
                choice = self.get_single_key("Enter choice: ").strip()
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
                        interval = int(self.get_line_input("Enter interval in seconds (min 30): "))
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
        self.get_single_key("Press any key to continue...")
    
    def show_command_help(self):
        """Display all available command words and their responses"""
        self.clear_screen()
        self.print_header()
        
        print("📋 AVAILABLE COMMAND WORDS")
        print("=" * 80)
        print()
        print("Commands can be sent by target nodes to control this station:")
        print()
        print("1️⃣  STOP")
        print("   └─ Pauses automatic telemetry sending")
        print("   └─ Response: '✅ AUTO-SEND STOPPED'")
        print()
        print("2️⃣  START")
        print("   └─ Resumes automatic telemetry sending")
        print("   └─ Response: '✅ AUTO-SEND STARTED'")
        print()
        print("3️⃣  FREQ##")
        print("   └─ Changes telemetry send interval (30-3600 seconds)")
        print("   └─ Example: FREQ60 sets interval to 60 seconds")
        print("   └─ Response: '✅ FREQ set to ##s (was XXs)'")
        print("   └─ Invalid: '❌ FREQ must be 30-3600 seconds'")
        print()
        print("4️⃣  RADIOCHECK")
        print("   └─ Requests signal strength information")
        print("   └─ Response: '📡 RADIOCHECK: SNR X.XdB | RSSI XdBm | Age Xs'")
        print("   └─ Shows current radio link quality from requesting node")
        print()
        print("5️⃣  WEATHERCHECK")
        print("   └─ Requests current telemetry/weather data")
        print("   └─ Response: '🌡️  WEATHERCHECK: [telemetry data]'")
        print("   └─ Includes temperature, humidity, pressure if available")
        print()
        print("6️⃣  KEYWORDS")
        print("   └─ Requests list of available commands")
        print("   └─ Response: '📋 Available: STOP START FREQ## RADIOCHECK WEATHERCHECK KEYWORDS'")
        print("   └─ Useful for discovering what commands this station supports")
        print()
        
        if self.chatbot and self.chatbot.is_available():
            print("7️⃣  CHATBOTON")
            print("   └─ Enables the AI chatbot")
            print("   └─ Loads TinyLlama model and begins responding to messages")
            print("   └─ Response: Greeting message + '✅ CHATBOT ENABLED'")
            print()
            print("8️⃣  CHATBOTOFF")
            print("   └─ Disables the AI chatbot")
            print("   └─ Unloads model and frees memory")
            print("   └─ Response: '✅ CHATBOT DISABLED'")
            print()
        
        print("-" * 80)
        print("⚙️  NOTES:")
        print("   • Commands only accepted from selected target nodes")
        print("   • All responses are automatic (no manual intervention needed)")
        print("   • Responses sent without ACK to reduce mesh traffic")
        print("   • Commands and responses logged to activity feed")
        print("   • Command history visible in conversation view")
        print()
        self.get_single_key("Press any key to continue...")
    
    def configure_chatbot(self):
        """Configure chatbot settings"""
        while True:
            self.clear_screen()
            self.print_header()
            
            print("🤖 CHATBOT CONFIGURATION")
            print("=" * 80)
            print()
            
            # Check availability
            if not self.chatbot or not self.chatbot.is_available():
                print("❌ ChatBot not available")
                print()
                print("To enable chatbot:")
                print("  1. Install: pip install llama-cpp-python")
                print("  2. Download model: python download_model.py")
                print("  3. Restart terminal monitor")
                print()
                self.get_single_key("Press any key to return...")
                return
            
            # Show status
            status = self.chatbot.get_status()
            print(f"Backend: {status['backend']}")
            print(f"Model: {status['model_path']}")
            print(f"Model exists: {'✅' if status['model_exists'] else '❌'}")
            print(f"Status: {'🟢 ENABLED' if self.chatbot_enabled and status['loaded'] else '🔴 DISABLED'}")
            print(f"Greeting: {self.chatbot_greeting}")
            print()
            print("-" * 80)
            print()
            print("OPTIONS:")
            print("1. Enable ChatBot")
            print("2. Disable ChatBot")
            print("3. Test ChatBot")
            print("4. Change Greeting")
            print("5. ChatBot Info")
            print("B. Back to Main Menu")
            print()
            
            choice = self.get_single_key("Enter choice: ").strip().upper()
            
            if choice == '1':
                # Enable chatbot
                if not status['model_exists']:
                    print("\n❌ Model file not found!")
                    print(f"Path: {self.chatbot_model_path}")
                    print("\nDownload with: python download_model.py")
                    time.sleep(3)
                elif self.chatbot_enabled and status['loaded']:
                    print("\n⚠️  ChatBot is already enabled")
                    time.sleep(1.5)
                else:
                    print("\n🔄 Loading model...")
                    if self.chatbot.load_model():
                        self.chatbot_enabled = True
                        self.save_config()
                        print("✅ ChatBot enabled successfully!")
                        time.sleep(1.5)
                    else:
                        print("❌ Failed to load model")
                        time.sleep(2)
                        
            elif choice == '2':
                # Disable chatbot
                if not self.chatbot_enabled:
                    print("\n⚠️  ChatBot is already disabled")
                    time.sleep(1.5)
                else:
                    self.chatbot.unload_model()
                    self.chatbot_enabled = False
                    self.save_config()
                    print("\n✅ ChatBot disabled")
                    time.sleep(1.5)
                    
            elif choice == '3':
                # Test chatbot
                if not self.chatbot_enabled or not status['loaded']:
                    print("\n⚠️  Enable ChatBot first")
                    time.sleep(1.5)
                else:
                    print("\n🧪 Testing ChatBot...")
                    print()
                    test_msg = "Hello, can you hear me?"
                    print(f"Test message: {test_msg}")
                    print("Generating response...")
                    response = self.chatbot.generate_response(test_msg)
                    if response:
                        print(f"\n🤖 Response: {response}")
                    else:
                        print("\n❌ No response generated")
                    print()
                    self.get_single_key("Press any key to continue...")
                    
            elif choice == '4':
                # Change greeting
                print("\n💬 Current greeting:")
                print(f"   {self.chatbot_greeting}")
                print()
                new_greeting = self.get_line_input("Enter new greeting (or blank to cancel): ").strip()
                if new_greeting:
                    self.chatbot_greeting = new_greeting
                    if self.chatbot:
                        self.chatbot.set_greeting(new_greeting)
                    self.save_config()
                    print("✅ Greeting updated")
                    time.sleep(1.5)
                    
            elif choice == '5':
                # Show info
                print("\n📖 CHATBOT INFORMATION")
                print("=" * 80)
                print()
                print("Model: TinyLlama-1.1B-Chat (Q4_K_M quantization)")
                print("Size: ~638 MB")
                print("Speed: 4-7 seconds per response on Pi5")
                print("Memory: ~1GB RAM when loaded")
                print()
                print("Features:")
                print("  • Responds to all non-keyword messages from target nodes")
                print("  • Keywords (STOP, START, etc.) always take priority")
                print("  • Responses limited to 200 characters for Meshtastic")
                print("  • Fully local AI - no cloud/internet needed")
                print("  • Apache 2.0 license - completely open source")
                print()
                print("Control via mesh:")
                print("  • Send CHATBOTON to enable remotely")
                print("  • Send CHATBOTOFF to disable remotely")
                print()
                self.get_single_key("Press any key to continue...")
                
            elif choice == 'B':
                return
    
    def run_auto_send_dashboard(self):
        """Run the auto-send dashboard with live updates"""
        import select
        
        # Send immediately on entry
        self.clear_screen()
        self.print_header()
        print("\n📤 Sending initial telemetry...")
        self.send_telemetry()
        time.sleep(1)
        
        # Send keyword command information
        print("📋 Sending keyword command info...")
        self.send_keyword_info()
        time.sleep(2)
        
        # Display loop with status updates
        try:
            last_display = 0
            display_interval = 1  # Update every 1 second
            
            # Set terminal to cbreak mode for single character input
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                
                while True:
                    # Update display every 1 second
                    if time.time() - last_display >= display_interval:
                        self.display_auto_send_status()
                        last_display = time.time()
                    
                    # Check for key press with short timeout
                    if select.select([sys.stdin], [], [], 0.5)[0]:
                        key = sys.stdin.read(1).upper()
                        
                        if key == 'M':
                            self.logger.info("User pressed M to return to menu")
                            print("\nReturning to menu...")
                            time.sleep(1)
                            return
                        elif key == 'S':
                            self.logger.info("User pressed S to send message")
                            self.message_interface()
                            self.clear_screen()
                            self.print_header()
                    
                    time.sleep(0.5)
            finally:
                # Restore terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        except KeyboardInterrupt:
            # Return to menu on Ctrl+C
            print("\nReturning to menu...")
            time.sleep(1)
        
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
            print("5. View Command Words")
            print("6. Configure ChatBot")
            print("7. Start Auto-Send")
            print("8. Stop Auto-Send")
            print("9. View Dashboard")
            print("0. Exit")
            print()
            
            choice = self.get_single_key("Enter choice: ").strip()
            
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
                self.show_command_help()
            elif choice == '6':
                self.configure_chatbot()
            elif choice == '7':
                # Start auto-send dashboard mode
                if not self.auto_send_enabled:
                    print("\n⚠️  Auto-send is disabled. Enable it in Configure Auto-Send first.")
                    time.sleep(2)
                elif not self.selected_nodes:
                    print("\n⚠️  No nodes selected. Configure nodes in Auto-Send settings first.")
                    time.sleep(2)
                else:
                    print("\nStarting auto-send...")
                    time.sleep(1)
                    # Run the auto-send dashboard loop
                    self.run_auto_send_dashboard()
            elif choice == '8':
                # Stop auto-send
                if self.auto_send_enabled:
                    self.auto_send_enabled = False
                    self.save_config()
                    print("\n✅ Auto-send stopped")
                else:
                    print("\n⚠️  Auto-send is already disabled")
                time.sleep(1.5)
            elif choice == '9':
                # View dashboard without auto-send
                print("\nOpening dashboard view...")
                time.sleep(1)
                self.display_auto_send_status()
                self.get_single_key("\nPress any key to return to menu...")
            elif choice == '0':
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
        
        # Initialize last_send_time to prevent immediate send from worker
        terminal.last_send_time = time.time()
        
        # Start auto-send worker thread
        worker_thread = threading.Thread(target=terminal.auto_send_worker, daemon=True)
        worker_thread.start()
        terminal.logger.info("Auto-send worker thread started")
        
        # Send immediately on startup
        terminal.clear_screen()
        terminal.print_header()
        print("\n📤 Sending initial telemetry...")
        terminal.send_telemetry()
        time.sleep(1)
        
        # Send keyword command information
        print("📋 Sending keyword command info...")
        terminal.send_keyword_info()
        time.sleep(2)
        
        # Display loop with status updates
        try:
            import select
            last_display = 0
            display_interval = 1  # Update every 1 second
            
            # Set terminal to cbreak mode for single character input
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                
                while True:
                    # Update display every 1 second
                    if time.time() - last_display >= display_interval:
                        terminal.display_auto_send_status()
                        last_display = time.time()
                    
                    # Check for key press with short timeout
                    if select.select([sys.stdin], [], [], 0.5)[0]:
                        key = sys.stdin.read(1).upper()
                        
                        if key == 'M':
                            terminal.logger.info("User pressed M to enter menu")
                            print("\nEntering menu...")
                            time.sleep(1)
                            break
                        elif key == 'S':
                            terminal.logger.info("User pressed S to send message")
                            terminal.message_interface()
                            terminal.clear_screen()
                            terminal.print_header()
                    
                    time.sleep(0.5)
            finally:
                # Restore terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        except KeyboardInterrupt:
            # Ctrl+C will be handled by signal handler
            pass
    
    # Show main menu
    terminal.main_menu()

if __name__ == "__main__":
    main()
