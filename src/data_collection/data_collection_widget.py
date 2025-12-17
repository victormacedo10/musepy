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
from threading import Lock, Event
from collections import deque
from enum import Enum

import numpy as np
from ..utils import pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PySide6.QtCore import QTimer, QThread, Signal, QMutex

# BrainFlow imports
from brainflow.board_shim import BrainFlowPresets, BoardShim, BrainFlowInputParams, BoardIds

# Local imports
from .connect_device_widget import ConnectDeviceWidget
from .record_data_widget import RecordDataWidget
from .view_recording_widget import ViewRecordingWidget
from .acquisition_plot_widget import AcquisitionPlotWidget


class StreamState(Enum):
    """Stream state enumeration"""
    IDLE = "idle"
    RUNNING = "running"
    DEAD = "dead"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class BrainFlowStreamWorker(QThread):
    """
    Background thread worker for BrainFlow I/O operations.
    Handles data acquisition, watchdog monitoring, and automatic recovery.
    """
    # Signals for communication with main thread
    data_ready = Signal(object, object, object)  # (df_eeg, df_imu, df_ppg)
    stream_state_changed = Signal(str)  # state name
    watchdog_triggered = Signal()  # stream detected as dead
    recovery_failed = Signal(str)  # error message
    status_update = Signal(str)  # status message for logging
    board_recovered = Signal(object)  # new board instance after recovery
    
    def __init__(self, board_shim, board_id, serial_number, logger=None):
        super().__init__()
        self.board_shim = board_shim
        self.board_id = board_id
        self.serial_number = serial_number
        self.logger = logger or logging.getLogger('MusePy.StreamWorker')
        
        # State management
        self.state = StreamState.IDLE
        self._state_lock = Lock()
        
        # Control flags
        self._stop_event = Event()
        self._pause_event = Event()
        self._pause_event.set()  # Start unpaused
        
        # Watchdog tracking
        self.last_sample_time = None
        self.last_timestamp = None
        self.last_sample_index = 0
        self.watchdog_timeout = 2.0  # 2 seconds
        self._watchdog_lock = Lock()
        self.stream_start_time_watchdog = None  # Track when stream actually started receiving data
        
        # Stream statistics
        self.sample_count = 0
        self.stream_start_time = None
        self.stream_frequency = 0.0
        self._stats_lock = Lock()
        
        # Recovery parameters
        self.recovery_attempts = 0
        self.max_recovery_attempts = 5
        self.recovery_backoff = 1.0  # Start with 1 second
        self.max_backoff = 30.0
        
        # Data buffer for thread-safe communication
        self.data_buffer = deque(maxlen=10)
        self._buffer_lock = Lock()
        
        # Logging interval (log stats every 5 seconds)
        self.last_log_time = None
        self.log_interval = 5.0
        
    def run(self):
        """Main worker thread loop"""
        self.logger.info("Stream worker thread started")
        self.set_state(StreamState.RUNNING)
        
        try:
            while not self._stop_event.is_set():
                # Check if paused
                if not self._pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # Main data acquisition loop
                if self.state == StreamState.RUNNING:
                    self._acquire_data()
                elif self.state == StreamState.DEAD:
                    self._handle_stream_death()
                elif self.state == StreamState.RECONNECTING:
                    # Recovery happens in _handle_stream_death
                    time.sleep(0.5)
                else:
                    time.sleep(0.1)
                    
                # Small sleep to prevent CPU spinning
                time.sleep(0.01)  # 10ms
                
        except Exception as e:
            self.logger.error(f"Fatal error in stream worker: {e}", exc_info=True)
            self.set_state(StreamState.ERROR)
            self.recovery_failed.emit(str(e))
        finally:
            self.logger.info("Stream worker thread stopped")
            
    def _acquire_data(self):
        """Acquire data from BrainFlow board"""
        try:
            # Check board data count
            data_count = 0
            try:
                data_count = self.board_shim.get_board_data_count(preset=BrainFlowPresets.DEFAULT_PRESET)
            except Exception as e:
                self.logger.warning(f"Error getting board data count: {e}")
                self._check_watchdog()
                return
            
            # Get EEG data
            df_eeg, df_imu, df_ppg = None, None, None
            has_data = False
            
            if data_count > 0:
                try:
                    # Get EEG data
                    data = self.board_shim.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
                    if data.size > 0:
                        has_data = True
                        # Process data in main thread context via signal
                        # For now, store raw data and let main thread process it
                        df_eeg = data
                        
                except Exception as e:
                    self.logger.warning(f"Error getting EEG data: {e}")
            
            # Get IMU data if available
            try:
                imu_count = self.board_shim.get_board_data_count(preset=BrainFlowPresets.AUXILIARY_PRESET)
                if imu_count > 0:
                    imu_data = self.board_shim.get_board_data(preset=BrainFlowPresets.AUXILIARY_PRESET)
                    if imu_data.size > 0:
                        df_imu = imu_data
            except Exception as e:
                self.logger.debug(f"IMU data not available: {e}")  # IMU data is optional
            
            # Get PPG data if available
            try:
                ppg_count = self.board_shim.get_board_data_count(preset=BrainFlowPresets.ANCILLARY_PRESET)
                if ppg_count > 0:
                    ppg_data = self.board_shim.get_board_data(preset=BrainFlowPresets.ANCILLARY_PRESET)
                    if ppg_data.size > 0:
                        df_ppg = ppg_data
            except Exception as e:
                self.logger.debug(f"PPG data not available: {e}")  # PPG data is optional
            
            # Update watchdog if we got data
            if has_data:
                self._update_watchdog()
                
                # Update statistics
                with self._stats_lock:
                    self.sample_count += data_count
                    if self.stream_start_time is None:
                        self.stream_start_time = time.time()
                    else:
                        elapsed = time.time() - self.stream_start_time
                        if elapsed > 0:
                            self.stream_frequency = self.sample_count / elapsed
                
                # Emit data to main thread
                self.data_ready.emit(df_eeg, df_imu, df_ppg)
            else:
                # No data received - check watchdog
                self._check_watchdog()
            
            # Periodic logging
            self._periodic_log(data_count)
            
        except Exception as e:
            self.logger.error(f"Error in _acquire_data: {e}", exc_info=True)
            self._check_watchdog()
    
    def _update_watchdog(self):
        """Update watchdog timestamp"""
        with self._watchdog_lock:
            self.last_sample_time = time.time()
            # Try to extract timestamp from last sample if possible
            # For now, just update time
    
    def _check_watchdog(self):
        """Check if stream is dead (no data for watchdog_timeout seconds)"""
        with self._watchdog_lock:
            now = time.time()
            if self.last_sample_time is None:
                # First check - initialize watchdog start time
                if self.stream_start_time_watchdog is None:
                    with self._stats_lock:
                        if self.stream_start_time is not None:
                            self.stream_start_time_watchdog = self.stream_start_time
                        else:
                            self.stream_start_time_watchdog = now
                else:
                    # Check if we've waited too long for first data
                    elapsed = now - self.stream_start_time_watchdog
                    if elapsed > self.watchdog_timeout:
                        # Stream started but no data received
                        self.logger.warning(f"Watchdog: No data received after {elapsed:.2f}s")
                        self.set_state(StreamState.DEAD)
                        self.watchdog_triggered.emit()
                return
            
            elapsed = now - self.last_sample_time
            if elapsed > self.watchdog_timeout:
                self.logger.warning(f"Watchdog triggered: No data for {elapsed:.2f}s")
                self.set_state(StreamState.DEAD)
                self.watchdog_triggered.emit()
    
    def _periodic_log(self, data_count):
        """Periodically log stream statistics"""
        now = time.time()
        if self.last_log_time is None:
            self.last_log_time = now
            return
        
        if now - self.last_log_time >= self.log_interval:
            with self._stats_lock:
                with self._watchdog_lock:
                    last_sample_str = f"{self.last_sample_time:.3f}" if self.last_sample_time else "None"
                    time_since_str = f"{(now - self.last_sample_time):.2f}s" if self.last_sample_time else "N/A"
                    log_msg = (
                        f"Stream stats - Data count: {data_count}, "
                        f"Total samples: {self.sample_count}, "
                        f"Frequency: {self.stream_frequency:.2f} Hz, "
                        f"Last sample: {last_sample_str}, "
                        f"Time since last: {time_since_str}"
                    )
                    self.logger.info(log_msg)
                    self.status_update.emit(log_msg)
            
            self.last_log_time = now
    
    def _handle_stream_death(self):
        """Handle stream death by attempting recovery"""
        if self.recovery_attempts >= self.max_recovery_attempts:
            self.logger.error(f"Max recovery attempts ({self.max_recovery_attempts}) reached")
            self.set_state(StreamState.ERROR)
            self.recovery_failed.emit(f"Failed after {self.max_recovery_attempts} recovery attempts")
            return
        
        self.recovery_attempts += 1
        self.set_state(StreamState.RECONNECTING)
        
        backoff_time = min(self.recovery_backoff * (2 ** (self.recovery_attempts - 1)), self.max_backoff)
        self.logger.info(f"Attempting recovery #{self.recovery_attempts} after {backoff_time:.1f}s backoff")
        
        # Wait for backoff
        if self._stop_event.wait(backoff_time):
            return  # Stop was requested
        
        try:
            # Attempt recovery
            self.status_update.emit(f"Recovery attempt {self.recovery_attempts}/{self.max_recovery_attempts}")
            
            # Stop stream
            try:
                self.board_shim.stop_stream()
            except Exception as e:
                self.logger.warning(f"Error stopping stream during recovery: {e}")
            
            # Release session
            try:
                self.board_shim.release_session()
            except Exception as e:
                self.logger.warning(f"Error releasing session during recovery: {e}")
            
                # Re-initialize board
            try:
                params = BrainFlowInputParams()
                if self.serial_number:
                    params.serial_number = self.serial_number
                
                # Create new board instance
                new_board = BoardShim(self.board_id, params)
                
                # Prepare session
                new_board.prepare_session()
                
                # Configure board
                try:
                    if self.board_id == BoardIds.MUSE_S_BOARD:
                        new_board.config_board("p61")
                    elif self.board_id == BoardIds.MUSE_2_BOARD:
                        new_board.config_board("p50")
                except Exception as e:
                    self.logger.warning(f"Error configuring board during recovery: {e}")
                
                # Start stream
                new_board.start_stream()
                
                # Update board reference
                self.board_shim = new_board
                
                # Emit signal to update main thread's board reference
                self.board_recovered.emit(new_board)
                
                # Reset recovery state
                self.recovery_attempts = 0
                self.recovery_backoff = 1.0
                
                # Reset watchdog
                with self._watchdog_lock:
                    self.last_sample_time = None
                    self.stream_start_time_watchdog = None
                
                # Reset stats
                with self._stats_lock:
                    self.stream_start_time = None
                    self.sample_count = 0
                    self.stream_frequency = 0.0
                
                self.logger.info("Recovery successful - stream restarted")
                self.set_state(StreamState.RUNNING)
                self.status_update.emit("Recovery successful")
                
            except Exception as e:
                self.logger.error(f"Recovery attempt {self.recovery_attempts} failed: {e}", exc_info=True)
                # Will retry on next iteration
                
        except Exception as e:
            self.logger.error(f"Unexpected error during recovery: {e}", exc_info=True)
    
    def set_state(self, state):
        """Thread-safe state update"""
        with self._state_lock:
            old_state = self.state
            self.state = state
        if old_state != state:
            self.logger.debug(f"State changed: {old_state.value} -> {state.value}")
            self.stream_state_changed.emit(state.value)
    
    def get_state(self):
        """Thread-safe state getter"""
        with self._state_lock:
            return self.state
    
    def pause(self):
        """Pause data acquisition"""
        self._pause_event.clear()
        self.logger.debug("Stream worker paused")
    
    def resume(self):
        """Resume data acquisition"""
        self._pause_event.set()
        self.logger.debug("Stream worker resumed")
    
    def stop(self):
        """Stop the worker thread"""
        self.logger.info("Stopping stream worker...")
        self._stop_event.set()
        self._pause_event.set()  # Resume to allow cleanup
        
        # Wait for thread to finish (with timeout)
        if self.isRunning():
            self.wait(3000)  # 3 second timeout
        
        # Cleanup BrainFlow resources
        if self.board_shim:
            try:
                self.board_shim.stop_stream()
            except Exception as e:
                self.logger.warning(f"Error stopping stream in cleanup: {e}")
            
            try:
                self.board_shim.release_session()
            except Exception as e:
                self.logger.warning(f"Error releasing session in cleanup: {e}")
        
        self.logger.info("Stream worker stopped")


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
        
        # Background stream worker
        self.stream_worker = None
        self.board_id = None
        self.serial_number = None
        
        # Cleanup flag
        self._is_closing = False
        
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
    
    def closeEvent(self, event):
        """Handle widget close event - ensure clean shutdown"""
        self.cleanup()
        super().closeEvent(event)
    
    def cleanup(self):
        """Clean shutdown - stop all threads and release resources"""
        if self._is_closing:
            return
        self._is_closing = True
        
        self.logger.info("Cleaning up DataCollectionWidget...")
        
        # Stop streaming
        self.stop_streaming()
        
        # Close CSV files if still open
        if self.csv_files:
            try:
                self.close_csv_files()
            except Exception as e:
                self.logger.error(f"Error closing CSV files during cleanup: {e}")
        
        self.logger.info("DataCollectionWidget cleanup complete")
        
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
        
        # Store board connection info for recovery
        if hasattr(self.connect_device_widget, 'device_combo'):
            self.board_id = self.connect_device_widget.device_combo.currentData()
        if hasattr(self.connect_device_widget, 'device_id_combo'):
            self.serial_number = self.connect_device_widget.device_id_combo.currentData()
        
        # Enable recording controls
        self.record_data_widget.set_enabled(True)
        self.logger.debug("Recording controls enabled")
        
        # Show reconnect button in connect widget
        if hasattr(self.connect_device_widget, 'reconnect_btn'):
            self.connect_device_widget.reconnect_btn.setVisible(True)
            self.connect_device_widget.reconnect_btn.setEnabled(True)
        
        # Don't start streaming automatically - only when recording starts
        
    def on_device_disconnected(self):
        """Handle device disconnection"""
        self.logger.info("Device disconnected")
        
        # Stop and cleanup stream worker
        self.stop_streaming()
        
        self.board = None
        self.is_connected = False
        
        # Disable recording controls
        self.record_data_widget.set_enabled(False)
        self.logger.debug("Recording controls disabled")
        
        # Hide reconnect button
        if hasattr(self.connect_device_widget, 'reconnect_btn'):
            self.connect_device_widget.reconnect_btn.setVisible(False)
            self.connect_device_widget.reconnect_btn.setEnabled(False)
        
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
                # Clear all presets - protect all calls with try/except
                try:
                    self.board.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
                except Exception as e:
                    self.logger.warning(f"Error clearing DEFAULT preset buffer: {e}")
                
                try:
                    self.board.get_board_data(preset=BrainFlowPresets.AUXILIARY_PRESET)
                except Exception as e:
                    self.logger.warning(f"Error clearing AUXILIARY preset buffer: {e}")
                
                try:
                    self.board.get_board_data(preset=BrainFlowPresets.ANCILLARY_PRESET)
                except Exception as e:
                    self.logger.warning(f"Error clearing ANCILLARY preset buffer: {e}")
                
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
        if self.demo_mode:
            # Demo mode uses timer-based approach
            if self.stream_timer is None:
                self.stream_timer = QTimer()
                self.stream_timer.timeout.connect(self.update_stream)
                self.stream_timer.start(200)
                self.logger.debug("Stream timer started (200ms interval)")
            return
        
        # Real mode: use background worker
        if self.stream_worker is not None and self.stream_worker.isRunning():
            self.logger.warning("Stream worker already running")
            return
        
        if not self.board:
            self.logger.error("Cannot start streaming: board not connected")
            return
        
        # Create and start background worker
        try:
            self.stream_worker = BrainFlowStreamWorker(
                self.board, 
                self.board_id, 
                self.serial_number,
                self.logger
            )
            self.stream_worker.data_ready.connect(self.on_stream_data_ready)
            self.stream_worker.watchdog_triggered.connect(self.on_watchdog_triggered)
            self.stream_worker.recovery_failed.connect(self.on_recovery_failed)
            self.stream_worker.status_update.connect(self.on_status_update)
            self.stream_worker.stream_state_changed.connect(self.on_stream_state_changed)
            self.stream_worker.board_recovered.connect(self.on_board_recovered)
            
            self.stream_worker.start()
            self.logger.info("Background stream worker started")
            
            # Also start UI update timer (faster updates for plotting)
            if self.stream_timer is None:
                self.stream_timer = QTimer()
                self.stream_timer.timeout.connect(self.update_plot_from_buffer)
                self.stream_timer.start(50)  # 20 Hz for UI updates
                self.logger.debug("UI update timer started (50ms interval)")
                
        except Exception as e:
            self.logger.error(f"Failed to start stream worker: {e}", exc_info=True)
            QMessageBox.critical(self, "Streaming Error", f"Failed to start streaming: {str(e)}")
            
    def stop_streaming(self):
        """Stop real-time data streaming"""
        # Stop background worker
        if self.stream_worker is not None:
            self.logger.info("Stopping stream worker...")
            self.stream_worker.stop()
            self.stream_worker = None
            self.logger.info("Stream worker stopped")
        
        # Stop UI timer
        if self.stream_timer:
            self.stream_timer.stop()
            self.stream_timer = None
            self.logger.debug("Stream timer stopped")
    
    def on_stream_data_ready(self, raw_eeg, raw_imu, raw_ppg):
        """Handle data ready signal from background worker (main thread)"""
        try:
            # Process raw data into DataFrames
            df_eeg = None
            df_imu = None
            df_ppg = None
            
            if raw_eeg is not None and raw_eeg.size > 0:
                df_eeg = self.make_dataframe(raw_eeg, BrainFlowPresets.DEFAULT_PRESET)
                if df_eeg.empty:
                    return
            
            if raw_imu is not None and raw_imu.size > 0:
                df_imu = self.make_dataframe(raw_imu, BrainFlowPresets.AUXILIARY_PRESET)
            
            if raw_ppg is not None and raw_ppg.size > 0:
                df_ppg = self.make_dataframe(raw_ppg, BrainFlowPresets.ANCILLARY_PRESET)
            
            # Process timestamps
            self._process_timestamps(df_eeg, df_imu, df_ppg)
            
            # Write data to CSV files incrementally if recording
            if self.is_recording:
                if df_eeg is not None and not df_eeg.empty:
                    self.write_data_to_csv('eeg', df_eeg)
                if df_imu is not None and not df_imu.empty:
                    self.write_data_to_csv('imu', df_imu)
                if df_ppg is not None and not df_ppg.empty:
                    self.write_data_to_csv('ppg', df_ppg)
            
            # Update stream data for plotting (only EEG for now)
            if df_eeg is not None and not df_eeg.empty:
                if self.stream_data.empty:
                    self.stream_data = df_eeg
                else:
                    self.stream_data = pd.concat([self.stream_data, df_eeg], ignore_index=True)
                    
        except Exception as e:
            self.logger.error(f"Error processing stream data: {str(e)}", exc_info=True)
    
    def update_plot_from_buffer(self):
        """Update plot from accumulated stream data (called by UI timer)"""
        if not self.stream_data.empty:
            self.acquisition_plot.update_stream_data(self.stream_data)
    
    def _process_timestamps(self, df_eeg, df_imu, df_ppg):
        """Process timestamps and set timestamp_start if needed"""
        # Set timestamp_start from the earliest timestamp across all data types
        if self.timestamp_start is None:
            earliest_timestamp = None
            
            # Check EEG timestamps
            if df_eeg is not None and not df_eeg.empty and 'timestamp' in df_eeg._columns:
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
                self.logger.info(f"Timestamp start set to: {self.timestamp_start} (from earliest timestamp across all data types)")
            else:
                self.logger.warning("Could not determine timestamp_start - no valid timestamps found")
        
        # Calculate time_rel for all data types using the same timestamp_start
        if self.timestamp_start is not None:
            if df_eeg is not None and not df_eeg.empty and 'timestamp' in df_eeg._columns:
                df_eeg['time_rel'] = df_eeg._data['timestamp'] - self.timestamp_start
            
            if df_imu is not None and not df_imu.empty and 'timestamp' in df_imu._columns:
                df_imu['time_rel'] = df_imu._data['timestamp'] - self.timestamp_start
            
            if df_ppg is not None and not df_ppg.empty and 'timestamp' in df_ppg._columns:
                df_ppg['time_rel'] = df_ppg._data['timestamp'] - self.timestamp_start
    
    def on_watchdog_triggered(self):
        """Handle watchdog trigger - stream is dead"""
        self.logger.warning("Watchdog triggered - stream appears dead")
        # Worker will handle recovery automatically
        # Optionally show user notification
        if self.is_recording:
            QMessageBox.warning(
                self, 
                "Stream Interrupted",
                "Data stream has stopped. Attempting automatic recovery..."
            )
    
    def on_recovery_failed(self, error_msg):
        """Handle recovery failure"""
        self.logger.error(f"Recovery failed: {error_msg}")
        QMessageBox.critical(
            self,
            "Stream Recovery Failed",
            f"Failed to recover data stream after multiple attempts.\n\n{error_msg}\n\n"
            "Please disconnect and reconnect the device manually."
        )
        # Optionally trigger manual reconnect
        if hasattr(self, 'connect_device_widget'):
            self.connect_device_widget.connect_btn.setChecked(False)
    
    def on_status_update(self, message):
        """Handle status update messages from worker"""
        self.logger.debug(f"Stream worker status: {message}")
    
    def on_stream_state_changed(self, state_name):
        """Handle stream state changes"""
        self.logger.info(f"Stream state changed to: {state_name}")
    
    def on_board_recovered(self, new_board):
        """Handle board recovery - update board reference"""
        self.logger.info("Board recovered - updating reference")
        self.board = new_board
        # Also update in connect widget if it has a reference
        if hasattr(self, 'connect_device_widget') and self.connect_device_widget:
            self.connect_device_widget.board = new_board
    
    def manual_reconnect(self):
        """Manually trigger stream reconnection"""
        if self.demo_mode:
            self.logger.info("Manual reconnect not applicable in demo mode")
            return
        
        if not self.is_connected:
            self.logger.warning("Cannot reconnect: device not connected")
            QMessageBox.warning(
                self,
                "Not Connected",
                "Device is not connected. Please connect the device first."
            )
            return
        
        self.logger.info("Manual reconnect triggered")
        
        # If worker is running, trigger recovery
        if self.stream_worker is not None and self.stream_worker.isRunning():
            # Force stream death state to trigger recovery
            self.stream_worker.set_state(StreamState.DEAD)
            # Reset recovery attempts to allow fresh attempt
            self.stream_worker.recovery_attempts = 0
        else:
            # Restart streaming
            self.stop_streaming()
            time.sleep(0.5)  # Brief pause
            self.start_streaming()
    
    def update_stream(self):
        """Update streaming data (for demo mode or fallback)"""
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
                
                # Write data to CSV files incrementally if recording
                if self.is_recording:
                    self.write_data_to_csv('eeg', df_eeg)
                
                # Update stream data for plotting
                if self.stream_data.empty:
                    self.stream_data = df_eeg
                else:
                    self.stream_data = pd.concat([self.stream_data, df_eeg], ignore_index=True)
                    
                # Update plot
                self.acquisition_plot.update_stream_data(self.stream_data)
            else:
                # Real mode should use background worker
                # This is a fallback if worker is not available
                self.logger.warning("update_stream called in real mode - should use background worker")
            
        except Exception as e:
            self.logger.error(f"Streaming error: {str(e)}", exc_info=True)
            print(f"Streaming error: {str(e)}")
            
    def write_data_to_csv(self, data_type, df):
        """Write data incrementally to CSV file"""
        if df is None or df.empty:
            self.logger.debug(f"{data_type}: DataFrame is None or empty, skipping CSV write")
            return
        
        if data_type not in self.csv_writers:
            self.logger.warning(f"{data_type}: CSV writer not found, skipping write")
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
            self.logger.debug(f"{data_type}: Wrote CSV header with {len(ordered_columns)} columns: {ordered_columns}")
        
        # Write data rows - ensure column order exactly matches header
        num_rows = len(df)
        if num_rows == 0:
            self.logger.debug(f"{data_type}: No rows to write")
            return
        
        # Validate DataFrame structure - ensure all columns have the same length
        column_lengths = {}
        for col in ordered_columns:
            if col not in df._data:
                self.logger.error(f"{data_type}: Column '{col}' not found. Available columns: {df._columns}")
                continue
            
            col_data = df._data[col]
            # Ensure it's a numpy array
            if not isinstance(col_data, np.ndarray):
                col_data = np.array(col_data)
            
            col_len = len(col_data)
            column_lengths[col] = col_len
            
            # Check if column length matches expected number of rows
            if col_len != num_rows:
                self.logger.warning(f"{data_type}: Column '{col}' has length {col_len} but DataFrame reports {num_rows} rows")
        
        # Use the actual number of rows from the first valid column
        if not column_lengths:
            self.logger.error(f"{data_type}: No valid columns found")
            return
        
        # Get the minimum length to avoid index errors
        actual_num_rows = min(column_lengths.values()) if column_lengths else num_rows
        
        # Validate that all columns have the same length (critical check)
        if len(set(column_lengths.values())) > 1:
            self.logger.error(f"{data_type}: Column length mismatch! Lengths: {column_lengths}")
            # Don't write if columns have different lengths - this indicates a serious problem
            return
        
        # Validate first row structure before writing
        if actual_num_rows > 0:
            first_row_values = []
            for col in ordered_columns:
                if col in df._data:
                    first_row_values.append(df._data[col][0])
                else:
                    first_row_values.append(None)
            
            # Check if first row looks correct (not all same value, reasonable data types)
            if len(set(first_row_values[:3])) == 1 and first_row_values[0] is not None:
                self.logger.warning(f"{data_type}: First row has identical values in first 3 columns: {first_row_values[:3]} - possible transpose issue")
            
            self.logger.debug(f"{data_type}: Writing {actual_num_rows} rows. First row sample (first 3 cols): {first_row_values[:3]}")
        
        # Write rows one by one, ensuring we don't go out of bounds
        rows_written = 0
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
            rows_written += 1
        
        # Flush to ensure data is written to disk
        self.csv_files[data_type].flush()
        try:
            os.fsync(self.csv_files[data_type].fileno())
        except (OSError, io.UnsupportedOperation):
            pass
        
        if rows_written > 0:
            self.logger.debug(f"{data_type}: Wrote {rows_written} rows to CSV")
    
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
            self.logger.debug(f"{preset}: Empty data received")
            return pd.DataFrame(columns=header)
        
        # Log initial data shape
        self.logger.debug(f"{preset}: Raw data shape: {data.shape}, size: {data.size}, expected columns: {num_columns}")
        
        # Ensure data is 2D
        if data.ndim == 1:
            self.logger.warning(f"{preset}: Data is 1D, reshaping to 2D")
            data = data.reshape(1, -1)
        
        # BrainFlow always returns data as (channels, samples)
        # So data.shape[0] should equal num_columns (number of channels)
        # We need to transpose to get (samples, channels)
        if data.shape[0] == num_columns:
            # Correct format: (channels, samples) -> transpose to (samples, channels)
            transposed_data = data.T
            self.logger.debug(f"{preset}: Transposed from (channels={data.shape[0]}, samples={data.shape[1]}) to (samples={transposed_data.shape[0]}, channels={transposed_data.shape[1]})")
        elif data.shape[1] == num_columns:
            # Already in (samples, channels) format - use as is
            transposed_data = data
            self.logger.debug(f"{preset}: Data already in (samples={data.shape[0]}, channels={data.shape[1]}) format")
        else:
            # Unexpected shape - log warning and try to fix
            self.logger.warning(f"{preset}: Unexpected data shape {data.shape}, expected ({num_columns}, N) or (N, {num_columns})")
            # Try to fix by assuming it's (channels, samples) if first dimension matches
            if data.shape[0] == num_columns:
                transposed_data = data.T
                self.logger.debug(f"{preset}: Fixed by transposing")
            else:
                # Last resort: try to reshape
                self.logger.error(f"{preset}: Cannot fix data shape {data.shape} for {num_columns} columns")
                return pd.DataFrame(columns=header)
        
        # Verify the final shape is correct: (num_samples, num_columns)
        if transposed_data.shape[1] != num_columns:
            self.logger.error(f"{preset}: After processing, data shape {transposed_data.shape} doesn't match {num_columns} columns")
            return pd.DataFrame(columns=header)
        
        # Create DataFrame using dictionary format to avoid FastDataFrame auto-transpose
        # FastDataFrame will transpose if shape[0] == len(columns), so we use dict format instead
        num_samples = transposed_data.shape[0]
        data_dict = {}
        for i, col_name in enumerate(header):
            data_dict[col_name] = transposed_data[:, i]
        
        df = pd.DataFrame(data_dict)
        
        # Verify the DataFrame structure is correct
        if len(df) > 0:
            # Check that each column has the same length (number of rows)
            first_col_len = len(df._data[df._columns[0]]) if df._columns else 0
            for col in df._columns:
                col_len = len(df._data[col])
                if col_len != first_col_len:
                    self.logger.warning(f"{preset}: Column '{col}' has length {col_len} but expected {first_col_len}")
            
            # Log sample values from first row to verify structure
            if first_col_len > 0:
                first_row_sample = {col: df._data[col][0] for col in df._columns[:3]}  # First 3 columns
                self.logger.debug(f"{preset}: First row sample (first 3 cols): {first_row_sample}, total rows: {first_col_len}")
        
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
            
