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
        self.timestamps_start = None
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
        self.timestamps_start = None
        self.acquisition_plot.clear_curves()
        self.logger.debug("Previous data cleared")
        
        # Clear BrainFlow board buffer to prevent data from previous recordings
        if self.board and not self.demo_mode:
            try:
                # Clear the board buffer by getting and discarding all current data
                self.board.get_board_data()  # This clears the buffer
                self.logger.info("Cleared BrainFlow board buffer")
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
            self.stream_timer.start(100)  # 10 Hz update rate
            self.logger.debug("Stream timer started (100ms interval)")
            
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
                if self.timestamps_start is None:
                    self.timestamps_start = now
                    self.logger.debug(f"Stream started at timestamp: {self.timestamps_start}")
                    
                t_rel = now - self.timestamps_start
                data_dict = {
                    'TP9': np.random.randn() * 50 + 100,
                    'AF7': np.random.randn() * 50 + 150,
                    'AF8': np.random.randn() * 50 + 200,
                    'TP10': np.random.randn() * 50 + 250,
                    'time_rel': t_rel
                }
                df_eeg = pd.DataFrame([data_dict])
                
                # For demo mode, also generate dummy IMU and PPG data
                df_imu = None
                df_ppg = None
                
            else:
                # Get real data from board - EEG
                if not self.board:
                    self.logger.warning("Board not available during streaming")
                    return
                    
                data = self.board.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
                if data.size == 0:
                    return  # No new data available
                    
                df_eeg = self.make_dataframe(data, BrainFlowPresets.DEFAULT_PRESET)
                if df_eeg.empty:
                    return
                    
                if self.timestamps_start is None:
                    self.timestamps_start = df_eeg['timestamp'].iloc[0]
                    self.logger.info(f"First EEG data received at timestamp: {self.timestamps_start}")
                
                df_eeg['time_rel'] = df_eeg['timestamp'] - self.timestamps_start
                
                # Get IMU data
                try:
                    imu_data = self.board.get_board_data(preset=BrainFlowPresets.AUXILIARY_PRESET)
                    if imu_data.size > 0:
                        df_imu = self.make_dataframe(imu_data, BrainFlowPresets.AUXILIARY_PRESET)
                        if not df_imu.empty and 'timestamp' in df_imu.columns:
                            df_imu['time_rel'] = df_imu['timestamp'] - self.timestamps_start
                    else:
                        df_imu = None
                except Exception as e:
                    self.logger.debug(f"No IMU data available: {e}")
                    df_imu = None
                
                # Get PPG data
                try:
                    ppg_data = self.board.get_board_data(preset=BrainFlowPresets.ANCILLARY_PRESET)
                    if ppg_data.size > 0:
                        df_ppg = self.make_dataframe(ppg_data, BrainFlowPresets.ANCILLARY_PRESET)
                        if not df_ppg.empty and 'timestamp' in df_ppg.columns:
                            df_ppg['time_rel'] = df_ppg['timestamp'] - self.timestamps_start
                    else:
                        df_ppg = None
                except Exception as e:
                    self.logger.debug(f"No PPG data available: {e}")
                    df_ppg = None
            
            # Write data to CSV files incrementally if recording
            if self.is_recording:
                self.write_data_to_csv('eeg', df_eeg)
                if df_imu is not None and not df_imu.empty:
                    self.write_data_to_csv('imu', df_imu)
                if df_ppg is not None and not df_ppg.empty:
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
            self.logger.warning(f"CSV writer not available for {data_type}")
            return
        
        try:
            writer = self.csv_writers[data_type]
            
            # Write header if not written yet
            if not self.csv_headers_written[data_type]:
                writer.writerow(df.columns.tolist())
                self.csv_headers_written[data_type] = True
                self.logger.debug(f"Wrote header for {data_type}: {df.columns.tolist()}")
            
            # Write data rows
            rows_written = 0
            for _, row in df.iterrows():
                writer.writerow(row.tolist())
                rows_written += 1
            
            # Flush to ensure data is written to disk
            self.csv_files[data_type].flush()
            try:
                os.fsync(self.csv_files[data_type].fileno())  # Force write to disk on Windows/Unix
            except (OSError, io.UnsupportedOperation):
                # Some file systems don't support fsync, that's okay
                pass
            
            if rows_written > 0:
                self.logger.debug(f"Wrote {rows_written} rows to {data_type} CSV")
                
        except Exception as e:
            self.logger.error(f"Error writing to {data_type} CSV: {e}", exc_info=True)
    
    def make_dataframe(self, data, preset):
        """Create DataFrame from raw board data"""
        if preset == BrainFlowPresets.DEFAULT_PRESET:
            chan_names = ['TP9', 'AF7', 'AF8', 'TP10', 'Right AUX']
        elif preset == BrainFlowPresets.AUXILIARY_PRESET:
            chan_names = ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']
        else:  # ANCILLARY_PRESET
            chan_names = ['PPG_1', 'PPG_2', 'Unknown']
            
        header = ['package_num'] + chan_names + ['timestamp', 'marker']
        return pd.DataFrame(data.T, columns=header)
        
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
            
    def save_recording(self, filename, description=""):
        """Save the current recording"""
        if not self.recorded_data:
            return False
            
        try:
            # Get data folder from record widget
            data_folder = self.record_data_widget.get_data_folder()
            subject_id = self.record_data_widget.get_subject_id()
            
            # Create subject folder if ID is provided
            if subject_id:
                save_folder = Path(data_folder) / subject_id
            else:
                save_folder = Path(data_folder)
                
            save_folder.mkdir(parents=True, exist_ok=True)
            
            # Save CSV files
            for key, df in self.recorded_data.items():
                if isinstance(df, pd.DataFrame) and not df.empty:
                    csv_path = save_folder / f"{filename}_{key}.csv"
                    df.to_csv(csv_path, index=False)
                    
            # Save combined data file
            data_path = save_folder / f"{filename}.data"
            with open(data_path, 'wb') as f:
                pickle.dump(self.recorded_data, f)
                
            # Save description if provided
            if description:
                desc_path = save_folder / f"{filename}_description.txt"
                with open(desc_path, 'w') as f:
                    f.write(description)
                    
            print(f"Recording saved: {filename}")
            return str(data_path)
            
        except Exception as e:
            print(f"Error saving recording: {str(e)}")
            return False
