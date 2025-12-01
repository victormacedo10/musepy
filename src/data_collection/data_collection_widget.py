"""
Data Collection Widget - Main interface for EEG data acquisition
"""

import pickle
import time
import logging
import csv
import io
import os
from pathlib import Path
from datetime import datetime

import numpy as np
from ..utils import pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PySide6.QtCore import QTimer

# BrainFlow imports
from brainflow.board_shim import BrainFlowPresets

# Local imports
from .connect_device_widget import ConnectDeviceWidget
from .record_data_widget import RecordDataWidget
from .view_recording_widget import ViewRecordingWidget
from .acquisition_plot_widget import AcquisitionPlotWidget


class DataCollectionWidget(QWidget):
    """Main data collection interface widget"""
    
    def __init__(self, demo_mode=False, parent=None):
        super().__init__(parent)
        self.demo_mode = demo_mode
        self.parent = parent
        
        # Initialize state
        self.board = None
        self.is_connected = False
        self.is_recording = False
        self.recorded_data = {}
        self.stream_data = pd.DataFrame()
        self.timestamp_start = None  # Single timestamp reference in seconds
        self.stream_timer = None
        
        # CSV file handles for incremental writing
        self.csv_files = {}
        self.csv_writers = {}
        self.csv_headers_written = {}
        self.recording_folder = None
        self.recording_filename = None
        
        # Setup logging
        self.setup_logging()
        
        # Setup UI
        self.setup_ui()
        # Don't call setup_connections here - it will be called after control panels are set up
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main content area - only plot
        self.acquisition_plot = AcquisitionPlotWidget(parent=self)
        layout.addWidget(self.acquisition_plot)
        
        # Control panels will be added to the left panel by the main app
        # Don't call setup_control_panels here - it will be called by the main app
    
    def setup_logging(self):
        """Setup logging to file in tmp folder inside data folder"""
        try:
            from pathlib import Path
            import sys
            
            # Get data folder path - try to get it from record_data_widget if available
            # Otherwise try to load saved preference, then use default location
            data_folder = None
            if hasattr(self, 'record_data_widget') and self.record_data_widget:
                try:
                    data_folder = Path(self.record_data_widget.get_data_folder())
                except:
                    pass
            
            # If not available, try to load saved preference
            if data_folder is None or not data_folder.exists():
                try:
                    # Import get_config_path from record_data_widget (module-level function)
                    from .record_data_widget import get_config_path
                    config_path = get_config_path()
                    prefs_file = config_path / "data_folder_preference.txt"
                    if prefs_file.exists():
                        with open(prefs_file, 'r', encoding='utf-8') as f:
                            saved_path = f.read().strip()
                        if saved_path and Path(saved_path).exists():
                            data_folder = Path(saved_path)
                except Exception:
                    pass
            
            # If still not available, use default data folder location (same as RecordDataWidget)
            if data_folder is None or not data_folder.exists():
                # Use same logic as RecordDataWidget.get_resource_path()
                if getattr(sys, 'frozen', False):
                    # Running as compiled executable - resources are in the bundle
                    resource_path = Path(sys._MEIPASS)
                else:
                    # Running as script
                    resource_path = Path(__file__).parent.parent.parent
                data_folder = resource_path / "data"
            
            # Create tmp folder inside data folder
            tmp_folder = data_folder / "tmp"
            tmp_folder.mkdir(parents=True, exist_ok=True)
            
            # Create log file with timestamp
            log_filename = f"musepy_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            log_path = tmp_folder / log_filename
            
            # Configure logger
            self.logger = logging.getLogger('MusePy.DataCollection')
            self.logger.setLevel(logging.DEBUG)
            
            # Remove existing handlers to avoid duplicates
            self.logger.handlers = []
            
            # Create file handler
            file_handler = logging.FileHandler(log_path, mode='a')
            file_handler.setLevel(logging.DEBUG)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(file_handler)
            
            # Also add console handler for immediate feedback
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            self.logger.info(f"Logging initialized. Log file: {log_path}")
            self.logger.info(f"Demo mode: {self.demo_mode}")
            
        except Exception as e:
            print(f"Failed to setup logging: {e}")
            # Create a basic logger that writes to console only
            self.logger = logging.getLogger('MusePy.DataCollection')
            self.logger.setLevel(logging.DEBUG)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(console_handler)
            self.logger.error(f"Failed to setup file logging: {e}")
        
    def setup_control_panels(self):
        """Setup control panels in the left panel"""
        # Get the control panel from the main app
        if hasattr(self.parent, 'control_panel'):
            # Clear existing widgets
            while self.parent.control_panel.layout().count():
                item = self.parent.control_panel.layout().takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            
            # Connect Device panel
            self.connect_device_widget = ConnectDeviceWidget(parent=self)
            self.parent.control_panel.layout().addWidget(self.connect_device_widget)
            
            # Record Data panel
            self.record_data_widget = RecordDataWidget(parent=self)
            self.parent.control_panel.layout().addWidget(self.record_data_widget)
            
            # View Recording panel
            self.view_recording_widget = ViewRecordingWidget(parent=self)
            self.parent.control_panel.layout().addWidget(self.view_recording_widget, 1)  # Give it stretch factor 1
            
            # Remove the stretch since View Recording will expand
            
            # Setup connections after widgets are created
            self.setup_connections()
        
    def setup_connections(self):
        """Setup signal connections between widgets"""
        # Connect device signals
        self.connect_device_widget.device_connected.connect(self.on_device_connected)
        self.connect_device_widget.device_disconnected.connect(self.on_device_disconnected)
        
        # Record data signals
        self.record_data_widget.recording_started.connect(self.on_recording_started)
        self.record_data_widget.recording_stopped.connect(self.on_recording_stopped)
        
        # View recording signals
        self.view_recording_widget.view_recording_requested.connect(self.on_view_recording)
        
    def on_device_connected(self, board):
        """Handle device connection"""
        self.logger.info("Device connected successfully")
        self.board = board
        self.is_connected = True
        
        # Enable recording controls
        self.record_data_widget.set_enabled(True)
        self.logger.debug("Recording controls enabled")
        
        # Don't start streaming automatically - only when recording starts
        
    def on_device_disconnected(self):
        """Handle device disconnection"""
        self.logger.info("Device disconnected")
        self.board = None
        self.is_connected = False
        
        # Disable recording controls
        self.record_data_widget.set_enabled(False)
        self.logger.debug("Recording controls disabled")
        
        # Stop streaming
        self.stop_streaming()
        
    def on_recording_started(self):
        """Handle recording start"""
        self.logger.info("=" * 80)
        self.logger.info("Recording started")
        self.is_recording = True
        
        # Clear previous data
        self.recorded_data = {}
        self.stream_data = pd.DataFrame()
        self.timestamp_start = None
        self.acquisition_plot.clear_curves()
        self.logger.debug("Previous data cleared")
        
        # Clear BrainFlow board buffer to prevent data from previous recordings
        if self.board and not self.demo_mode:
            try:
                # Clear the board buffer by getting and discarding all current data
                # Clear all presets
                self.board.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
                self.board.get_board_data(preset=BrainFlowPresets.AUXILIARY_PRESET)
                self.board.get_board_data(preset=BrainFlowPresets.ANCILLARY_PRESET)
                self.logger.info("Cleared BrainFlow board buffer for all presets")
            except Exception as e:
                self.logger.error(f"Error clearing board buffer: {e}", exc_info=True)
        
        # Initialize CSV files for incremental writing
        try:
            self.initialize_csv_files()
            self.logger.info("CSV files initialized for incremental writing")
        except Exception as e:
            self.logger.error(f"Failed to initialize CSV files: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to initialize CSV files: {str(e)}")
            self.is_recording = False
            return
        
        # Start streaming when recording starts
        self.start_streaming()
        self.logger.info("Data streaming started")
        
        # Disable view recording during active recording
        self.view_recording_widget.set_enabled(False)
        self.logger.debug("View recording widget disabled")
        
    def on_recording_stopped(self, data_dict):
        """Handle recording stop"""
        self.logger.info("Recording stopped")
        self.is_recording = False
        self.recorded_data = data_dict
        
        # Close CSV files
        try:
            self.close_csv_files()
            self.logger.info("CSV files closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing CSV files: {e}", exc_info=True)
        
        # Stop streaming when recording stops
        self.stop_streaming()
        self.logger.info("Streaming stopped")
        
        # Reset plot to streaming view
        self.acquisition_plot.reset_view()
        self.logger.debug("Plot view reset")

        # Enable view recording
        self.view_recording_widget.set_enabled(True)
        self.logger.debug("View recording widget enabled")
        
        # Update view recording with latest file and display it
        if data_dict and 'file_path' in data_dict:
            self.view_recording_widget.set_data_file(data_dict['file_path'])
            # Automatically display the recording
            self.on_view_recording(data_dict['file_path'])
            self.logger.info(f"Recording displayed: {data_dict['file_path']}")
        
        self.logger.info("=" * 80)
            
    def on_view_recording(self, file_path):
        """Handle view recording request"""
        try:
            # Load the recording data
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            
            # Update the plot with recorded data
            self.acquisition_plot.display_recording_data(data)
            
            # Update metadata
            self.view_recording_widget.update_metadata(data)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load recording: {str(e)}")
            
    def initialize_csv_files(self):
        """Initialize CSV files for incremental data writing"""
        self.logger.debug("Initializing CSV files for incremental writing")
        
        # Get recording details from record_data_widget
        if not hasattr(self, 'record_data_widget'):
            raise RuntimeError("record_data_widget not initialized")
        
        data_folder = self.record_data_widget.get_data_folder()
        subject_id = self.record_data_widget.get_subject_id()
        self.recording_filename = self.record_data_widget.filename_edit.text()
        
        self.logger.info(f"Recording filename: {self.recording_filename}")
        self.logger.info(f"Data folder: {data_folder}")
        self.logger.info(f"Subject ID: {subject_id if subject_id else 'None'}")
        
        # Create subject folder if ID is provided
        if subject_id:
            self.recording_folder = Path(data_folder) / subject_id
        else:
            self.recording_folder = Path(data_folder)
        
        self.recording_folder.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Recording folder created/verified: {self.recording_folder}")
        
        # Initialize CSV files for each data type
        data_types = ['eeg', 'imu', 'ppg']
        
        for data_type in data_types:
            csv_path = self.recording_folder / f"{self.recording_filename}_{data_type}.csv"
            self.logger.debug(f"Creating CSV file for {data_type}: {csv_path}")
            
            # Open file in write mode with UTF-8 encoding and unbuffered mode for immediate writes
            self.csv_files[data_type] = open(csv_path, 'w', newline='', encoding='utf-8', buffering=1)
            self.csv_writers[data_type] = csv.writer(self.csv_files[data_type])
            self.csv_headers_written[data_type] = False
            
            self.logger.info(f"CSV file initialized: {csv_path}")
        
        self.logger.info("All CSV files initialized successfully")
    
    def close_csv_files(self):
        """Close all open CSV files"""
        self.logger.debug("Closing CSV files")
        
        for data_type, file_handle in self.csv_files.items():
            try:
                # Ensure all data is written to disk
                file_handle.flush()
                os.fsync(file_handle.fileno())  # Force write to disk
                file_handle.close()
                self.logger.debug(f"Closed CSV file for {data_type}")
            except Exception as e:
                self.logger.error(f"Error closing CSV file for {data_type}: {e}", exc_info=True)
        
        # Clear the dictionaries
        self.csv_files = {}
        self.csv_writers = {}
        self.csv_headers_written = {}
        
        self.logger.info("All CSV files closed")
    
    def start_streaming(self):
        """Start real-time data streaming"""
        if self.stream_timer is None:
            self.stream_timer = QTimer()
            self.stream_timer.timeout.connect(self.update_stream)
            # Use 50ms interval (20 Hz) for more stable sampling rate and to catch all data
            self.stream_timer.start(200)
            self.logger.debug("Stream timer started (200ms interval)")
            
    def stop_streaming(self):
        """Stop real-time data streaming"""
        if self.stream_timer:
            self.stream_timer.stop()
            self.stream_timer = None
            self.logger.debug("Stream timer stopped")
    
    def update_stream(self):
        """Update streaming data"""
        if not self.is_connected:
            return
            
        try:
            if self.demo_mode:
                # Generate demo data
                now = time.time()
                if self.timestamp_start is None:
                    self.timestamp_start = now
                    self.logger.debug(f"Demo stream started at timestamp: {self.timestamp_start}")
                    
                t_rel = now - self.timestamp_start
                data_dict = {
                    'TP9': np.random.randn() * 50 + 100,
                    'AF7': np.random.randn() * 50 + 150,
                    'AF8': np.random.randn() * 50 + 200,
                    'TP10': np.random.randn() * 50 + 250,
                    'time_rel': t_rel
                }
                df_eeg = pd.DataFrame([data_dict])
                df_imu = None
                df_ppg = None
                
            else:
                # Get real data from board
                if not self.board:
                    self.logger.warning("Board not available during streaming")
                    return
                
                # Get EEG data
                data = self.board.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
                if data.size == 0:
                    return  # No new data available

                df_eeg = self.make_dataframe(data, BrainFlowPresets.DEFAULT_PRESET)
                if df_eeg.empty:
                    return
                
                # Get IMU data
                df_imu = None
                try:
                    imu_data = self.board.get_board_data(preset=BrainFlowPresets.AUXILIARY_PRESET)
                    if imu_data.size > 0:
                        df_imu = self.make_dataframe(imu_data, BrainFlowPresets.AUXILIARY_PRESET)
                except Exception as e:
                    self.logger.debug(f"No IMU data available: {e}")
                
                # Get PPG data
                df_ppg = None
                try:
                    ppg_data = self.board.get_board_data(preset=BrainFlowPresets.ANCILLARY_PRESET)
                    if ppg_data.size > 0:
                        df_ppg = self.make_dataframe(ppg_data, BrainFlowPresets.ANCILLARY_PRESET)
                except Exception as e:
                    self.logger.debug(f"No PPG data available: {e}")
                
                # Set timestamp_start from the earliest timestamp across all data types
                # This ensures no negative time_rel values
                if self.timestamp_start is None:
                    earliest_timestamp = None
                    
                    # Check EEG timestamps
                    if not df_eeg.empty and 'timestamp' in df_eeg._columns:
                        eeg_timestamps = df_eeg._data['timestamp']
                        if len(eeg_timestamps) > 0:
                            earliest_timestamp = eeg_timestamps[0]
                    
                    # Check IMU timestamps
                    if df_imu is not None and not df_imu.empty and 'timestamp' in df_imu._columns:
                        imu_timestamps = df_imu._data['timestamp']
                        if len(imu_timestamps) > 0:
                            if earliest_timestamp is None or imu_timestamps[0] < earliest_timestamp:
                                earliest_timestamp = imu_timestamps[0]
                    
                    # Check PPG timestamps
                    if df_ppg is not None and not df_ppg.empty and 'timestamp' in df_ppg._columns:
                        ppg_timestamps = df_ppg._data['timestamp']
                        if len(ppg_timestamps) > 0:
                            if earliest_timestamp is None or ppg_timestamps[0] < earliest_timestamp:
                                earliest_timestamp = ppg_timestamps[0]
                    
                    if earliest_timestamp is not None:
                        self.timestamp_start = earliest_timestamp
                        self.logger.debug(f"Timestamp start set to: {self.timestamp_start}")
                
                # Calculate time_rel for all data types using the same timestamp_start
                if self.timestamp_start is not None:
                    if not df_eeg.empty and 'timestamp' in df_eeg._columns:
                        df_eeg['time_rel'] = df_eeg._data['timestamp'] - self.timestamp_start
                    
                    if df_imu is not None and not df_imu.empty and 'timestamp' in df_imu._columns:
                        df_imu['time_rel'] = df_imu._data['timestamp'] - self.timestamp_start
                    
                    if df_ppg is not None and not df_ppg.empty and 'timestamp' in df_ppg._columns:
                        df_ppg['time_rel'] = df_ppg._data['timestamp'] - self.timestamp_start
            
            # Write data to CSV files incrementally if recording
            if self.is_recording:
                self.write_data_to_csv('eeg', df_eeg)
                if df_imu is not None:
                    self.write_data_to_csv('imu', df_imu)
                if df_ppg is not None:
                    self.write_data_to_csv('ppg', df_ppg)
            
            # Update stream data for plotting (only EEG for now)
            if self.stream_data.empty:
                self.stream_data = df_eeg
            else:
                self.stream_data = pd.concat([self.stream_data, df_eeg], ignore_index=True)
                
            # Update plot
            self.acquisition_plot.update_stream_data(self.stream_data)
            
        except Exception as e:
            self.logger.error(f"Streaming error: {str(e)}", exc_info=True)
            print(f"Streaming error: {str(e)}")
            
    def write_data_to_csv(self, data_type, df):
        """Write data incrementally to CSV file"""
        if df is None or df.empty:
            return
        
        if data_type not in self.csv_writers:
            return
        
        writer = self.csv_writers[data_type]
        
        # Reorder columns: original columns first, then time_rel at the end
        # Preserve the original column order from make_dataframe
        original_columns = [col for col in df._columns if col != 'time_rel']
        if 'time_rel' in df._columns:
            ordered_columns = original_columns + ['time_rel']
        else:
            ordered_columns = original_columns
        
        # Write header if not written yet
        if not self.csv_headers_written[data_type]:
            writer.writerow(ordered_columns)
            self.csv_headers_written[data_type] = True
        
        # Write data rows - ensure column order exactly matches header
        num_rows = len(df)
        if num_rows == 0:
            return
        
        # Validate DataFrame structure - ensure all columns have the same length
        column_lengths = {}
        for col in ordered_columns:
            if col not in df._data:
                self.logger.error(f"Column '{col}' not found in {data_type} DataFrame. Available columns: {df._columns}")
                continue
            
            col_data = df._data[col]
            # Ensure it's a numpy array
            if not isinstance(col_data, np.ndarray):
                col_data = np.array(col_data)
            
            col_len = len(col_data)
            column_lengths[col] = col_len
            
            # Check if column length matches expected number of rows
            if col_len != num_rows:
                self.logger.warning(f"Column '{col}' has length {col_len} but DataFrame reports {num_rows} rows in {data_type} data")
        
        # Use the actual number of rows from the first valid column
        if not column_lengths:
            self.logger.error(f"No valid columns found for {data_type} data")
            return
        
        # Get the minimum length to avoid index errors
        actual_num_rows = min(column_lengths.values()) if column_lengths else num_rows
        
        # Write rows one by one, ensuring we don't go out of bounds
        for i in range(actual_num_rows):
            row_data = []
            for col in ordered_columns:
                if col not in df._data:
                    # Missing column - use NaN
                    row_data.append(np.nan)
                    continue
                
                col_data = df._data[col]
                # Ensure it's a numpy array
                if not isinstance(col_data, np.ndarray):
                    col_data = np.array(col_data)
                
                # Get the i-th element from this column
                if i < len(col_data):
                    row_data.append(col_data[i])
                else:
                    # Out of bounds - use NaN
                    row_data.append(np.nan)
            
            # Write the complete row
            writer.writerow(row_data)
        
        # Flush to ensure data is written to disk
        self.csv_files[data_type].flush()
        try:
            os.fsync(self.csv_files[data_type].fileno())
        except (OSError, io.UnsupportedOperation):
            pass
    
    def make_dataframe(self, data, preset):
        """Create DataFrame from raw board data"""
        if preset == BrainFlowPresets.DEFAULT_PRESET:
            chan_names = ['TP9', 'AF7', 'AF8', 'TP10', 'Right AUX']
        elif preset == BrainFlowPresets.AUXILIARY_PRESET:
            chan_names = ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']
        else:  # ANCILLARY_PRESET
            chan_names = ['PPG_1', 'PPG_2', 'Unknown']
            
        header = ['package_num'] + chan_names + ['timestamp', 'marker']
        num_columns = len(header)
        
        # BrainFlow returns data in shape (num_channels, num_samples)
        # We need to transpose to get (num_samples, num_channels) for DataFrame
        if data.size == 0:
            return pd.DataFrame(columns=header)
        
        # Ensure data is 2D
        if data.ndim == 1:
            data = data.reshape(1, -1)
        
        # BrainFlow always returns data as (channels, samples)
        # So data.shape[0] should equal num_columns (number of channels)
        # We need to transpose to get (samples, channels)
        if data.shape[0] == num_columns:
            # Correct format: (channels, samples) -> transpose to (samples, channels)
            transposed_data = data.T
        elif data.shape[1] == num_columns:
            # Already in (samples, channels) format - use as is
            transposed_data = data
        else:
            # Unexpected shape - log warning and try to fix
            self.logger.warning(f"Unexpected data shape {data.shape} for preset {preset}, expected ({num_columns}, N) or (N, {num_columns})")
            # Try to fix by assuming it's (channels, samples) if first dimension matches
            if data.shape[0] == num_columns:
                transposed_data = data.T
            else:
                # Last resort: try to reshape
                self.logger.error(f"Cannot fix data shape {data.shape} for {num_columns} columns")
                return pd.DataFrame(columns=header)
        
        # Verify the final shape is correct: (num_samples, num_columns)
        if transposed_data.shape[1] != num_columns:
            self.logger.error(f"After processing, data shape {transposed_data.shape} doesn't match {num_columns} columns for preset {preset}")
            return pd.DataFrame(columns=header)
        
        # Create DataFrame - FastDataFrame expects (samples, channels) format
        # which is what we have now
        df = pd.DataFrame(transposed_data, columns=header)
        
        # Verify the DataFrame structure is correct
        if len(df) > 0:
            # Check that each column has the same length (number of rows)
            first_col_len = len(df._data[df._columns[0]]) if df._columns else 0
            for col in df._columns:
                col_len = len(df._data[col])
                if col_len != first_col_len:
                    self.logger.warning(f"Column '{col}' has length {col_len} but expected {first_col_len} in {preset} DataFrame")
        
        return df
        
    def get_board_data(self, preset):
        """Get data from board for a specific preset"""
        if not self.board:
            return pd.DataFrame()
            
        try:
            data = self.board.get_board_data(preset=preset)
            return self.make_dataframe(data, preset)
        except Exception as e:
            print(f"Error getting board data: {str(e)}")
            return pd.DataFrame()
            
