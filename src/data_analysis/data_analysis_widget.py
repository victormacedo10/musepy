"""
Data Analysis Widget - Main interface for data analysis
"""

import os
import pickle
import pandas as pd
import numpy as np
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLineEdit, 
    QLabel, QComboBox, QSpinBox, QTextEdit, QFileDialog, 
    QMessageBox, QSizePolicy, QTreeWidget, QTreeWidgetItem,
    QMenu, QAbstractItemView, QDialog, QSplitter, QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction


class ResponsiveCanvas(FigureCanvas):
    def __init__(self, fig, parent=None):
        super().__init__(fig)
        self.parent_widget = parent
        
    def resizeEvent(self, event):
        fig = self.figure
        dpi = fig.get_dpi()                     # logical DPI
        w_in = max(4.0, self.width()  / dpi)    # keep sane min
        h_in = max(3.0, self.height() / dpi)
        if (abs(fig.get_figwidth()  - w_in) > 1e-2 or
            abs(fig.get_figheight() - h_in) > 1e-2):
            fig.set_size_inches(w_in, h_in, forward=True)
        super().resizeEvent(event)
        
        # Trigger comprehensive plot resize if parent widget supports it
        if self.parent_widget and hasattr(self.parent_widget, 'resize_plot_to_fit_area'):
            # Find the widget that contains this canvas
            for child in self.parent_widget.findChildren(QWidget):
                if hasattr(child, 'canvas') and child.canvas == self:
                    self.parent_widget.resize_plot_to_fit_area(child)
                    break



class SafeNavigationToolbar(NavigationToolbar):
    def set_message(self, s):
        try:
            super().set_message(s)
        except RuntimeError:
            # Suppress the error if the underlying C++ object has been deleted
            pass


class ResponsiveContentArea(QWidget):
    """Content area widget that can handle resize events for responsive plotting"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.data_analysis_widget = None
        
    def set_data_analysis_widget(self, data_analysis_widget):
        """Set reference to the DataAnalysisWidget for proper resize handling"""
        self.data_analysis_widget = data_analysis_widget
        
    def resizeEvent(self, event):
        """Handle resize events to adjust plot sizes"""
        super().resizeEvent(event)
        # Call the DataAnalysisWidget's resize method if available
        if self.data_analysis_widget and hasattr(self.data_analysis_widget, 'resize_plot_to_fit_area'):
            # Find the widget that contains this content area
            for child in self.data_analysis_widget.findChildren(QWidget):
                if hasattr(child, 'content_area') and child.content_area == self:
                    self.data_analysis_widget.resize_plot_to_fit_area(child)
                    break


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
    view_output_executed = Signal(str)  # script_id
    
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
            
            # Emit signal to update main area
            self.view_output_executed.emit(script_id)
            
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


class DataAnalysisWidget(QWidget):
    """Main data analysis interface widget with 2x2 grid layout"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.visualization_data = {}
        
        self.setup_ui()
        
    def resizeEvent(self, event):
        """Handle widget resize events to update all plots"""
        super().resizeEvent(event)
        # Use a timer to delay the resize to avoid conflicts during layout
        QTimer.singleShot(50, self.resize_all_plots)
        
    def setup_ui(self):
        """Setup the user interface with 2x2 grid layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create main horizontal splitter
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.setChildrenCollapsible(True)
        
        # Create upper and lower widgets
        upper_widget = QWidget()
        lower_widget = QWidget()
        
        # Setup upper and lower layouts with vertical splitters
        self.setup_split_layout(upper_widget, "upper")
        self.setup_split_layout(lower_widget, "lower")
        
        # Add to main splitter
        main_splitter.addWidget(upper_widget)
        main_splitter.addWidget(lower_widget)
        
        # Set equal sizes
        main_splitter.setSizes([main_splitter.height() // 2, main_splitter.height() // 2])
        
        layout.addWidget(main_splitter)
        
    def setup_split_layout(self, parent_widget, region):
        """Setup a split layout for upper or lower region"""
        layout = QHBoxLayout(parent_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create vertical splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(True)
        
        # Create left and right content areas
        left_area = self.create_content_area(f"{region}_left")
        right_area = self.create_content_area(f"{region}_right")
        
        # Add to splitter
        splitter.addWidget(left_area)
        splitter.addWidget(right_area)
        
        # Set equal sizes
        splitter.setSizes([splitter.width() // 2, splitter.width() // 2])
        
        layout.addWidget(splitter)
        
    def create_content_area(self, area_id):
        """Create a content area with dropdowns and display area"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create dropdown layout
        dropdown_layout = QHBoxLayout()
        dropdown_layout.setSpacing(5)
        
        # First dropdown (Plot/Table) - fixed width with 30/70 proportion
        type_combo = QComboBox()
        type_combo.addItems(["Plot", "Table"])
        type_combo.setFixedWidth(60)  # Smaller width to maintain 30/70 proportion
        type_combo.setStyleSheet("""
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
                width: 0px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ced4da;
                selection-background-color: #e3f2fd;
                selection-color: #495057;
            }
        """)
        
        # Second dropdown (dynamic options) - stretching
        options_combo = QComboBox()
        options_combo.addItem("None")
        options_combo.setStyleSheet("""
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
                width: 0px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ced4da;
                selection-background-color: #e3f2fd;
                selection-color: #495057;
            }
        """)
        
        # Add dropdowns to layout
        dropdown_layout.addWidget(type_combo)
        dropdown_layout.addWidget(options_combo)
        
        # Create content display area
        content_area = ResponsiveContentArea(widget)
        content_area.set_data_analysis_widget(self)  # Set reference to DataAnalysisWidget
        content_area.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }
        """)
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create canvas container for plots
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(canvas_container)
        
        # Create bottom widget for toolbar and controls (fixed height)
        bottom_widget = QWidget()
        bottom_widget.setFixedHeight(50)
        bottom_widget.setStyleSheet("border: none;")
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(bottom_widget)
        
        # Create DPI and save controls
        dpi_label = QLabel("DPI:")
        dpi_label.setStyleSheet("color: #495057; font-size: 11px; border: none;")
        dpi_input = QSpinBox()
        dpi_input.setRange(50, 600)
        dpi_input.setValue(300)  # Default to 300 DPI for high quality
        dpi_input.setFixedWidth(60)
        dpi_input.setStyleSheet("""
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
        save_button = QPushButton("Save Figure")
        save_button.setStyleSheet("""
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
        
        # Add controls to bottom layout
        bottom_layout.addStretch()
        bottom_layout.addWidget(dpi_label)
        bottom_layout.addWidget(dpi_input)
        bottom_layout.addWidget(save_button)
        
        # Placeholder text
        placeholder = QLabel("Select Plot or Table to display content")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-style: italic;
                font-size: 12px;
            }
        """)
        canvas_layout.addWidget(placeholder)
        
        # Add layouts to main layout
        layout.addLayout(dropdown_layout)
        layout.addWidget(content_area)
        
        # Store references
        widget.type_combo = type_combo
        widget.options_combo = options_combo
        widget.content_area = content_area
        widget.canvas_container = canvas_container
        widget.canvas_layout = canvas_layout
        widget.bottom_widget = bottom_widget
        widget.bottom_layout = bottom_layout
        widget.dpi_input = dpi_input
        widget.save_button = save_button
        widget.area_id = area_id
        
        # Connect signals
        type_combo.currentTextChanged.connect(lambda text: self.on_type_changed(widget, text))
        options_combo.currentTextChanged.connect(lambda text: self.on_option_changed(widget, text))
        
        return widget
        
    def on_type_changed(self, widget, content_type):
        """Handle content type change (Plot/Table)"""
        # Block signals temporarily to prevent unwanted triggers
        widget.options_combo.blockSignals(True)
        
        # Reset options dropdown
        widget.options_combo.clear()
        widget.options_combo.addItem("None")
        
        # Update options based on visualization data
        if hasattr(self.parent, 'visualization_results') and self.parent.visualization_results:
            if content_type == "Plot" and "plots" in self.parent.visualization_results:
                for plot_name in self.parent.visualization_results["plots"].keys():
                    widget.options_combo.addItem(plot_name)
            elif content_type == "Table" and "tables" in self.parent.visualization_results:
                for table_name in self.parent.visualization_results["tables"].keys():
                    widget.options_combo.addItem(table_name)
        
        # Set selection back to "None"
        widget.options_combo.setCurrentText("None")
        
        # Unblock signals
        widget.options_combo.blockSignals(False)
        
        # Update placeholder
        self.update_placeholder(widget, content_type)
        
    def on_option_changed(self, widget, option_name):
        """Handle option selection change"""
        # Handle empty or None option names
        if not option_name or option_name == "None":
            self.update_placeholder(widget, widget.type_combo.currentText())
            return
            
        content_type = widget.type_combo.currentText()
        
        if content_type == "Plot":
            self.display_plot(widget, option_name)
        elif content_type == "Table":
            self.display_table(widget, option_name)
            
    def clear_content_area(self, content_area):
        """Clear all content from a content area"""
        # Clear existing content
        for i in reversed(range(content_area.layout().count())):
            item = content_area.layout().itemAt(i)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                # Clear nested layout
                for j in reversed(range(item.layout().count())):
                    nested_item = item.layout().itemAt(j)
                    if nested_item.widget():
                        nested_item.widget().setParent(None)
                # Remove the layout itself
                content_area.layout().removeItem(item)
        
    def update_placeholder(self, widget, content_type):
        """Update placeholder text in content area"""
        # Clear existing content from canvas layout
        for i in reversed(range(widget.canvas_layout.count())):
            item = widget.canvas_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
        
        # Remove old toolbar if it exists (from previous plot)
        if hasattr(widget, 'plot_toolbar') and widget.plot_toolbar is not None:
            widget.bottom_layout.removeWidget(widget.plot_toolbar)
            widget.plot_toolbar.setParent(None)
            # Use a short delay to let pending events finish before deletion.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, widget.plot_toolbar.deleteLater)
            widget.plot_toolbar = None
        
        # Show/hide save button and DPI controls based on content type
        if content_type == "Plot":
            # Show save button and DPI controls for plots
            widget.save_button.setVisible(True)
            widget.dpi_input.setVisible(True)
            # Find and show the DPI label
            for i in range(widget.bottom_layout.count()):
                item = widget.bottom_layout.itemAt(i)
                if item.widget() and hasattr(item.widget(), 'text') and item.widget().text() == "DPI:":
                    item.widget().setVisible(True)
                    break
        else:
            # Hide save button and DPI controls for tables
            widget.save_button.setVisible(False)
            widget.dpi_input.setVisible(False)
            # Find and hide the DPI label
            for i in range(widget.bottom_layout.count()):
                item = widget.bottom_layout.itemAt(i)
                if item.widget() and hasattr(item.widget(), 'text') and item.widget().text() == "DPI:":
                    item.widget().setVisible(False)
                    break
        
        # Add new placeholder
        placeholder = QLabel(f"Select a {content_type} to display content")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-style: italic;
                font-size: 12px;
            }
        """)
        widget.canvas_layout.addWidget(placeholder)
        

    def display_plot(self, widget, plot_name):
        try:
            fig = self.parent.visualization_results["plots"][plot_name]

            # Clear any previous font size storage to ensure fresh scaling
            if hasattr(fig, '_original_font_sizes'):
                delattr(fig, '_original_font_sizes')

            # prefer constrained layout; fallback if older MPL
            try:
                fig.set_layout_engine('constrained')
            except Exception:
                fig.set_constrained_layout(True)

            # clear previous canvas/widgets
            for i in reversed(range(widget.canvas_layout.count())):
                item = widget.canvas_layout.itemAt(i)
                if w := item.widget():
                    w.setParent(None)

            if hasattr(widget, 'canvas') and widget.canvas is not None:
                widget.canvas.setParent(None)
                widget.canvas.deleteLater()

            # create canvas *then* size by resizeEvent
            widget.canvas = ResponsiveCanvas(fig, self)  # Pass DataAnalysisWidget as parent
            widget.canvas.setContentsMargins(0, 0, 0, 0)
            widget.canvas_layout.setContentsMargins(0, 0, 0, 0)
            widget.canvas_layout.setSpacing(0)
            widget.canvas_layout.addWidget(widget.canvas)

            if getattr(widget, 'plot_toolbar', None):
                widget.bottom_layout.removeWidget(widget.plot_toolbar)
                widget.plot_toolbar.setParent(None)
                widget.plot_toolbar.deleteLater()

            widget.plot_toolbar = SafeNavigationToolbar(widget.canvas, widget)
            widget.bottom_layout.insertWidget(0, widget.plot_toolbar)

            widget.save_button.setVisible(True)
            widget.dpi_input.setVisible(True)

            try:
                widget.save_button.clicked.disconnect()
            except Exception:
                pass
            widget.save_button.clicked.connect(lambda: self.save_figure(fig, widget.dpi_input.value()))

            # Ensure proper initial sizing and layout
            widget.canvas.draw_idle()
            
            # Force immediate resize to fit the current container size
            self.resize_plot_to_fit_area(widget)
            
            # Additional delayed resize to handle any layout changes
            QTimer.singleShot(10, lambda: self.resize_plot_to_fit_area(widget))
            QTimer.singleShot(100, lambda: self.resize_plot_to_fit_area(widget))

        except Exception as e:
            err = QLabel(f"Error displaying plot: {e}")
            err.setAlignment(Qt.AlignCenter)
            err.setStyleSheet("color:#dc3545;")
            widget.canvas_layout.addWidget(err)
            
    def display_table(self, widget, table_name):
        """Display a table with scrollable content"""
        try:
            # Get table data
            table_data = self.parent.visualization_results["tables"][table_name]
            
            # Clear existing content from canvas layout
            for i in reversed(range(widget.canvas_layout.count())):
                item = widget.canvas_layout.itemAt(i)
                if item.widget():
                    item.widget().setParent(None)
            
            # Remove old toolbar if it exists (from previous plot)
            if hasattr(widget, 'plot_toolbar') and widget.plot_toolbar is not None:
                widget.bottom_layout.removeWidget(widget.plot_toolbar)
                widget.plot_toolbar.setParent(None)
                # Use a short delay to let pending events finish before deletion.
                QTimer.singleShot(0, widget.plot_toolbar.deleteLater)
                widget.plot_toolbar = None
            
            # Hide save button and DPI controls for tables
            widget.save_button.setVisible(False)
            widget.dpi_input.setVisible(False)
            # Find and hide the DPI label
            for i in range(widget.bottom_layout.count()):
                item = widget.bottom_layout.itemAt(i)
                if item.widget() and hasattr(item.widget(), 'text') and item.widget().text() == "DPI:":
                    item.widget().setVisible(False)
                    break
            
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
            
            # Populate table
            if isinstance(table_data, pd.DataFrame):
                # Set dimensions
                table_widget.setRowCount(len(table_data))
                table_widget.setColumnCount(len(table_data.columns))
                
                # Set headers
                table_widget.setHorizontalHeaderLabels(table_data.columns)
                
                # Populate data
                for i in range(len(table_data)):
                    for j in range(len(table_data.columns)):
                        item = QTableWidgetItem(str(table_data.iloc[i, j]))
                        table_widget.setItem(i, j, item)
                        
            elif isinstance(table_data, (list, tuple)):
                # Handle list/tuple data
                if table_data and isinstance(table_data[0], (list, tuple)):
                    # 2D data
                    table_widget.setRowCount(len(table_data))
                    table_widget.setColumnCount(len(table_data[0]))
                    
                    for i, row in enumerate(table_data):
                        for j, value in enumerate(row):
                            item = QTableWidgetItem(str(value))
                            table_widget.setItem(i, j, item)
                else:
                    # 1D data
                    table_widget.setRowCount(len(table_data))
                    table_widget.setColumnCount(1)
                    
                    for i, value in enumerate(table_data):
                        item = QTableWidgetItem(str(value))
                        table_widget.setItem(i, 0, item)
            
            # Enable alternating row colors
            table_widget.setAlternatingRowColors(True)
            
            # Enable scrolling
            table_widget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
            table_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            
            # Auto-resize columns
            table_widget.resizeColumnsToContents()
            
            # Add to layout
            widget.canvas_layout.addWidget(table_widget)
            
        except Exception as e:
            # Show error message
            error_label = QLabel(f"Error displaying table: {str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #dc3545; font-size: 11px;")
            widget.content_area.layout().addWidget(error_label)
            
    def save_figure(self, fig, dpi):
        """Save the current figure"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Save Figure", 
                "", 
                "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*.*)"
            )
            if file_path:
                fig.savefig(file_path, dpi=dpi, bbox_inches='tight')
                QMessageBox.information(self, "Success", f"Figure saved successfully to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save figure: {str(e)}")
            
    def update_visualization_data(self, visualization_results):
        """Update visualization data and refresh all content areas"""
        self.visualization_data = visualization_results
        
        # Find all content areas and update their options
        for child in self.findChildren(QWidget):
            if hasattr(child, 'area_id') and hasattr(child, 'type_combo'):
                current_type = child.type_combo.currentText()
                self.on_type_changed(child, current_type)
                
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
    
    def _get_screen_dpi_factor(self):
        """Get DPI scaling factor for the current screen"""
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    # Get logical DPI and physical DPI
                    logical_dpi = screen.logicalDotsPerInch()
                    physical_dpi = screen.physicalDotsPerInch()
                    # Calculate scaling factor (typically 1.0, 1.25, 1.5, 2.0 for Windows)
                    dpi_factor = logical_dpi / 96.0  # 96 is standard Windows DPI
                    return max(0.75, min(2.0, dpi_factor))  # Clamp between 0.75 and 2.0
        except Exception:
            pass
        return 1.0  # Default fallback
    
    def _get_screen_size_category(self):
        """Determine screen size category for appropriate scaling"""
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    geometry = screen.availableGeometry()
                    width = geometry.width()
                    height = geometry.height()
                    
                    # Calculate diagonal size in inches (rough estimate)
                    dpi = screen.logicalDotsPerInch()
                    diag_pixels = (width**2 + height**2)**0.5
                    diag_inches = diag_pixels / dpi
                    
                    if diag_inches < 15:
                        return "small"  # Small laptops/tablets
                    elif diag_inches < 20:
                        return "medium"  # Standard laptops
                    else:
                        return "large"  # Desktop monitors
        except Exception:
            pass
        return "medium"  # Default fallback
    
    def _store_original_font_sizes(self, fig):
        """Store original font sizes to prevent cumulative scaling"""
        if not hasattr(fig, '_original_font_sizes'):
            fig._original_font_sizes = {}
            
        for i, ax in enumerate(fig.get_axes()):
            ax_key = f"ax_{i}"
            if ax_key not in fig._original_font_sizes:
                fig._original_font_sizes[ax_key] = {}
                
                # Store original font sizes
                if ax.title and ax.title.get_text():
                    fig._original_font_sizes[ax_key]['title'] = ax.title.get_fontsize()
                if ax.xaxis.label:
                    fig._original_font_sizes[ax_key]['xlabel'] = ax.xaxis.label.get_fontsize()
                if ax.yaxis.label:
                    fig._original_font_sizes[ax_key]['ylabel'] = ax.yaxis.label.get_fontsize()
                    
                # Store tick label sizes
                x_lbls = ax.xaxis.get_ticklabels()
                y_lbls = ax.yaxis.get_ticklabels()
                if x_lbls:
                    fig._original_font_sizes[ax_key]['xtick'] = x_lbls[0].get_size()
                if y_lbls:
                    fig._original_font_sizes[ax_key]['ytick'] = y_lbls[0].get_size()
                    
                # Store legend font sizes
                leg = ax.get_legend()
                if leg is not None:
                    fig._original_font_sizes[ax_key]['legend'] = []
                    for txt in leg.get_texts():
                        fig._original_font_sizes[ax_key]['legend'].append(txt.get_fontsize())
                    if leg.get_title() is not None:
                        fig._original_font_sizes[ax_key]['legend_title'] = leg.get_title().get_fontsize()

    def _scale_figure_style(self, fig, target_px, base_px=None, min_scale=0.8, max_scale=1.4, alpha=0.7):
        """Improved scaling that prevents cumulative scaling and adapts to screen size"""
        # Store original font sizes on first call
        self._store_original_font_sizes(fig)
        
        # Get screen DPI factor and size category
        dpi_factor = self._get_screen_dpi_factor()
        screen_category = self._get_screen_size_category()
        
        # Adjust base_px based on screen size and DPI
        if base_px is None:
            # Base pixel size should be adjusted for screen size
            if screen_category == "small":
                base_px = 500  # Small screens (15" laptops, etc.)
            elif screen_category == "medium":
                base_px = 700  # Medium screens (standard laptops)
            else:
                base_px = 1000  # Large screens (desktop monitors)
                
        # Apply DPI factor to base_px
        base_px = base_px / dpi_factor
        
        # Adjust scaling parameters based on screen size
        if screen_category == "small":
            # More conservative scaling for small screens
            alpha = 0.6
            min_scale = 0.8
            max_scale = 1.3
        elif screen_category == "medium":
            # Balanced scaling for medium screens
            alpha = 0.7
            min_scale = 0.8
            max_scale = 1.4
        else:
            # More aggressive scaling for large screens
            alpha = 0.8
            min_scale = 0.7
            max_scale = 1.5
        
        # Calculate scaling factor
        raw = (max(1.0, float(target_px)) / float(base_px)) ** alpha
        s = max(min_scale, min(max_scale, raw))

        for i, ax in enumerate(fig.get_axes()):
            ax_key = f"ax_{i}"
            original_sizes = fig._original_font_sizes.get(ax_key, {})
            
            # Apply scaling to titles and labels
            if 'title' in original_sizes:
                ax.title.set_fontsize(original_sizes['title'] * s)
            if 'xlabel' in original_sizes:
                ax.xaxis.label.set_fontsize(original_sizes['xlabel'] * s)
            if 'ylabel' in original_sizes:
                ax.yaxis.label.set_fontsize(original_sizes['ylabel'] * s)

            # Apply scaling to tick labels with minimum size protection
            if 'xtick' in original_sizes:
                # Adjust minimum size based on screen category
                min_tick_size = 6 if screen_category == "small" else 8
                new_size = max(min_tick_size, original_sizes['xtick'] * s)
                ax.tick_params(axis='x', which='major', labelsize=new_size)
                ax.tick_params(axis='x', which='minor', labelsize=max(4, new_size * 0.85))
            if 'ytick' in original_sizes:
                # Adjust minimum size based on screen category
                min_tick_size = 6 if screen_category == "small" else 8
                new_size = max(min_tick_size, original_sizes['ytick'] * s)
                ax.tick_params(axis='y', which='major', labelsize=new_size)
                ax.tick_params(axis='y', which='minor', labelsize=max(4, new_size * 0.85))

            # Scale line properties
            for line in ax.lines:
                lw = line.get_linewidth()
                if lw is not None:
                    line.set_linewidth(max(0.7, lw * s))
                ms = line.get_markersize()
                if ms is not None:
                    line.set_markersize(max(2.8, ms * s))

            # Scale legend with minimum size protection
            leg = ax.get_legend()
            if leg is not None and 'legend' in original_sizes:
                legend_sizes = original_sizes['legend']
                # Adjust minimum legend size based on screen category
                min_legend_size = 7 if screen_category == "small" else 9
                for j, txt in enumerate(leg.get_texts()):
                    if j < len(legend_sizes):
                        new_size = max(min_legend_size, legend_sizes[j] * s)
                        txt.set_fontsize(new_size)
                if 'legend_title' in original_sizes:
                    min_title_size = 8 if screen_category == "small" else 10
                    title_size = max(min_title_size, original_sizes['legend_title'] * s)
                    leg.get_title().set_fontsize(title_size)

    def resize_plot_to_fit_area(self, widget):
        """Resize plot to fit the available area with proper error handling"""
        if not getattr(widget, 'canvas', None):
            return
        try:
            fig = widget.canvas.figure
            W  = widget.canvas_container.width()
            H  = widget.canvas_container.height()
            if W <= 0 or H <= 0:
                return

            dpi = fig.get_dpi()                 # keep logical dpi as-is
            w_in = max(4.0, W / dpi)
            h_in = max(3.0, H / dpi)
            fig.set_size_inches(w_in, h_in, forward=True)

            # Improved style scaling with screen-aware parameters
            self._scale_figure_style(fig, W, base_px=None, min_scale=0.7, max_scale=1.5)
            widget.canvas.draw_idle()
        except Exception as e:
            # Silently handle resize errors to prevent crashes
            print(f"Resize error: {e}")
    
    def resize_all_plots(self):
        """Resize all plots in all content areas"""
        for child in self.findChildren(QWidget):
            if hasattr(child, 'area_id') and hasattr(child, 'canvas') and child.canvas is not None:
                self.resize_plot_to_fit_area(child)
    
    def debug_scaling_info(self):
        """Debug method to print scaling information"""
        dpi_factor = self._get_screen_dpi_factor()
        screen_category = self._get_screen_size_category()
        print(f"Screen DPI Factor: {dpi_factor}")
        print(f"Screen Category: {screen_category}")
        
        # Find a plot to analyze
        for child in self.findChildren(QWidget):
            if hasattr(child, 'canvas') and child.canvas is not None:
                W = child.canvas_container.width()
                H = child.canvas_container.height()
                print(f"Plot container size: {W}x{H}")
                
                if screen_category == "small":
                    base_px = 500
                elif screen_category == "medium":
                    base_px = 700
                else:
                    base_px = 1000
                    
                adjusted_base = base_px / dpi_factor
                raw = (max(1.0, float(W)) / float(adjusted_base)) ** 0.7
                scale = max(0.8, min(1.4, raw))
                print(f"Calculated scale factor: {scale}")
                break
