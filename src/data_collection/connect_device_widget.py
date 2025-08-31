"""
Connect Device Widget - Handles device selection and connection
"""

from PySide6.QtWidgets import (
    QGroupBox, QSizePolicy, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel
)
from PySide6.QtCore import Signal, QThread
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds


class BoardConnectWorker(QThread):
    """Worker thread for board connection to avoid blocking UI"""
    success = Signal(object)  # emit the board instance
    failure = Signal(Exception)
    progress = Signal(str)

    def __init__(self, board_id):
        super().__init__()
        self.board_id = board_id

    def run(self):
        try:
            self.progress.emit("Initializing connection...")
            params = BrainFlowInputParams()
            
            self.progress.emit("Creating board instance...")
            board = BoardShim(self.board_id, params)
            
            self.progress.emit("Preparing session...")
            board.prepare_session()
            
            self.progress.emit("Configuring board...")
            board.config_board('p61')
            
            self.progress.emit("Starting stream...")
            board.start_stream()
            
            self.progress.emit("Connection successful!")
            self.success.emit(board)
            
        except Exception as e:
            self.failure.emit(e)


class ConnectDeviceWidget(QGroupBox):
    """Widget for device connection controls"""
    
    # Signals
    device_connected = Signal(object)  # emits board instance
    device_disconnected = Signal()
    
    def __init__(self, parent=None):
        super().__init__("🔗 Connect Device")
        self.parent = parent
        self.board = None
        self.conn_worker = None
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Device type selection
        device_layout = QHBoxLayout()
        type_label = QLabel("Choose Device:")
        type_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        device_layout.addWidget(type_label)
        
        self.device_combo = QComboBox()
        self.device_combo.addItem("Muse 2", BoardIds.MUSE_2_BOARD)
        self.device_combo.addItem("Muse S", BoardIds.MUSE_S_BOARD)
        device_layout.addWidget(self.device_combo)
        
        # Connect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setCheckable(True)
        self.connect_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        device_layout.addWidget(self.connect_btn)
        
        layout.addLayout(device_layout)
        
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
            QComboBox {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 5px;
                color: #495057;
                min-width: 50px;
            }
            QComboBox:focus {
                border-color: #007bff;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ced4da;
                selection-background-color: #007bff;
                selection-color: white;
                color: black;
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:checked {
                background-color: #dc3545;
            }
            QPushButton:checked:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.connect_btn.toggled.connect(self.toggle_connection)
        
    def toggle_connection(self, checked):
        """Toggle device connection"""
        if checked:
            self.connect_device()
        else:
            self.disconnect_device()
            
    def connect_device(self):
        """Connect to the selected device"""
        if self.parent and hasattr(self.parent, 'demo_mode') and self.parent.demo_mode:
            # Demo mode - simulate connection
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setEnabled(True)
            self.device_combo.setEnabled(False)
            self.device_connected.emit(None)  # No real board in demo mode
            return
            
        # Get selected board ID
        board_id = self.device_combo.currentData()
        
        # Update UI
        self.connect_btn.setText("Connecting...")
        self.connect_btn.setEnabled(False)
        self.device_combo.setEnabled(False)
        
        # Start connection worker
        self.conn_worker = BoardConnectWorker(board_id)
        self.conn_worker.success.connect(self.on_connection_success)
        self.conn_worker.failure.connect(self.on_connection_failure)
        self.conn_worker.progress.connect(self.on_connection_progress)
        self.conn_worker.start()
        
    def disconnect_device(self):
        """Disconnect from the device"""
        if self.parent and hasattr(self.parent, 'demo_mode') and self.parent.demo_mode:
            # Demo mode - simulate disconnection
            self.connect_btn.setText("Connect")
            self.device_combo.setEnabled(True)
            self.device_disconnected.emit()
            return
            
        # Disconnect real board
        if self.board:
            try:
                self.board.stop_stream()
                self.board.release_session()
            except Exception as e:
                print(f"Error disconnecting board: {e}")
            finally:
                self.board = None
                
        # Update UI
        self.connect_btn.setText("Connect")
        self.device_combo.setEnabled(True)
        self.device_disconnected.emit()
        
    def on_connection_success(self, board):
        """Handle successful connection"""
        self.board = board
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setEnabled(True)
        self.device_connected.emit(board)
        
    def on_connection_failure(self, exception):
        """Handle connection failure"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Connection Failed", 
                           f"Failed to connect to device:\n{str(exception)}")
        
        # Reset UI
        self.connect_btn.setChecked(False)
        self.connect_btn.setText("🔗 Connect")
        self.connect_btn.setEnabled(True)
        self.device_combo.setEnabled(True)
        
    def on_connection_progress(self, message):
        """Handle connection progress updates"""
        # Could be used to update status bar or log
        print(f"Connection: {message}")
        
    def get_selected_device(self):
        """Get the currently selected device type"""
        return self.device_combo.currentText()
        
    def is_connected(self):
        """Check if device is connected"""
        return self.connect_btn.isChecked()
