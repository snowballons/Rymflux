# src/rymflux/core/metadata.py

import httpx
from typing import Optional, Dict, Any

from .models import Audiobook

class GoogleBooksMetadata:
    """A service to enrich audiobook data using the Google Books API."""

    API_URL = "https://www.googleapis.com/books/v1/volumes"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Google Books API key is required.")
        self.api_key = api_key

    async def fetch(self, title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetches book metadata from Google Books API.
        Returns the 'volumeInfo' dictionary of the best match, or None.
        """
        query_parts = [f'intitle:"{title}"']
        if author:
            query_parts.append(f'inauthor:"{author}"')
        
        query = "+".join(query_parts)
        
        params = {"q": query, "key": self.api_key, "maxResults": 1}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.API_URL, params=params)
                response.raise_for_status()
                data = response.json()

            if data.get("totalItems", 0) > 0 and "items" in data:
                # Return the volumeInfo of the first and most likely result
                return data["items"][0].get("volumeInfo")
        except Exception as e:
            print(f"Error fetching from Google Books API: {e}")
        
        return None