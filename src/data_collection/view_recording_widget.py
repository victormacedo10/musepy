"""
View Recording Widget - Handles viewing recorded data and metadata
"""

import pickle
from pathlib import Path
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QLabel, QScrollArea, QWidget, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal


class MetadataWidget(QWidget):
    """Widget for displaying metadata information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.metadata_labels = {}
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Title
        title = QLabel("Recording Info:")
        title.setStyleSheet("font-weight: bold; color: #495057; background-color: white; border-right: none;")
        layout.addWidget(title)
        
        # Scroll area for metadata
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(300)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        # Metadata container
        self.metadata_container = QWidget()
        self.metadata_container.setStyleSheet("background-color: white;")
        self.metadata_layout = QVBoxLayout(self.metadata_container)
        self.metadata_layout.setSpacing(3)
        
        scroll.setWidget(self.metadata_container)
        layout.addWidget(scroll)
        
    def update_metadata(self, data_dict):
        """Update metadata display with new data"""
        # Clear existing metadata
        for label in self.metadata_labels.values():
            label.setParent(None)
        self.metadata_labels.clear()
        
        # Clear any existing stretch
        while self.metadata_layout.count():
            item = self.metadata_layout.takeAt(self.metadata_layout.count()-1)
            if item.spacerItem():
                self.metadata_layout.removeItem(item)
        
        if not data_dict:
            return
            
        # Calculate metadata
        metadata = {}
                
        # Additional metadata from recording
        if 'metadata' in data_dict:
            meta = data_dict['metadata']
            if 'subject_id' in meta and meta['subject_id']:
                metadata['Subject ID'] = meta['subject_id']
            if 'timestamp' in meta:
                metadata['Date Created'] = meta['timestamp']
            if 'recording_duration' in meta:
                duration = meta['recording_duration']
                hours, remainder = divmod(int(duration), 3600)
                minutes, seconds = divmod(remainder, 60)
                metadata['Recording Duration'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Number of samples for each data type
        for data_type in ['eeg', 'ppg', 'imu']:
            if data_type in data_dict and not data_dict[data_type].empty:
                sample_count = len(data_dict[data_type])
                if 'time_rel' in data_dict[data_type].columns and len(data_dict[data_type]) > 1:
                    time_diffs = data_dict[data_type]['time_rel'].diff().dropna()
                    if len(time_diffs) > 0:
                        avg_interval = time_diffs.mean()
                        sampling_rate = 1.0 / avg_interval if avg_interval > 0 else 0
                        metadata[f'{data_type.upper()} FS'] = f"{sampling_rate:.1f} Hz"
                    duration = data_dict[data_type]['time_rel'].max() - data_dict[data_type]['time_rel'].min()
                    metadata[f'{data_type.upper()} Duration'] = f"{duration:.2f}s"
                metadata[f'{data_type.upper()} Samples'] = f"{sample_count:,}"
                    
        # Create labels for each metadata item
        for key, value in metadata.items():
            label = QLabel(f"<b>{key}</b>: {value}")
            label.setStyleSheet("""
                QLabel {
                    color: #495057;
                    padding: 2px 2px;
                    background-color: white;
                    border-radius: 2px;
                    border-right: none;
                }
            """)
            self.metadata_labels[key] = label
            self.metadata_layout.addWidget(label)
            
        # Add stretch to push content to top
        self.metadata_layout.addStretch()


class ViewRecordingWidget(QGroupBox):
    """Widget for viewing recorded data"""
    
    # Signals
    view_recording_requested = Signal(str)  # emits file path
    
    def __init__(self, parent=None):
        super().__init__("🖹 View Recording")
        self.parent = parent
        self.current_file_path = ""
        
        self.setup_ui()
        self.setup_connections()
        self.set_enabled(True)
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Data file selection
        file_layout = QHBoxLayout()
        file_label = QLabel("File Path:")
        file_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        file_layout.addWidget(file_label)
        
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a .data file to view...")
        file_layout.addWidget(self.file_edit)
        
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
        self.browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_btn)
        
        # View button on same line
        self.view_btn = QPushButton("View")
        self.view_btn.setFixedWidth(60)
        self.view_btn.setStyleSheet("""
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
        self.view_btn.clicked.connect(self.view_recording)
        file_layout.addWidget(self.view_btn)
        
        layout.addLayout(file_layout)
        
        # Metadata display
        self.metadata_widget = MetadataWidget()
        layout.addWidget(self.metadata_widget)
        
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
            QPushButton {
                background-color: #f8f9fa;
                color: #495057;
                border: 2px solid #007bff;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
            QPushButton:pressed {
                background-color: #bbdefb;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #6c757d;
                border-color: #ced4da;
            }
        """)
        
    def setup_connections(self):
        """Setup signal connections"""
        pass
        
    def browse_file(self):
        """Browse for data file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Recording File",
            "",
            "Data Files (*.data);;All Files (*.*)"
        )
        if file_path:
            self.set_data_file(file_path)
            
    def set_data_file(self, file_path):
        """Set the data file path"""
        self.current_file_path = file_path
        self.file_edit.setText(file_path)
        
        # Enable view button if file exists
        self.view_btn.setEnabled(Path(file_path).exists())
        
    def view_recording(self):
        """View the selected recording"""
        if not self.current_file_path:
            QMessageBox.warning(self, "No File", "Please select a data file first.")
            return
            
        if not Path(self.current_file_path).exists():
            QMessageBox.warning(self, "File Not Found", "The selected file does not exist.")
            return
            
        # Emit signal to load the recording
        self.view_recording_requested.emit(self.current_file_path)
        
    def update_metadata(self, data_dict):
        """Update metadata display"""
        self.metadata_widget.update_metadata(data_dict)
        
    def set_enabled(self, enabled):
        """Enable or disable the widget"""
        self.file_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        # Check if view button should be enabled
        view_enabled = enabled
        if enabled and self.current_file_path:
            view_enabled = Path(self.current_file_path).exists()
        self.view_btn.setEnabled(view_enabled)
