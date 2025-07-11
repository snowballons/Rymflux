# src/rymflux/gui/main.py

import sys
from typing import Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from qfluentwidgets import FluentWindow, NavigationItemPosition, setTheme, Theme, InfoBar, InfoBarPosition, FluentIcon

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

        # --- Create Pages ---
        self.search_page = SearchPage(self)
        self.player_page = PlayerPage(self)
        self.settings_page = SettingsPage(self)

        # --- Initialize UI and Navigation ---
        self._init_navigation()
        self._load_sources()
        self._connect_signals()
        
    def _init_navigation(self):
        # Add pages to the navigation interface
        self.navigationInterface.addWidget(
            routeKey='search',
            widget=self.search_page,  # Already NavigationWidget
            onClick=lambda: self.navigationInterface.setCurrentItem('search')
        )
        self.navigationInterface.addWidget(
            routeKey='player',
            widget=self.player_page,  # Already NavigationWidget
            onClick=lambda: self.navigationInterface.setCurrentItem('player')
        )
        # Add navigation items (the icons on the left)
        self.navigationInterface.addItem(
            routeKey='search',
            icon=FluentIcon.SEARCH,
            text='Search'
        )
        self.navigationInterface.addItem(
            routeKey='player',
            icon=FluentIcon.MUSIC,
            text='Player'
        )
        # Add settings icon at the bottom
        self.navigationInterface.addItem(
            routeKey='settings',
            icon=FluentIcon.SETTING,
            text='Settings',
            onClick=lambda: self.navigationInterface.setCurrentItem('settings'),
            position=NavigationItemPosition.BOTTOM
        )
        self.navigationInterface.addWidget(
            routeKey='settings',
            widget=self.settings_page,  # Already NavigationWidget
            onClick=lambda: self.navigationInterface.setCurrentItem('settings')
        )

    def _load_sources(self):
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
        # Page signals -> Main Window logic
        self.search_page.search_requested.connect(self.start_search)
        self.search_page.result_selected.connect(self.on_result_selected)
        self.player_page.chapter_selected.connect(self.on_chapter_selected)
        
        # Player widget signals -> QMediaPlayer
        player_controls = self.player_page.player_widget
        player_controls.play.connect(self.player.play)
        player_controls.pause.connect(self.player.pause)
        player_controls.stop.connect(self.player.stop)
        player_controls.seek.connect(self.player.setPosition)
        player_controls.volume_changed.connect(lambda v: self.audio_output.setVolume(v / 100.0))
        player_controls.next_track.connect(self.play_next_chapter)
        player_controls.prev_track.connect(self.play_previous_chapter)
        
        # QMediaPlayer signals -> Player widget UI
        self.player.positionChanged.connect(lambda p: player_controls.update_progress(p, self.player.duration()))
        self.player.durationChanged.connect(lambda d: player_controls.update_progress(self.player.position(), d))
        self.player.playbackStateChanged.connect(player_controls.set_playing_state)

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
            self.player_page.load_audiobook_details(audiobook)
        else:
            from rymflux.core.models import Audiobook
            self.player_page.load_audiobook_details(Audiobook(title="", source_name="", url="", chapters=[]))
        if audiobook:
            self.show_info_bar("Details Loaded", f"Ready to play '{audiobook.title[:30]}...'.")
            self.navigationInterface.setCurrentItem('player') # Switch to player page
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

    def show_info_bar(self, title: str, content: str, is_error: bool = False):
        pos = InfoBarPosition.TOP
        if is_error:
            InfoBar.error(title, content, duration=3000, parent=self).show()
        else:
            InfoBar.info(title, content, duration=2000, parent=self).show()

def main():
    """The main function to launch the GUI."""
    # This setting is valid in Qt6 and helps with fractional scaling.
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    # The two lines causing the error have been REMOVED from this version.
    # QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)  <-- REMOVED
    # QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)      <-- REMOVED

    app = QApplication(sys.argv)
    
    setTheme(Theme.DARK)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())