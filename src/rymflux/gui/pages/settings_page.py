# src/rymflux/gui/pages/settings_page.py

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        layout = QVBoxLayout(self)
        label = QLabel("Settings will go here.\n(e.g., Theme selection, Source Management)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)