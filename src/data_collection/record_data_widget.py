"""
Record Data Widget - Handles data recording controls
"""

import sys
import pickle
import io
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QLabel, QTextEdit, QFileDialog, QMessageBox, QScrollArea, QWidget
)
from PySide6.QtCore import Signal, QTimer, Qt, QThread
from PySide6.QtGui import QPixmap, QIcon
from ..utils import pd

# Google Drive imports
GOOGLE_DRIVE_AVAILABLE = False
GOOGLE_DRIVE_IMPORT_ERROR = None
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_DRIVE_AVAILABLE = True
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
except ImportError as e:
    GOOGLE_DRIVE_AVAILABLE = False
    GOOGLE_DRIVE_IMPORT_ERROR = str(e)
    print(f"Google Drive libraries not available: {e}")


def get_resource_path():
    """Get the base path for read-only resources (bundled with app), compatible with PyInstaller"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - resources are in the bundle
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent.parent.parent


def get_config_path():
    """Get the path for writable configuration files (user directory), compatible with PyInstaller"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use user's config directory
        if sys.platform == 'darwin':  # macOS
            config_dir = Path.home() / 'Library' / 'Application Support' / 'MusePy'
        elif sys.platform == 'win32':  # Windows
            config_dir = Path.home() / 'AppData' / 'Local' / 'MusePy'
        else:  # Linux
            config_dir = Path.home() / '.config' / 'musepy'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    else:
        # Running as script - use google_drive folder
        return Path(__file__).parent.parent.parent / 'google_drive'


class GDriveAuthWorker(QThread):
    """Worker thread for Google Drive authentication to avoid blocking UI"""
    authentication_complete = Signal(object)  # Emits service object or None
    authentication_failed = Signal(str)  # Emits error message
    
    def __init__(self, credentials_file, token_file, scopes, parent=None):
        super().__init__(parent)
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.scopes = scopes
        # Setup logger
        self.logger = logging.getLogger('MusePy.GDriveAuth')
        self.logger.setLevel(logging.DEBUG)
        
    def run(self):
        """Run authentication in background thread"""
        try:
            self.logger.info("Starting Google Drive authentication worker thread")
            creds = None
            
            # Check for existing token
            if self.token_file.exists():
                self.logger.debug(f"Found existing token file: {self.token_file}")
                try:
                    creds = Credentials.from_authorized_user_file(str(self.token_file), self.scopes)
                    self.logger.debug(f"Loaded credentials from token file. Valid: {creds.valid if creds else False}")
                except Exception as e:
                    self.logger.warning(f"Failed to load credentials from token file: {e}")
                    creds = None
            else:
                self.logger.debug("No existing token file found")
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    self.logger.info("Credentials expired, attempting to refresh...")
                    try:
                        creds.refresh(Request())
                        self.logger.info("Successfully refreshed credentials")
                    except Exception as e:
                        self.logger.warning(f"Failed to refresh credentials: {e}, need to re-authenticate")
                        # Refresh failed, need to re-authenticate
                        creds = None
                
                if not creds:
                    # Need to authenticate via browser
                    self.logger.info("No valid credentials, starting browser authentication...")
                    self.logger.debug(f"Credentials file: {self.credentials_file}")
                    self.logger.debug(f"Credentials file exists: {self.credentials_file.exists()}")
                    
                    if not self.credentials_file.exists():
                        error_msg = f"Credentials file not found: {self.credentials_file}"
                        self.logger.error(error_msg)
                        self.authentication_failed.emit(error_msg)
                        return
                    
                    try:
                        self.logger.info("Creating OAuth flow and opening browser...")
                        flow = InstalledAppFlow.from_client_secrets_file(
                            str(self.credentials_file), self.scopes)
                        self.logger.info("Starting local server for OAuth callback...")
                        creds = flow.run_local_server(port=0)
                        self.logger.info("OAuth flow completed successfully")
                    except KeyboardInterrupt:
                        # User interrupted (Ctrl+C)
                        self.logger.warning("Authentication interrupted by user")
                        self.authentication_failed.emit("Authentication cancelled by user")
                        return
                    except Exception as e:
                        # Handle all OAuth errors (including cancellation/denial)
                        error_msg = str(e)
                        error_type = type(e).__name__
                        self.logger.warning(f"OAuth flow error ({error_type}): {error_msg}")
                        
                        # Check for cancellation indicators in error message or type
                        if ('access_denied' in error_msg.lower() or 
                            'cancelled' in error_msg.lower() or
                            'denied' in error_msg.lower() or
                            'user' in error_type.lower()):
                            self.authentication_failed.emit("Authentication cancelled by user")
                        else:
                            self.authentication_failed.emit(f"Authentication failed: {error_msg}")
                        return
                    
                    # Save the credentials for the next run
                    try:
                        self.logger.info(f"Saving credentials to: {self.token_file}")
                        with open(self.token_file, 'w') as token:
                            token.write(creds.to_json())
                        self.logger.info("Credentials saved successfully")
                    except Exception as e:
                        error_msg = f"Failed to save credentials: {str(e)}"
                        self.logger.error(error_msg, exc_info=True)
                        self.authentication_failed.emit(error_msg)
                        return
            
            # Build and return service
            self.logger.info("Building Google Drive service...")
            service = build('drive', 'v3', credentials=creds)
            self.logger.info("Google Drive service created successfully")
            self.authentication_complete.emit(service)
            
        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.authentication_failed.emit(error_msg)


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
        
        # Setup logger (use the same logger as parent if available)
        self.logger = logging.getLogger('MusePy.RecordData')
        self.logger.setLevel(logging.DEBUG)
        
        # Setup default data folder
        resource_path = get_resource_path()
        self.default_data_folder = resource_path / "data"
        self.default_data_folder.mkdir(exist_ok=True)
        
        # Google Drive settings
        self.gdrive_enabled = True
        self.gdrive_service = None
        self.gdrive_folder_id = None
        self.gdrive_auth_worker = None
        self.gdrive_auth_in_progress = False
        
        self.setup_ui()
        self.load_data_folder_preference()  # Load saved data folder path
        self.setup_connections()
        self.load_gdrive_settings()
        self.set_enabled(False)  # Initially disabled until device is connected
        
        # Log Google Drive availability status
        if GOOGLE_DRIVE_AVAILABLE:
            self.logger.info("Google Drive libraries are available")
        else:
            self.logger.warning(f"Google Drive libraries not available. Import error: {GOOGLE_DRIVE_IMPORT_ERROR}")
        
        self.logger.info("RecordDataWidget initialized")
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Create scroll area for form fields
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { background-color: white; }")
        
        # Create widget to hold the scrollable content
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("QWidget { background-color: white; }")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        scroll_layout.addLayout(folder_layout)
        
        # Subject ID
        subject_layout = QHBoxLayout()
        subject_label = QLabel("Subject ID:")
        subject_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        subject_layout.addWidget(subject_label)
        
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("Enter subject ID (optional)")
        subject_layout.addWidget(self.subject_edit)
        
        scroll_layout.addLayout(subject_layout)
        
        # File name
        file_layout = QHBoxLayout()
        file_label = QLabel("File Name:")
        file_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        file_layout.addWidget(file_label)
        
        self.filename_edit = QLineEdit()
        self.filename_edit.setText(datetime.now().strftime("%Y%m%d_%H%M%S"))
        file_layout.addWidget(self.filename_edit)
        
        scroll_layout.addLayout(file_layout)

        # Description
        desc_label = QLabel("Description:")
        desc_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        scroll_layout.addWidget(desc_label)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setPlaceholderText("Enter recording description...")
        scroll_layout.addWidget(self.description_edit)
        
        # Set the scroll widget
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Record button, timer, and Google Drive button
        record_layout = QHBoxLayout()
        
        # Recording timer display (first)
        self.timer_label = QLabel("00:00:00s")
        self.timer_label.setFixedWidth(90)
        self.timer_label.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
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
                min-width: 90px;
                text-align: center;
            }
        """)
        record_layout.addWidget(self.timer_label)
        
        # Start Recording button (second)
        self.record_btn = QPushButton("Start Recording")
        self.record_btn.setFixedHeight(40)
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self.toggle_recording)
        record_layout.addWidget(self.record_btn)
        
        # Google Drive toggle button (third)
        self.gdrive_btn = QPushButton()
        self.gdrive_btn.setFixedSize(40, 40)
        self.gdrive_btn.setCheckable(True)
        self.gdrive_btn.setChecked(True)  # Selected by default
        self.gdrive_btn.setToolTip("Upload to Google Drive")
        self.gdrive_btn.clicked.connect(self.toggle_gdrive)
        
        # Load Google Drive logo
        logo_path = get_resource_path() / "assets" / "gd_logo.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                # Scale to fit button
                scaled_pixmap = pixmap.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.gdrive_btn.setIcon(QIcon(scaled_pixmap))
        else:
            self.gdrive_btn.setText("GD")
            self.gdrive_btn.setToolTip("Upload to Google Drive (logo not found)")
        
        # Style the Google Drive button
        self.gdrive_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 2px solid #6c757d;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:checked {
                background-color: #d4edda;
                border: 2px solid #28a745;
            }
            QPushButton:checked:hover {
                background-color: #c3e6cb;
                border: 2px solid #218838;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                border-color: #ced4da;
            }
        """)
        
        record_layout.addWidget(self.gdrive_btn)
        
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
            self.save_data_folder_preference(folder)  # Save the selected folder
    
    def save_data_folder_preference(self, folder_path):
        """Save the data folder path to preferences file"""
        try:
            config_path = get_config_path()
            prefs_file = config_path / "data_folder_preference.txt"
            with open(prefs_file, 'w', encoding='utf-8') as f:
                f.write(str(folder_path))
            self.logger.debug(f"Saved data folder preference: {folder_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save data folder preference: {e}")
    
    def load_data_folder_preference(self):
        """Load the saved data folder path from preferences file"""
        try:
            config_path = get_config_path()
            prefs_file = config_path / "data_folder_preference.txt"
            if prefs_file.exists():
                with open(prefs_file, 'r', encoding='utf-8') as f:
                    saved_path = f.read().strip()
                if saved_path and Path(saved_path).exists():
                    self.folder_edit.setText(saved_path)
                    self.logger.debug(f"Loaded data folder preference: {saved_path}")
                    return
            # If no preference file or path doesn't exist, use default
            self.logger.debug("No saved data folder preference found, using default")
        except Exception as e:
            self.logger.warning(f"Failed to load data folder preference: {e}")
            
    def toggle_recording(self):
        """Toggle recording on/off"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()
            
    def start_recording(self):
        """Start recording"""
        if not self.parent or not hasattr(self.parent, 'is_connected') or not self.parent.is_connected:
            self.logger.warning("Attempted to start recording without device connection")
            QMessageBox.warning(self, "Not Connected", "Please connect to a device first.")
            self.record_btn.setChecked(False)
            return
            
        self.is_recording = True
        self.recording_start_time = datetime.now()
        self.logger.info(f"Recording started at {self.recording_start_time}")
        
        # Update UI
        self.record_btn.setText("Stop Recording")
        self.record_btn.setChecked(True)
        self.folder_edit.setEnabled(False)
        self.subject_edit.setEnabled(False)
        self.description_edit.setEnabled(False)
        self.filename_edit.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.logger.debug("UI updated for recording state")
        
        # Start timer
        self.recording_timer.start(1000)  # Update every second
        self.logger.debug("Recording timer started")
        
        # Emit signal
        self.recording_started.emit()
        self.logger.debug("Recording started signal emitted")
        
    def stop_recording(self):
        """Stop recording"""
        self.logger.info("Stopping recording...")
        self.is_recording = False
        
        # Stop timer
        self.recording_timer.stop()
        self.logger.debug("Recording timer stopped")
        
        # Update UI
        self.record_btn.setText("Start Recording")
        self.record_btn.setChecked(False)
        self.folder_edit.setEnabled(True)
        self.subject_edit.setEnabled(True)
        self.description_edit.setEnabled(True)
        self.filename_edit.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.logger.debug("UI updated for stopped state")
        
        # Reset timer display
        self.timer_label.setText("00:00:00s")
        
        # Collect recorded data from CSV files
        recorded_data = {}
        
        # Read CSV files that were written incrementally
        try:
            data_folder = self.get_data_folder()
            subject_id = self.get_subject_id()
            filename = self.filename_edit.text()
            
            # Determine recording folder
            if subject_id:
                recording_folder = Path(data_folder) / subject_id
            else:
                recording_folder = Path(data_folder)
            
            self.logger.info(f"Reading CSV files from: {recording_folder}")
            
            # Read each CSV file
            for data_type in ['eeg', 'imu', 'ppg']:
                csv_path = recording_folder / f"{filename}_{data_type}.csv"
                if csv_path.exists():
                    try:
                        df = pd.read_csv(csv_path)
                        if not df.empty:
                            recorded_data[data_type] = df
                            self.logger.info(f"Read {len(df)} rows from {data_type} CSV")
                        else:
                            self.logger.warning(f"{data_type} CSV is empty")
                    except Exception as e:
                        self.logger.error(f"Error reading {data_type} CSV: {e}", exc_info=True)
                else:
                    self.logger.warning(f"{data_type} CSV not found: {csv_path}")
            
            # Add metadata
            recorded_data['metadata'] = {
                'filename': filename,
                'subject_id': subject_id, 
                'description': self.description_edit.toPlainText(),
                'recording_duration': self.get_recording_duration(),
                'timestamp': datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
            }
            self.logger.debug(f"Metadata created: {recorded_data['metadata']}")
            
            # Save recording with proper file structure (merge CSVs and create .data file)
            if recorded_data:
                file_path = self.save_recording_with_files(recorded_data)
                if file_path:
                    recorded_data['file_path'] = file_path
                    self.logger.info(f"Recording saved to: {file_path}")
                else:
                    self.logger.error("Failed to save recording")
        except Exception as e:
            self.logger.error(f"Error processing recorded data: {e}", exc_info=True)
                    
        # Emit signal with recorded data
        self.recording_stopped.emit(recorded_data)
        self.logger.debug("Recording stopped signal emitted")
        
        # Update filename for next recording
        self.filename_edit.setText(datetime.now().strftime("%Y%m%d_%H%M%S"))
        self.logger.info(f"Recording stop complete. Duration: {self.get_recording_duration():.2f}s")
        
    def save_recording_with_files(self, recorded_data):
        """Save recording with proper file structure"""
        try:
            self.logger.info("Saving recording with files...")
            
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
            self.logger.debug(f"Save folder: {save_folder}")
            
            # Individual CSV files are already saved incrementally by data_collection_widget
            for key in ['eeg', 'imu', 'ppg']:
                csv_path = save_folder / f"{filename}_{key}.csv"
                if csv_path.exists():
                    self.logger.info(f"Individual CSV exists: {csv_path}")
                        
            # Save combined .data file (always)
            data_path = save_folder / f"{filename}.data"
            with open(data_path, 'wb') as f:
                pickle.dump(recorded_data, f)
            self.logger.info(f"Saved .data file: {data_path}")
                
            # Save description if provided (always)
            if description:
                desc_path = save_folder / f"{filename}_description.txt"
                with open(desc_path, 'w') as f:
                    f.write(description)
                self.logger.info(f"Saved description: {desc_path}")
                    
            self.logger.info(f"Recording saved successfully: {filename}")
            
            # Upload to Google Drive if enabled
            if self.gdrive_enabled:
                try:
                    self.logger.info("Google Drive upload is enabled, starting upload process...")
                    # Determine what to upload
                    subject_id = self.get_subject_id()
                    if subject_id:
                        # Upload the entire subject folder
                        upload_path = save_folder
                        self.logger.info(f"Preparing to upload folder: {upload_path}")
                        self.upload_to_gdrive_async(upload_path, subject_id)
                    else:
                        # Upload just the data file
                        upload_path = data_path
                        self.logger.info(f"Preparing to upload file: {upload_path}")
                        self.upload_to_gdrive_async(upload_path)
                except Exception as e:
                    self.logger.error(f"❌ Error during Google Drive upload: {e}", exc_info=True)
                    QMessageBox.warning(self, "Upload Warning", 
                                      f"Recording saved locally but failed to upload to Google Drive: {str(e)}")
            else:
                self.logger.info("Google Drive upload is disabled, skipping upload")
            
            return str(data_path)
            
        except Exception as e:
            self.logger.error(f"Error saving recording: {str(e)}", exc_info=True)
            return False
            
    def update_timer(self):
        """Update the recording timer display using relative time from stream data"""
        if self.parent and hasattr(self.parent, 'stream_data') and not self.parent.stream_data.empty:
            if 'time_rel' in self.parent.stream_data.columns:
                time_rel_data = np.array(self.parent.stream_data._data['time_rel'], dtype=float)
                if time_rel_data.size > 0:
                    elapsed = time_rel_data[-1] - time_rel_data[0]
                    if elapsed < 0:
                        elapsed = 0
                    hours, remainder = divmod(int(round(elapsed)), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}s")
                    return

        # Fallback to elapsed wall-clock time if stream data not available
        if self.recording_start_time:
            elapsed = datetime.now() - self.recording_start_time
            total_seconds = int(elapsed.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}s")
            
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
        # Google Drive button is always enabled (can be toggled independently)
        
    def get_data_folder(self):
        """Get the current data folder path"""
        return self.folder_edit.text()
        
    def get_subject_id(self):
        """Get the current subject ID"""
        return self.subject_edit.text().strip()
        
    def get_description(self):
        """Get the current description"""
        return self.description_edit.toPlainText().strip()
        
    def toggle_gdrive(self):
        """Toggle Google Drive upload"""
        # Only check availability when trying to ENABLE, not when disabling
        if self.gdrive_btn.isChecked():  # User is trying to enable
            if not GOOGLE_DRIVE_AVAILABLE:
                error_details = ""
                if GOOGLE_DRIVE_IMPORT_ERROR:
                    error_details = f"\n\nImport error: {GOOGLE_DRIVE_IMPORT_ERROR}"
                QMessageBox.warning(self, "Google Drive Not Available", 
                                  "Google Drive libraries are not installed or not accessible. Please install them to enable upload functionality.\n\n"
                                  f"Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client{error_details}\n\n"
                                  "Note: Make sure you're installing in the correct Python environment.")
                self.gdrive_btn.setChecked(False)
                self.gdrive_enabled = False
                return
        
        # Update enabled state based on button
        self.gdrive_enabled = self.gdrive_btn.isChecked()
        self.logger.info(f"Google Drive upload {'enabled' if self.gdrive_enabled else 'disabled'}")
        if GOOGLE_DRIVE_AVAILABLE:
            self.logger.info("Google Drive libraries are available")
        else:
            self.logger.warning(f"Google Drive libraries not available. Import error: {GOOGLE_DRIVE_IMPORT_ERROR}")
            
    def load_gdrive_settings(self):
        """Load Google Drive settings from files"""
        if not GOOGLE_DRIVE_AVAILABLE:
            # Keep button enabled but show warning tooltip
            self.gdrive_btn.setToolTip("Google Drive libraries not installed - install to enable upload")
            # Uncheck button if libraries aren't available
            self.gdrive_btn.setChecked(False)
            self.gdrive_enabled = False
            self.logger.warning("Google Drive libraries not available, disabling upload")
            return
            
        # Check for credentials.json file (read from bundled resources)
        resource_path = get_resource_path()
        credentials_file = resource_path / "google_drive" / "credentials.json"
        
        if not credentials_file.exists():
            # Uncheck the Google Drive button and update tooltip
            self.gdrive_btn.setChecked(False)
            self.gdrive_btn.setToolTip("Google Drive credentials not found - add credentials.json to enable upload")
            self.gdrive_enabled = False
            self.logger.warning(f"Google Drive credentials not found at: {credentials_file}")
            return
        
        # Credentials found, ensure button state matches enabled state
        # If button is checked, keep it checked; otherwise sync with gdrive_enabled
        if not self.gdrive_btn.isChecked():
            self.gdrive_enabled = False
        else:
            self.gdrive_enabled = True
            
        # Load folder ID (read from bundled resources)
        folder_id_file = resource_path / "google_drive" / "folder_id.txt"
        
        if folder_id_file.exists():
            try:
                with open(folder_id_file, 'r') as f:
                    self.gdrive_folder_id = f.read().strip()
                self.logger.info(f"Loaded Google Drive folder ID: {self.gdrive_folder_id}")
            except Exception as e:
                self.logger.warning(f"Error loading folder ID: {e}")
                self.gdrive_folder_id = None
        else:
            self.gdrive_folder_id = None
            self.logger.info("No Google Drive folder ID file found")
            
    def authenticate_gdrive(self, callback=None):
        """Authenticates with Google Drive API using OAuth.
        
        Args:
            callback: Optional callback function that receives (service, error) tuple.
                     If None, returns service directly (blocking for existing tokens only).
        
        Returns:
            Service object if callback is None and authentication succeeds immediately,
            None if callback is provided (async) or if authentication fails.
        """
        if not GOOGLE_DRIVE_AVAILABLE:
            if callback:
                callback(None, "Google Drive libraries not available")
            return None
        
        # Paths for read-only resources (bundled with app)
        resource_path = get_resource_path()
        credentials_file = resource_path / "google_drive" / "credentials.json"
        
        # Path for writable token file (user config directory)
        config_path = get_config_path()
        token_file = config_path / "token.json"
        
        # Check if credentials file exists
        if not credentials_file.exists():
            error_msg = f"credentials.json not found at {credentials_file}.\n\nPlease add your Google Drive OAuth credentials."
            if callback:
                callback(None, error_msg)
            else:
                QMessageBox.critical(self, "Google Drive Error", error_msg)
            return None
        
        # Try to load existing credentials first (fast path)
        try:
            if token_file.exists():
                creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
                
                # If credentials are valid, return immediately
                if creds and creds.valid:
                    service = build('drive', 'v3', credentials=creds)
                    if callback:
                        callback(service, None)
                    return service
                
                # If expired but has refresh token, try to refresh
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        service = build('drive', 'v3', credentials=creds)
                        # Save refreshed token
                        with open(token_file, 'w') as token:
                            token.write(creds.to_json())
                        if callback:
                            callback(service, None)
                        return service
                    except Exception:
                        # Refresh failed, need to re-authenticate
                        pass
        except Exception:
            # Token file exists but is invalid, need to re-authenticate
            pass
        
        # Need browser authentication - use worker thread to avoid blocking UI
        if callback:
            # Async mode: use worker thread
            if self.gdrive_auth_in_progress:
                self.logger.warning("Authentication already in progress, ignoring new request")
                callback(None, "Authentication already in progress")
                return None
            
            self.logger.info("Starting async authentication with worker thread...")
            self.gdrive_auth_in_progress = True
            
            # Show message to user that browser will open
            QMessageBox.information(self, "Google Drive Authentication", 
                                  "A browser window will open for Google Drive authentication.\n\n"
                                  "Please sign in and grant permissions. You can close this message.")
            
            # Create and start worker thread
            self.gdrive_auth_worker = GDriveAuthWorker(
                credentials_file, token_file, SCOPES, self
            )
            
            def on_auth_complete(service):
                self.logger.info("Authentication completed successfully")
                self.gdrive_auth_in_progress = False
                self.gdrive_service = service
                callback(service, None)
            
            def on_auth_failed(error_msg):
                self.logger.warning(f"Authentication failed: {error_msg}")
                self.gdrive_auth_in_progress = False
                self.gdrive_service = None
                callback(None, error_msg)
            
            self.gdrive_auth_worker.authentication_complete.connect(on_auth_complete)
            self.gdrive_auth_worker.authentication_failed.connect(on_auth_failed)
            self.logger.info("Starting worker thread...")
            self.gdrive_auth_worker.start()
            self.logger.info("Worker thread started")
            return None
        else:
            # Synchronous mode (for backward compatibility, but should be avoided)
            # This will block the UI, but we handle cancellation better
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_file), SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
                    
                service = build('drive', 'v3', credentials=creds)
                return service
            except KeyboardInterrupt:
                # User interrupted
                QMessageBox.warning(self, "Authentication Cancelled", 
                                  "Google Drive authentication was cancelled. "
                                  "Local file has been saved successfully.")
                return None
            except Exception as error:
                # Handle all OAuth errors (including cancellation/denial)
                error_msg = str(error)
                error_type = type(error).__name__
                self.logger.warning(f"OAuth flow error ({error_type}): {error_msg}")
                
                # Check for cancellation indicators in error message or type
                if ('access_denied' in error_msg.lower() or 
                    'cancelled' in error_msg.lower() or
                    'denied' in error_msg.lower() or
                    'user' in error_type.lower()):
                    QMessageBox.warning(self, "Authentication Cancelled", 
                                      "Google Drive authentication was cancelled. "
                                      "Local file has been saved successfully.")
                else:
                    QMessageBox.critical(self, "Google Drive Error", 
                                       f"Authentication error: {error_msg}")
                return None
            
    def upload_to_gdrive_async(self, file_path, subject_id=None):
        """Upload file or folder to Google Drive asynchronously (non-blocking)"""
        if not self.gdrive_enabled:
            self.logger.info("Google Drive upload is disabled (button unchecked)")
            return
        
        if not GOOGLE_DRIVE_AVAILABLE:
            error_details = ""
            if GOOGLE_DRIVE_IMPORT_ERROR:
                error_details = f"\n\nImport error: {GOOGLE_DRIVE_IMPORT_ERROR}"
            error_msg = f"Google Drive libraries are not available. Please install them to enable upload functionality.{error_details}"
            self.logger.error(error_msg)
            QMessageBox.warning(self, "Google Drive Not Available", 
                              f"{error_msg}\n\n"
                              "Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client\n\n"
                              "Note: Make sure you're installing in the correct Python environment.")
            return
        
        file_path = Path(file_path)
        self.logger.info(f"Starting async Google Drive upload for: {file_path}")
        
        def on_auth_complete(service, error):
            """Callback when authentication completes"""
            if error:
                # Authentication failed or was cancelled
                self.logger.warning(f"Google Drive authentication failed: {error}")
                if "cancelled" in error.lower():
                    QMessageBox.information(self, "Upload Cancelled", 
                                          "Google Drive upload was cancelled. "
                                          "Your recording has been saved locally.")
                else:
                    QMessageBox.warning(self, "Upload Warning", 
                                      f"Recording saved locally but Google Drive upload failed: {error}")
                return
            
            if not service:
                self.logger.warning("Google Drive service not available")
                return
            
            self.gdrive_service = service
            self.logger.info("Authentication successful, proceeding with upload...")
            
            # Now perform the upload
            try:
                if file_path.is_file():
                    # Upload single file
                    self.logger.info(f"Uploading single file: {file_path}")
                    upload_success = self._upload_file_to_gdrive(file_path)
                elif file_path.is_dir():
                    # Upload entire folder (subject folder)
                    self.logger.info(f"Uploading folder: {file_path}")
                    upload_success = self._upload_folder_to_gdrive(file_path, subject_id)
                else:
                    self.logger.warning(f"Invalid path for upload: {file_path}")
                    upload_success = False
                
                if upload_success:
                    self.logger.info("✅ Recording uploaded to Google Drive successfully")
                else:
                    self.logger.warning("❌ Failed to upload recording to Google Drive")
                    
            except Exception as e:
                self.logger.error(f"❌ Error during Google Drive upload: {e}", exc_info=True)
                QMessageBox.warning(self, "Upload Warning", 
                                  f"Recording saved locally but failed to upload to Google Drive: {str(e)}")
        
        # Authenticate (async) and then upload
        if self.gdrive_service:
            # Already authenticated, upload directly
            self.logger.info("Already authenticated, uploading directly...")
            on_auth_complete(self.gdrive_service, None)
        else:
            # Need to authenticate first
            self.logger.info("Not authenticated, starting authentication...")
            self.authenticate_gdrive(callback=on_auth_complete)
    
    def upload_to_gdrive(self, file_path, subject_id=None):
        """Upload file or folder to Google Drive (synchronous, for backward compatibility)"""
        if not self.gdrive_enabled or not GOOGLE_DRIVE_AVAILABLE:
            return False
            
        try:
            # Authenticate if we haven't already
            if not self.gdrive_service:
                self.gdrive_service = self.authenticate_gdrive()
                
            if not self.gdrive_service:
                return False
                
            file_path = Path(file_path)
            
            if file_path.is_file():
                # Upload single file
                return self._upload_file_to_gdrive(file_path)
            elif file_path.is_dir():
                # Upload entire folder (subject folder)
                return self._upload_folder_to_gdrive(file_path, subject_id)
            else:
                print(f"Invalid path for upload: {file_path}")
                return False
                
        except Exception as e:
            QMessageBox.critical(self, "Upload Error", f"An error occurred during upload: {str(e)}")
            return False
            
    def _upload_file_to_gdrive(self, file_path):
        """Upload a single file to Google Drive"""
        try:
            file_metadata = {
                'name': file_path.name,
                'mimeType': 'application/octet-stream'
            }
            
            # Add the folder ID if specified
            if self.gdrive_folder_id:
                file_metadata['parents'] = [self.gdrive_folder_id]

            # Create media object for file upload
            media = MediaIoBaseUpload(io.FileIO(str(file_path), 'rb'),
                                      mimetype='application/octet-stream',
                                      resumable=True)
            
            # Call the Drive v3 API to create the file
            file = self.gdrive_service.files().create(body=file_metadata,
                                                      media_body=media,
                                                      fields='id').execute()
                                                      
            print(f"✅ File uploaded successfully: {file_path.name} (ID: {file.get('id')})")
            return True

        except HttpError as error:
            print(f"❌ Error during file upload: {error}")
            return False
        except Exception as e:
            print(f"❌ An unexpected error occurred during file upload: {e}")
            return False
            
    def _upload_folder_to_gdrive(self, folder_path, subject_id):
        """Upload entire folder to Google Drive"""
        try:
            # Create folder in Google Drive first
            folder_metadata = {
                'name': folder_path.name if subject_id else 'MusePy_Recording',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            # Add the folder ID if specified
            if self.gdrive_folder_id:
                folder_metadata['parents'] = [self.gdrive_folder_id]

            # Create the folder in Google Drive
            folder = self.gdrive_service.files().create(body=folder_metadata,
                                                       fields='id').execute()
            
            folder_id = folder.get('id')
            print(f"✅ Created folder in Google Drive: {folder_path.name} (ID: {folder_id})")
            
            # Upload all files in the folder
            uploaded_count = 0
            for file_path in folder_path.iterdir():
                if file_path.is_file():
                    file_metadata = {
                        'name': file_path.name,
                        'parents': [folder_id]
                    }
                    
                    media = MediaIoBaseUpload(io.FileIO(str(file_path), 'rb'),
                                              mimetype='application/octet-stream',
                                              resumable=True)
                    
                    file = self.gdrive_service.files().create(body=file_metadata,
                                                              media_body=media,
                                                              fields='id').execute()
                    uploaded_count += 1
                    print(f"✅ Uploaded: {file_path.name}")
                    
            print(f"✅ Folder upload completed: {uploaded_count} files uploaded")
            return True

        except HttpError as error:
            print(f"❌ Error during folder upload: {error}")
            return False
        except Exception as e:
            print(f"❌ An unexpected error occurred during folder upload: {e}")
            return False
