#!/usr/bin/env python3
"""
Bluetooth Scanner Test Script
Tests BLE scanning functionality to see what devices are visible
"""

import asyncio
import sys
from datetime import datetime

try:
    from bleak import BleakScanner
except ImportError:
    print("ERROR: bleak library is required for BLE scanning.")
    print("Install it with: pip install bleak")
    sys.exit(1)


async def scan_devices(timeout_sec: float = 10.0, filter_muse: bool = False):
    """
    Scan for BLE devices
    
    Args:
        timeout_sec: How long to scan for devices
        filter_muse: If True, only show Muse devices
    """
    print(f"{'='*60}")
    print(f"Bluetooth BLE Scanner Test")
    print(f"{'='*60}")
    print(f"Scan timeout: {timeout_sec} seconds")
    print(f"Filter for Muse devices: {filter_muse}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    print("Scanning for BLE devices...\n")
    
    try:
        # Discover devices
        devices = await BleakScanner.discover(timeout=timeout_sec)
        
        if not devices:
            print("❌ No BLE devices found.")
            print("\nTroubleshooting tips:")
            print("  • Make sure Bluetooth is enabled on your computer")
            print("  • Ensure devices are in pairing/discoverable mode")
            print("  • Try moving devices closer to your computer")
            print("  • For Muse headbands: ensure LED is on and not connected to another device")
            return []
        
        # Filter Muse devices if requested
        if filter_muse:
            devices = [d for d in devices if d.name and d.name.startswith("Muse-")]
        
        # Display results
        print(f"✅ Found {len(devices)} device(s):\n")
        print(f"{'No.':<4} {'Device Name':<30} {'MAC Address':<20} {'RSSI':<6}")
        print(f"{'-'*4} {'-'*30} {'-'*20} {'-'*6}")
        
        device_list = []
        for idx, device in enumerate(devices, 1):
            name = device.name if device.name else "(No Name)"
            address = device.address
            rssi = device.rssi if hasattr(device, 'rssi') and device.rssi else "N/A"
            
            print(f"{idx:<4} {name:<30} {address:<20} {rssi:<6}")
            device_list.append({
                'name': name,
                'address': address,
                'rssi': rssi
            })
        
        print(f"\n{'-'*60}")
        
        # Show Muse-specific devices
        muse_devices = [d for d in devices if d.name and d.name.startswith("Muse-")]
        if muse_devices:
            print(f"\n🧠 Muse devices found: {len(muse_devices)}")
            for device in muse_devices:
                print(f"   • {device.name}")
        elif not filter_muse:
            print("\n🧠 No Muse devices found")
            print("   (Muse device names should start with 'Muse-')")
        
        return device_list
        
    except Exception as e:
        print(f"❌ Error during scanning: {e}")
        print(f"\nError type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """Main function to run the BLE scanner"""
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Bluetooth BLE scanner to see what devices are visible",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_bluetooth_scanner.py                    # Scan all devices for 10 seconds
  python test_bluetooth_scanner.py --timeout 5        # Scan for 5 seconds
  python test_bluetooth_scanner.py --muse-only        # Only show Muse devices
  python test_bluetooth_scanner.py --continuous       # Continuous scanning (Ctrl+C to stop)
        """
    )
    
    parser.add_argument(
        '--timeout',
        type=float,
        default=10.0,
        help='Scan timeout in seconds (default: 10.0)'
    )
    
    parser.add_argument(
        '--muse-only',
        action='store_true',
        help='Only show Muse devices (names starting with "Muse-")'
    )
    
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Continuous scanning mode (press Ctrl+C to stop)'
    )
    
    args = parser.parse_args()
    
    # Run scanner
    if args.continuous:
        print("🔄 Continuous scanning mode (press Ctrl+C to stop)\n")
        try:
            scan_count = 1
            while True:
                print(f"\n{'#'*60}")
                print(f"Scan #{scan_count}")
                print(f"{'#'*60}\n")
                asyncio.run(scan_devices(timeout_sec=args.timeout, filter_muse=args.muse_only))
                scan_count += 1
                print("\nWaiting 2 seconds before next scan...")
                import time
                time.sleep(2)
        except KeyboardInterrupt:
            print("\n\n⏹️  Scanning stopped by user")
    else:
        # Single scan
        asyncio.run(scan_devices(timeout_sec=args.timeout, filter_muse=args.muse_only))
    
    print("\n✅ Scan complete!")


if __name__ == "__main__":
    main()

