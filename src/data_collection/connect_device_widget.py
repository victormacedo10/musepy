"""
Connect Device Widget - Handles device selection and connection
"""

from PySide6.QtWidgets import (
    QGroupBox, QSizePolicy, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel, QMessageBox
)
from PySide6.QtCore import Signal, QThread
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
import asyncio

# ---------- Workers ----------

class MuseScanWorker(QThread):
    """Worker to scan BLE for Muse devices without blocking UI"""
    success = Signal(list, list)   # (muse_names, all_devices_info)
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

        from datetime import datetime
        
        print(f"\n{'='*60}")
        print(f"🔍 Bluetooth BLE Scanner")
        print(f"{'='*60}")
        print(f"Scan timeout: {self.timeout_sec} seconds")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        self.progress.emit("Scanning for BLE devices...")
        print("Scanning for BLE devices...\n")
        
        devices = await BleakScanner.discover(timeout=self.timeout_sec)
        
        # Collect all device info
        all_devices_info = []
        muse_names = []
        
        for d in devices:
            device_info = {
                'name': d.name if d.name else "(No Name)",
                'address': d.address,
                'rssi': d.rssi if hasattr(d, 'rssi') and d.rssi else "N/A"
            }
            all_devices_info.append(device_info)
            
            # Track Muse devices
            if d.name and d.name.startswith("Muse-"):
                muse_names.append(d.name)
        
        # De-duplicate Muse names while preserving order
        seen = set()
        unique_muse = [n for n in muse_names if not (n in seen or seen.add(n))]
        
        return unique_muse, all_devices_info

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            muse_names, all_devices = loop.run_until_complete(self._scan_async())
            loop.close()
            self.success.emit(muse_names, all_devices)
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
        
        # --- Row 2: Reconnect button (only visible when connected) ---
        self.reconnect_btn = QPushButton("Reconnect Stream")
        self.reconnect_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.reconnect_btn.setEnabled(False)  # Only enabled when connected
        self.reconnect_btn.setVisible(False)  # Hidden by default
        layout.addWidget(self.reconnect_btn)

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
        self.reconnect_btn.clicked.connect(self.trigger_reconnect)

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

    def on_scan_success(self, names: list[str], all_devices: list[dict]):
        self.scan_btn.setEnabled(True)
        
        # Print all discovered devices
        if not all_devices:
            print("❌ No BLE devices found.")
            print("\nTroubleshooting tips:")
            print("  • Make sure Bluetooth is enabled on your computer")
            print("  • Ensure devices are in pairing/discoverable mode")
            print("  • Try moving devices closer to your computer")
            print("  • For Muse headbands: ensure LED is on and not connected to another device\n")
        else:
            print(f"✅ Found {len(all_devices)} device(s):\n")
            print(f"{'No.':<4} {'Device Name':<30} {'MAC Address':<20} {'RSSI':<6}")
            print(f"{'-'*4} {'-'*30} {'-'*20} {'-'*6}")
            
            for idx, device in enumerate(all_devices, 1):
                name = device['name']
                address = device['address']
                rssi = device['rssi']
                print(f"{idx:<4} {name:<30} {address:<20} {rssi:<6}")
            
            print(f"\n{'-'*60}")
            
            # Show Muse-specific devices
            if names:
                print(f"\n🧠 Muse devices found: {len(names)}")
                for name in names:
                    print(f"   • {name}")
            else:
                print("\n🧠 No Muse devices found")
                print("   (Muse device names should start with 'Muse-')")
            
            print(f"\n{'='*60}\n")

        # Show dialog if no Muse devices found
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
        self.connect_btn.setEnabled(True)

    def on_scan_failure(self, e: Exception):
        self.scan_btn.setEnabled(True)
        self.connect_btn.setEnabled(False)
        
        print(f"\n❌ Scan failed: {e}")
        print(f"Error type: {type(e).__name__}\n")
        
        import traceback
        traceback.print_exc()
        
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
            # Hide reconnect button
            self.reconnect_btn.setVisible(False)
            self.reconnect_btn.setEnabled(False)
            self.device_disconnected.emit()
            return

        if self.board:
            try:
                try:
                    self.board.stop_stream()
                except Exception as e:
                    print(f"Error stopping stream during disconnect: {e}")
                
                try:
                    self.board.release_session()
                except Exception as e:
                    print(f"Error releasing session during disconnect: {e}")
            except Exception as e:
                print(f"Error disconnecting board: {e}")
            finally:
                self.board = None

        # Reset UI
        self.connect_btn.setText("Connect")
        self.device_combo.setEnabled(True)
        self.device_id_combo.setEnabled(True)
        self.scan_btn.setEnabled(True)
        # Hide reconnect button
        self.reconnect_btn.setVisible(False)
        self.reconnect_btn.setEnabled(False)
        self.device_disconnected.emit()

    def on_connection_success(self, board):
        self.board = board
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setEnabled(True)
        # Show and enable reconnect button
        self.reconnect_btn.setVisible(True)
        self.reconnect_btn.setEnabled(True)
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
    
    def trigger_reconnect(self):
        """Trigger manual stream reconnection"""
        if self.parent and hasattr(self.parent, 'manual_reconnect'):
            self.parent.manual_reconnect()
        else:
            QMessageBox.warning(
                self,
                "Reconnect Unavailable",
                "Reconnect functionality is not available."
            )

    # Helpers (unchanged)
    def get_selected_device(self):
        return self.device_combo.currentText()

    def is_connected(self):
        return self.connect_btn.isChecked()
