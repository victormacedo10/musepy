"""
Utility functions for MusePy application
"""

from PySide6.QtWidgets import QMessageBox, QInputDialog


def show_dialog(title, message, icon=QMessageBox.Information):
    """Show a simple message dialog"""
    msg_box = QMessageBox()
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setIcon(icon)
    msg_box.exec()


def question_dialog(title, message):
    """Show a yes/no question dialog"""
    msg_box = QMessageBox()
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.Yes)
    
    result = msg_box.exec()
    return result == QMessageBox.Yes


def input_dialog(title, message, default_text=""):
    """Show an input dialog"""
    text, ok = QInputDialog.getText(None, title, message, text=default_text)
    return text if ok else None
