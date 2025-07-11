# src/rymflux/gui/main.py

import sys
from PyQt6.QtWidgets import (
    QApplication, 
    QMainWindow, 
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QLabel,
    QStatusBar,
    QTextEdit,
    QSplitter,
    QGroupBox
)
import asyncio
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont
import subprocess
import httpx

from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl
from .player import ModernPlayer

# Import our core components
from rymflux.core.config import load_sources_from_yaml
from rymflux.core.sources import CustomSource, AudioSource
from rymflux.core.models import AudioItem, Audiobook
from rymflux.core.sources import ArchiveSource

from .workers import SearchWorker, DetailsWorker

# Remove the SearchWorker and DetailsWorker class definitions (lines 21-61)


class MainWindow(QMainWindow):
    """
    The main window for the Rymflux GUI application.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rymflux")
        self.resize(1024, 768)

        # --- Core Components & State ---
        self.sources = []
        self.search_worker = None
        self.details_worker = None
        self.current_search_results: list[AudioItem] = []
        self.current_audiobook: Audiobook | None = None
        
        # --- Native Media Player Setup ---
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.5) # Start at 50% volume

        # --- GUI Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter()
        self.main_layout.addWidget(splitter)
        
        # Left Pane
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.addLayout(self._create_search_area())
        self.results_list = QListWidget()
        left_layout.addWidget(self.results_list)
        splitter.addWidget(left_pane)

        # Right Pane
        right_pane = self._create_details_area()
        splitter.addWidget(right_pane)
        splitter.setSizes([300, 700])

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # --- Initial State & Connections ---
        self._load_sources()
        self._connect_signals()
        self.status_bar.showMessage("Ready.")

    def _load_sources(self):
        """Loads sources from the configuration file."""
        source_configs = load_sources_from_yaml("sources.yaml")
        if not source_configs:
            # In a real app, show a popup error here
            print("GUI Error: 'sources.yaml' not found or is empty.")
            return
        self.sources = []
        for config in source_configs:
            source_type = config.get("type", "custom")
            if source_type == "archive":
                self.sources.append(ArchiveSource(name=config["name"], base_url=""))
            else:
                self.sources.append(
                    CustomSource(
                        name=config["name"],
                        base_url=config["base_url"],
                        rules=config["rules"]
                    )
                )

    def _create_search_area(self) -> QHBoxLayout:
        """Creates the horizontal layout for the search bar and button."""
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for an audiobook or podcast...")
        search_layout.addWidget(self.search_input)
        self.search_button = QPushButton("Search")
        search_layout.addWidget(self.search_button)
        return search_layout

    def _create_details_area(self) -> QWidget:
        """Creates the widget for the right-hand details pane."""
        # This is much cleaner now
        details_group = QGroupBox("Player")
        layout = QVBoxLayout(details_group)
        
        self.player_controls = ModernPlayer()
        self.detail_chapters_list = QListWidget()
        
        layout.addWidget(self.player_controls)
        layout.addWidget(self.detail_chapters_list)
        
        return details_group
        
    def on_result_selected(self):
        """Slot to handle when a search result is clicked."""
        selected_index = self.results_list.currentRow()
        if selected_index < 0 or selected_index >= len(self.current_search_results):
            return

        selected_item = self.current_search_results[selected_index]
        self.status_bar.showMessage(f"Fetching details for '{selected_item.title}'...")
        
        # Use our new DetailsWorker
        self.details_worker = DetailsWorker(source=self.sources[0], item=selected_item)
        self.details_worker.finished.connect(self.on_details_finished)
        self.details_worker.start()
        
    def on_details_finished(self, audiobook: Audiobook | None):
        """Slot to update the UI with the fetched details."""
        self.current_audiobook = audiobook
        self.detail_chapters_list.clear()

        if not audiobook:
            self.status_bar.showMessage("Failed to fetch details.")
            return

        if audiobook.chapters:
            for chapter in audiobook.chapters:
                self.detail_chapters_list.addItem(chapter.title)

        self.status_bar.showMessage(f"Loaded '{audiobook.title}'. Double-click a chapter to play.")

    def on_chapter_double_clicked(self):
        """Plays the currently selected chapter."""
        current_row = self.detail_chapters_list.currentRow()
        self._play_chapter_at_index(current_row)

    def play_next_chapter(self):
        """Plays the next chapter in the list."""
        if self.detail_chapters_list.count() == 0: return
        current_row = self.detail_chapters_list.currentRow()
        next_row = (current_row + 1) % self.detail_chapters_list.count()
        self._play_chapter_at_index(next_row)

    def play_previous_chapter(self):
        """Plays the previous chapter in the list."""
        if self.detail_chapters_list.count() == 0: return
        current_row = self.detail_chapters_list.currentRow()
        prev_row = (current_row - 1) if current_row > 0 else self.detail_chapters_list.count() - 1
        self._play_chapter_at_index(prev_row)

    def _play_chapter_at_index(self, index: int):
        """A helper method to play a chapter at a given index."""
        if not self.current_audiobook or not self.current_audiobook.chapters:
            return
        if not (0 <= index < len(self.current_audiobook.chapters)):
            return

        self.detail_chapters_list.setCurrentRow(index)
        selected_chapter = self.current_audiobook.chapters[index]
        
        self.status_bar.showMessage(f"Loading '{selected_chapter.title}'...")
        self.player_controls.set_track_info(self.current_audiobook, selected_chapter.title)
        
        self.player.setSource(QUrl(selected_chapter.url))
        self.player.play()

    def start_search(self):
        """Slot to handle the search button click."""
        query = self.search_input.text().strip()
        if not query:
            self.status_bar.showMessage("Please enter a search term.")
            return

        if not self.sources:
            self.status_bar.showMessage("Error: No sources loaded.")
            return

        self.search_button.setEnabled(False)
        self.status_bar.showMessage(f"Searching {len(self.sources)} sources for '{query}'...")
        self.results_list.clear()

        # Pass the ENTIRE list of sources to the worker
        self.search_worker = SearchWorker(sources=self.sources, query=query)
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.start()

    def on_search_finished(self, results: list[AudioItem]):
        """Slot to handle the results from the SearchWorker."""
        self.search_button.setEnabled(True)
        self.current_search_results = results

        if not results:
            self.status_bar.showMessage(f"No results found.")
            return

        self.results_list.clear()
        for item in results:
            # Add the source name for clarity
            self.results_list.addItem(f"{item.title} ({item.source_name})")
            
        self.status_bar.showMessage(f"Found {len(results)} results from all sources.")

    def _connect_signals(self):
        """A dedicated method to connect all signals to slots."""
        # Search controls
        self.search_button.clicked.connect(self.start_search)
        self.results_list.itemClicked.connect(self.on_result_selected)
        
        # Chapter list
        self.detail_chapters_list.itemDoubleClicked.connect(self.on_chapter_double_clicked)
        
        # Player Controls -> QMediaPlayer
        self.player_controls.play.connect(self.player.play)
        self.player_controls.pause.connect(self.player.pause)
        self.player_controls.stop.connect(self.player.stop)
        self.player_controls.seek.connect(self.player.setPosition)
        # New signal connections
        self.player_controls.volume_changed.connect(lambda vol: self.audio_output.setVolume(vol / 100.0))
        self.player_controls.next_track.connect(self.play_next_chapter)
        self.player_controls.prev_track.connect(self.play_previous_chapter)

        # QMediaPlayer -> Player Controls
        self.player.positionChanged.connect(self._on_player_position_or_duration_changed)
        self.player.durationChanged.connect(self._on_player_position_or_duration_changed)
        self.player.playbackStateChanged.connect(self.player_controls.set_playing_state)

    def _on_player_position_or_duration_changed(self, _):
        position = self.player.position()
        duration = self.player.duration()
        self.player_controls.update_progress(position, duration)

def main():
    """The main function to launch the GUI."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()