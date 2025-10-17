"""
Record Data Widget - Handles data recording controls
"""

import pickle
import io
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QLabel, QTextEdit, QFileDialog, QMessageBox, QScrollArea, QWidget
)
from PySide6.QtCore import Signal, QTimer, Qt
from PySide6.QtGui import QPixmap, QIcon
from ..utils import pd

# Google Drive imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_DRIVE_AVAILABLE = True
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False


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
        
        # Google Drive settings
        self.gdrive_enabled = True
        self.gdrive_service = None
        self.gdrive_folder_id = None
        
        self.setup_ui()
        self.setup_connections()
        self.load_gdrive_settings()
        self.set_enabled(False)  # Initially disabled until device is connected
        
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
        logo_path = Path(__file__).parent.parent.parent / "assets" / "gd_logo.png"
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
                        # Add time_rel column for metadata calculation
                        if 'timestamp' in imu_data.columns and self.parent.timestamps_start:
                            imu_data['time_rel'] = imu_data['timestamp'] - self.parent.timestamps_start
                        recorded_data['imu'] = imu_data
                        
                    # Get PPG data
                    ppg_data = self.parent.get_board_data(BrainFlowPresets.ANCILLARY_PRESET)
                    if not ppg_data.empty:
                        # Add time_rel column for metadata calculation
                        if 'timestamp' in ppg_data.columns and self.parent.timestamps_start:
                            ppg_data['time_rel'] = ppg_data['timestamp'] - self.parent.timestamps_start
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
            
            # Upload to Google Drive if enabled
            if self.gdrive_enabled:
                try:
                    # Determine what to upload
                    subject_id = self.get_subject_id()
                    if subject_id:
                        # Upload the entire subject folder
                        upload_path = save_folder
                        upload_success = self.upload_to_gdrive(upload_path, subject_id)
                    else:
                        # Upload just the data file
                        upload_path = data_path
                        upload_success = self.upload_to_gdrive(upload_path)
                    
                    if upload_success:
                        print("✅ Recording uploaded to Google Drive successfully")
                    else:
                        print("❌ Failed to upload recording to Google Drive")
                        
                except Exception as e:
                    print(f"❌ Error during Google Drive upload: {e}")
                    QMessageBox.warning(self, "Upload Warning", 
                                      f"Recording saved locally but failed to upload to Google Drive: {str(e)}")
            
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
        if not GOOGLE_DRIVE_AVAILABLE:
            QMessageBox.warning(self, "Google Drive Not Available", 
                              "Google Drive libraries are not installed. Please install them to enable upload functionality.\n\n"
                              "Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            self.gdrive_btn.setChecked(False)
            self.gdrive_enabled = False
            return
            
        self.gdrive_enabled = self.gdrive_btn.isChecked()
            
    def load_gdrive_settings(self):
        """Load Google Drive settings from files"""
        if not GOOGLE_DRIVE_AVAILABLE:
            # Keep button enabled but show warning tooltip
            self.gdrive_btn.setToolTip("Google Drive libraries not installed - install to enable upload")
            return
            
        # Check for credentials.json file
        base_path = Path(__file__).parent.parent.parent
        credentials_file = base_path / "google_drive" / "credentials.json"
        
        if not credentials_file.exists():
            # Uncheck the Google Drive button and update tooltip
            self.gdrive_btn.setChecked(False)
            self.gdrive_btn.setToolTip("Google Drive credentials not found - add credentials.json to enable upload")
            self.gdrive_enabled = False
            return
            
        # Load folder ID
        folder_id_file = base_path / "google_drive" / "folder_id.txt"
        
        if folder_id_file.exists():
            try:
                with open(folder_id_file, 'r') as f:
                    self.gdrive_folder_id = f.read().strip()
            except Exception as e:
                print(f"Error loading folder ID: {e}")
                self.gdrive_folder_id = None
        else:
            self.gdrive_folder_id = None
            
    def authenticate_gdrive(self):
        """Authenticates with Google Drive API and returns a service object."""
        if not GOOGLE_DRIVE_AVAILABLE:
            return None
            
        creds = None
        base_path = Path(__file__).parent.parent.parent
        token_file = base_path / "google_drive" / "token.json"
        credentials_file = base_path / "google_drive" / "credentials.json"
        
        # The file token.json stores the user's access and refresh tokens.
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
            
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Make sure credentials.json is in the same folder
                if not credentials_file.exists():
                    QMessageBox.critical(self, "Google Drive Error", 
                                       f"credentials.json not found at {credentials_file}. Please add your Google Drive credentials.")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
                creds = flow.run_local_server(port=0)
                
            # Save the credentials for the next run
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
        
        try:
            service = build('drive', 'v3', credentials=creds)
            return service
        except HttpError as error:
            QMessageBox.critical(self, "Google Drive Error", f"An error occurred during authentication: {error}")
            return None
            
    def upload_to_gdrive(self, file_path, subject_id=None):
        """Upload file or folder to Google Drive"""
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
