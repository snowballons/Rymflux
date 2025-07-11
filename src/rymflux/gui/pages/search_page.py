# src/rymflux/gui/pages/search_page.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget
from PyQt6.QtCore import pyqtSignal
from qfluentwidgets import LineEdit, PrimaryPushButton, NavigationWidget

from rymflux.core.models import AudioItem

class SearchPage(NavigationWidget):
    """ The page for searching and displaying results. """
    search_requested = pyqtSignal(str)
    result_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent, isSelectable=False)
        
        main_layout = QVBoxLayout(self)
        
        # Search area
        search_layout = QHBoxLayout()
        self.search_input = LineEdit(self)
        self.search_input.setPlaceholderText("Search for an audiobook...")
        self.search_button = PrimaryPushButton("Search")
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        main_layout.addLayout(search_layout)

        # Results list
        self.results_list = QListWidget(self)
        main_layout.addWidget(self.results_list)

        # Connect signals
        self.search_button.clicked.connect(self._on_search)
        self.search_input.returnPressed.connect(self._on_search)
        self.results_list.itemClicked.connect(lambda item: self.result_selected.emit(self.results_list.row(item)))
    
    def _on_search(self):
        query = self.search_input.text().strip()
        if query:
            self.search_requested.emit(query)
            
    def display_results(self, results: list[AudioItem]):
        self.results_list.clear()
        if not results:
            self.results_list.addItem("No results found.")
            return
            
        for item in results:
            self.results_list.addItem(f"{item.title} ({item.source_name})")