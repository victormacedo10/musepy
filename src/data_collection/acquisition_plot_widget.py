"""
Acquisition Plot Widget - Real-time EEG visualization with PyQtGraph
"""

import numpy as np
from ..utils import pd
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit
)
from PySide6.QtGui import QIntValidator


class AcquisitionPlotWidget(QWidget):
    """Widget for real-time EEG data visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # Plot configuration
        self.plot_interval = 5  # seconds
        self.channel_names = ['TP9', 'AF7', 'AF8', 'TP10']
        self.channel_colors = {
            'TP9': '#E74C3C',     # Red
            'AF7': '#3498DB',     # Blue
            'AF8': '#F39C12',     # Orange
            'TP10': '#27AE60'     # Green
        }
        
        # Data storage
        self.stream_data = pd.DataFrame()
        self.recording_data = None
        self.is_showing_recording = False
        
        # Plot objects
        self.plot_widget = None
        self.plot_item = None
        self.curves = {}
        self.channel_checkboxes = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Create PyQtGraph widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')  # White background
        self.plot_item = self.plot_widget.getPlotItem()
        
        # Configure plot
        self.plot_item.setTitle("EEG Data Acquisition", color='#495057', size='14pt')
        self.plot_item.setLabel('left', 'Amplitude (μV)', color='#495057')
        self.plot_item.setLabel('bottom', 'Time (s)', color='#495057')
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        
        # Set axis colors
        self.plot_item.getAxis('left').setPen(pg.mkPen(color='#495057'))
        self.plot_item.getAxis('bottom').setPen(pg.mkPen(color='#495057'))
        self.plot_item.getAxis('left').setTextPen(pg.mkPen(color='#495057'))
        self.plot_item.getAxis('bottom').setTextPen(pg.mkPen(color='#495057'))
        
        # Initialize curves for each channel
        for channel in self.channel_names:
            color = self.channel_colors[channel]
            pen = pg.mkPen(color=color, width=2)
            self.curves[channel] = self.plot_item.plot(
                name=channel,
                pen=pen,
                symbol=None  # No symbols for cleaner look
            )
            
        layout.addWidget(self.plot_widget)
        
        # Controls layout
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)  # Add more spacing between elements
        
        # Channel checkboxes
        channels_label = QLabel("Available Channels:")
        channels_label.setStyleSheet("background-color: white; color: #495057;")
        controls_layout.addWidget(channels_label)
        
        for channel in self.channel_names:
            checkbox = QCheckBox(channel)
            checkbox.setChecked(True)
            checkbox.toggled.connect(lambda checked, ch=channel: self.toggle_channel(ch, checked))
            
            # Style checkbox with channel color
            color = self.channel_colors[channel]
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: #495057;
                    font-weight: bold;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid #ced4da;
                    border-radius: 3px;
                    background-color: white;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {color};
                    border-color: {color};
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
                }}
            """)
            
            self.channel_checkboxes[channel] = checkbox
            controls_layout.addWidget(checkbox)
            controls_layout.addSpacing(5)  # Add small spacing after each checkbox
            
        controls_layout.addStretch()
        
        # Plot interval control
        controls_layout.addWidget(QLabel("⏱️ Plot Interval (s):"))
        
        self.interval_input = QLineEdit()
        self.interval_input.setFixedWidth(60)
        self.interval_input.setText(str(self.plot_interval))
        
        # Add integer validator
        interval_validator = QIntValidator(1, 9999, self)
        self.interval_input.setValidator(interval_validator)
        
        self.interval_input.editingFinished.connect(self.on_interval_changed)
        self.interval_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 2px 4px;
                color: #495057;
            }
        """)
        controls_layout.addWidget(self.interval_input)
        
        layout.addLayout(controls_layout)
        
    def toggle_channel(self, channel, visible):
        """Toggle channel visibility"""
        if channel in self.curves:
            self.curves[channel].setVisible(visible)
            
    def on_interval_changed(self):
        """Handle plot interval change from line edit"""
        text = self.interval_input.text()
        if text:  # Only update if text is not empty
            try:
                interval = int(text)
                if 1 <= interval <= 9999:
                    self.plot_interval = interval
            except ValueError:
                # Reset to current value if invalid
                self.interval_input.setText(str(self.plot_interval))
        
    def update_stream_data(self, data):
        """Update the plot with new streaming data"""
        if data.empty:
            return
            
        self.stream_data = data
        self.is_showing_recording = False
        
        # Update each channel
        for channel in self.channel_names:
            if channel in data.columns and 'time_rel' in data.columns:
                time_data = data['time_rel']
                channel_data = data[channel]
                
                # Convert to numpy arrays for PyQtGraph compatibility
                time_array = time_data.to_numpy() if hasattr(time_data, 'to_numpy') else time_data
                channel_array = channel_data.to_numpy() if hasattr(channel_data, 'to_numpy') else channel_data
                
                # Update curve data
                self.curves[channel].setData(time_array, channel_array)
                
        # Update plot range to show last N seconds
        if 'time_rel' in data.columns and len(data) > 0:
            last_time = data['time_rel'].max()
            start_time = max(0, last_time - self.plot_interval)
            self.plot_item.setXRange(start_time, last_time, padding=0)
            
    def display_recording_data(self, data_dict):
        """Display recorded data in the plot"""
        self.recording_data = data_dict
        self.is_showing_recording = True
        
        if 'eeg' in data_dict and not data_dict['eeg'].empty:
            eeg_data = data_dict['eeg']
            
            # Update each channel
            for channel in self.channel_names:
                if channel in eeg_data.columns:
                    if 'time_rel' in eeg_data.columns:
                        time_data = eeg_data['time_rel']
                    elif 'timestamp' in eeg_data.columns:
                        # Create relative time if not available
                        time_data = eeg_data['timestamp'] - eeg_data['timestamp'].min()
                    else:
                        # Use sample indices
                        time_data = np.arange(len(eeg_data))
                        
                    channel_data = eeg_data[channel]
                    
                    # Convert to numpy arrays for PyQtGraph compatibility
                    time_array = time_data.to_numpy() if hasattr(time_data, 'to_numpy') else time_data
                    channel_array = channel_data.to_numpy() if hasattr(channel_data, 'to_numpy') else channel_data
                    
                    self.curves[channel].setData(time_array, channel_array)
                    
            # Set full range for recording view
            if 'time_rel' in eeg_data.columns:
                time_range = eeg_data['time_rel'].max() - eeg_data['time_rel'].min()
                self.plot_item.setXRange(0, time_range, padding=0)
            elif 'timestamp' in eeg_data.columns:
                time_range = (eeg_data['timestamp'] - eeg_data['timestamp'].min()).max()
                self.plot_item.setXRange(0, time_range, padding=0)
            else:
                self.plot_item.setXRange(0, len(eeg_data), padding=0)
                
        # Update plot title
        self.plot_item.setTitle("EEG Recording View", color='#495057', size='14pt')
        
    def clear_curves(self):
        """Clear all plot curves"""
        for channel in self.channel_names:
            if channel in self.curves:
                self.curves[channel].clear()
                
        # Reset title
        self.plot_item.setTitle("EEG Data Acquisition", color='#495057', size='14pt')
        self.is_showing_recording = False
        
    def reset_view(self):
        """Reset plot to streaming view"""
        self.is_showing_recording = False
        self.plot_item.setTitle("EEG Data Acquisition", color='#495057', size='14pt')
        
        # Clear curves
        self.clear_curves()
        
        # Reset range
        self.plot_item.setXRange(0, self.plot_interval, padding=0)
        
    def get_visible_channels(self):
        """Get list of currently visible channels"""
        return [channel for channel, checkbox in self.channel_checkboxes.items() 
                if checkbox.isChecked()]
