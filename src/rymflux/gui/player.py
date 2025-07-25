# src/rymflux/gui/player.py

from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QSlider, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from qfluentwidgets import IndeterminateProgressRing, FluentIcon, PushButton, Icon
from typing import Optional

from rymflux.core.models import Audiobook

class ModernPlayer(QWidget):
    """
    A modern, stylish audiobook player widget with icon-based controls, cover art display,
    and volume control. Emits signals for playback control and seeking.
    
    Signals:
        play: Emitted when the play button is pressed.
        pause: Emitted when the pause button is pressed.
        stop: Emitted when the stop button is pressed.
        next_track: Emitted when the next track button is pressed.
        prev_track: Emitted when the previous track button is pressed.
        seek: Emitted when the progress slider is moved, with the seek position (ms).
        volume_changed: Emitted when the volume slider is moved, with the volume level (0-100).
    """
    # Signals
    play = pyqtSignal()
    pause = pyqtSignal()
    stop = pyqtSignal()
    next_track = pyqtSignal()
    prev_track = pyqtSignal()
    seek = pyqtSignal(int)
    volume_changed = pyqtSignal(int)

    # Constants from your friend's excellent plan
    COVER_ART_SIZE = 300  # Increased size for more impact
    BUTTON_SIZE = 45
    MARGIN = 15
    DEFAULT_COVER_TEXT = "No Cover Available"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_playing = False  # Track playback state
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize the UI components and layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        main_layout.setSpacing(self.MARGIN)

        # --- 1. Cover Art Container (with loading spinner) ---
        self.cover_art_container = QWidget()
        self.cover_art_container.setFixedSize(self.COVER_ART_SIZE, self.COVER_ART_SIZE)
        
        self.cover_art_label = QLabel(self.DEFAULT_COVER_TEXT, self.cover_art_container)
        self.cover_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_art_label.setGeometry(0, 0, self.COVER_ART_SIZE, self.COVER_ART_SIZE)
        self.cover_art_label.setStyleSheet("background-color: #2c3e50; color: white; border-radius: 8px;")
        
        self.loading_spinner = IndeterminateProgressRing(self.cover_art_container)
        self.loading_spinner.setFixedSize(60, 60)
        spinner_pos = (self.COVER_ART_SIZE - 60) // 2
        self.loading_spinner.move(spinner_pos, spinner_pos)
        self.loading_spinner.hide() # Initially hidden
        
        main_layout.addWidget(self.cover_art_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- 2. Track Info ---
        self.title_label = QLabel("Select a chapter to play")
        title_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.author_label = QLabel()
        author_font = QFont("Segoe UI", 10)
        self.author_label.setFont(author_font)
        self.author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.author_label)
        main_layout.addSpacing(self.MARGIN)

        # --- 3. Progress Bar and Time ---
        progress_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.total_time_label = QLabel("00:00")

        progress_layout.addWidget(self.current_time_label)
        progress_layout.addWidget(self.progress_slider)
        progress_layout.addWidget(self.total_time_label)
        main_layout.addLayout(progress_layout)

        # --- 4. Volume Control ---
        volume_layout = QHBoxLayout()
        volume_icon = QLabel()
        volume_icon.setPixmap(Icon(FluentIcon.MUTE).pixmap(20, 20))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        volume_layout.addWidget(volume_icon)
        volume_layout.addWidget(self.volume_slider)
        main_layout.addLayout(volume_layout)
        
        # --- 5. Control Buttons ---
        controls_layout = QHBoxLayout()
        button_style = "PushButton { border: none; border-radius: 5px; background-color: transparent; } PushButton:hover { background-color: rgba(255, 255, 255, 0.1); }"
        
        self.prev_button = PushButton(FluentIcon.LEFT_ARROW, "")
        self.play_pause_button = PushButton(FluentIcon.PLAY, "")
        self.stop_button = PushButton(Icon(FluentIcon.CLOSE), "")
        self.next_button = PushButton(FluentIcon.RIGHT_ARROW, "")
        
        for btn in [self.prev_button, self.stop_button, self.next_button]:
            btn.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
            btn.setStyleSheet(button_style)
        
        self.play_pause_button.setFixedSize(60, 60) # Main button is larger
        self.play_pause_button.setStyleSheet(button_style)

        controls_layout.addStretch()
        controls_layout.addWidget(self.prev_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.next_button)
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)

    def _connect_signals(self):
        """Connect signals to their respective slots."""
        self.play_pause_button.clicked.connect(self._on_play_pause_clicked)
        self.stop_button.clicked.connect(self.stop)
        self.next_button.clicked.connect(self.next_track)
        self.prev_button.clicked.connect(self.prev_track)
        self.progress_slider.sliderMoved.connect(self.seek)
        self.volume_slider.valueChanged.connect(self.volume_changed)

    def _on_play_pause_clicked(self):
        """Handle play/pause button clicks."""
        if not self._is_playing:
            self.play.emit()
        else:
            self.pause.emit()

    def set_track_info(self, audiobook: Optional[Audiobook], chapter_title: str):
        if not audiobook:
            self.title_label.setText("Rymflux Player")
            self.author_label.setText("Search for an audiobook to begin")
            return
            
        self.title_label.setText(chapter_title)
        self.author_label.setText(f"from '{audiobook.title}'")

    def show_cover_art_loading(self):
        self.cover_art_label.setText("") # Clear "No Cover..." text
        self.cover_art_label.setPixmap(QPixmap()) # Clear old pixmap
        self.loading_spinner.show()
        self.loading_spinner.start()

    def set_cover_art(self, pixmap: QPixmap):
        self.loading_spinner.stop()
        self.loading_spinner.hide()
        if pixmap.isNull():
            self.cover_art_label.setText(self.DEFAULT_COVER_TEXT)
            self.cover_art_label.setPixmap(QPixmap()) # Ensure it's cleared
        else:
            self.cover_art_label.setText("")
            scaled_pixmap = pixmap.scaled(
                self.COVER_ART_SIZE, self.COVER_ART_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_art_label.setPixmap(scaled_pixmap)

    def set_playing_state(self, is_playing: bool):
        self._is_playing = is_playing
        if is_playing:
            self.play_pause_button.setIcon(FluentIcon.PAUSE)
        else:
            self.play_pause_button.setIcon(FluentIcon.PLAY)

    def update_progress(self, position: int, duration: int):
        if duration <= 0: return

        self.progress_slider.blockSignals(True)
        self.progress_slider.setRange(0, duration)
        self.progress_slider.setValue(position)
        self.progress_slider.blockSignals(False)

        self.current_time_label.setText(self._format_time(position))
        self.total_time_label.setText(self._format_time(duration))

    def _format_time(self, ms: int) -> str:
        if ms < 0: ms = 0
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        hours = int((ms / (1000 * 60 * 60)) % 24)
        if hours > 0:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"