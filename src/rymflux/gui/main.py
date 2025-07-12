# src/rymflux/gui/main.py

import sys
from typing import Optional

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, setTheme, Theme, InfoBar, 
    InfoBarPosition, FluentIcon
)

# --- Local Module Imports ---
from .pages.search_page import SearchPage
from .pages.player_page import PlayerPage
from .pages.settings_page import SettingsPage
from .workers import SearchWorker, DetailsWorker
from rymflux.core.config import load_sources_from_yaml
from rymflux.core.sources import CustomSource, ArchiveSource, AudioSource
from rymflux.core.models import AudioItem, Audiobook

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rymflux")
        self.resize(1100, 800)

        # --- Core Components & State ---
        self.sources: list[AudioSource] = []
        self.search_worker: Optional[SearchWorker] = None
        self.details_worker: Optional[DetailsWorker] = None
        self.current_search_results: list[AudioItem] = []
        self.current_audiobook: Optional[Audiobook] = None
        
        # --- Media Player Setup ---
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.5)

        # --- Create Pages (as simple QWidgets) ---
        self.search_page = SearchPage(self)
        self.search_page.setObjectName("search_page")
        self.player_page = PlayerPage(self)
        self.player_page.setObjectName("player_page")
        self.settings_page = SettingsPage(self)
        self.settings_page.setObjectName("settings_page")

        # --- Initialize UI and Navigation ---
        self._init_navigation()
        self._load_sources()
        self._connect_signals()
        
    def _init_navigation(self):
        # Use addSubInterface for proper integration with FluentWindow
        self.addSubInterface(self.search_page, FluentIcon.SEARCH, 'Search')
        self.addSubInterface(self.player_page, FluentIcon.MUSIC, 'Player')
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, 'Settings', NavigationItemPosition.BOTTOM)
        
        # Set the default page
        self.navigationInterface.setCurrentItem(self.search_page.objectName())

    def _load_sources(self):
        # This method is unchanged and correct.
        try:
            source_configs = load_sources_from_yaml("sources.yaml")
            if not source_configs:
                self.show_info_bar("Warning", "sources.yaml not found or is empty.")
                return
            self.sources = [
                ArchiveSource(name=c["name"], base_url="") if c.get("type") == "archive"
                else CustomSource(name=c["name"], base_url=c["base_url"], rules=c["rules"])
                for c in source_configs
            ]
        except Exception as e:
            self.show_info_bar("Error", f"Failed to load sources: {e}", is_error=True)

    def _connect_signals(self):
        # This method is unchanged and correct.
        self.search_page.search_requested.connect(self.start_search)
        self.search_page.result_selected.connect(self.on_result_selected)
        self.player_page.chapter_selected.connect(self.on_chapter_selected)
        
        player_controls = self.player_page.player_widget
        player_controls.play.connect(self.player.play)
        player_controls.pause.connect(self.player.pause)
        player_controls.stop.connect(self.player.stop)
        player_controls.seek.connect(self.player.setPosition)
        player_controls.volume_changed.connect(lambda v: self.audio_output.setVolume(v / 100.0))
        player_controls.next_track.connect(self.play_next_chapter)
        player_controls.prev_track.connect(self.play_previous_chapter)
        
        self.player.positionChanged.connect(lambda p: player_controls.update_progress(p, self.player.duration()))
        self.player.durationChanged.connect(lambda d: player_controls.update_progress(self.player.position(), d))
        self.player.playbackStateChanged.connect(player_controls.set_playing_state)

    def show_info_bar(self, title: str, content: str, is_error: bool = False):
        """Displays a Fluent InfoBar for notifications."""
        pos = InfoBarPosition.TOP
        if is_error:
            InfoBar.error(title, content, duration=3000, parent=self).show()
        else:
            InfoBar.info(title, content, duration=2000, parent=self).show()

    # All worker and playback logic methods below are unchanged and correct.
    # start_search, on_search_finished, on_result_selected, on_details_finished, etc.
    # Make sure you have your working versions of these methods here.
    def start_search(self, query: str):
        if not self.sources:
            self.show_info_bar("Error", "No sources loaded.", is_error=True)
            return
        
        self.search_worker = SearchWorker(self.sources, query)
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.start()
        self.show_info_bar("Searching", f"Searching for '{query}'...")

    def on_search_finished(self, results: list[AudioItem]):
        self.current_search_results = results
        self.search_page.display_results(results)
        self.show_info_bar("Search Complete", f"Found {len(results)} results.")

    def on_result_selected(self, index: int):
        if not (0 <= index < len(self.current_search_results)):
            return
        
        selected_item = self.current_search_results[index]
        self.show_info_bar("Loading", f"Fetching details for '{selected_item.title[:30]}...'")
        
        source = next((s for s in self.sources if s.name == selected_item.source_name), None)
        if not source:
            self.show_info_bar("Error", f"Source '{selected_item.source_name}' not found.", is_error=True)
            return

        self.details_worker = DetailsWorker(source, selected_item)
        self.details_worker.finished.connect(self.on_details_finished)
        self.details_worker.start()

    def on_details_finished(self, audiobook: Optional[Audiobook]):
        self.current_audiobook = audiobook
        
        if audiobook is not None:
            # Pass the audiobook object to the player page to update its UI
            self.player_page.load_audiobook_details(audiobook)
            self.show_info_bar("Details Loaded", f"Ready to play '{audiobook.title[:30]}...'.")
            # Switch the main view to the player page automatically
            self.navigationInterface.setCurrentItem(self.player_page.objectName())
        else:
            self.show_info_bar("Error", "Failed to fetch details.", is_error=True)

    def on_chapter_selected(self, index: int):
        self._play_chapter_at_index(index)
    
    def play_next_chapter(self):
        if not self.current_audiobook or not self.current_audiobook.chapters: return
        current_row = self.player_page.chapter_list.currentRow()
        next_row = (current_row + 1) % len(self.current_audiobook.chapters)
        self._play_chapter_at_index(next_row)

    def play_previous_chapter(self):
        if not self.current_audiobook or not self.current_audiobook.chapters: return
        current_row = self.player_page.chapter_list.currentRow()
        prev_row = (current_row - 1) if current_row > 0 else len(self.current_audiobook.chapters) - 1
        self._play_chapter_at_index(prev_row)

    def _play_chapter_at_index(self, index: int):
        if not self.current_audiobook or not self.current_audiobook.chapters or not (0 <= index < len(self.current_audiobook.chapters)):
            return
        self.player_page.chapter_list.setCurrentRow(index)
        chapter = self.current_audiobook.chapters[index]
        self.player_page.player_widget.set_track_info(self.current_audiobook, chapter.title)
        self.player.setSource(QUrl(chapter.url))
        self.player.play()

def main():
    """The main function to launch the GUI."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    setTheme(Theme.DARK)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())