"""
Minimal BrainFlow script to connect and collect data from a Muse 2 device.
Prints the final sampling rate obtained.
"""

import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowPresets


def main():
    # Initialize connection parameters
    params = BrainFlowInputParams()
    
    # Optionally specify device serial number (e.g., "Muse-XXXX")
    # If None, will connect to the first available Muse 2 device
    # params.serial_number = "Muse-XXXX"  # Uncomment and set if needed
    
    # Create board instance for Muse 2
    board = BoardShim(BoardIds.MUSE_2_BOARD, params)
    
    try:
        print("Connecting to Muse 2 device...")
        board.prepare_session()
        
        print("Configuring board (enabling PPG)...")
        board.config_board("p50")  # Enable PPG in ANCILLARY for Muse 2
        
        print("Starting data stream...")
        board.start_stream()
        
        # Collect data for a few seconds
        print("Collecting data for 5 seconds...")
        time.sleep(5)
        
        # Get EEG data
        print("Retrieving data...")
        data = board.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
        
        if data.size == 0:
            print("No data collected!")
            return
        
        # Extract timestamps (last column in BrainFlow data)
        timestamps = data[-1, :]
        
        if len(timestamps) < 2:
            print(f"Not enough data points ({len(timestamps)}). Need at least 2.")
            return
        
        # Calculate sampling rate from timestamps
        # Sort timestamps to handle any out-of-order samples
        sorted_timestamps = np.sort(timestamps)
        time_diffs = np.diff(sorted_timestamps)
        
        # Use only positive differences (in seconds)
        positive_diffs = time_diffs[time_diffs > 0]
        
        if len(positive_diffs) > 0:
            avg_interval = np.mean(positive_diffs)
            sampling_rate = 1.0 / avg_interval
            print(f"\n{'='*60}")
            print(f"Data Collection Complete")
            print(f"{'='*60}")
            print(f"Total samples collected: {len(timestamps)}")
            print(f"Average time interval: {avg_interval*1000:.2f} ms")
            print(f"Final sampling rate: {sampling_rate:.2f} Hz")
            print(f"{'='*60}\n")
        else:
            print("Could not calculate sampling rate (no valid time differences)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        try:
            board.stop_stream()
            board.release_session()
            print("Disconnected from device.")
        except:
            pass


if __name__ == "__main__":
    main()

