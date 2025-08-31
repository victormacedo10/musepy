"""
Data Analysis Widget - Main interface for data analysis
"""

import sys
import os
import pickle
import pandas as pd
import numpy as np
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, Union
from collections.abc import Mapping, Sequence

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLineEdit, 
    QLabel, QComboBox, QSpinBox, QCheckBox, QTextEdit, QFileDialog, 
    QMessageBox, QScrollArea, QFrame, QSizePolicy, QTreeWidget, QTreeWidgetItem,
    QMenu, QAbstractItemView, QHeaderView, QDialog
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QAction


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
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Data File", 
            "", 
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
        self.script_path_edit.setPlaceholderText("Select a processing script to load")
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
        
    def browse_script(self):
        """Browse for a script to load"""
        script_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Processing Script", 
            "", 
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
            
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "File Error", "Script file does not exist.")
            return
            
        # Auto-generate script ID from filename
        script_id = Path(script_path).stem
        
        try:
            # Verify the script has the required function
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
            
            QMessageBox.information(self, "Success", f"Processing applied successfully. Results stored as '{script_id}'.")
            
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
    
    def __init__(self, parent=None):
        super().__init__("👁️ Data Visualization")
        self.parent = parent
        self.scripts_dict = {}
        
        self.setup_ui()
        self.setup_connections()
        
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
        self.script_path_edit.setPlaceholderText("Select a visualization script to load")
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
        
    def browse_script(self):
        """Browse for a script to load"""
        script_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Visualization Script", 
            "", 
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
            
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "File Error", "Script file does not exist.")
            return
            
        # Auto-generate script ID from filename
        script_id = Path(script_path).stem
        
        try:
            # Verify the script has the required function
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
            
            # Keep script path for multiple executions
            
            QMessageBox.information(self, "Success", f"Visualization executed successfully. Results stored as '{script_id}'.")
            
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


class DataAnalysisWidget(QWidget):
    """Main data analysis interface widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Placeholder for data analysis content in main area
        placeholder = QLabel("Data Analysis Content\n(Coming Soon)")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("""
            QLabel {
                color: #6c757d; 
                font-style: italic; 
                font-size: 18px;
                padding: 40px;
                background-color: #f8f9fa;
                border: 2px dashed #dee2e6;
                border-radius: 8px;
            }
        """)
        layout.addWidget(placeholder)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
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
