#!/usr/bin/env python3
"""
Set Meshtastic telemetry environment interval to 60 seconds
"""
import subprocess
import sys

def set_telemetry_interval():
    """Execute meshtastic command to set both telemetry intervals to 60 seconds on Heltec V3 via USB"""
    try:
        # Set both environment and device telemetry intervals to 60 seconds
        # This sends telemetry data over the mesh every 60 seconds instead of the default 1800 (30 minutes)
        result = subprocess.run(
            ['/home/iain/Meshtastic/venv/bin/meshtastic', 
             '--set', 'telemetry.environment_update_interval', '60',
             '--set', 'telemetry.device_update_interval', '60',
             '--port', '/dev/ttyUSB0'],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("Command executed successfully!")
        print(result.stdout)
        
        if result.stderr:
            print("Warnings/Info:", result.stderr)
            
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        if e.stdout:
            print(f"Output: {e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"Error output: {e.stderr}", file=sys.stderr)
        return 1
        
    except FileNotFoundError:
        print("Error: 'meshtastic' command not found. Make sure it's installed in the virtual environment.", file=sys.stderr)
        return 1
        
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(set_telemetry_interval())
