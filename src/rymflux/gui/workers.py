# src/rymflux/gui/workers.py

import asyncio
from PyQt6.QtCore import QThread, pyqtSignal
import httpx
from PyQt6.QtGui import QPixmap
from typing import Optional

# Import what the workers need from the core module
from rymflux.core.sources import AudioSource
from rymflux.core.models import AudioItem, Audiobook
from rymflux.core.metadata import GoogleBooksMetadata

class SearchWorker(QThread):
    """
    A dedicated worker thread to run async searches across ALL sources.
    """
    finished = pyqtSignal(list)

    def __init__(self, sources: list[AudioSource], query: str):
        super().__init__()
        self.sources = sources
        self.query = query

    def run(self):
        # This implementation can be further improved, but let's stick with what works for now.
        # It's better to create a new event loop for the thread.
        try:
            results = asyncio.run(self._search_all())
            self.finished.emit(results)
        except Exception as e:
            print(f"Error in search worker: {e}")
            self.finished.emit([])
    
    async def _search_all(self):
        tasks = [source.search(self.query) for source in self.sources]
        results_from_all_sources = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_results = []
        for result in results_from_all_sources:
            if isinstance(result, list):
                all_results.extend(result)
            else:
                print(f"A source failed during search: {result}")
        return all_results

class DetailsWorker(QThread):
    """
    A worker thread that fetches details from both the source scraper AND
    the Google Books API concurrently, then merges them.
    """
    finished = pyqtSignal(object)

    # IMPORTANT: You must put your actual API key here.
    GOOGLE_API_KEY = "AIzaSyAjZUWjEfFHLALqpvy3xGb_ij8VFQItfS8" 

    def __init__(self, source: AudioSource, item: AudioItem, parent=None):
        super().__init__(parent)
        self.source = source
        self.item = item
        if self.GOOGLE_API_KEY != "YOUR_API_KEY_HERE":
            self.metadata_service = GoogleBooksMetadata(api_key=self.GOOGLE_API_KEY)
        else:
            self.metadata_service = None
            print("Warning: Google Books API key not set. Metadata will be limited.")

    def run(self):
        """Runs the fetching process in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            merged_audiobook = loop.run_until_complete(self._fetch_and_merge())
            self.finished.emit(merged_audiobook)
        except Exception as e:
            print(f"Error in details worker: {e}")
            self.finished.emit(None)
        finally:
            loop.close()

    async def _fetch_and_merge(self) -> Optional[Audiobook]:
        # --- Define the two concurrent tasks ---
        task_scrape_details = self.source.get_details(self.item)
        
        task_fetch_metadata = None
        if self.metadata_service:
            task_fetch_metadata = self.metadata_service.fetch(title=self.item.title)

        # --- Run tasks concurrently ---
        if task_fetch_metadata:
            results = await asyncio.gather(task_scrape_details, task_fetch_metadata, return_exceptions=True)
            scraped_audiobook = results[0] if not isinstance(results[0], Exception) else None
            google_metadata = results[1] if not isinstance(results[1], Exception) else None
        else:
            scraped_audiobook = await task_scrape_details
            google_metadata = None

        # --- Merge the results ---
        if not scraped_audiobook or not isinstance(scraped_audiobook, Audiobook):
            # If we can't get chapters, there's no point proceeding.
            return None

        final_audiobook = scraped_audiobook

        if google_metadata and isinstance(google_metadata, dict):
            # Override scraped data with higher-quality API data
            final_audiobook.author = ", ".join(google_metadata.get("authors", [])) or scraped_audiobook.author
            final_audiobook.description = google_metadata.get("description", scraped_audiobook.description)
            final_audiobook.cover_image_url = google_metadata.get("imageLinks", {}).get("thumbnail") or scraped_audiobook.cover_image_url

        return final_audiobook

class CoverArtWorker(QThread):
    """
    A worker thread to download a cover image from a URL without freezing the GUI.
    Emits a QPixmap when finished.
    """
    finished = pyqtSignal(QPixmap)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        pixmap = QPixmap()
        if not self.url:
            self.finished.emit(pixmap) # Emit empty pixmap
            return

        try:
            # Use a synchronous client here as it's a simple, one-off request in a thread
            with httpx.Client(timeout=15.0) as client:
                response = client.get(self.url, follow_redirects=True)
                response.raise_for_status()
                pixmap.loadFromData(response.content)
        except Exception as e:
            print(f"Error fetching cover art from {self.url}: {e}")
        
        self.finished.emit(pixmap)
