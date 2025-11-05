"""
View Recording Widget - Handles viewing recorded data and metadata
"""

import pickle
import logging
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QLabel, QScrollArea, QWidget, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal
from ..utils import pd


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
        
        # Setup logger
        self.logger = logging.getLogger('MusePy.ViewRecording')
        self.logger.setLevel(logging.DEBUG)
        
        self.setup_ui()
        self.setup_connections()
        self.set_enabled(True)
        
        self.logger.info("ViewRecordingWidget initialized")
        
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
        self.file_edit.setPlaceholderText("Select a .data or .csv file to view...")
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
            "Data Files (*.data);;CSV Files (*.csv);;All Files (*.*)"
        )
        if file_path:
            self.set_data_file(file_path)
            self.logger.info(f"File selected: {file_path}")
            
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
            
        file_path = Path(self.current_file_path)
        if not file_path.exists():
            QMessageBox.warning(self, "File Not Found", "The selected file does not exist.")
            return
        
        self.logger.info(f"Viewing recording: {file_path}")
        
        # Check if the selected file is a CSV file
        if file_path.suffix.lower() == '.csv':
            self.logger.info("CSV file detected, checking for reconstruction...")
            data_file_path = self.handle_csv_file(file_path)
            if data_file_path is None:
                return  # Error was already shown to user
            file_path = data_file_path
            
        # Emit signal to load the recording
        self.view_recording_requested.emit(str(file_path))
        self.logger.info(f"Recording view requested: {file_path}")
        
    def handle_csv_file(self, csv_file_path):
        """
        Handle CSV file selection. Check for .data file existence,
        and if not found, reconstruct it from the three base CSV files.
        
        Returns:
            Path to the .data file, or None if reconstruction failed
        """
        csv_file_path = Path(csv_file_path)
        folder = csv_file_path.parent
        
        # Extract base filename (remove _eeg, _imu, _ppg, or _combined suffix)
        filename = csv_file_path.stem
        for suffix in ['_eeg', '_imu', '_ppg', '_combined']:
            if filename.endswith(suffix):
                filename = filename[:-len(suffix)]
                break
        
        self.logger.info(f"Base filename extracted: {filename}")
        
        # Check if .data file exists
        data_file_path = folder / f"{filename}.data"
        if data_file_path.exists():
            self.logger.info(f".data file already exists: {data_file_path}")
            return data_file_path
        
        # Check if combined CSV exists - if yes, just need to create .data from it
        combined_csv_path = folder / f"{filename}_combined.csv"
        if combined_csv_path.exists():
            self.logger.info(f"Combined CSV exists, creating .data from it: {combined_csv_path}")
            return self.create_data_from_combined_csv(folder, filename, combined_csv_path)
        
        # Check if all three base CSV files exist
        eeg_path = folder / f"{filename}_eeg.csv"
        imu_path = folder / f"{filename}_imu.csv"
        ppg_path = folder / f"{filename}_ppg.csv"
        
        existing_files = []
        missing_files = []
        
        for file_path, name in [(eeg_path, 'EEG'), (imu_path, 'IMU'), (ppg_path, 'PPG')]:
            if file_path.exists():
                existing_files.append((file_path, name))
                self.logger.info(f"{name} CSV found: {file_path}")
            else:
                missing_files.append(name)
                self.logger.warning(f"{name} CSV not found: {file_path}")
        
        # If not all three exist, show error
        if len(existing_files) < 3:
            error_msg = (
                f"Cannot reconstruct .data file for '{filename}'.\n\n"
                f"Found: {', '.join([name for _, name in existing_files])}\n"
                f"Missing: {', '.join(missing_files)}\n\n"
                f"All three CSV files (EEG, IMU, PPG) are required to reconstruct the recording."
            )
            self.logger.error(error_msg)
            QMessageBox.warning(self, "Missing Files", error_msg)
            return None
        
        # All three files exist - reconstruct the .data file
        self.logger.info("All three base CSV files found. Reconstructing .data file...")
        return self.reconstruct_data_file(folder, filename, eeg_path, imu_path, ppg_path)
    
    def create_data_from_combined_csv(self, folder, filename, combined_csv_path):
        """Create .data file from existing combined CSV"""
        try:
            self.logger.info(f"Reading combined CSV: {combined_csv_path}")
            combined_df = pd.read_csv(combined_csv_path)
            
            # For now, treat the combined data as EEG data
            # In the future, could split it back into EEG, IMU, PPG
            recorded_data = {
                'eeg': combined_df,
                'metadata': {
                    'filename': filename,
                    'subject_id': '',
                    'description': 'Reconstructed from combined CSV',
                    'recording_duration': 0,
                    'timestamp': datetime.now().strftime("%H:%M:%S - %d/%m/%Y"),
                    'reconstructed': True
                }
            }
            
            # Save .data file
            data_path = folder / f"{filename}.data"
            with open(data_path, 'wb') as f:
                pickle.dump(recorded_data, f)
            
            self.logger.info(f"Created .data file from combined CSV: {data_path}")
            QMessageBox.information(
                self, 
                "File Reconstructed", 
                f"Successfully created .data file from combined CSV:\n{data_path}"
            )
            
            return data_path
            
        except Exception as e:
            error_msg = f"Failed to create .data file from combined CSV: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Error", error_msg)
            return None
    
    def reconstruct_data_file(self, folder, filename, eeg_path, imu_path, ppg_path):
        """
        Reconstruct .data file and combined CSV from the three base CSV files.
        This is the recovery feature for when the app froze during recording.
        """
        try:
            self.logger.info("Starting .data file reconstruction...")
            
            # Read all three CSV files
            self.logger.info(f"Reading EEG CSV: {eeg_path}")
            eeg_df = pd.read_csv(eeg_path)
            
            self.logger.info(f"Reading IMU CSV: {imu_path}")
            imu_df = pd.read_csv(imu_path)
            
            self.logger.info(f"Reading PPG CSV: {ppg_path}")
            ppg_df = pd.read_csv(ppg_path)
            
            self.logger.info(f"Loaded: EEG={len(eeg_df)} rows, IMU={len(imu_df)} rows, PPG={len(ppg_df)} rows")
            
            # Create combined CSV
            combined_df = None
            
            # Start with EEG as base
            if not eeg_df.empty:
                combined_df = eeg_df.copy()
                self.logger.debug(f"Base EEG data: {len(combined_df)} rows")
            
            # Merge IMU data
            if not imu_df.empty and combined_df is not None:
                if 'timestamp' in combined_df.columns and 'timestamp' in imu_df.columns:
                    combined_df = pd.merge_asof(
                        combined_df.sort_values('timestamp'),
                        imu_df.sort_values('timestamp'),
                        on='timestamp',
                        direction='nearest',
                        suffixes=('', '_imu')
                    )
                    self.logger.debug(f"Merged IMU data: {len(imu_df)} rows")
            
            # Merge PPG data
            if not ppg_df.empty and combined_df is not None:
                if 'timestamp' in combined_df.columns and 'timestamp' in ppg_df.columns:
                    combined_df = pd.merge_asof(
                        combined_df.sort_values('timestamp'),
                        ppg_df.sort_values('timestamp'),
                        on='timestamp',
                        direction='nearest',
                        suffixes=('', '_ppg')
                    )
                    self.logger.debug(f"Merged PPG data: {len(ppg_df)} rows")
            
            # Save combined CSV
            if combined_df is not None and not combined_df.empty:
                combined_csv_path = folder / f"{filename}_combined.csv"
                combined_df.to_csv(combined_csv_path, index=False)
                self.logger.info(f"Created combined CSV: {combined_csv_path} ({len(combined_df)} rows)")
            
            # Calculate recording duration
            recording_duration = 0
            if not eeg_df.empty and 'time_rel' in eeg_df.columns:
                recording_duration = eeg_df['time_rel'].max() - eeg_df['time_rel'].min()
            
            # Create metadata
            metadata = {
                'filename': filename,
                'subject_id': '',
                'description': 'Reconstructed from CSV files (recovery mode)',
                'recording_duration': recording_duration,
                'timestamp': datetime.now().strftime("%H:%M:%S - %d/%m/%Y"),
                'reconstructed': True
            }
            
            # Create recorded_data dictionary
            recorded_data = {
                'eeg': eeg_df,
                'imu': imu_df,
                'ppg': ppg_df,
                'metadata': metadata
            }
            
            # Save .data file
            data_path = folder / f"{filename}.data"
            with open(data_path, 'wb') as f:
                pickle.dump(recorded_data, f)
            
            self.logger.info(f"Successfully created .data file: {data_path}")
            
            # Show success message
            QMessageBox.information(
                self, 
                "File Reconstructed", 
                f"Successfully reconstructed .data file and combined CSV from base CSV files:\n\n"
                f"Created:\n"
                f"  • {filename}.data\n"
                f"  • {filename}_combined.csv\n\n"
                f"This recording can now be viewed normally."
            )
            
            return data_path
            
        except Exception as e:
            error_msg = f"Failed to reconstruct .data file: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Reconstruction Error", error_msg)
            return None
    
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
