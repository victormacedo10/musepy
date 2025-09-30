"""
Connect Device Widget - Handles device selection and connection
"""

from PySide6.QtWidgets import (
    QGroupBox, QSizePolicy, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel, QMessageBox
)
from PySide6.QtCore import Signal, QThread
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

# NEW: for BLE scan
import asyncio

# ---------- Workers ----------

class MuseScanWorker(QThread):
    """Worker to scan BLE for Muse devices without blocking UI"""
    success = Signal(list)   # list of device names like ["Muse-41D2", "Muse-7A3B"]
    failure = Signal(Exception)
    progress = Signal(str)

    def __init__(self, timeout_sec: float = 5.0):
        super().__init__()
        self.timeout_sec = timeout_sec

    async def _scan_async(self):
        try:
            from bleak import BleakScanner  # import here to give a clean error if missing
        except Exception as e:
            raise RuntimeError(
                "Bleak is required for BLE scanning. Install it with 'pip install bleak'."
            ) from e

        self.progress.emit("Scanning for BLE devices...")
        devices = await BleakScanner.discover(timeout=self.timeout_sec)
        # Filter by Muse advertising name
        names = []
        for d in devices:
            # Some platforms report None names until metadata resolves; keep it defensive
            if d.name and d.name.startswith("Muse-"):
                names.append(d.name)
        # De-duplicate while preserving order
        seen = set()
        unique = [n for n in names if not (n in seen or seen.add(n))]
        return unique

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            names = loop.run_until_complete(self._scan_async())
            loop.close()
            self.success.emit(names)
        except Exception as e:
            self.failure.emit(e)


class BoardConnectWorker(QThread):
    """Worker thread for board connection to avoid blocking UI"""
    success = Signal(object)  # emit the board instance
    failure = Signal(Exception)
    progress = Signal(str)

    def __init__(self, board_id, serial_number: str | None):
        super().__init__()
        self.board_id = board_id
        self.serial_number = serial_number

    def run(self):
        try:
            self.progress.emit("Initializing connection...")
            params = BrainFlowInputParams()
            # Pass the chosen Muse identifier (the BLE device *name* "Muse-XXXX")
            if self.serial_number:
                params.serial_number = self.serial_number

            self.progress.emit("Creating board instance...")
            board = BoardShim(self.board_id, params)

            self.progress.emit("Preparing session...")
            board.prepare_session()

            self.progress.emit("Configuring board...")
            if self.board_id == BoardIds.MUSE_S_BOARD:
                board.config_board("p61")  # enable PPG in ANCILLARY for Muse S
            elif self.board_id == BoardIds.MUSE_2_BOARD:
                board.config_board("p50")  # enable PPG in ANCILLARY for Muse 2

            self.progress.emit("Starting stream...")
            board.start_stream()

            self.progress.emit("Connection successful!")
            self.success.emit(board)

        except Exception as e:
            self.failure.emit(e)


# ---------- Widget ----------

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
        self.scan_worker = None

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Row 0: Device ID (Muse-XXXX) + Scan button ---
        id_layout = QHBoxLayout()

        id_label = QLabel("Device ID:")
        id_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        id_layout.addWidget(id_label)

        self.device_id_combo = QComboBox()
        self.device_id_combo.setMinimumWidth(140)
        id_layout.addWidget(self.device_id_combo, 1)

        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        id_layout.addWidget(self.scan_btn)

        layout.addLayout(id_layout)

        # --- Row 1: Device TYPE + Connect toggle ---
        device_layout = QHBoxLayout()

        type_label = QLabel("Choose Device:")
        type_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        device_layout.addWidget(type_label)

        self.device_combo = QComboBox()
        self.device_combo.addItem("Muse 2", BoardIds.MUSE_2_BOARD)
        self.device_combo.addItem("Muse S", BoardIds.MUSE_S_BOARD)
        self.device_combo.setMinimumWidth(120)
        device_layout.addWidget(self.device_combo)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setCheckable(True)
        self.connect_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if self.parent and hasattr(self.parent, "demo_mode") and self.parent.demo_mode:
            self.connect_btn.setEnabled(True)
        else:
            self.connect_btn.setEnabled(False)  # Start disabled until a scan finds devices
        device_layout.addWidget(self.connect_btn)

        layout.addLayout(device_layout)

        # Styling (reuse your existing QSS)
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
            }
            QComboBox:focus { border-color: #007bff; }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ced4da;
                selection-background-color: #007bff;
                selection-color: white;
                color: black;
            }
            QComboBox::drop-down { border: none; width: 0px; }
            QComboBox::down-arrow { image: none; width: 0; height: 0; }
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:pressed { background-color: #1e7e34; }
            QPushButton:checked { background-color: #dc3545; }
            QPushButton:checked:hover { background-color: #c82333; }
            QPushButton:disabled { background-color: #6c757d; color: #ffffff; }
        """)

    def setup_connections(self):
        self.connect_btn.toggled.connect(self.toggle_connection)
        self.scan_btn.clicked.connect(self.scan_for_devices)

    # ---------- Scan flow ----------

    def scan_for_devices(self):
        """Scan BLE for Muse devices and populate the ID combo"""
        # UI prep
        self.scan_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        self.device_id_combo.clear()

        self.scan_worker = MuseScanWorker(timeout_sec=5.0)
        self.scan_worker.progress.connect(self.on_scan_progress)
        self.scan_worker.success.connect(self.on_scan_success)
        self.scan_worker.failure.connect(self.on_scan_failure)
        self.scan_worker.start()

    def on_scan_progress(self, msg: str):
        print(f"Scan: {msg}")

    def on_scan_success(self, names: list[str]):
        self.scan_btn.setEnabled(True)

        if not names:
            QMessageBox.information(
                self, "No Muse Found",
                "No Muse devices were found nearby.\n"
                "• Make sure the headband is in BLE pairing mode (LED on, not connected)\n"
                "• Keep it close to the computer\n"
                "• Try rescanning"
            )
            # keep Connect disabled
            self.connect_btn.setEnabled(False)
            return

        # Populate dropdown with names (Muse-XXXX)
        for n in names:
            self.device_id_combo.addItem(n, n)
        self.device_id_combo.setCurrentIndex(0)

        # Enable Connect now that we have at least one target
        self.connect_btn.setEnabled(True)  # <-- if you truly wanted it disabled, flip to False

    def on_scan_failure(self, e: Exception):
        self.scan_btn.setEnabled(True)
        self.connect_btn.setEnabled(False)
        QMessageBox.critical(
            self, "Scan Failed",
            f"Failed to scan for Muse devices.\n\n{e}"
        )

    # ---------- Connect / Disconnect ----------

    def toggle_connection(self, checked):
        if checked:
            self.connect_device()
        else:
            self.disconnect_device()

    def connect_device(self):
        """Connect to the selected device"""
        if self.parent and hasattr(self.parent, "demo_mode") and self.parent.demo_mode:
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setEnabled(True)
            self.device_combo.setEnabled(False)
            self.device_id_combo.setEnabled(False)
            self.scan_btn.setEnabled(False)
            self.device_connected.emit(None)
            return

        # Require a discovered ID
        serial_id = self.device_id_combo.currentData()
        if not serial_id:
            QMessageBox.warning(
                self, "Select Device",
                "No Muse device ID selected. Scan and pick a Muse-XXXX before connecting."
            )
            self.connect_btn.setChecked(False)
            return

        board_id = self.device_combo.currentData()

        # Update UI
        self.connect_btn.setText("Connecting...")
        self.connect_btn.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.device_id_combo.setEnabled(False)
        self.scan_btn.setEnabled(False)

        # Start connection worker with the chosen serial_number
        self.conn_worker = BoardConnectWorker(board_id, serial_id)
        self.conn_worker.success.connect(self.on_connection_success)
        self.conn_worker.failure.connect(self.on_connection_failure)
        self.conn_worker.progress.connect(self.on_connection_progress)
        self.conn_worker.start()

    def disconnect_device(self):
        """Disconnect from the device"""
        if self.parent and hasattr(self.parent, "demo_mode") and self.parent.demo_mode:
            self.connect_btn.setText("Connect")
            self.device_combo.setEnabled(True)
            self.device_id_combo.setEnabled(True)
            self.scan_btn.setEnabled(True)
            self.device_disconnected.emit()
            return

        if self.board:
            try:
                self.board.stop_stream()
                self.board.release_session()
            except Exception as e:
                print(f"Error disconnecting board: {e}")
            finally:
                self.board = None

        # Reset UI
        self.connect_btn.setText("Connect")
        self.device_combo.setEnabled(True)
        self.device_id_combo.setEnabled(True)
        self.scan_btn.setEnabled(True)
        self.device_disconnected.emit()

    def on_connection_success(self, board):
        self.board = board
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setEnabled(True)
        self.device_connected.emit(board)

    def on_connection_failure(self, exception):
        QMessageBox.critical(
            self, "Connection Failed",
            f"Failed to connect to device:\n{exception}"
        )
        self.connect_btn.setChecked(False)
        self.connect_btn.setText("Connect")
        self.connect_btn.setEnabled(True)
        self.device_combo.setEnabled(True)
        self.device_id_combo.setEnabled(True)
        self.scan_btn.setEnabled(True)

    def on_connection_progress(self, message):
        print(f"Connection: {message}")

    # Helpers (unchanged)
    def get_selected_device(self):
        return self.device_combo.currentText()

    def is_connected(self):
        return self.connect_btn.isChecked()
