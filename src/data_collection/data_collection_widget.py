"""
Data Collection Widget - Main interface for EEG data acquisition
"""

import pickle
import time
from pathlib import Path

import pandas as pd
import numpy as np
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
        self.board = board
        self.is_connected = True
        
        # Enable recording controls
        self.record_data_widget.set_enabled(True)
        
        # Don't start streaming automatically - only when recording starts
        
    def on_device_disconnected(self):
        """Handle device disconnection"""
        self.board = None
        self.is_connected = False
        
        # Disable recording controls
        self.record_data_widget.set_enabled(False)
        
        # Stop streaming
        self.stop_streaming()
        
    def on_recording_started(self):
        """Handle recording start"""
        self.is_recording = True
        
        # Clear previous data
        self.recorded_data = {}
        self.stream_data = pd.DataFrame()
        self.timestamps_start = None
        self.acquisition_plot.clear_curves()
        
        # Start streaming when recording starts
        self.start_streaming()
        
        # Disable view recording during active recording
        self.view_recording_widget.set_enabled(False)
        
    def on_recording_stopped(self, data_dict):
        """Handle recording stop"""
        self.is_recording = False
        self.recorded_data = data_dict
        
        # Stop streaming when recording stops
        self.stop_streaming()
        
        # Reset plot to streaming view
        self.acquisition_plot.reset_view()

        # Enable view recording
        self.view_recording_widget.set_enabled(True)
        
        # Update view recording with latest file and display it
        if data_dict and 'file_path' in data_dict:
            self.view_recording_widget.set_data_file(data_dict['file_path'])
            # Automatically display the recording
            self.on_view_recording(data_dict['file_path'])
            
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
            
    def start_streaming(self):
        """Start real-time data streaming"""
        if self.stream_timer is None:
            self.stream_timer = QTimer()
            self.stream_timer.timeout.connect(self.update_stream)
            self.stream_timer.start(100)  # 10 Hz update rate
            
    def stop_streaming(self):
        """Stop real-time data streaming"""
        if self.stream_timer:
            self.stream_timer.stop()
            self.stream_timer = None
            
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
                    
                t_rel = now - self.timestamps_start
                data_dict = {
                    'TP9': np.random.randn() * 50 + 100,
                    'AF7': np.random.randn() * 50 + 150,
                    'AF8': np.random.randn() * 50 + 200,
                    'TP10': np.random.randn() * 50 + 250,
                    'time_rel': t_rel
                }
                df = pd.DataFrame([data_dict])
            else:
                # Get real data from board
                if not self.board:
                    return
                    
                data = self.board.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
                if data.size == 0:
                    return
                    
                df = self.make_dataframe(data, BrainFlowPresets.DEFAULT_PRESET)
                if df.empty:
                    return
                    
                if self.timestamps_start is None:
                    self.timestamps_start = df['timestamp'].iloc[0]
                df['time_rel'] = df['timestamp'] - self.timestamps_start
                
            # Update stream data
            if self.stream_data.empty:
                self.stream_data = df
            else:
                self.stream_data = pd.concat([self.stream_data, df], ignore_index=True)
                
            # Update plot
            self.acquisition_plot.update_stream_data(self.stream_data)
            
        except Exception as e:
            print(f"Streaming error: {str(e)}")
            
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
