"""
Record Data Widget - Handles data recording controls
"""

import os
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QLabel, QTextEdit, QFileDialog, QMessageBox
)
import pandas as pd
from PySide6.QtCore import Signal, QTimer, Qt
from PySide6.QtGui import QFont, QPalette, QColor


class RecordDataWidget(QGroupBox):
    """Widget for data recording controls"""
    
    # Signals
    recording_started = Signal()
    recording_stopped = Signal(dict)  # emits recorded data dictionary
    
    def __init__(self, parent=None):
        super().__init__("📉 Record Data")
        self.parent = parent
        self.is_recording = False
        self.recording_timer = None
        self.recording_start_time = None
        
        # Setup default data folder
        base_path = Path(__file__).parent.parent.parent
        self.default_data_folder = base_path / "data"
        self.default_data_folder.mkdir(exist_ok=True)
        
        self.setup_ui()
        self.setup_connections()
        self.set_enabled(False)  # Initially disabled until device is connected
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Data folder selection
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Data Folder:")
        folder_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        folder_layout.addWidget(folder_label)
        
        self.folder_edit = QLineEdit(str(self.default_data_folder))
        self.folder_edit.setReadOnly(True)
        folder_layout.addWidget(self.folder_edit)
        
        self.browse_btn = QPushButton("📁")
        self.browse_btn.setFixedWidth(50)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #495057;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
            }
        """)
        self.browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.browse_btn)
        
        layout.addLayout(folder_layout)
        
        # Subject ID
        subject_layout = QHBoxLayout()
        subject_label = QLabel("Subject ID:")
        subject_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        subject_layout.addWidget(subject_label)
        
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("Enter subject ID (optional)")
        subject_layout.addWidget(self.subject_edit)
        
        layout.addLayout(subject_layout)
        
        # File name
        file_layout = QHBoxLayout()
        file_label = QLabel("File Name:")
        file_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        file_layout.addWidget(file_label)
        
        self.filename_edit = QLineEdit()
        self.filename_edit.setText(datetime.now().strftime("%Y%m%d_%H%M%S"))
        file_layout.addWidget(self.filename_edit)
        
        layout.addLayout(file_layout)

        # Description
        desc_label = QLabel("Description:")
        desc_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        layout.addWidget(desc_label)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setPlaceholderText("Enter recording description...")
        layout.addWidget(self.description_edit)
        
        # Record button and timer
        record_layout = QHBoxLayout()
        
        self.record_btn = QPushButton("Start Recording")
        self.record_btn.setFixedHeight(40)
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self.toggle_recording)
        record_layout.addWidget(self.record_btn)
        
        # Recording timer display
        self.timer_label = QLabel("00:00:00s")
        self.timer_label.setFixedWidth(100)
        self.timer_label.setStyleSheet("""
            QLabel {
                font-family: 'Courier New', monospace;
                font-size: 16px;
                font-weight: bold;
                color: #495057;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 80px;
                text-align: center;
            }
        """)
        record_layout.addWidget(self.timer_label)
        
        layout.addLayout(record_layout)
        
        # Apply styling
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #495057;
            }
            QLineEdit {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 8px;
                color: #495057;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
            QLineEdit:disabled {
                background-color: #e9ecef;
                color: #6c757d;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 8px;
                color: #495057;
            }
            QTextEdit:focus {
                border-color: #007bff;
            }
            QTextEdit:disabled {
                background-color: #e9ecef;
                color: #6c757d;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        
        # Special styling for record button
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #495057;
                border: 2px solid #28a745;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #e8f5e8;
            }
            QPushButton:pressed {
                background-color: #d4edda;
            }
            QPushButton:checked {
                background-color: #f8f9fa;
                color: #dc3545;
                border-color: #dc3545;
            }
            QPushButton:checked:hover {
                background-color: #ffeaea;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #6c757d;
                border-color: #ced4da;
            }
        """)
        
    def setup_connections(self):
        """Setup signal connections"""
        # Timer for updating recording time
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_timer)
        
    def browse_folder(self):
        """Browse for data folder"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Data Folder", 
            self.folder_edit.text()
        )
        if folder:
            self.folder_edit.setText(folder)
            
    def toggle_recording(self):
        """Toggle recording on/off"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()
            
    def start_recording(self):
        """Start recording"""
        if not self.parent or not hasattr(self.parent, 'is_connected') or not self.parent.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a device first.")
            self.record_btn.setChecked(False)
            return
            
        self.is_recording = True
        self.recording_start_time = datetime.now()
        
        # Update UI
        self.record_btn.setText("Stop Recording")
        self.record_btn.setChecked(True)
        self.folder_edit.setEnabled(False)
        self.subject_edit.setEnabled(False)
        self.description_edit.setEnabled(False)
        self.filename_edit.setEnabled(False)
        self.browse_btn.setEnabled(False)
        
        # Start timer
        self.recording_timer.start(1000)  # Update every second
        
        # Emit signal
        self.recording_started.emit()
        
    def stop_recording(self):
        """Stop recording"""
        self.is_recording = False
        
        # Stop timer
        self.recording_timer.stop()
        
        # Update UI
        self.record_btn.setText("Start Recording")
        self.record_btn.setChecked(False)
        self.folder_edit.setEnabled(True)
        self.subject_edit.setEnabled(True)
        self.description_edit.setEnabled(True)
        self.filename_edit.setEnabled(True)
        self.browse_btn.setEnabled(True)
        
        # Reset timer display
        self.timer_label.setText("00:00:00s")
        
        # Collect recorded data from parent
        recorded_data = {}
        if self.parent and hasattr(self.parent, 'stream_data') and not self.parent.stream_data.empty:
            # Get EEG data from streaming
            recorded_data['eeg'] = self.parent.stream_data.copy()
            
            # Get IMU and PPG data if available
            if hasattr(self.parent, 'board') and self.parent.board:
                try:
                    from brainflow.board_shim import BrainFlowPresets
                    # Get IMU data
                    imu_data = self.parent.get_board_data(BrainFlowPresets.AUXILIARY_PRESET)
                    if not imu_data.empty:
                        recorded_data['imu'] = imu_data
                        
                    # Get PPG data
                    ppg_data = self.parent.get_board_data(BrainFlowPresets.ANCILLARY_PRESET)
                    if not ppg_data.empty:
                        recorded_data['ppg'] = ppg_data
                except Exception as e:
                    print(f"Error getting IMU/PPG data: {e}")
            
            # Add metadata
            recorded_data['metadata'] = {
                'filename': self.filename_edit.text(),
                'subject_id': self.subject_edit.text(), 
                'description': self.description_edit.toPlainText(),
                'recording_duration': self.get_recording_duration(),
                'timestamp': datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
            }
            
            # Save recording with proper file structure
            if recorded_data:
                file_path = self.save_recording_with_files(recorded_data)
                if file_path:
                    recorded_data['file_path'] = file_path
                    
        # Emit signal with recorded data
        self.recording_stopped.emit(recorded_data)
        
        # Update filename for next recording
        self.filename_edit.setText(datetime.now().strftime("%Y%m%d_%H%M%S"))
        
    def save_recording_with_files(self, recorded_data):
        """Save recording with proper file structure"""
        try:
            # Get data folder from record widget
            data_folder = self.get_data_folder()
            subject_id = self.get_subject_id()
            filename = self.filename_edit.text()
            description = self.description_edit.toPlainText()
            
            # Create subject folder if ID is provided
            if subject_id:
                save_folder = Path(data_folder) / subject_id
            else:
                save_folder = Path(data_folder)
                
            save_folder.mkdir(parents=True, exist_ok=True)
            
            # Save CSV files (only if not in demo mode and we have real data)
            if not (self.parent and hasattr(self.parent, 'demo_mode') and self.parent.demo_mode):
                for key, df in recorded_data.items():
                    if isinstance(df, pd.DataFrame) and not df.empty and key in ['eeg', 'ppg', 'imu']:
                        csv_path = save_folder / f"{filename}_{key}.csv"
                        df.to_csv(csv_path, index=False)
                        print(f"Saved {key} CSV: {csv_path}")
                        
            # Save combined data file (always)
            data_path = save_folder / f"{filename}.data"
            with open(data_path, 'wb') as f:
                pickle.dump(recorded_data, f)
            print(f"Saved data file: {data_path}")
                
            # Save description if provided (always)
            if description:
                desc_path = save_folder / f"{filename}_description.txt"
                with open(desc_path, 'w') as f:
                    f.write(description)
                print(f"Saved description: {desc_path}")
                    
            print(f"Recording saved: {filename}")
            return str(data_path)
            
        except Exception as e:
            print(f"Error saving recording: {str(e)}")
            return False
            
    def update_timer(self):
        """Update the recording timer display"""
        if self.recording_start_time:
            # Try to get time from streaming data first
            if self.parent and hasattr(self.parent, 'stream_data') and not self.parent.stream_data.empty:
                if 'time_rel' in self.parent.stream_data.columns:
                    max_time = self.parent.stream_data['time_rel'].max()
                    if max_time > 0:
                        hours, remainder = divmod(int(round(max_time)), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}s")
                        return
            
    def get_recording_duration(self):
        """Get the recording duration in seconds"""
        if self.recording_start_time:
            elapsed = datetime.now() - self.recording_start_time
            return elapsed.total_seconds()
        return 0
        
    def set_enabled(self, enabled):
        """Enable or disable the widget"""
        self.record_btn.setEnabled(enabled)
        self.folder_edit.setEnabled(enabled)
        self.subject_edit.setEnabled(enabled)
        self.description_edit.setEnabled(enabled)
        self.filename_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        
    def get_data_folder(self):
        """Get the current data folder path"""
        return self.folder_edit.text()
        
    def get_subject_id(self):
        """Get the current subject ID"""
        return self.subject_edit.text().strip()
        
    def get_description(self):
        """Get the current description"""
        return self.description_edit.toPlainText().strip()
