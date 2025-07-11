# src/rymflux/gui/workers.py

import asyncio
from PyQt6.QtCore import QThread, pyqtSignal

# Import what the workers need from the core module
from rymflux.core.sources import AudioSource
from rymflux.core.models import AudioItem, Audiobook

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
    A worker thread to fetch the full details of a selected audio item.
    """
    finished = pyqtSignal(object) 

    def __init__(self, source: AudioSource, item: AudioItem):
        super().__init__()
        self.source = source
        self.item = item

    def run(self):
        """Fetches details in a separate thread."""
        try:
            details = asyncio.run(self.source.get_details(self.item))
            self.finished.emit(details)
        except Exception as e:
            print(f"Error in details worker: {e}")
            self.finished.emit(None)