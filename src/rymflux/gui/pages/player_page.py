# src/rymflux/gui/pages/player_page.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget
from PyQt6.QtCore import pyqtSignal

from rymflux.core.models import Audiobook
from ..player import ModernPlayer # Note the relative import

class PlayerPage(QWidget):
    """ The page for displaying audiobook details and chapters. """
    chapter_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        main_layout = QVBoxLayout(self)
        
        self.player_widget = ModernPlayer(self)
        self.chapter_list = QListWidget(self)
        
        main_layout.addWidget(self.player_widget)
        main_layout.addWidget(self.chapter_list)
        
        self.chapter_list.itemDoubleClicked.connect(lambda item: self.chapter_selected.emit(self.chapter_list.row(item)))

    def load_audiobook_details(self, audiobook: Audiobook):
        self.chapter_list.clear()
        if not audiobook or not audiobook.chapters:
            from rymflux.core.models import Audiobook
            self.player_widget.set_track_info(Audiobook(title="", source_name="", url="", chapters=[]), "Could not load details")
            return
        # We don't play anything yet, just set the initial info
        self.player_widget.set_track_info(audiobook, "Select a chapter to play")
        for chapter in audiobook.chapters:
            self.chapter_list.addItem(chapter.title)