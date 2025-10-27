#!/usr/bin/env python3
"""
Simple test script to test BLE connection without the full application
"""
import logging
import sys
import meshtastic.ble_interface

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_ble_connection(address="F0:9E:9E:75:7A:8D"):
    """Test BLE connection with the exact parameters"""
    try:
        print(f"Testing BLE connection to: {address}")
        
        # Create BLE interface with exact signature
        print("Creating BLEInterface...")
        interface = meshtastic.ble_interface.BLEInterface(
            address=address,
            noProto=False,
            debugOut=None,
            noNodes=False
        )
        
        print("BLEInterface created successfully!")
        print(f"Interface object: {interface}")
        
        # Test basic info
        if hasattr(interface, 'myInfo'):
            print(f"Device info available: {interface.myInfo}")
        else:
            print("Device info not yet available")
            
        # Close the interface
        if hasattr(interface, 'close'):
            interface.close()
            print("Connection closed")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        print(f"Exception type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else "F0:9E:9E:75:7A:8D"
    success = test_ble_connection(address)
    sys.exit(0 if success else 1)