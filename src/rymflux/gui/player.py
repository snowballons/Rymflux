from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QSlider, QLabel, QStyle, QApplication
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap

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

    # Constants
    COVER_ART_SIZE = 200
    BUTTON_SIZE = 50
    ICON_SCALE = 0.7
    MARGIN = 10
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

        # 1. Cover Art Placeholder
        self.cover_art_label = QLabel(self.DEFAULT_COVER_TEXT)
        self.cover_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_art_label.setFixedSize(self.COVER_ART_SIZE, self.COVER_ART_SIZE)
        self.cover_art_label.setStyleSheet("background-color: #2c3e50; color: white; border-radius: 5px;")
        self.cover_art_label.setAccessibleName("Audiobook cover art")
        main_layout.addWidget(self.cover_art_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 2. Track Info
        self.title_label = QLabel("Select a chapter to play")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setAccessibleName("Chapter title")

        self.author_label = QLabel("")
        author_font = QFont()
        author_font.setPointSize(10)
        self.author_label.setFont(author_font)
        self.author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.author_label.setAccessibleName("Audiobook title")

        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.author_label)
        main_layout.addSpacing(self.MARGIN)

        # 3. Progress Bar and Time
        progress_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setAccessibleName("Current playback time")
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setAccessibleName("Playback progress slider")
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setAccessibleName("Total track duration")

        progress_layout.addWidget(self.current_time_label)
        progress_layout.addWidget(self.progress_slider)
        progress_layout.addWidget(self.total_time_label)
        main_layout.addLayout(progress_layout)

        # 4. Volume Control
        volume_layout = QHBoxLayout()
        self.volume_label = QLabel("Volume:")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)  # Default volume
        self.volume_slider.setAccessibleName("Volume control slider")
        volume_layout.addWidget(self.volume_label)
        volume_layout.addWidget(self.volume_slider)
        main_layout.addLayout(volume_layout)

        # 5. Control Buttons
        controls_layout = QHBoxLayout()
        style = QApplication.style()

        if style is not None:
            self.prev_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward), "")
        else:
            self.prev_button = QPushButton("")
        self.prev_button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.prev_button.setToolTip("Previous Chapter")
        self.prev_button.setAccessibleName("Previous chapter button")

        if style is not None:
            self.play_pause_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "")
        else:
            self.play_pause_button = QPushButton("")
        self.play_pause_button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.play_pause_button.setToolTip("Play/Pause")
        self.play_pause_button.setAccessibleName("Play or pause button")

        if style is not None:
            self.stop_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "")
        else:
            self.stop_button = QPushButton("")
        self.stop_button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.stop_button.setToolTip("Stop")
        self.stop_button.setAccessibleName("Stop playback button")

        if style is not None:
            self.next_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward), "")
        else:
            self.next_button = QPushButton("")
        self.next_button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.next_button.setToolTip("Next Chapter")
        self.next_button.setAccessibleName("Next chapter button")

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
        self._is_playing = not self._is_playing
        if self._is_playing:
            self.play.emit()
        else:
            self.pause.emit()
        self.set_playing_state(self._is_playing)

    def set_track_info(self, audiobook: Audiobook, chapter_title: str):
        """
        Update the player with audiobook and chapter information.

        Args:
            audiobook: The Audiobook object containing metadata.
            chapter_title: The title of the current chapter.
        """
        if not audiobook or not chapter_title:
            self.title_label.setText("Invalid chapter")
            self.author_label.setText("")
            self.cover_art_label.setText(self.DEFAULT_COVER_TEXT)
            return

        self.title_label.setText(chapter_title)
        self.author_label.setText(f"from '{audiobook.title}'")
        # Placeholder for future cover art loading
        self.cover_art_label.setText(self.DEFAULT_COVER_TEXT)
        # Example: self.set_cover_art(audiobook.cover_art_url)

    def set_cover_art(self, image_path: str):
        """
        Set the cover art image for the current audiobook.

        Args:
            image_path: Path or URL to the cover art image.
        """
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.cover_art_label.setText(self.DEFAULT_COVER_TEXT)
        else:
            scaled_pixmap = pixmap.scaled(
                self.COVER_ART_SIZE, self.COVER_ART_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_art_label.setPixmap(scaled_pixmap)

    def set_playing_state(self, is_playing: bool):
        """
        Update the play/pause button icon based on playback state.

        Args:
            is_playing: True if the audiobook is playing, False otherwise.
        """
        style = QApplication.style()
        if style is not None:
            icon = style.standardIcon(
                QStyle.StandardPixmap.SP_MediaPause if is_playing else QStyle.StandardPixmap.SP_MediaPlay
            )
            self.play_pause_button.setIcon(icon)
            self.play_pause_button.setIconSize(
                self.play_pause_button.size() * self.ICON_SCALE
            )
        self._is_playing = is_playing

    def update_progress(self, position: int, duration: int):
        """
        Update the progress slider and time labels.

        Args:
            position: Current playback position in milliseconds.
            duration: Total duration of the track in milliseconds.
        """
        if duration < 0 or position < 0:
            self.current_time_label.setText("00:00")
            self.total_time_label.setText("00:00")
            self.progress_slider.setValue(0)
            return

        self.progress_slider.blockSignals(True)
        self.progress_slider.setRange(0, duration)
        self.progress_slider.setValue(position)
        self.progress_slider.blockSignals(False)

        self.current_time_label.setText(self._format_time(position))
        self.total_time_label.setText(self._format_time(duration))

    def _format_time(self, ms: int) -> str:
        """
        Format milliseconds into a time string (HH:MM:SS or MM:SS).

        Args:
            ms: Time in milliseconds.

        Returns:
            Formatted time string.
        """
        if ms <= 0:
            return "00:00"
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        hours = int((ms / (1000 * 60 * 60)) % 24)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"