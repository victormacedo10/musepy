#!/usr/bin/env python3
"""
MusePy - Modern EEG Data Acquisition and Analysis Tool
Main application entry point
"""

import sys
from pathlib import Path
from typing import Dict, Any
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QFrame, QLabel
from PySide6.QtGui import QIcon, QPalette, QColor
import matplotlib as mpl
import matplotlib
matplotlib.use("Qt5Agg")              # match the working script
import matplotlib as mpl
mpl.rcParams.update({
    "figure.dpi": 120,                # logical DPI only (QtAgg will upscale for HiDPI)
    "path.snap": True,                # crisper ticks/spines on fractional scales
    "axes.linewidth": 0.8,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
})
# Import our custom modules
from src.data_collection.data_collection_widget import DataCollectionWidget
from src.data_analysis.data_analysis_widget import (DataAnalysisWidget, InputDataWidget, ProcessingWidget, 
                                                    VisualizationWidget, VariableInspectorWidget, SessionManagementWidget)

class MusePyApp(QMainWindow):
    """Main application window for MusePy"""
    
    def __init__(self, demo_mode=False):
        super().__init__()
        self.demo_mode = demo_mode
        self.setup_ui()
        self.setup_theme()
        self.setup_window()
        
    def setup_ui(self):
        """Setup the main user interface"""
        self.setWindowTitle("MusePy - EEG Data Acquisition and Analysis by LabEsporte UnB")
        self.setMinimumSize(1400, 900)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create left panel with navigation and controls
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel)
        
        # Create content area (plot)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.addWidget(self.content_widget, 1)
        
        # Initialize feature widgets
        self.data_collection_widget = DataCollectionWidget(self.demo_mode, parent=self)
        self.data_analysis_widget = DataAnalysisWidget(parent=self)
        
        # Add widgets to content area
        self.content_layout.addWidget(self.data_collection_widget)
        self.content_layout.addWidget(self.data_analysis_widget)
        
        # Show data collection by default
        self.show_data_collection()
        
    def create_left_panel(self):
        """Create the left panel with navigation and controls"""
        
        left_frame = QFrame()
        left_frame.setFixedWidth(400)
        left_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-right: 1px solid #dee2e6;
            }
        """)
        
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Title section
        title_label = QWidget()
        title_label.setFixedHeight(50)
        title_label.setStyleSheet("""
            QWidget {
                background-color: #495057;
            }
        """)
        title_layout = QHBoxLayout(title_label)
        title_layout.setContentsMargins(15, 10, 15, 10)
        
        title_text = QLabel("🧠 MusePy - EEG Analysis Tool")
        title_text.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                border-right: none;
            }
        """)
        
        title_layout.addWidget(title_text)
        left_layout.addWidget(title_label)
        
        # Navigation toggle buttons
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(15, 10, 15, 10)
        nav_layout.setSpacing(10)
        
        self.data_collection_btn = self.create_nav_toggle_button("📈 Data Collection", True)
        self.data_analysis_btn = self.create_nav_toggle_button("📊 Data Analysis", False)
        
        nav_layout.addWidget(self.data_collection_btn)
        nav_layout.addWidget(self.data_analysis_btn)
        left_layout.addWidget(nav_widget)
        
        # Connect button signals
        self.data_collection_btn.clicked.connect(self.show_data_collection)
        self.data_analysis_btn.clicked.connect(self.show_data_analysis)
        
        # Add control panels (will be populated by data collection widget)
        self.control_panel = QWidget()
        self.control_panel.setLayout(QVBoxLayout())
        self.control_panel.layout().setContentsMargins(15, 15, 15, 15)
        self.control_panel.layout().setSpacing(15)
        left_layout.addWidget(self.control_panel)
        
        # Store reference to control panel for data analysis widget
        self.data_analysis_control_panel = None
        
        return left_frame
    
    def create_nav_toggle_button(self, text, is_active=False):
        """Create a navigation toggle button"""
        button = QPushButton(text)
        button.setFixedHeight(40)
        button.setCheckable(True)
        button.setChecked(is_active)
        
        # Style based on active state
        if is_active:
            button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #007bff;
                    border: none;
                    border-bottom: 3px solid #007bff;
                    font-weight: bold;
                    padding: 8px 12px;
                }
                QPushButton:hover {
                    background-color: #e3f2fd;
                }
            """)
        else:
            button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #6c757d;
                    border: none;
                    border-bottom: 3px solid transparent;
                    padding: 8px 12px;
                }
                QPushButton:hover {
                    background-color: #f8f9fa;
                    color: #495057;
                }
                QPushButton:checked {
                    background-color: transparent;
                    color: #007bff;
                    border-bottom: 3px solid #007bff;
                    font-weight: bold;
                }
            """)
        
        return button
    
    def show_data_collection(self):
        """Show data collection interface"""
        self.data_collection_widget.show()
        self.data_analysis_widget.hide()
        self.data_collection_btn.setChecked(True)
        self.data_analysis_btn.setChecked(False)
        
        # Update button styles
        self.data_collection_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #007bff;
                border: none;
                border-bottom: 3px solid #007bff;
                font-weight: bold;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
        """)
        self.data_analysis_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6c757d;
                border: none;
                border-bottom: 3px solid transparent;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                color: #495057;
            }
            QPushButton:checked {
                background-color: transparent;
                color: #007bff;
                border-bottom: 3px solid #007bff;
                font-weight: bold;
            }
        """)
        
        # Show data collection controls in left panel
        if hasattr(self, 'control_panel'):
            # Clear existing layout
            for i in reversed(range(self.control_panel.layout().count())):
                item = self.control_panel.layout().itemAt(i)
                if item.widget():
                    item.widget().setParent(None)
            
            # Add data collection controls
            if hasattr(self.data_collection_widget, 'setup_control_panels'):
                self.data_collection_widget.setup_control_panels()
        
    def show_data_analysis(self):
        """Show data analysis interface"""
        self.data_collection_widget.hide()
        self.data_analysis_widget.show()
        self.data_collection_btn.setChecked(False)
        self.data_analysis_btn.setChecked(True)
        
        # Update button styles
        self.data_analysis_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #007bff;
                border: none;
                border-bottom: 3px solid #007bff;
                font-weight: bold;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
        """)
        self.data_collection_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6c757d;
                border: none;
                border-bottom: 3px solid transparent;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                color: #495057;
            }
            QPushButton:checked {
                background-color: transparent;
                color: #007bff;
                border-bottom: 3px solid #007bff;
                font-weight: bold;
            }
        """)
        
        # Clear left panel for data analysis
        if hasattr(self, 'control_panel'):
            # Clear existing layout
            for i in reversed(range(self.control_panel.layout().count())):
                item = self.control_panel.layout().itemAt(i)
                if item.widget():
                    item.widget().setParent(None)
            
            # Create data analysis control panel with all widgets
            if not self.data_analysis_control_panel:
                self.data_analysis_control_panel = QWidget()
                analysis_layout = QVBoxLayout(self.data_analysis_control_panel)
                analysis_layout.setContentsMargins(0, 0, 0, 0)
                analysis_layout.setSpacing(0)
                
                # Create InputDataWidget
                self.input_data_widget = InputDataWidget(parent=self)
                analysis_layout.addWidget(self.input_data_widget)
                
                # Create ProcessingWidget
                self.processing_widget = ProcessingWidget(parent=self)
                analysis_layout.addWidget(self.processing_widget)
                
                # Create VisualizationWidget
                self.visualization_widget = VisualizationWidget(parent=self)
                analysis_layout.addWidget(self.visualization_widget)
                
                # Create Variable Inspector
                self.variable_inspector = VariableInspectorWidget(parent=self)
                analysis_layout.addWidget(self.variable_inspector)
                
                # Create Session Management (at the bottom)
                self.session_management_widget = SessionManagementWidget(parent=self)
                analysis_layout.addWidget(self.session_management_widget)
                
                # Connect signals
                self.input_data_widget.file_loaded.connect(self.on_data_file_loaded)
                self.input_data_widget.file_deleted.connect(self.on_data_file_deleted)
                self.visualization_widget.view_output_executed.connect(self.on_visualization_executed)
            
            self.control_panel.layout().addWidget(self.data_analysis_control_panel)
    
    def on_data_file_loaded(self, file_id: str, file_path: str):
        """Handle data file loaded event"""
        # Update the variable inspector with current data
        if hasattr(self, 'variable_inspector'):
            data_dict = self.get_combined_data_dict()
            self.variable_inspector.update_data(data_dict)
            
    def on_data_file_deleted(self, file_id: str):
        """Handle data file deleted event"""
        # Update the variable inspector with current data
        if hasattr(self, 'variable_inspector'):
            data_dict = self.get_combined_data_dict()
            self.variable_inspector.update_data(data_dict)
            
    def on_visualization_executed(self, script_id: str):
        """Handle visualization execution event"""
        # Update the data analysis widget with new visualization data
        if hasattr(self, 'data_analysis_widget'):
            self.data_analysis_widget.update_visualization_data(self.visualization_results)
            

            
    def get_combined_data_dict(self) -> Dict[str, Any]:
        """Get combined data dictionary with input, processing, and visualization data"""
        combined_dict = {
            "input": {},
            "processing": {},
            "visualization": {}
        }
        
        # Add input data
        if hasattr(self, 'input_data_widget'):
            combined_dict["input"] = self.input_data_widget.get_data_dict()
            
        # Add processing results
        if hasattr(self, 'processing_results') and self.processing_results:
            combined_dict["processing"] = self.processing_results
            
        # Add visualization results
        if hasattr(self, 'visualization_results') and self.visualization_results:
            combined_dict["visualization"] = self.visualization_results
            
        return combined_dict
    
    def setup_theme(self):
        """Setup light theme for the application"""
        app = QApplication.instance()
        
        # Create light theme palette
        palette = QPalette()
        
        # Window colors
        palette.setColor(QPalette.Window, QColor(248, 249, 250))
        palette.setColor(QPalette.WindowText, QColor(33, 37, 41))
        
        # Base colors
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(248, 249, 250))
        
        # Text colors
        palette.setColor(QPalette.Text, QColor(33, 37, 41))
        palette.setColor(QPalette.PlaceholderText, QColor(108, 117, 125))
        
        # Button colors
        palette.setColor(QPalette.Button, QColor(255, 255, 255))
        palette.setColor(QPalette.ButtonText, QColor(33, 37, 41))
        
        # Highlight colors
        palette.setColor(QPalette.Highlight, QColor(0, 123, 255))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        
        # Link colors
        palette.setColor(QPalette.Link, QColor(0, 123, 255))
        palette.setColor(QPalette.LinkVisited, QColor(102, 16, 242))
        
        # Apply palette
        app.setPalette(palette)
        
        # Additional styling for specific widgets
        app.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #ced4da;
                height: 8px;
                background: #e9ecef;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #007bff;
                border: 1px solid #007bff;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
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
        """)
    
    def setup_window(self):
        """Setup window properties"""
        # Set window icon if available
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Center window on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Get demo mode from command line flag
    demo_mode = "--demo" in sys.argv
    
    # Create and show main window
    window = MusePyApp(demo_mode=demo_mode)
    window.showMaximized()
    
    # Start application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
