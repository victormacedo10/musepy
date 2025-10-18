"""
Data Analysis Widget - Main interface for data analysis
"""

import os
import pickle
from ..utils import pd
import numpy as np
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLineEdit, 
    QLabel, QComboBox, QSpinBox, QTextEdit, QFileDialog, 
    QMessageBox, QSizePolicy, QTreeWidget, QTreeWidgetItem,
    QMenu, QAbstractItemView, QDialog, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction
import pyqtgraph as pg


def is_python_available():
    """Check if Python is available on the system (for external script execution)"""
    try:
        # Try to run python command
        result = subprocess.run([sys.executable, '--version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        # If current Python is not available, try common Python commands
        for cmd in ['python', 'python3', 'python.exe']:
            try:
                result = subprocess.run([cmd, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return True
            except Exception:
                continue
        return False


def is_external_script_supported():
    """Check if external script loading is supported (Python available or not PyInstaller)"""
    # If running from PyInstaller, external scripts may not work reliably
    if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
        # Running from PyInstaller bundle
        return is_python_available()
    else:
        # Running from source code - external scripts should work
        return True





class SafeNavigationToolbar(NavigationToolbar):
    def set_message(self, s):
        try:
            super().set_message(s)
        except RuntimeError:
            # Suppress the error if the underlying C++ object has been deleted
            pass




class VariableInspectorWidget(QWidget):
    """Widget for inspecting nested data structures"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.data_dict = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Title
        title_label = QLabel("🔍 Variable Inspector")
        title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #495057;
                font-size: 12px;
                padding: 5px 0px;
            }
        """)
        layout.addWidget(title_label)
        
        # Tree widget for data structure
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Data", "Content"])
        self.tree_widget.setColumnWidth(0, 200)
        self.tree_widget.setColumnWidth(1, 300)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.tree_widget.itemDoubleClicked.connect(self.show_full_content)
        
        # Enable horizontal scrolling for long content
        self.tree_widget.header().setStretchLastSection(False)
        
        # Style the tree widget
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                color: #495057;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 2px;
                border-bottom: 1px solid #f8f9fa;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #495057;
            }
            QTreeWidget::item:alternate {
                background-color: #f8f9fa;
            }
            QTreeWidget::item:hover {
                background-color: #e9ecef;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 4px;
                font-weight: bold;
                color: #495057;
            }
        """)
        
        layout.addWidget(self.tree_widget)
        
    def update_data(self, data_dict: Dict[str, Any]):
        """Update the tree with new data"""
        self.data_dict = data_dict
        self.tree_widget.clear()
        
        for key, value in data_dict.items():
            root_item = self.create_tree_item(key, value)
            self.tree_widget.addTopLevelItem(root_item)
            
        # Expand all items by default
        self.tree_widget.expandAll()
        
    def create_tree_item(self, key: str, value: Any) -> QTreeWidgetItem:
        """Create a tree item for a key-value pair"""
        item = QTreeWidgetItem()
        item.setText(0, key)
        
        # Get combined type and size information for content column
        content_info = self.get_content_info(value)
        item.setText(1, content_info)
        
        # Set icon or styling based on type
        if isinstance(value, dict):
            # Check if this is a script with result
            if "script_path" in value and "result" in value:
                # Add script path item
                script_path_item = QTreeWidgetItem()
                script_path_item.setText(0, "Script Path")
                script_path_item.setText(1, value["script_path"])
                item.addChild(script_path_item)
                
                # Add result item
                result_item = QTreeWidgetItem()
                result_item.setText(0, "Result")
                result_item.setText(1, str(type(value["result"]).__name__))
                item.addChild(result_item)
                
                # Add nested result structure
                if isinstance(value["result"], dict):
                    for sub_key, sub_value in value["result"].items():
                        child_item = self.create_tree_item(sub_key, sub_value)
                        result_item.addChild(child_item)
            else:
                # Add child items for dictionary keys (nested structure)
                for sub_key, sub_value in value.items():
                    child_item = self.create_tree_item(sub_key, sub_value)
                    item.addChild(child_item)
                
        elif isinstance(value, (list, tuple)):
            # Add child items for list elements (limit to first 10)
            for i, sub_value in enumerate(value[:10]):
                child_item = self.create_tree_item(f"[{i}]", sub_value)
                item.addChild(child_item)
            if len(value) > 10:
                more_item = QTreeWidgetItem()
                more_item.setText(0, f"... and {len(value) - 10} more items")
                more_item.setText(1, "")
                item.addChild(more_item)
                
        elif isinstance(value, pd.DataFrame):
            # Add Columns item
            columns_item = QTreeWidgetItem()
            columns_item.setText(0, "Columns")
            columns_item.setText(1, str(list(value.columns)))
            item.addChild(columns_item)
            
        elif isinstance(value, np.ndarray):
            # Add Value item
            value_item = QTreeWidgetItem()
            value_item.setText(0, "Value")
            value_str = str(value.flatten()[:10])  # Show first 10 elements
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            value_item.setText(1, value_str)
            item.addChild(value_item)
            
        elif isinstance(value, str) and value == "Unknown":
            # For unknown file formats, no additional children needed
            pass
            
        else:
            # For simple types, no additional children needed
            pass
            
        return item
        
    def get_content_info(self, value: Any) -> str:
        """Get combined type and size information for the content column"""
        if isinstance(value, dict):
            # Check if this is a script with result
            if "script_path" in value and "result" in value:
                return f"script (with result)"
            return f"dict ({len(value)} keys)"
        elif isinstance(value, (list, tuple)):
            return f"{type(value).__name__} ({len(value)} items)"
        elif isinstance(value, pd.DataFrame):
            return f"DataFrame ({value.shape[0]}×{value.shape[1]})"
        elif isinstance(value, np.ndarray):
            return f"ndarray ({value.shape})"
        elif isinstance(value, str):
            if value == "Unknown":
                return "Unknown"
            return f"str ({value})"
        elif isinstance(value, (int, float)):
            return f"{type(value).__name__} ({value})"
        else:
            return f"{type(value).__name__}"
            
    def get_icon(self, emoji: str):
        """Get an icon (placeholder for emoji)"""
        # For now, we'll use text instead of icons
        # In a future version, we could implement proper icon handling
        return None
        
    def show_context_menu(self, position):
        """Show context menu for tree items"""
        item = self.tree_widget.itemAt(position)
        if not item:
            return
            
        # Only show options for top-level items
        if item.parent() is None:
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: white;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 4px;
                }
                QMenu::item {
                    background-color: transparent;
                    color: #495057;
                    padding: 6px 12px;
                    border-radius: 2px;
                }
                QMenu::item:selected {
                    background-color: #e9ecef;
                    color: #495057;
                }
            """)
            
            # Determine the category and item type
            category = self.get_item_category(item)
            item_id = item.text(0)
            

                
            # Add Remove option for all items
            delete_action = QAction("Remove", self)
            delete_action.triggered.connect(lambda: self.delete_item(item_id, category))
            menu.addAction(delete_action)
            
            # Show menu at cursor position
            menu.exec_(self.tree_widget.mapToGlobal(position))
            
    def get_item_category(self, item: QTreeWidgetItem) -> str:
        """Get the category of an item (input, processing, visualization)"""
        # Navigate up to find the root category
        current_item = item
        while current_item.parent() is not None:
            current_item = current_item.parent()
            
        # The root item text is the category
        return current_item.text(0)
            
    def delete_item(self, item_id: str, category: str):
        """Delete an item from the specified category"""
        if category == "input":
            if hasattr(self.parent, 'input_data_widget'):
                self.parent.input_data_widget.remove_file(item_id)
        elif category == "processing":
            if hasattr(self.parent, 'processing_results'):
                self.parent.processing_results = {}
        elif category == "visualization":
            if hasattr(self.parent, 'visualization_results'):
                self.parent.visualization_results = {}
                
        # Update the display
        data_dict = self.parent.get_combined_data_dict()
        self.update_data(data_dict)
            
    def delete_file(self, file_id: str):
        """Delete a file from the data dictionary"""
        if file_id in self.data_dict:
            # Remove from local data_dict
            del self.data_dict[file_id]
            
            # Emit signal to parent to handle deletion
            if hasattr(self.parent, 'file_deleted'):
                self.parent.file_deleted.emit(file_id)
            # Also try to access the main window's input_data_widget
            elif hasattr(self.parent, 'input_data_widget'):
                self.parent.input_data_widget.remove_file(file_id)
            # Update the display after deletion
            self.update_data(self.data_dict)
                
    def get_selected_file_id(self) -> Optional[str]:
        """Get the currently selected file ID"""
        current_item = self.tree_widget.currentItem()
        if current_item and current_item.parent() is None:
            return current_item.text(0)
        return None
        
    def show_full_content(self, item: QTreeWidgetItem, column: int):
        """Show full content in a dialog when double-clicking on content column"""
        if column == 1:  # Content column
            # Find the actual value for this item
            value = self.get_item_value(item)
            if value is not None:
                dialog = QDialog(self)
                dialog.setWindowTitle(f"Full Content - {item.text(0)}")
                dialog.setModal(True)
                dialog.resize(800, 600)
                
                layout = QVBoxLayout(dialog)
                
                # Add a read-only text edit
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setStyleSheet("""
                    QTextEdit {
                        background-color: white;
                        border: 1px solid #ced4da;
                        border-radius: 4px;
                        padding: 8px;
                        font-family: monospace;
                        font-size: 11px;
                    }
                """)
                
                # Format the content based on data type
                content_text = self.format_value_for_display(value)
                text_edit.setPlainText(content_text)
                
                layout.addWidget(text_edit)
                
                # Add close button
                close_button = QPushButton("Close")
                close_button.clicked.connect(dialog.accept)
                close_button.setStyleSheet("""
                    QPushButton {
                        background-color: #007bff;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 8px 16px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #0056b3;
                    }
                """)
                layout.addWidget(close_button)
                
                dialog.exec_()
                
    def get_item_value(self, item: QTreeWidgetItem) -> Any:
        """Get the actual value for a tree item"""
        # Navigate up to find the root item (file ID)
        root_item = item
        while root_item.parent() is not None:
            root_item = root_item.parent()
            
        # Get the file ID
        file_id = root_item.text(0)
        
        # Navigate down to find the actual value
        current_value = self.data_dict.get(file_id)
        if current_value is None:
            return None
            
        # If this is the root item, return the value
        if item == root_item:
            return current_value
            
        # Navigate down the tree to find the specific value
        path = []
        current_item = item
        while current_item.parent() != root_item:
            path.append(current_item.text(0))
            current_item = current_item.parent()
        path.append(current_item.text(0))
        path.reverse()
        
        # Navigate through the value structure
        for key in path:
            if isinstance(current_value, dict) and key in current_value:
                current_value = current_value[key]
            elif isinstance(current_value, (list, tuple)):
                try:
                    # Handle list indices like "[0]", "[1]", etc.
                    if key.startswith('[') and key.endswith(']'):
                        index = int(key[1:-1])
                        current_value = current_value[index]
                    else:
                        return None
                except (ValueError, IndexError):
                    return None
            elif key == "Columns" and isinstance(current_value, pd.DataFrame):
                return current_value
            elif key == "Value" and isinstance(current_value, (pd.DataFrame, np.ndarray)):
                return current_value
            else:
                return None
                
        return current_value
        
    def format_value_for_display(self, value: Any) -> str:
        """Format a value for display in the modal"""
        if isinstance(value, dict):
            result = f"Dictionary with {len(value)} keys:\n"
            result += "=" * 50 + "\n\n"
            result += "Keys:\n"
            result += str(list(value.keys())) + "\n\n"
            result += "Values:\n"
            result += str(value)
            return result
            
        elif isinstance(value, (list, tuple)):
            result = f"{type(value).__name__} with {len(value)} items:\n"
            result += "=" * 50 + "\n\n"
            result += str(value)
            return result
            
        elif isinstance(value, pd.DataFrame):
            result = f"DataFrame with shape {value.shape}:\n"
            result += "=" * 50 + "\n\n"
            result += "Columns:\n"
            result += str(list(value.columns)) + "\n\n"
            result += "Data (first 10 rows):\n"
            result += str(value.head(10))
            return result
            
        elif isinstance(value, np.ndarray):
            result = f"NumPy Array with shape {value.shape}:\n"
            result += "=" * 50 + "\n\n"
            if value.size <= 100:
                result += str(value)
            else:
                result += "First 100 elements:\n"
                result += str(value.flatten()[:100])
                result += f"\n\n... and {value.size - 100} more elements"
            return result
            
        elif isinstance(value, str):
            result = f"String ({len(value)} characters):\n"
            result += "=" * 50 + "\n\n"
            result += value
            return result
            
        else:
            result = f"{type(value).__name__}:\n"
            result += "=" * 50 + "\n\n"
            result += str(value)
            return result


class InputDataWidget(QGroupBox):
    """Widget for input data selection and management"""
    # Signals
    file_loaded = Signal(str, str)  # file_id, file_path
    file_deleted = Signal(str)  # file_id
    
    def __init__(self, parent=None):
        super().__init__("🗃️ Select Data")
        self.parent = parent
        self.data_dict = {}
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # File path input and browse button
        file_path_layout = QHBoxLayout()
        path_label = QLabel("File Path:")
        path_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        file_path_layout.addWidget(path_label)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select a data file to load")
        file_path_layout.addWidget(self.file_path_edit)

        self.browse_button = QPushButton("📁")
        self.browse_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.browse_button.setStyleSheet("""
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
        file_path_layout.addWidget(self.browse_button)
        
        layout.addLayout(file_path_layout)
        
        # File ID input
        file_id_layout = QHBoxLayout()
        file_id_label = QLabel("File ID:")
        file_id_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        file_id_layout.addWidget(file_id_label)
        
        self.file_id_edit = QLineEdit()
        self.file_id_edit.setPlaceholderText("Enter a unique identifier for this file")
        file_id_layout.addWidget(self.file_id_edit)
        layout.addLayout(file_id_layout)
        
        # Load button
        self.load_button = QPushButton("Load File")
        self.load_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.load_button.setStyleSheet("""
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
        layout.addWidget(self.load_button)
        
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
            QLineEdit::placeholder {
                color: #6c757d;
            }
        """)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.browse_button.clicked.connect(self.browse_file)
        self.load_button.clicked.connect(self.load_file)
        self.file_deleted.connect(self.remove_file)
        
    def browse_file(self):
        """Browse for a file to load"""
        # Get default data directory (data folder in app.py directory)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        data_dir = os.path.join(root_dir, "data")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Data File", 
            data_dir, 
            "Data Files (*.data *.csv *.pkl *.pickle);;All Files (*.*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
            # Auto-generate file ID from filename if not set
            if not self.file_id_edit.text().strip():
                file_id = Path(file_path).stem
                self.file_id_edit.setText(file_id)
                
    def load_file(self):
        """Load the selected file"""
        file_path = self.file_path_edit.text().strip()
        file_id = self.file_id_edit.text().strip()
        
        if not file_path or not file_id:
            QMessageBox.warning(self, "Input Error", "Please provide both a file path and a file ID.")
            return
            
        if file_id in self.data_dict:
            QMessageBox.warning(self, "Duplicate ID", f"File ID '{file_id}' already exists. Please use a different ID.")
            return
            
        try:
            # Load the data based on file extension
            data = self.load_data_file(file_path)
            
            # Add to data dictionary
            self.data_dict[file_id] = data
            
            # Emit signal
            self.file_loaded.emit(file_id, file_path)
            
            # Clear input fields
            self.file_path_edit.clear()
            self.file_id_edit.clear()
            
            QMessageBox.information(self, "Success", f"File '{file_id}' loaded successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
            
    def load_data_file(self, file_path: str) -> Any:
        """Load data from various file formats"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.data':
            # Pickle format
            with open(file_path, 'rb') as f:
                return pickle.load(f)
        elif file_ext == '.csv':
            # CSV format
            return pd.read_csv(file_path)
        elif file_ext in ['.pkl', '.pickle']:
            # Pickle format
            with open(file_path, 'rb') as f:
                return pickle.load(f)
        else:
            # Try to load as pickle first, then CSV
            try:
                with open(file_path, 'rb') as f:
                    return pickle.load(f)
            except:
                try:
                    return pd.read_csv(file_path)
                except:
                    # Return "Unknown" for unrecognized formats
                    return "Unknown"
                    
    def remove_file(self, file_id: str):
        """Remove a file from the data dictionary"""
        if file_id in self.data_dict:
            del self.data_dict[file_id]
            
    def get_data_dict(self) -> Dict[str, Any]:
        """Get the current data dictionary"""
        return self.data_dict.copy()
        
    def clear_data(self):
        """Clear all loaded data"""
        self.data_dict.clear()


class ProcessingWidget(QGroupBox):
    """Widget for processing script selection and execution"""
    
    # Signals
    script_loaded = Signal(str, str)  # script_id, script_path
    script_deleted = Signal(str)  # script_id
    
    def __init__(self, parent=None):
        super().__init__("🔧 Data Processing")
        self.parent = parent
        self.scripts_dict = {}
        
        self.setup_ui()
        self.setup_connections()
        self.setup_external_script_support()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Script path input and browse button
        script_path_layout = QHBoxLayout()
        path_label = QLabel("Script Path:")
        path_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        script_path_layout.addWidget(path_label)

        self.script_path_edit = QLineEdit()
        self.script_path_edit.setPlaceholderText("Enter 'Default' or select a processing script")
        
        # Set default script path to "Default"
        self.script_path_edit.setText("Default")
        
        script_path_layout.addWidget(self.script_path_edit)

        self.browse_button = QPushButton("📁")
        self.browse_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.browse_button.setStyleSheet("""
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
        script_path_layout.addWidget(self.browse_button)
        
        layout.addLayout(script_path_layout)
        
        # Apply Processing button
        self.apply_button = QPushButton("Apply Processing")
        self.apply_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.apply_button.setStyleSheet("""
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
        layout.addWidget(self.apply_button)
        
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
            QLineEdit::placeholder {
                color: #6c757d;
            }
        """)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.browse_button.clicked.connect(self.browse_script)
        self.apply_button.clicked.connect(self.apply_processing)
        
    def setup_external_script_support(self):
        """Setup external script loading support based on environment"""
        if not is_external_script_supported():
            self.browse_button.setEnabled(False)
            self.browse_button.setToolTip("External script loading not supported in this environment")
            # Add a note about using default script
            self.browse_button.setText("📁 (Default Only)")
        
    def browse_script(self):
        """Browse for a script to load"""
        # Get default experiments directory (experiments folder in app.py directory)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        experiments_dir = os.path.join(root_dir, "experiments")
        
        script_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Processing Script", 
            experiments_dir, 
            "Python Files (*.py);;All Files (*.*)"
        )
        if script_path:
            self.script_path_edit.setText(script_path)
            
    def apply_processing(self):
        """Apply processing script and store results"""
        script_path = self.script_path_edit.text().strip()
        
        if not script_path:
            QMessageBox.warning(self, "Input Error", "Please provide a script path.")
            return
            
        # Check if file exists (skip check for "Default")
        if script_path != "Default" and not os.path.exists(script_path):
            QMessageBox.warning(self, "File Error", "Script file does not exist.")
            return
        
        # Clear processing results before applying new processing
        if hasattr(self.parent, 'processing_results'):
            self.parent.processing_results = {}
            
        # Update variable inspector to reflect cleared processing data
        if hasattr(self.parent, 'variable_inspector'):
            data_dict = self.parent.get_combined_data_dict()
            self.parent.variable_inspector.update_data(data_dict)
            
        # Auto-generate script ID from filename
        if script_path == "Default":
            script_id = "neuro_v1_processing"
        else:
            script_id = Path(script_path).stem
        
        try:
            # Check if this is the default script
            if script_path == "Default":
                # Use direct import for default script
                import sys
                current_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.dirname(os.path.dirname(current_dir))
                if root_dir not in sys.path:
                    sys.path.insert(0, root_dir)
                
                from experiments.neuro_v1 import processing as module
            else:
                # Use importlib for external scripts
                spec = importlib.util.spec_from_file_location(script_id, script_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            
            if not hasattr(module, 'processing_function'):
                QMessageBox.warning(self, "Function Error", "Script must contain a 'processing_function' function.")
                return
            
            # Get input data (file paths only)
            input_data = {}
            if hasattr(self.parent, 'input_data_widget'):
                input_data = self.parent.input_data_widget.get_data_dict()
            
            # Execute the processing function
            result = module.processing_function(input_data)
            
            # Store the result directly in the processing category (overwrite previous results)
            self.parent.processing_results = result
            
            # Update the variable inspector
            if hasattr(self.parent, 'variable_inspector'):
                data_dict = self.parent.get_combined_data_dict()
                self.parent.variable_inspector.update_data(data_dict)
            
            # Keep script path for multiple executions
            
            QMessageBox.information(self, "Success", "Processing applied successfully. Results stored at Variable Inspector.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply processing:\n{str(e)}")
            
    def remove_script(self, script_id: str):
        """Remove a script from the scripts dictionary"""
        if script_id in self.scripts_dict:
            del self.scripts_dict[script_id]
            
    def get_scripts_dict(self) -> Dict[str, str]:
        """Get the current scripts dictionary"""
        return self.scripts_dict.copy()
        
    def clear_scripts(self):
        """Clear all loaded scripts"""
        self.scripts_dict.clear()
        
    def execute_script(self, script_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a processing script with input data"""
        if script_id not in self.scripts_dict:
            raise ValueError(f"Script '{script_id}' not found")
            
        script_path = self.scripts_dict[script_id]
        
        # Reload the module to get any changes
        spec = importlib.util.spec_from_file_location(script_id, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Execute the processing function
        return module.processing_function(input_data)


class VisualizationWidget(QGroupBox):
    """Widget for visualization script selection and execution"""
    # Signals
    script_loaded = Signal(str, str)  # script_id, script_path
    script_deleted = Signal(str)  # script_id
    view_output_executed = Signal(str)  # script_id
    
    def __init__(self, parent=None):
        super().__init__("👁️ Data Visualization")
        self.parent = parent
        self.scripts_dict = {}
        
        self.setup_ui()
        self.setup_connections()
        self.setup_external_script_support()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Script path input and browse button
        script_path_layout = QHBoxLayout()
        path_label = QLabel("Script Path:")
        path_label.setStyleSheet("background-color: white; color: #495057; border-right: none;")
        script_path_layout.addWidget(path_label)

        self.script_path_edit = QLineEdit()
        self.script_path_edit.setPlaceholderText("Enter 'Default' or select a visualization script")
        
        # Set default script path to "Default"
        self.script_path_edit.setText("Default")
        
        script_path_layout.addWidget(self.script_path_edit)

        self.browse_button = QPushButton("📁")
        self.browse_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.browse_button.setStyleSheet("""
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
        script_path_layout.addWidget(self.browse_button)
        
        layout.addLayout(script_path_layout)
        
        # View Output button
        self.view_output_button = QPushButton("View Output")
        self.view_output_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.view_output_button.setStyleSheet("""
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
        layout.addWidget(self.view_output_button)
        
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
            QLineEdit::placeholder {
                color: #6c757d;
            }
        """)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.browse_button.clicked.connect(self.browse_script)
        self.view_output_button.clicked.connect(self.view_output)
        
    def setup_external_script_support(self):
        """Setup external script loading support based on environment"""
        if not is_external_script_supported():
            self.browse_button.setEnabled(False)
            self.browse_button.setToolTip("External script loading not supported in this environment")
            # Add a note about using default script
            self.browse_button.setText("📁 (Default Only)")
        
    def browse_script(self):
        """Browse for a script to load"""
        # Get default experiments directory (experiments folder in app.py directory)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        experiments_dir = os.path.join(root_dir, "experiments")
        
        script_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Visualization Script", 
            experiments_dir, 
            "Python Files (*.py);;All Files (*.*)"
        )
        if script_path:
            self.script_path_edit.setText(script_path)
            
    def view_output(self):
        """Execute visualization script and store results"""
        script_path = self.script_path_edit.text().strip()
        
        if not script_path:
            QMessageBox.warning(self, "Input Error", "Please provide a script path.")
            return
            
        # Check if file exists (skip check for "Default")
        if script_path != "Default" and not os.path.exists(script_path):
            QMessageBox.warning(self, "File Error", "Script file does not exist.")
            return
        
        # Clear visualization results before applying new visualization
        if hasattr(self.parent, 'visualization_results'):
            self.parent.visualization_results = {}
            
        # Update visualization widget dropdowns to reflect cleared data
        if hasattr(self.parent, 'data_analysis_widget'):
            self.parent.data_analysis_widget.update_visualization_data({})
            
        # Update variable inspector to reflect cleared visualization data
        if hasattr(self.parent, 'variable_inspector'):
            data_dict = self.parent.get_combined_data_dict()
            self.parent.variable_inspector.update_data(data_dict)
            
        # Auto-generate script ID from filename
        if script_path == "Default":
            script_id = "neuro_v1_visualization"
        else:
            script_id = Path(script_path).stem
        
        try:
            # Check if this is the default script
            if script_path == "Default":
                # Use direct import for default script
                import sys
                current_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.dirname(os.path.dirname(current_dir))
                if root_dir not in sys.path:
                    sys.path.insert(0, root_dir)
                
                from experiments.neuro_v1 import visualization as module
            else:
                # Use importlib for external scripts
                spec = importlib.util.spec_from_file_location(script_id, script_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            
            if not hasattr(module, 'visualization_function'):
                QMessageBox.warning(self, "Function Error", "Script must contain a 'visualization_function' function.")
                return
            
            # Get input and processing data
            input_data = {}
            processing_data = {}
            
            if hasattr(self.parent, 'input_data_widget'):
                input_data = self.parent.input_data_widget.get_data_dict()
                
            if hasattr(self.parent, 'processing_results'):
                processing_data = self.parent.processing_results
            
            # Execute the visualization function
            result = module.visualization_function(input_data, processing_data)
            
            # Store the result directly in the visualization category (overwrite previous results)
            self.parent.visualization_results = result
            
            # Update the variable inspector
            if hasattr(self.parent, 'variable_inspector'):
                data_dict = self.parent.get_combined_data_dict()
                self.parent.variable_inspector.update_data(data_dict)
            
            # Emit signal to update main area
            self.view_output_executed.emit(script_id)
            
            # Keep script path for multiple executions
            
            QMessageBox.information(self, "Success", "Visualization executed successfully. Results stored at Variable Inspector.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to execute visualization:\n{str(e)}")
            
    def remove_script(self, script_id: str):
        """Remove a script from the scripts dictionary"""
        if script_id in self.scripts_dict:
            del self.scripts_dict[script_id]
            
    def get_scripts_dict(self) -> Dict[str, str]:
        """Get the current scripts dictionary"""
        return self.scripts_dict.copy()
        
    def clear_scripts(self):
        """Clear all loaded scripts"""
        self.scripts_dict.clear()
        
    def execute_script(self, script_id: str, input_data: Dict[str, Any], processing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a visualization script with input and processing data"""
        if script_id not in self.scripts_dict:
            raise ValueError(f"Script '{script_id}' not found")
            
        script_path = self.scripts_dict[script_id]
        
        # Reload the module to get any changes
        spec = importlib.util.spec_from_file_location(script_id, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Execute the visualization function
        return module.visualization_function(input_data, processing_data)


class SessionManagementWidget(QGroupBox):
    """Widget for session management (save/load)"""
    
    def __init__(self, parent=None):
        super().__init__("💾 Session Management")
        self.parent = parent
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Buttons in horizontal layout
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save Session")
        self.save_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        
        self.load_button = QPushButton("Load Session")
        self.load_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.load_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        
        layout.addLayout(button_layout)
        
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
        """)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.save_button.clicked.connect(self.save_session)
        self.load_button.clicked.connect(self.load_session)
        
    def get_default_session_directory(self):
        """Get the default session directory (sessions folder in app.py directory)"""
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up to the root directory (where app.py is)
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        # Create sessions directory
        sessions_dir = os.path.join(root_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        return sessions_dir
        
    def save_session(self):
        """Save the current session state"""
        # Get default session directory
        session_dir = self.get_default_session_directory()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Session", 
            session_dir, 
            "Session Files (*.session);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            # Collect all session data
            session_data = {
                # Input data
                "input_data": {},
                # Processing data
                "processing_results": {},
                "processing_script_path": "",
                # Visualization data
                "visualization_results": {},
                "visualization_script_path": "",
                # Variable inspector data
                "variable_inspector_data": {},
                # Main area splitter dimensions
                "main_area_splitters": {},
                # Current plots and tables
                "current_plots_tables": {}
            }
            
            # Get input data
            if hasattr(self.parent, 'input_data_widget'):
                session_data["input_data"] = self.parent.input_data_widget.get_data_dict()
                
            # Get processing data
            if hasattr(self.parent, 'processing_results'):
                session_data["processing_results"] = self.parent.processing_results
                
            # Get processing script path
            if hasattr(self.parent, 'processing_widget'):
                session_data["processing_script_path"] = self.parent.processing_widget.script_path_edit.text().strip()
                
            # Get visualization data
            if hasattr(self.parent, 'visualization_results'):
                session_data["visualization_results"] = self.parent.visualization_results
                
            # Get visualization script path
            if hasattr(self.parent, 'visualization_widget'):
                session_data["visualization_script_path"] = self.parent.visualization_widget.script_path_edit.text().strip()
                
            # Get variable inspector data
            if hasattr(self.parent, 'variable_inspector'):
                session_data["variable_inspector_data"] = self.parent.variable_inspector.data_dict
                
            # Get main area splitter dimensions (if available)
            if hasattr(self.parent, 'main_area'):
                # This would need to be implemented based on the actual splitter structure
                pass
                
            # Get current plots and tables state (if available)
            if hasattr(self.parent, 'data_analysis_widget'):
                # This would need to be implemented based on the actual widget structure
                pass
                
            # Save session data
            with open(file_path, "wb") as f:
                pickle.dump(session_data, f)
                
            QMessageBox.information(self, "Session Saved", "The session was saved successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving the session:\n{str(e)}")
            
    def load_session(self):
        """Load a previously saved session"""
        # Get default session directory
        session_dir = self.get_default_session_directory()
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Session", 
            session_dir, 
            "Session Files (*.session);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            # Load session data
            with open(file_path, "rb") as f:
                session_data = pickle.load(f)
                
            # Restore input data
            if hasattr(self.parent, 'input_data_widget') and "input_data" in session_data:
                self.parent.input_data_widget.data_dict = session_data["input_data"].copy()
                
            # Restore processing data
            if "processing_results" in session_data:
                self.parent.processing_results = session_data["processing_results"]
                
            # Restore processing script path
            if hasattr(self.parent, 'processing_widget') and "processing_script_path" in session_data:
                self.parent.processing_widget.script_path_edit.setText(session_data["processing_script_path"])
                
            # Restore visualization data
            if "visualization_results" in session_data:
                self.parent.visualization_results = session_data["visualization_results"]
                
            # Restore visualization script path
            if hasattr(self.parent, 'visualization_widget') and "visualization_script_path" in session_data:
                self.parent.visualization_widget.script_path_edit.setText(session_data["visualization_script_path"])
                
            # Restore variable inspector data
            if hasattr(self.parent, 'variable_inspector') and "variable_inspector_data" in session_data:
                self.parent.variable_inspector.data_dict = session_data["variable_inspector_data"]
                
            # Update the variable inspector display
            if hasattr(self.parent, 'variable_inspector'):
                data_dict = self.parent.get_combined_data_dict()
                self.parent.variable_inspector.update_data(data_dict)
                
            # Update visualization widget if available
            if hasattr(self.parent, 'data_analysis_widget') and "visualization_results" in session_data:
                self.parent.data_analysis_widget.update_visualization_data(session_data["visualization_results"])
                
            QMessageBox.information(self, "Session Loaded", "The session was loaded successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"An error occurred while loading the session:\n{str(e)}")


class TableViewDialog(QDialog):
    """Modal dialog for viewing table data"""
    
    def __init__(self, table_data, table_name, parent=None):
        super().__init__(parent)
        self.table_data = table_data
        self.table_name = table_name
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle(f"Table Viewer - {self.table_name}")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title label
        title_label = QLabel(f"📊 {self.table_name}")
        title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #495057;
                font-size: 14px;
                padding: 5px 0px;
            }
        """)
        layout.addWidget(title_label)
        
        # Create table widget
        table_widget = QTableWidget()
        table_widget.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                color: #495057;
                font-size: 11px;
                gridline-color: #f8f9fa;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f8f9fa;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #495057;
            }
            QTableWidget::item:alternate {
                background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 4px;
                font-weight: bold;
                color: #495057;
            }
        """)
        
        # Hide row headers (row index)
        table_widget.verticalHeader().setVisible(False)
        
        # Populate table based on data type
        if isinstance(self.table_data, pd.DataFrame) or hasattr(self.table_data, 'columns'):
            # Set dimensions
            table_widget.setRowCount(len(self.table_data))
            table_widget.setColumnCount(len(self.table_data.columns))
            
            # Set headers
            table_widget.setHorizontalHeaderLabels(self.table_data.columns)
            
            # Populate data - use safe indexing for FastDataFrame compatibility
            for i in range(len(self.table_data)):
                for j in range(len(self.table_data.columns)):
                    try:
                        # Try iloc first (pandas DataFrame)
                        value = self.table_data.iloc[i, j]
                    except AttributeError:
                        # Fallback to direct indexing (FastDataFrame)
                        value = self.table_data[self.table_data.columns[j]].iloc[i] if hasattr(self.table_data, 'iloc') else self.table_data[self.table_data.columns[j]][i]
                    item = QTableWidgetItem(str(value))
                    table_widget.setItem(i, j, item)
                    
        elif isinstance(self.table_data, (list, tuple)):
            # Handle list/tuple data
            if self.table_data and isinstance(self.table_data[0], (list, tuple)):
                # 2D data
                table_widget.setRowCount(len(self.table_data))
                table_widget.setColumnCount(len(self.table_data[0]))
                
                for i, row in enumerate(self.table_data):
                    for j, value in enumerate(row):
                        item = QTableWidgetItem(str(value))
                        table_widget.setItem(i, j, item)
            else:
                # 1D data
                table_widget.setRowCount(len(self.table_data))
                table_widget.setColumnCount(1)
                
                for i, value in enumerate(self.table_data):
                    item = QTableWidgetItem(str(value))
                    table_widget.setItem(i, 0, item)
        
        # Enable alternating row colors
        table_widget.setAlternatingRowColors(True)
        
        # Enable scrolling
        table_widget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        # Auto-resize columns
        table_widget.resizeColumnsToContents()
        
        layout.addWidget(table_widget)
        
        # Add close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)


class DataEditingWidget(QWidget):
    """Widget for editing and cropping data files"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.channel_names = ['TP9', 'AF7', 'AF8', 'TP10']
        self.channel_colors = {
            'TP9': '#E74C3C',     # Red
            'AF7': '#3498DB',     # Blue
            'AF8': '#F39C12',     # Orange
            'TP10': '#27AE60'     # Green
        }
        
        self.current_file_id = None
        self.current_data = None
        self.cropped_data = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # File selection dropdown
        file_selection_layout = QHBoxLayout()
        file_label = QLabel("Select File:")
        file_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        file_selection_layout.addWidget(file_label)
        
        self.file_combo = QComboBox()
        self.file_combo.addItem("None")
        self.file_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                color: #495057;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ced4da;
                color: #495057;
                selection-background-color: #e3f2fd;
                selection-color: #495057;
            }
        """)
        self.file_combo.currentTextChanged.connect(self.on_file_changed)
        file_selection_layout.addWidget(self.file_combo)
        
        layout.addLayout(file_selection_layout)
        
        # Create PyQtGraph widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')  # White background
        self.plot_item = self.plot_widget.getPlotItem()
        
        # Configure plot
        self.plot_item.setTitle("EEG Data - Data Editing", color='#495057', size='14pt')
        self.plot_item.setLabel('left', 'Amplitude (μV)', color='#495057')
        self.plot_item.setLabel('bottom', 'Time (s)', color='#495057')
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        
        # Set axis colors
        self.plot_item.getAxis('left').setPen(pg.mkPen(color='#495057'))
        self.plot_item.getAxis('bottom').setPen(pg.mkPen(color='#495057'))
        self.plot_item.getAxis('left').setTextPen(pg.mkPen(color='#495057'))
        self.plot_item.getAxis('bottom').setTextPen(pg.mkPen(color='#495057'))
        
        # Initialize curves for each channel
        self.curves = {}
        for channel in self.channel_names:
            color = self.channel_colors[channel]
            pen = pg.mkPen(color=color, width=2)
            self.curves[channel] = self.plot_item.plot(
                name=channel,
                pen=pen,
                symbol=None
            )
        
        # Add linear region for cropping
        self.crop_region = pg.LinearRegionItem(
            values=[0, 10],
            brush=pg.mkBrush(100, 100, 255, 50),
            pen=pg.mkPen('b', width=2)
        )
        self.crop_region.setZValue(-10)
        self.plot_item.addItem(self.crop_region)
        
        layout.addWidget(self.plot_widget)
        
        # All buttons in one horizontal layout
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        # Apply Crop button (updates data in place)
        self.apply_crop_button = QPushButton("Apply Crop")
        self.apply_crop_button.setEnabled(False)
        self.apply_crop_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
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
                color: #ced4da;
            }
        """)
        self.apply_crop_button.clicked.connect(self.apply_crop)
        buttons_layout.addWidget(self.apply_crop_button)
        
        # Save Cropped Data button (saves to file)
        self.save_cropped_button = QPushButton("Save Cropped Data")
        self.save_cropped_button.setEnabled(False)
        self.save_cropped_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ced4da;
            }
        """)
        self.save_cropped_button.clicked.connect(self.save_cropped_data)
        buttons_layout.addWidget(self.save_cropped_button)
        
        
        # Remove Data button
        self.remove_button = QPushButton("Remove Data")
        self.remove_button.setEnabled(False)
        self.remove_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ced4da;
            }
        """)
        self.remove_button.clicked.connect(self.remove_data)
        buttons_layout.addWidget(self.remove_button)
        
        layout.addLayout(buttons_layout)
        
    def update_file_list(self, file_dict):
        """Update the file dropdown with available files"""
        # Block signals to avoid triggering on_file_changed
        self.file_combo.blockSignals(True)
        
        # Clear and repopulate
        self.file_combo.clear()
        self.file_combo.addItem("None")
        
        for file_id in file_dict.keys():
            self.file_combo.addItem(file_id)
        
        self.file_combo.blockSignals(False)
        
    def on_file_changed(self, file_id):
        """Handle file selection change"""
        if not file_id or file_id == "None":
            self.clear_plot()
            self.current_file_id = None
            self.current_data = None
            self.apply_crop_button.setEnabled(False)
            self.save_cropped_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            return
        
        # Get data from parent
        if hasattr(self.parent, 'input_data_widget'):
            data_dict = self.parent.input_data_widget.get_data_dict()
            if file_id in data_dict:
                self.current_file_id = file_id
                self.current_data = data_dict[file_id]
                self.plot_data(self.current_data)
                self.apply_crop_button.setEnabled(True)
                self.save_cropped_button.setEnabled(True)
                self.remove_button.setEnabled(True)
            else:
                self.clear_plot()
                self.apply_crop_button.setEnabled(False)
                self.save_cropped_button.setEnabled(False)
                self.remove_button.setEnabled(False)
        
    def plot_data(self, data):
        """Plot EEG data from the selected file"""
        try:
            if 'eeg' not in data:
                QMessageBox.warning(self, "No EEG Data", "The selected file does not contain EEG data.")
                return
            
            eeg_data = data['eeg']
            
            # Handle different data formats
            if hasattr(eeg_data, 'columns'):
                # Pandas DataFrame format
                # Get time data
                if 'timestamp' in eeg_data.columns:
                    time_data = np.array(eeg_data['timestamp'] - eeg_data['timestamp'].min())
                else:
                    time_data = np.arange(len(eeg_data))
                
                # Plot each channel
                for channel in self.channel_names:
                    if channel in eeg_data.columns:
                        channel_data = eeg_data[channel].to_numpy()
                        self.curves[channel].setData(time_data, channel_data)
                        
            elif isinstance(eeg_data, dict):
                # Dictionary format (from .data files)
                # Get time data
                if 'timestamp' in eeg_data:
                    timestamp = eeg_data['timestamp']
                    if hasattr(timestamp, 'to_numpy'):
                        time_data = (timestamp - timestamp.min()).to_numpy()
                    else:
                        # Already numpy array
                        time_data = timestamp - timestamp.min()
                else:
                    # Estimate time based on first available channel
                    first_channel = None
                    for channel in self.channel_names:
                        if channel in eeg_data:
                            first_channel = channel
                            break
                    if first_channel:
                        channel_data = eeg_data[first_channel]
                        if hasattr(channel_data, '__len__'):
                            time_data = np.arange(len(channel_data))
                        else:
                            time_data = np.array([0])
                    else:
                        time_data = np.array([0])
                
                # Plot each channel
                for channel in self.channel_names:
                    if channel in eeg_data:
                        channel_data = eeg_data[channel]
                        # Convert to numpy array if needed
                        if hasattr(channel_data, 'to_numpy'):
                            channel_array = channel_data.to_numpy()
                        else:
                            # Already numpy array or list
                            channel_array = np.array(channel_data)
                        self.curves[channel].setData(time_data, channel_array)
            else:
                QMessageBox.warning(self, "Unsupported Data Format", 
                                  f"Unsupported EEG data format: {type(eeg_data)}")
                return
            
            # Set crop region to full range initially
            if len(time_data) > 0:
                time_min = time_data[0]
                time_max = time_data[-1]
                self.crop_region.setRegion([time_min, time_max])
                self.plot_item.setXRange(time_min, time_max, padding=0)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot data:\n{str(e)}")
    
    def clear_plot(self):
        """Clear all plot curves"""
        for channel in self.channel_names:
            if channel in self.curves:
                self.curves[channel].clear()
    
    def apply_crop(self):
        """Apply crop to the current data in place"""
        if self.current_data is None or self.current_file_id is None:
            QMessageBox.warning(self, "No Data", "No data is currently loaded.")
            return
        
        try:
            # Get crop region bounds
            crop_start, crop_end = self.crop_region.getRegion()
            
            # Crop all data types
            cropped_data = {}
            
            # Crop EEG data
            if 'eeg' in self.current_data:
                eeg_data = self.current_data['eeg'].copy()
                if 'timestamp' in eeg_data.columns:
                    time_data = eeg_data['timestamp'] - eeg_data['timestamp'].min()
                    mask = (time_data >= crop_start) & (time_data <= crop_end)
                    # Use direct boolean indexing instead of .loc for FastDataFrame compatibility
                    masked_data = eeg_data[mask]
                    cropped_data['eeg'] = masked_data.reset_index(drop=True)
                else:
                    cropped_data['eeg'] = eeg_data
            
            # Crop PPG data
            if 'ppg' in self.current_data:
                ppg_data = self.current_data['ppg'].copy()
                if 'timestamp' in ppg_data.columns:
                    time_data = ppg_data['timestamp'] - ppg_data['timestamp'].min()
                    mask = (time_data >= crop_start) & (time_data <= crop_end)
                    # Use direct boolean indexing instead of .loc for FastDataFrame compatibility
                    masked_data = ppg_data[mask]
                    cropped_data['ppg'] = masked_data.reset_index(drop=True)
                else:
                    cropped_data['ppg'] = ppg_data
            
            # Crop IMU data
            if 'imu' in self.current_data:
                imu_data = self.current_data['imu'].copy()
                if 'timestamp' in imu_data.columns:
                    time_data = imu_data['timestamp'] - imu_data['timestamp'].min()
                    mask = (time_data >= crop_start) & (time_data <= crop_end)
                    # Use direct boolean indexing instead of .loc for FastDataFrame compatibility
                    masked_data = imu_data[mask]
                    cropped_data['imu'] = masked_data.reset_index(drop=True)
                else:
                    cropped_data['imu'] = imu_data
            
            # Copy any other data
            for key in self.current_data:
                if key not in ['eeg', 'ppg', 'imu']:
                    cropped_data[key] = self.current_data[key]
            
            # Update the data in the parent's input_data_widget
            if hasattr(self.parent, 'input_data_widget'):
                self.parent.input_data_widget.data_dict[self.current_file_id] = cropped_data
                self.current_data = cropped_data
                
                # Replot the cropped data
                self.plot_data(cropped_data)
                
                # Update variable inspector
                if hasattr(self.parent, 'variable_inspector'):
                    data_dict = self.parent.get_combined_data_dict()
                    self.parent.variable_inspector.update_data(data_dict)
                
                QMessageBox.information(self, "Success", "Data cropped successfully and updated in place.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply crop:\n{str(e)}")
    
    def save_cropped_data(self):
        """Save the cropped data to a .data file"""
        if self.current_data is None or self.current_file_id is None:
            QMessageBox.warning(self, "No Data", "No data is currently loaded.")
            return
        
        try:
            # Get crop region bounds
            crop_start, crop_end = self.crop_region.getRegion()
            
            # Crop all data types
            cropped_data = {}
            
            # Crop EEG data
            if 'eeg' in self.current_data:
                eeg_data = self.current_data['eeg'].copy()
                if 'timestamp' in eeg_data.columns:
                    time_data = eeg_data['timestamp'] - eeg_data['timestamp'].min()
                    mask = (time_data >= crop_start) & (time_data <= crop_end)
                    cropped_data['eeg'] = eeg_data[mask].reset_index(drop=True)
                else:
                    cropped_data['eeg'] = eeg_data
            
            # Crop PPG data
            if 'ppg' in self.current_data:
                ppg_data = self.current_data['ppg'].copy()
                if 'timestamp' in ppg_data.columns:
                    time_data = ppg_data['timestamp'] - ppg_data['timestamp'].min()
                    mask = (time_data >= crop_start) & (time_data <= crop_end)
                    cropped_data['ppg'] = ppg_data[mask].reset_index(drop=True)
                else:
                    cropped_data['ppg'] = ppg_data
            
            # Crop IMU data
            if 'imu' in self.current_data:
                imu_data = self.current_data['imu'].copy()
                if 'timestamp' in imu_data.columns:
                    time_data = imu_data['timestamp'] - imu_data['timestamp'].min()
                    mask = (time_data >= crop_start) & (time_data <= crop_end)
                    cropped_data['imu'] = imu_data[mask].reset_index(drop=True)
                else:
                    cropped_data['imu'] = imu_data
            
            # Copy any other data
            for key in self.current_data:
                if key not in ['eeg', 'ppg', 'imu']:
                    cropped_data[key] = self.current_data[key]
            
            # Get save location
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(os.path.dirname(current_dir))
            data_dir = os.path.join(root_dir, "data")
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Cropped Data",
                data_dir,
                "Data Files (*.data);;All Files (*.*)"
            )
            
            if file_path:
                # Save as pickle
                with open(file_path, 'wb') as f:
                    pickle.dump(cropped_data, f)
                
                QMessageBox.information(self, "Success", f"Cropped data saved successfully to:\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save cropped data:\n{str(e)}")
    
    def remove_data(self):
        """Remove the selected file from opened files and variable inspector"""
        if self.current_file_id is None:
            QMessageBox.warning(self, "No File Selected", "No file is currently selected.")
            return
        
        try:
            # Confirm removal
            reply = QMessageBox.question(self, "Remove Data", 
                                       f"Are you sure you want to remove '{self.current_file_id}' from the opened files?\n"
                                       "This will also clear it from the Variable Inspector.",
                                       QMessageBox.Yes | QMessageBox.No, 
                                       QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                # Remove from input data widget
                if hasattr(self.parent, 'input_data_widget'):
                    if self.current_file_id in self.parent.input_data_widget.data_dict:
                        del self.parent.input_data_widget.data_dict[self.current_file_id]
                
                # Store file_id for success message before clearing
                removed_file_id = self.current_file_id
                
                # Clear current data
                self.current_file_id = None
                self.current_data = None
                self.clear_plot()
                
                # Update file list dropdown
                self.update_file_list(self.parent.input_data_widget.get_data_dict())
                
                # Update variable inspector
                if hasattr(self.parent, 'variable_inspector'):
                    data_dict = self.parent.get_combined_data_dict()
                    self.parent.variable_inspector.update_data(data_dict)
                
                # Disable buttons
                self.apply_crop_button.setEnabled(False)
                self.save_cropped_button.setEnabled(False)
                self.remove_button.setEnabled(False)
                
                QMessageBox.information(self, "Success", f"File '{removed_file_id}' has been removed.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to remove data:\n{str(e)}")


class DataAnalysisWidget(QWidget):
    """Main data analysis interface widget with single plot and table selection"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.visualization_data = {}
        
        self.setup_ui()
        
        
    def setup_ui(self):
        """Setup the user interface with tabs for data editing and visualization"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                color: #495057;
                border: 1px solid #ced4da;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #007bff;
            }
            QTabBar::tab:hover {
                background-color: #e9ecef;
            }
        """)
        
        # Create Data Editing tab
        self.data_editing_widget = DataEditingWidget(self.parent)
        self.tab_widget.addTab(self.data_editing_widget, "Data Editing")
        
        # Create Data Visualization tab
        self.data_visualization_widget = self.create_visualization_tab()
        self.tab_widget.addTab(self.data_visualization_widget, "Data Visualization")
        
        layout.addWidget(self.tab_widget)
        
    def create_visualization_tab(self):
        """Create the data visualization tab (existing functionality)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Create main content area
        self.main_content = self.create_main_content()
        layout.addWidget(self.main_content, 1)  # Give it stretch factor
        
        # Create table selection bar
        self.table_bar = self.create_table_selection_bar()
        layout.addWidget(self.table_bar)
        
        return widget
        
    def create_main_content(self):
        """Create the main content area with plot display"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Plot label
        plot_label_layout = QHBoxLayout()
        plot_label = QLabel("Plot:")
        plot_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }
        """)
        plot_label_layout.addWidget(plot_label)
        
        # Plot options dropdown
        self.plot_combo = QComboBox()
        self.plot_combo.addItem("None")
        self.plot_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.plot_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                color: #495057;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ced4da;
                color: #495057;
                selection-background-color: #e3f2fd;
                selection-color: #495057;
            }
        """)
        self.plot_combo.currentTextChanged.connect(self.on_plot_changed)
        plot_label_layout.addWidget(self.plot_combo)
        
        layout.addLayout(plot_label_layout)
        
        # Create content display area
        self.plot_content_area = QWidget()
        self.plot_content_area.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }
        """)
        content_layout = QVBoxLayout(self.plot_content_area)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create canvas container for plots
        self.canvas_container = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_container)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.canvas_container)
        
        # Create bottom widget for toolbar and controls
        self.bottom_widget = QWidget()
        self.bottom_widget.setFixedHeight(40)
        self.bottom_widget.setStyleSheet("border: none;")
        self.bottom_layout = QHBoxLayout(self.bottom_widget)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.bottom_widget)
        
        # Create DPI and save controls
        dpi_label = QLabel("DPI:")
        dpi_label.setStyleSheet("color: #495057; font-size: 11px; border: none;")
        self.dpi_input = QSpinBox()
        self.dpi_input.setRange(50, 600)
        self.dpi_input.setValue(300)  # Default to 300 DPI for high quality
        self.dpi_input.setStyleSheet("""
            QSpinBox {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 2px 4px;
                color: #495057;
                font-size: 11px;
            }
        """)
        
        # Save button
        self.save_button = QPushButton("Save Figure")
        self.save_button.setStyleSheet("""
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
        self.save_button.clicked.connect(self.save_current_figure)
        
        # Add controls to bottom layout
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(dpi_label)
        self.bottom_layout.addWidget(self.dpi_input)
        self.bottom_layout.addWidget(self.save_button)
        
        # Placeholder text
        placeholder = QLabel("Select a Plot to display")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-style: italic;
                font-size: 12px;
            }
        """)
        self.canvas_layout.addWidget(placeholder)
        
        layout.addWidget(self.plot_content_area, 1)  # Give it stretch factor
        
        # Store references
        self.canvas = None
        self.plot_toolbar = None
        self.current_figure = None
        
        return widget
        
    def create_table_selection_bar(self):
        """Create the table selection bar with dropdown and view button"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }
        """)
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Table label
        table_label = QLabel("Table:")
        table_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }
        """)
        layout.addWidget(table_label)
        
        # Table options dropdown
        self.table_combo = QComboBox()
        self.table_combo.addItem("None")
        self.table_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.table_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                color: #495057;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ced4da;
                color: #495057;
                selection-background-color: #e3f2fd;
                selection-color: #495057;
            }
        """)
        layout.addWidget(self.table_combo)
        
        # View button
        self.view_table_button = QPushButton("View")
        self.view_table_button.setStyleSheet("""
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
                color: #ced4da;
            }
        """)
        self.view_table_button.clicked.connect(self.view_selected_table)
        self.view_table_button.setEnabled(False)  # Disabled until a table is selected
        layout.addWidget(self.view_table_button)
        
        # Connect table combo changes to enable/disable button
        self.table_combo.currentTextChanged.connect(self.on_table_selection_changed)
        
        return widget
        
    def on_plot_changed(self, plot_name):
        """Handle plot selection change"""
        # Handle empty or None plot names
        if not plot_name or plot_name == "None":
            self.clear_plot_area()
            return
            
        # Display the selected plot
        self.display_plot(plot_name)
    
    def on_table_selection_changed(self, table_name):
        """Handle table selection change - enables/disables view button"""
        if table_name and table_name != "None":
            self.view_table_button.setEnabled(True)
        else:
            self.view_table_button.setEnabled(False)
    
    def view_selected_table(self):
        """Open modal to view the selected table"""
        table_name = self.table_combo.currentText()
        if not table_name or table_name == "None":
            return
        
        try:
            # Get table data
            table_data = self.parent.visualization_results["tables"][table_name]
            
            # Create and show modal dialog
            dialog = TableViewDialog(table_data, table_name, parent=self)
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to display table:\n{str(e)}")
            
    def clear_plot_area(self):
        """Clear the plot area and show placeholder"""
        # Clear existing content from canvas layout
        for i in reversed(range(self.canvas_layout.count())):
            item = self.canvas_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
        
        # Remove old toolbar if it exists
        if self.plot_toolbar is not None:
            self.bottom_layout.removeWidget(self.plot_toolbar)
            self.plot_toolbar.setParent(None)
            QTimer.singleShot(0, self.plot_toolbar.deleteLater)
            self.plot_toolbar = None
        
        # Clear canvas reference
        if self.canvas is not None:
            self.canvas.setParent(None)
            self.canvas.deleteLater()
            self.canvas = None
        
        self.current_figure = None
        
        # Add placeholder
        placeholder = QLabel("Select a Plot to display")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-style: italic;
                font-size: 12px;
            }
        """)
        self.canvas_layout.addWidget(placeholder)
        

    def display_plot(self, plot_name):
        """Display the selected plot"""
        try:
            fig = self.parent.visualization_results["plots"][plot_name]
            self.current_figure = fig

            # Clear previous canvas/widgets
            for i in reversed(range(self.canvas_layout.count())):
                item = self.canvas_layout.itemAt(i)
                if w := item.widget():
                    w.setParent(None)

            if self.canvas is not None:
                self.canvas.setParent(None)
                self.canvas.deleteLater()

            # Create simple canvas without responsive features
            self.canvas = FigureCanvas(fig)
            self.canvas.setContentsMargins(0, 0, 0, 0)
            self.canvas_layout.setContentsMargins(0, 0, 0, 0)
            self.canvas_layout.setSpacing(0)
            self.canvas_layout.addWidget(self.canvas)

            # Update toolbar
            if self.plot_toolbar is not None:
                self.bottom_layout.removeWidget(self.plot_toolbar)
                self.plot_toolbar.setParent(None)
                self.plot_toolbar.deleteLater()

            self.plot_toolbar = SafeNavigationToolbar(self.canvas, self)
            self.bottom_layout.insertWidget(0, self.plot_toolbar)

            # Draw the plot
            self.canvas.draw()

        except Exception as e:
            err = QLabel(f"Error displaying plot: {e}")
            err.setAlignment(Qt.AlignCenter)
            err.setStyleSheet("color:#dc3545;")
            self.canvas_layout.addWidget(err)
            
    def save_current_figure(self):
        """Save the currently displayed figure"""
        if self.current_figure is None:
            QMessageBox.warning(self, "No Plot", "No plot is currently displayed.")
            return
        
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Save Figure", 
                "", 
                "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*.*)"
            )
            if file_path:
                dpi = self.dpi_input.value()
                self.current_figure.savefig(file_path, dpi=dpi, bbox_inches='tight')
                QMessageBox.information(self, "Success", f"Figure saved successfully to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save figure: {str(e)}")
            
    def update_visualization_data(self, visualization_results):
        """Update visualization data and refresh dropdown options"""
        self.visualization_data = visualization_results
        
        # Block signals temporarily
        self.plot_combo.blockSignals(True)
        self.table_combo.blockSignals(True)
        
        # Update plot combo
        self.plot_combo.clear()
        self.plot_combo.addItem("None")
        if "plots" in visualization_results:
            for plot_name in visualization_results["plots"].keys():
                self.plot_combo.addItem(plot_name)
        
        # Update table combo
        self.table_combo.clear()
        self.table_combo.addItem("None")
        if "tables" in visualization_results:
            for table_name in visualization_results["tables"].keys():
                self.table_combo.addItem(table_name)
        
        # Unblock signals
        self.plot_combo.blockSignals(False)
        self.table_combo.blockSignals(False)
                
    def get_data_dict(self) -> Dict[str, Any]:
        """Get the current data dictionary"""
        # Get data from the InputDataWidget in the left panel
        if hasattr(self.parent, 'input_data_widget'):
            return self.parent.input_data_widget.get_data_dict()
        return {}
        
    def clear_data(self):
        """Clear all loaded data"""
        if hasattr(self.parent, 'input_data_widget'):
            self.parent.input_data_widget.clear_data()
            
    def update_variable_inspector(self):
        """Update the variable inspector with current data"""
        # This method is now handled directly in the main window
        pass
    
    def update_data_editing_files(self):
        """Update the file list in the data editing widget"""
        if hasattr(self, 'data_editing_widget') and hasattr(self.parent, 'input_data_widget'):
            data_dict = self.parent.input_data_widget.get_data_dict()
            self.data_editing_widget.update_file_list(data_dict)
    
