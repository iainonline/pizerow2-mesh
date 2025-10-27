#!/usr/bin/env python3
"""
Test script for Meshtastic Bluetooth Controller
Run this to verify installation and basic functionality
"""

import sys
import os

def test_python_version():
    """Test if Python version is compatible"""
    print("Testing Python version...")
    if sys.version_info >= (3, 9):
        print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} is compatible")
        return True
    else:
        print(f"✗ Python {sys.version_info.major}.{sys.version_info.minor} is not compatible (need 3.9+)")
        return False

def test_imports():
    """Test if required modules can be imported"""
    print("\nTesting imports...")
    modules = {
        'meshtastic': 'Meshtastic Python API',
        'bleak': 'Bluetooth Low Energy library', 
        'psutil': 'System utilities',
        'pubsub': 'Publisher-subscriber messaging'
    }
    
    success = True
    for module, description in modules.items():
        try:
            __import__(module)
            print(f"✓ {module} - {description}")
        except ImportError as e:
            print(f"✗ {module} - {description} (Error: {e})")
            success = False
    
    return success

def test_bluetooth():
    """Test if Bluetooth is available"""
    print("\nTesting Bluetooth availability...")
    try:
        import subprocess
        result = subprocess.run(['bluetoothctl', 'show'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Bluetooth controller is accessible")
            return True
        else:
            print("✗ Bluetooth controller not accessible")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"✗ Bluetooth test failed: {e}")
        return False

def test_file_structure():
    """Test if all required files exist"""
    print("\nTesting file structure...")
    required_files = [
        'main.py',
        'meshtastic_comm.py', 
        'start.sh',
        'requirements.txt',
        'config.json',
        'README.md'
    ]
    
    success = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file} exists")
        else:
            print(f"✗ {file} missing")
            success = False
    
    return success

def test_config():
    """Test configuration file"""
    print("\nTesting configuration...")
    try:
        import json
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        required_keys = ['message_frequency', 'from_node', 'to_node', 'ble_address', 'auto_scan']
        missing_keys = [key for key in required_keys if key not in config]
        
        if not missing_keys:
            print("✓ Configuration file is valid")
            print(f"  - Message frequency: {config['message_frequency']} seconds")
            print(f"  - From node: {config['from_node']}")
            print(f"  - To node: {config['to_node']}")
            return True
        else:
            print(f"✗ Configuration missing keys: {missing_keys}")
            return False
            
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Meshtastic Bluetooth Controller - System Test")
    print("=" * 60)
    
    tests = [
        ('Python Version', test_python_version),
        ('File Structure', test_file_structure), 
        ('Configuration', test_config),
        ('Python Imports', test_imports),
        ('Bluetooth', test_bluetooth)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:<20} : {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! The system is ready to use.")
        print("\nNext steps:")
        print("1. Run: ./start.sh --setup    (if not done already)")
        print("2. Run: ./start.sh           (to start the application)")
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please fix the issues above.")
        print("\nTroubleshooting:")
        print("- Run: ./start.sh --setup   (to install dependencies)")
        print("- Check Bluetooth service: sudo systemctl status bluetooth")
        print("- Verify user permissions:  groups | grep bluetooth")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)