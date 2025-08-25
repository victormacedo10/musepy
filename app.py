import sys
import os
import pickle
import importlib.util
import pandas as pd
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem, QComboBox, QSizePolicy,
    QFileDialog, QTableWidget, QTableWidgetItem, QTabWidget, QMessageBox, QSpinBox,
    QCheckBox, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QThread
# Matplotlib imports for embedding plots in PySide6
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt  # For dummy experiments usage
import numpy as np  # Added for demo mode random data
import time  # For demo timestamps
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowPresets
import pyqtgraph as pg
from src.pyqtgraph_class import GraphWidget
from src.utils import show_dialog, question_dialog
import logging
import re


class BoardConnectWorker(QThread):
    success = Signal(object)      # emit the board instance
    failure = Signal(Exception)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            params = BrainFlowInputParams()
            board = BoardShim(BoardIds.MUSE_2_BOARD, params)
            board.prepare_session()
            board.config_board('p61')
            board.start_stream()
            print("Board connected and streaming started")
            self.success.emit(board)
        except Exception as e:
            self.failure.emit(e)


class SafeNavigationToolbar(NavigationToolbar):
    def set_message(self, s):
        try:
            super().set_message(s)
        except RuntimeError:
            # Suppress the error if the underlying C++ object has been deleted
            pass


class EmittingStream(QObject):
    textWritten = Signal(str)
    def write(self, text):
        # collapse multiple newlines to a single one
        if text == '' or text == '\n':
            return
        text = re.sub(r'\n+', '\n', text)
        self.textWritten.emit(text)
    def flush(self):
        pass


# Helper to build DataFrame from raw board data
def make_df(data, preset, descr):
    if preset == BrainFlowPresets.DEFAULT_PRESET:
        chan_names = ['TP9','AF7','AF8','TP10','Right AUX']
    elif preset == BrainFlowPresets.AUXILIARY_PRESET:
        chan_names = ['AccX','AccY','AccZ','GyroX','GyroY','GyroZ']
    else:  # ANCILLARY_PRESET
        chan_names = ['PPG_1', 'PPG_2', 'Unknown']
    header = ['package_num'] + chan_names + ['timestamp','marker']
    return pd.DataFrame(data.T, columns=header)


class MainWindow(QMainWindow):
    def __init__(self, demo_mode=False):
        super().__init__()
        self.demo_mode = demo_mode  # Demo mode flag
        self.setWindowTitle("MusePy - LabEsporte UnB")
        # streaming window length in seconds (adjustable)
        self.stream_window = 5
        self.inputs_dict = {}
        self.processed_data_dict = {}
        self.experiment_output = {}
        self.processing_script_path = ''
        self.experiment_script_path = ''
        # Muse recording storage
        base = os.path.dirname(os.path.abspath(__file__))
        self.muse_folder = os.path.join(base, 'data')
        os.makedirs(self.muse_folder, exist_ok=True)
        self.recorded_data = {}
        self.board = None
        self.descr = BoardShim.get_board_descr(BoardIds.MUSE_2_BLED_BOARD.value)

        # Main UI
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        # Left: visualization tabs
        self.tabs = self.create_visualization_tabs()
        main_layout.addWidget(self.tabs, 2)
        # Right: controls
        ctrl = QWidget(); ctrl_layout = QVBoxLayout(ctrl)
        ctrl_layout.addWidget(self.create_record_group())
        ctrl_layout.addWidget(self.create_input_data_group())
        ctrl_layout.addWidget(self.create_processing_group())
        ctrl_layout.addWidget(self.create_experiment_group())
        ctrl_layout.addWidget(self.create_session_group())
        
        # add multiline log view below session management
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        ctrl_layout.addWidget(self.log_text)

        # redirect prints to log_text
        self.emitting_stream = EmittingStream()
        self.emitting_stream.textWritten.connect(self.log_text.append)
        sys.stdout = self.emitting_stream
        sys.stderr = self.emitting_stream

        # capture Python‐level logs (including BrainFlow) in our QTextEdit
        self.log_handler = logging.StreamHandler(self.emitting_stream)
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.DEBUG)

        ctrl_layout.addStretch()
        main_layout.addWidget(ctrl, 1)
        # enable brainflow logging to stdout/stderr
        BoardShim.enable_board_logger()

    # --- Record Data Group ---
    def create_record_group(self):
        group = QGroupBox("Record Data")
        layout = QVBoxLayout()
        # Working directory selector
        hwd = QHBoxLayout()
        self.rec_wd_edit = QLineEdit(self.muse_folder)
        btn_wd = QPushButton("Browse...")
        btn_wd.clicked.connect(self.browse_record_folder)
        hwd.addWidget(QLabel("Working Dir:"))
        hwd.addWidget(self.rec_wd_edit)
        hwd.addWidget(btn_wd)
        layout.addLayout(hwd)
        # single toggle button for connect/disconnect
        self.conn_btn = QPushButton("Connect")
        self.conn_btn.setCheckable(True)
        self.conn_btn.toggled.connect(self.toggle_connection)
        layout.addWidget(self.conn_btn)
        # Start/Stop recording button
        self.rec_btn = QPushButton("Start Recording")
        self.rec_btn.setCheckable(True)
        self.rec_btn.clicked.connect(self.toggle_record)
        layout.addWidget(self.rec_btn)
        # Filename and save
        hfn = QHBoxLayout()
        self.rec_fn_edit = QLineEdit()
        btn_save = QPushButton("Save Data")
        btn_save.clicked.connect(self.save_record)
        hfn.addWidget(QLabel("Filename:"))
        hfn.addWidget(self.rec_fn_edit)
        hfn.addWidget(btn_save)
        layout.addLayout(hfn)
        group.setLayout(layout)
        return group

    def browse_record_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Working Directory", self.rec_wd_edit.text())
        if d:
            self.muse_folder = d
            self.rec_wd_edit.setText(d)

    def connect_board(self):
        print("Connecting to board...")
        params = BrainFlowInputParams()
        self.board = BoardShim(BoardIds.MUSE_2_BOARD, params)
        self.board.prepare_session()
        self.board.config_board('p61')
        self.board.start_stream()
        print("Board connected and streaming started")

    def disconnect_board(self):
        if hasattr(self, 'board') and self.board:
            print("Stopping stream...")
            self.board.stop_stream()
            self.board.release_session()
            print("Board disconnected")

    def on_board_connected(self, board):
        self.board = board
        self.conn_btn.setText("Disconnect")
        self.conn_btn.setEnabled(True)

    def on_board_connection_failed(self, exc):
        QMessageBox.critical(self, "Connection failed", str(exc))
        self.conn_btn.setChecked(False)
        self.conn_btn.setEnabled(True)

    def toggle_connection(self, checked):
        if checked:
            if self.demo_mode:
                print("Demo mode: simulating connection")
                self.on_board_connected(None)
                return
            self.conn_btn.setText("Connecting...")
            self.conn_btn.setEnabled(False)
            self.conn_worker = BoardConnectWorker()
            self.conn_worker.success.connect(self.on_board_connected)
            self.conn_worker.failure.connect(self.on_board_connection_failed)
            self.conn_worker.start()
        else:
            if self.demo_mode:
                print("Demo mode: disconnecting")
                self.conn_btn.setText("Connect")
                return
            # similarly, you could offload disconnect if it blocks
            self.disconnect_board()
            self.conn_btn.setText("Connect")

    def toggle_record(self, checked):
        if checked:
            print("Recording started – clearing old data and plots")
            # clear board buffer to avoid old data
            if hasattr(self, 'board') and self.board:
                _ = self.board.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
                _ = self.board.get_board_data(preset=BrainFlowPresets.AUXILIARY_PRESET)
                _ = self.board.get_board_data(preset=BrainFlowPresets.ANCILLARY_PRESET)
            # clear previous data
            self.recorded_data = {}
            self.stream_data = pd.DataFrame()
            # clear curves
            for c in self.stream_curves.values():
                c.clear()
            # start timer
            self.rec_btn.setText("Stop Recording")
            self.timestamps_start = None
            self.stream_timer = QTimer()
            self.stream_timer.timeout.connect(self.update_stream)
            self.stream_timer.start(100)
        else:
            print("Recording stopped")
            self.rec_btn.setText("Start Recording")
            if hasattr(self, 'stream_timer'):
                self.stream_timer.stop()
            print("Using accumulated stream data for EEG, fetching final aux/ppg")
            # use accumulated streaming data for EEG (most complete)
            df_eeg = self.stream_data.copy() if hasattr(self, 'stream_data') and not self.stream_data.empty else pd.DataFrame()
            # get final aux/ppg data from board buffer
            aux = self.board.get_board_data(preset=BrainFlowPresets.AUXILIARY_PRESET)
            ppg = self.board.get_board_data(preset=BrainFlowPresets.ANCILLARY_PRESET)
            df_aux = make_df(aux, BrainFlowPresets.AUXILIARY_PRESET, self.descr)
            df_ppg = make_df(ppg, BrainFlowPresets.ANCILLARY_PRESET, self.descr)
            self.recorded_data = {'eeg': df_eeg, 'imu': df_aux, 'ppg': df_ppg}
            # prompt and save
            if question_dialog("Save Recording", "Do you want to save the EEG recording?"):
                print("Saving recording")
                self.save_record()
            else:
                print("Recording discarded")
                show_dialog("Info", "Recording discarded.")

    def update_stream(self):
        # Demo mode: generate random data for each channel
        if self.demo_mode:
            now = time.time()
            if self.timestamps_start is None:
                self.timestamps_start = now
            t_rel = now - self.timestamps_start
            # generate one sample of random EEG channels
            data_dict = {chan: np.random.randn() for chan in self.stream_chan_names}
            df = pd.DataFrame([data_dict])
            df['time_rel'] = t_rel
        else:
            # fetch and append new data from real board
            data = self.board.get_board_data(preset=BrainFlowPresets.DEFAULT_PRESET)
            df = make_df(data, BrainFlowPresets.DEFAULT_PRESET, self.descr)
            if df.empty:
                return
            if self.timestamps_start is None:
                self.timestamps_start = df['timestamp'].iloc[0]
            df['time_rel'] = df['timestamp'] - self.timestamps_start
        if self.stream_data.empty:
            self.stream_data = df
        else:
            self.stream_data = pd.concat([self.stream_data, df], ignore_index=True)
        # update plot curves per‐channel
        t = self.stream_data['time_rel']
        for chan in self.stream_chan_names:
            # always update curve data, but show/hide according to checkbox
            self.stream_curves[chan].setData(
                t,
                self.stream_data[chan],
                pen=pg.mkPen(color=self.curve_colors[chan])
            )
            self.stream_curves[chan].setVisible(self.stream_checkboxes[chan].isChecked())
        # always show last N seconds
        last_t = t.iloc[-1]
        self.stream_plot_item.setXRange(
            max(0, last_t - self.stream_window), last_t, padding=0
        )

    def on_channel_toggled(self, chan, checked):
        """Repopulate stored data and show/hide curve on toggle."""
        if hasattr(self, 'stream_data') and not self.stream_data.empty:
            t = self.stream_data['time_rel']
            # always refill the curve with full data
            self.stream_curves[chan].setData(
                t,
                self.stream_data[chan],
                pen=pg.mkPen(color=self.curve_colors[chan])
            )
        # then just show or hide
        self.stream_curves[chan].setVisible(checked)

    def save_record(self):
        name = self.rec_fn_edit.text().strip() or datetime.now().strftime("%Y%m%d_%H%M%S")
        for key, df in self.recorded_data.items():
            df.to_csv(os.path.join(self.muse_folder, f"{name}_{key}.csv"), index=False)
        # pickle
        with open(os.path.join(self.muse_folder, f"{name}.data"), 'wb') as f:
            pickle.dump(self.recorded_data, f)
        rec_path = os.path.join(self.muse_folder, f"{name}.data")
        self.input_file_line.setText(rec_path)
        self.input_label_line.setText('muse_data')
        self.load_file()
        QMessageBox.information(self, "Saved", "Muse data saved.")

    def create_input_data_group(self):
        group_box = QGroupBox("Input Data")
        layout = QVBoxLayout()

        # File path input and browse button
        file_layout = QHBoxLayout()
        self.input_file_line = QLineEdit()
        file_layout.addWidget(QLabel("File Path:"))
        file_layout.addWidget(self.input_file_line)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_input_file)
        file_layout.addWidget(browse_button)
        layout.addLayout(file_layout)

        # Label input for the CSV file
        label_layout = QHBoxLayout()
        self.input_label_line = QLineEdit()
        label_layout.addWidget(QLabel("Label:"))
        label_layout.addWidget(self.input_label_line)
        layout.addLayout(label_layout)

        # Load CSV button
        load_button = QPushButton("Load File")
        load_button.clicked.connect(self.load_file)
        layout.addWidget(load_button)

        # List widget to display loaded files
        self.input_list_widget = QListWidget()
        layout.addWidget(self.input_list_widget)

        # Remove selected button
        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected_input)
        layout.addWidget(remove_button)

        group_box.setLayout(layout)
        return group_box

    def create_processing_group(self):
        group_box = QGroupBox("Processing")
        layout = QVBoxLayout()

        # Processing script path input and browse button
        proc_layout = QHBoxLayout()
        self.proc_script_line = QLineEdit()
        proc_layout.addWidget(QLabel("Script:"))
        proc_layout.addWidget(self.proc_script_line)
        proc_browse = QPushButton("Browse")
        proc_browse.clicked.connect(self.browse_processing_script)
        proc_layout.addWidget(proc_browse)
        layout.addLayout(proc_layout)

        # Process button
        process_button = QPushButton("Process Data")
        process_button.clicked.connect(self.process_data)
        layout.addWidget(process_button)

        group_box.setLayout(layout)
        return group_box

    def create_experiment_group(self):
        group_box = QGroupBox("Experiment")
        layout = QVBoxLayout()

        # Experiment script path input and browse button
        exp_layout = QHBoxLayout()
        self.exp_script_line = QLineEdit()
        exp_layout.addWidget(QLabel("Script:"))
        exp_layout.addWidget(self.exp_script_line)
        exp_browse = QPushButton("Browse")
        exp_browse.clicked.connect(self.browse_experiment_script)
        exp_layout.addWidget(exp_browse)
        layout.addLayout(exp_layout)

        # Run experiment button
        run_button = QPushButton("Run Experiment")
        run_button.clicked.connect(self.run_experiment)
        layout.addWidget(run_button)

        group_box.setLayout(layout)
        return group_box

    def create_session_group(self):
        group_box = QGroupBox("Session Management")
        layout = QHBoxLayout()

        save_button = QPushButton("Save Session")
        save_button.clicked.connect(self.save_session)
        
        load_button = QPushButton("Load Session")
        load_button.clicked.connect(self.load_session)
        
        layout.addWidget(save_button)
        layout.addWidget(load_button)

        group_box.setLayout(layout)
        return group_box

    def create_visualization_tabs(self):
        tabs = QTabWidget()
        # Stream Tab
        self.stream_tab = QWidget()
        stream_layout = QVBoxLayout(self.stream_tab)
        self.stream_plot = GraphWidget()
        # Create a PlotItem for streaming
        self.stream_plot_item = self.stream_plot.addPlot(title="EEG Stream")
        # EEG channel names for default preset
        self.stream_chan_names = ['TP9','AF7','AF8','TP10']
        self.stream_curves = {}
        # share color map for curves
        self.curve_colors = {'TP9':'r','TP10':'b','AF7':'g','AF8':'k'}

        for chan in self.stream_chan_names:
            self.stream_curves[chan] = self.stream_plot_item.plot(name=chan)
        stream_layout.addWidget(self.stream_plot)

        # checkboxes to toggle each stream curve
        checkbox_layout = QHBoxLayout()
        self.stream_checkboxes = {}
        # replace direct setVisible binding with our handler
        for chan in self.stream_chan_names:
            cb = QCheckBox(chan)
            cb.setChecked(True)
            cb.toggled.connect(lambda checked, c=chan: self.on_channel_toggled(c, checked))
            checkbox_layout.addWidget(cb)
            self.stream_checkboxes[chan] = cb
        stream_layout.addLayout(checkbox_layout)

        # window‐length selector
        win_layout = QHBoxLayout()
        win_layout.addWidget(QLabel("Window (s):"))
        self.window_spin = QSpinBox()
        self.window_spin.setRange(1, 60)
        self.window_spin.setValue(self.stream_window)
        self.window_spin.valueChanged.connect(lambda v: setattr(self, 'stream_window', v))
        win_layout.addWidget(self.window_spin)
        stream_layout.addLayout(win_layout)
        tabs.addTab(self.stream_tab, "Stream")

        # Plots Tab (existing)
        self.plots_tab = QWidget()
        plots_layout = QVBoxLayout()
        # Combo box for selecting a plot
        self.plot_combo_box = QComboBox()
        self.plot_combo_box.currentIndexChanged.connect(self.update_plot_view)
        plots_layout.addWidget(self.plot_combo_box)
        # Container for the canvas only
        self.canvas_container = QWidget()
        self.canvas_layout = QVBoxLayout()
        self.canvas_container.setLayout(self.canvas_layout)
        plots_layout.addWidget(self.canvas_container)
        # Bottom widget: fixed height horizontal layout for toolbar and save controls
        self.plot_bottom_widget = QWidget()
        self.plot_bottom_widget.setFixedHeight(50)
        self.plot_bottom_layout = QHBoxLayout()
        self.plot_bottom_widget.setLayout(self.plot_bottom_layout)
        plots_layout.addWidget(self.plot_bottom_widget)
        self.save_button = QPushButton("Save Plot")
        self.save_button.clicked.connect(self.save_current_plot)
        self.dpi_spin_box = QSpinBox()
        self.dpi_spin_box.setMinimumWidth(100)
        self.dpi_spin_box.setRange(1, 1200)
        self.dpi_spin_box.setValue(300)
        self.plot_bottom_layout.addStretch()
        self.plot_bottom_layout.addWidget(self.save_button)
        self.plot_bottom_layout.addWidget(QLabel("DPI:"))
        self.plot_bottom_layout.addWidget(self.dpi_spin_box)
        self.plots_tab.setLayout(plots_layout)
        tabs.addTab(self.plots_tab, "Plots")

        # Tables Tab (existing)
        self.tables_tab = QWidget()
        tables_layout = QVBoxLayout()
        self.table_combo_box = QComboBox()
        self.table_combo_box.currentIndexChanged.connect(self.update_table_view)
        tables_layout.addWidget(self.table_combo_box)
        self.table_widget = QTableWidget()
        tables_layout.addWidget(self.table_widget)
        self.tables_tab.setLayout(tables_layout)
        tabs.addTab(self.tables_tab, "Tables")

        return tabs

    # --- Input Data Methods ---
    def browse_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "All Files (*.*)")
        if file_path:
            self.input_file_line.setText(file_path)
            # Set the default label to the file name (without the directory path)
            self.input_label_line.setText(Path(file_path).stem)

    def load_file(self):
        file_path = self.input_file_line.text().strip()
        label = self.input_label_line.text().strip()
        if not file_path or not label:
            QMessageBox.warning(self, "Input Error", "Please provide both a file path and a label.")
            return
        try:
            self.inputs_dict[label] = file_path

            # Add item to list widget; store file path as data for reference if needed
            item = QListWidgetItem(f"{label}: {os.path.basename(file_path)}")
            item.setData(Qt.UserRole, file_path)
            self.input_list_widget.addItem(item)

            # Clear input fields
            self.input_file_line.clear()
            self.input_label_line.clear()
        except Exception as e:
            QMessageBox.critical(self, "Error Loading File", f"An error occurred:\n{str(e)}")

    def remove_selected_input(self):
        selected_items = self.input_list_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            text = item.text()
            # Assume the label is before the colon
            label = text.split(":")[0].strip()
            if label in self.inputs_dict:
                del self.inputs_dict[label]
            self.input_list_widget.takeItem(self.input_list_widget.row(item))

    # --- Processing Methods ---
    def browse_processing_script(self):
        script_path, _ = QFileDialog.getOpenFileName(self, "Select Processing Script", "", "Python Files (*.py)")
        if script_path:
            self.proc_script_line.setText(script_path)
            self.processing_script_path = script_path

    def process_data(self):
        script_path = self.proc_script_line.text().strip()
        if not script_path:
            QMessageBox.warning(self, "Input Error", "Please select a processing script.")
            return
        if not self.inputs_dict:
            QMessageBox.warning(self, "Input Error", "No input data loaded.")
            return

        try:
            # Load module from the given file path
            spec = importlib.util.spec_from_file_location("processing_module", script_path)
            processing_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(processing_module)

            # Check if function exists
            if not hasattr(processing_module, "processing_function"):
                QMessageBox.critical(self, "Error", "The script does not define 'processing_function'.")
                return

            # Call the processing function
            self.processed_data_dict = processing_module.processing_function(self.inputs_dict)
            QMessageBox.information(self, "Success", "Data processed successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Processing Error", f"An error occurred:\n{str(e)}")

    # --- Experiment Methods ---
    def browse_experiment_script(self):
        script_path, _ = QFileDialog.getOpenFileName(self, "Select Experiment Script", "", "Python Files (*.py)")
        if script_path:
            self.exp_script_line.setText(script_path)
            self.experiment_script_path = script_path

    def run_experiment(self):
        script_path = self.exp_script_line.text().strip()
        if not script_path:
            QMessageBox.warning(self, "Input Error", "Please select an experiment script.")
            return
        if not self.inputs_dict or not self.processed_data_dict:
            QMessageBox.warning(self, "Input Error", "Ensure input data is loaded and processed before running an experiment.")
            return

        try:
            # Load module from the given file path
            spec = importlib.util.spec_from_file_location("experiment_module", script_path)
            experiment_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(experiment_module)

            # Check if function exists
            if not hasattr(experiment_module, "experiment_function"):
                QMessageBox.critical(self, "Error", "The script does not define 'experiment_function'.")
                return

            # Call the experiment function
            self.experiment_output = experiment_module.experiment_function(self.inputs_dict, self.processed_data_dict)

            # Update combo boxes for plots and tables automatically
            self.update_output_combo_boxes()

            # QMessageBox.information(self, "Success", "Experiment ran successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Experiment Error", f"An error occurred:\n{str(e)}")

    def update_output_combo_boxes(self):
        # Update plots combo box
        current_plot_text = self.plot_combo_box.currentText()
        self.plot_combo_box.clear()
        if "plots" in self.experiment_output:
            for key in self.experiment_output["plots"]:
                self.plot_combo_box.addItem(key)
                if current_plot_text == key:
                    self.plot_combo_box.setCurrentText(current_plot_text)

        # Update tables combo box
        current_table_text = self.table_combo_box.currentText()
        self.table_combo_box.clear()
        if "tables" in self.experiment_output:
            for key in self.experiment_output["tables"]:
                self.table_combo_box.addItem(key)
                if current_table_text == key:
                    self.table_combo_box.setCurrentText(current_table_text)

        # # Auto-update views if there is at least one item
        # if self.plot_combo_box.count() > 0:
        #     self.plot_combo_box.setCurrentIndex(0)
        # if self.table_combo_box.count() > 0:
        #     self.table_combo_box.setCurrentIndex(0)

    def refresh_experiment_output(self):
        script_path = self.exp_script_line.text().strip()
        if not script_path:
            return
        try:
            spec = importlib.util.spec_from_file_location("experiment_module", script_path)
            experiment_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(experiment_module)
            if not hasattr(experiment_module, "experiment_function"):
                QMessageBox.critical(self, "Error", "The experiment script does not define 'experiment_function'.")
                return
            # Re-run the experiment function to get a fresh output
            self.experiment_output = experiment_module.experiment_function(self.inputs_dict, self.processed_data_dict)
        except Exception as e:
            QMessageBox.critical(self, "Experiment Error", f"An error occurred while re-running the experiment:\n{str(e)}")

    # --- Visualization Methods ---
    def update_plot_view(self):
        key = self.plot_combo_box.currentText()
        if not key:
            return

        # Refresh the experiment output to get a fresh figure for the selected key
        self.refresh_experiment_output()
        if "plots" not in self.experiment_output or key not in self.experiment_output["plots"]:
            return

        plot_fig = self.experiment_output["plots"][key]

        try:
            # Remove old canvas if it exists
            if hasattr(self, 'canvas') and self.canvas is not None:
                self.canvas_layout.removeWidget(self.canvas)
                self.canvas.setParent(None)
                # Use a short delay to let pending events finish before deletion.
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self.canvas.deleteLater)
            
            # Create a new canvas with the fresh figure and add it to the container
            self.canvas = FigureCanvas(plot_fig)
            self.canvas_layout.addWidget(self.canvas)
            self.canvas.draw()

            # Create a new toolbar for the new canvas.
            # If a toolbar already exists in the bottom layout, remove it.
            if hasattr(self, 'plot_toolbar') and self.plot_toolbar is not None:
                self.plot_bottom_layout.removeWidget(self.plot_toolbar)
                self.plot_toolbar.setParent(None)
                QTimer.singleShot(0, self.plot_toolbar.deleteLater)
            
            self.plot_toolbar = SafeNavigationToolbar(self.canvas, self)
            # Insert the new toolbar at the beginning (index 0) of the bottom layout.
            self.plot_bottom_layout.insertWidget(0, self.plot_toolbar)
        except Exception as e:
            QMessageBox.critical(self, "Plot Error", f"An error occurred while updating the plot:\n{str(e)}")

    def update_table_view(self):
        key = self.table_combo_box.currentText()
        if not key or "tables" not in self.experiment_output:
            return

        try:
            df = self.experiment_output["tables"][key]
            self.display_dataframe(df)
        except Exception as e:
            QMessageBox.critical(self, "Table Error", f"An error occurred while updating the table:\n{str(e)}")

    def display_dataframe(self, df):
        # Clear the table widget and set dimensions
        if not isinstance(df, pd.DataFrame):
            QMessageBox.warning(self, "Display Error", "The table data is not a valid pandas DataFrame.")
            return

        self.table_widget.clear()
        self.table_widget.setRowCount(len(df.index))
        self.table_widget.setColumnCount(len(df.columns))
        self.table_widget.setHorizontalHeaderLabels(df.columns.astype(str).tolist())

        # Populate the table widget
        for i, row in enumerate(df.itertuples(index=False)):
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                self.table_widget.setItem(i, j, item)
        self.table_widget.resizeColumnsToContents()

    def save_current_plot(self):
        if not hasattr(self, 'canvas') or self.canvas is None:
            return
        dpi_value = self.dpi_spin_box.value()
        # Open a file save dialog to choose the file location and format
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Plot", "", "PNG Files (*.png);;PDF Files (*.pdf);;All Files (*)")
        if not file_path:
            return
        try:
            # Save the current figure with the specified DPI
            self.canvas.figure.savefig(file_path, dpi=dpi_value)
            QMessageBox.information(self, "Saved", f"Plot saved successfully at {dpi_value} dpi.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving the plot:\n{str(e)}")
    
    # --- Session Management ---
    def save_session(self):
        # Create experiments folder if it doesn't exist
        exp_folder = os.path.join(os.getcwd(), "experiments")
        os.makedirs(exp_folder, exist_ok=True)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Session", exp_folder, "Experiment Files (*.exp)")
        if not file_path:
            return

        session_data = {
            "inputs_dict": self.inputs_dict,
            "processed_data_dict": self.processed_data_dict,
            "experiment_output": self.experiment_output,
            "processing_script_path": self.proc_script_line.text().strip(),
            "experiment_script_path": self.exp_script_line.text().strip(),
            # Optionally, you could also save the list of input files if needed.
        }
        try:
            with open(file_path, "wb") as f:
                pickle.dump(session_data, f)
            QMessageBox.information(self, "Session Saved", "The session was saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving the session:\n{str(e)}")

    def load_session(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Session", "", "Experiment Files (*.exp)")
        if not file_path:
            return

        try:
            with open(file_path, "rb") as f:
                session_data = pickle.load(f)
            self.inputs_dict = session_data.get("inputs_dict", {})
            self.processed_data_dict = session_data.get("processed_data_dict", {})
            self.experiment_output = session_data.get("experiment_output", {})
            proc_path = session_data.get("processing_script_path", "")
            exp_path = session_data.get("experiment_script_path", "")

            self.proc_script_line.setText(proc_path)
            self.exp_script_line.setText(exp_path)

            # Rebuild the input list widget based on inputs_dict
            self.input_list_widget.clear()
            for label, df in self.inputs_dict.items():
                # Here we don't store file paths since we already loaded the data,
                # but you could store them as needed.
                item = QListWidgetItem(f"{label}")
                self.input_list_widget.addItem(item)

            # Update combo boxes for output if available
            self.update_output_combo_boxes()

            QMessageBox.information(self, "Session Loaded", "The session was loaded successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"An error occurred while loading the session:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Enable demo mode via --demo flag
    demo_mode = '--demo' in sys.argv
    window = MainWindow(demo_mode=demo_mode)
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())
