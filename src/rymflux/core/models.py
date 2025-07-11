# audiostream/core/models.py

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class AudioItem:
    """A generic base class for any item that can be played."""
    title: str
    source_name: str  # e.g., "LibriVox" or "MyCustomSite"
    url: str  # The URL to the audiobook/podcast page
    
@dataclass
class Chapter:
    """Represents a single chapter of an audiobook."""
    title: str
    url: str # Direct URL to the chapter's audio file

@dataclass
class Audiobook(AudioItem):
    """Represents a full audiobook with metadata and chapters."""
    author: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    chapters: List[Chapter] = field(default_factory=list)

@dataclass
class Episode:
    """Represents a single episode of a podcast."""
    title: str
    url: str # Direct URL to the episode's audio file
    description: Optional[str] = None
    publication_date: Optional[str] = None

@dataclass
class Podcast(AudioItem):
    """Represents a podcast series with metadata and episodes."""
    author: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    episodes: List[Episode] = field(default_factory=list)