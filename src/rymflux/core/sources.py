import abc
import asyncio
from typing import List, Optional, Union, Dict, Any
import httpx
from bs4 import BeautifulSoup
import yt_dlp
from .models import AudioItem, Audiobook, Podcast, Chapter, Episode
from .logging import get_logger
from .config import load_sources_from_yaml

logger = get_logger(__name__)

class AudioSource(abc.ABC):
    """
    An abstract base class (ABC) that defines the contract for all audio sources.
    Every source, whether for an audiobook or a podcast, must implement these methods.
    """
    def __init__(self, name: str, base_url: str, client: Optional[httpx.AsyncClient] = None):
        self.name = name
        self.base_url = base_url
        # Add headers to mimic a real browser
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        self.client = client if client else httpx.AsyncClient(headers=headers, timeout=10.0)

    @abc.abstractmethod
    async def search(self, query: str) -> List[AudioItem]:
        """
        Searches the source for a given query and returns a list of basic AudioItems.
        This method should be lightweight and not fetch full details like chapters.
        """
        pass

    @abc.abstractmethod
    async def get_details(self, item: AudioItem) -> Optional[Union[Audiobook, Podcast]]:
        """
        Takes a basic AudioItem and fetches its full details, including chapters or
        episodes, description, author, etc.
        """
        pass

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.client.aclose()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"


class CustomSource(AudioSource):
    """
    A dynamic audio source that is configured by a set of scraping rules
    provided in a dictionary (typically from a YAML/JSON file).
    """
    def __init__(self, name: str, base_url: str, rules: Dict[str, Any]):
        super().__init__(name, base_url)
        self.rules = rules
        if "search" not in self.rules or "details" not in self.rules:
            raise ValueError("Configuration for CustomSource must include 'search' and 'details' rules.")

    async def search(self, query: str) -> List[AudioItem]:
        """Performs a search using the defined CSS selectors."""
        search_rule = self.rules["search"]
        
        relative_search_path = search_rule["url"].format(query=query)
        search_url = str(httpx.URL(self.base_url).join(relative_search_path))

        logger.debug(f"Fetching search URL: {search_url}")

        try:
            response = await self.client.get(search_url, follow_redirects=True)
            response.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"Request to {self.name} failed: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        
        item_containers = soup.select(search_rule["item_container_selector"])
        logger.debug(f"Found {len(item_containers)} potential result containers.")

        results = []
        for container in item_containers:
            title_element = container.select_one(search_rule["title_selector"])
            url_element = container.select_one(search_rule["url_selector"])

            if title_element and url_element and url_element.has_attr('href'):
                title = title_element.get_text(strip=True)
                relative_url = url_element['href']
                item_url = str(httpx.URL(self.base_url).join(str(relative_url)))
                
                results.append(AudioItem(title=title, source_name=self.name, url=item_url))
            else:
                logger.debug("A container was found, but title/URL selector failed within it.")

        return results

    async def get_details(self, item: AudioItem) -> Optional[Union[Audiobook, Podcast]]:
        """
        Fetches the full details for an AudioItem by scraping its URL.
        """
        logger.info(f"Fetching details for: '{item.title}' at {item.url}")
        
        try:
            response = await self.client.get(item.url, follow_redirects=True)
            response.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"Could not fetch details from {item.url}: {e}")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Helper function to safely extract text or attributes
        def safe_get(selector, attribute=None):
            element = soup.select_one(selector)
            if not element:
                return None
            if attribute:
                return element.get(attribute)
            return element.get_text(strip=True)

        author = safe_get(self.rules["details"].get("author_selector"))
        description = safe_get(self.rules["details"].get("description_selector"))
        cover_image_url = safe_get(self.rules["details"].get("cover_image_url_selector"), attribute='src')
        
        author = str(author) if author is not None else None
        description = str(description) if description is not None else None
        cover_image_url = str(cover_image_url) if cover_image_url is not None else None
        
        # Scrape chapters
        chapters = []
        chapter_containers = soup.select(self.rules["details"]["chapter_container_selector"])
        logger.debug(f"Found {len(chapter_containers)} chapter containers.")

        for i, container in enumerate(chapter_containers, 1):
            url_element = container.select_one(self.rules["details"]["chapter_url_selector"])
            if url_element and url_element.has_attr('src'):
                chapter_url = str(url_element['src'])
                chapter_title = f"Chapter {i}"
                chapters.append(Chapter(title=chapter_title, url=chapter_url))

        return Audiobook(
            title=item.title,
            source_name=item.source_name,
            url=item.url,
            author=author,
            description=description,
            cover_image_url=cover_image_url,
            chapters=chapters
        )

class ArchiveSource(AudioSource):
    """
    A dedicated source for archive.org, specifically for the LibriVox collection.
    This source uses the official archive.org API instead of HTML scraping.
    """
    def __init__(self, name: str, base_url: str, client: Optional[httpx.AsyncClient] = None):
        super().__init__(name, "https://archive.org", client=client)
        self.api_url = "https://archive.org/advancedsearch.php"
        self.metadata_url_template = "https://archive.org/metadata/{identifier}"

    async def search(self, query: str) -> List[AudioItem]:
        # Using the cleaner query format and fl[] parameter array
        params = (
            ("q", f"collection:librivoxaudio AND title:({query})"),
            ("fl[]", "identifier"),
            ("fl[]", "title"),
            ("fl[]", "creator"),
            ("output", "json"),
            ("rows", "50")  # Ask for up to 50 results
        )
        
        try:
            async with httpx.AsyncClient(headers=self.client.headers, timeout=10.0) as client:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                data = response.json()
            
            results = []
            for doc in data.get("response", {}).get("docs", []):
                if 'identifier' in doc:
                    item_url = f"{self.base_url}/details/{doc['identifier']}"
                    results.append(
                        AudioItem(
                            title=doc.get("title", "Unknown Title"),
                            source_name=self.name,
                            url=item_url
                        )
                    )
            return results
        except Exception as e:
            logger.error(f"Error searching Archive.org: {e}")
            return []

    async def get_details(self, item: AudioItem) -> Optional[Audiobook]:
        identifier = item.url.split('/')[-1].strip()
        if not identifier: return None
        
        metadata_url = self.metadata_url_template.format(identifier=identifier)
        
        try:
            async with httpx.AsyncClient(headers=self.client.headers, timeout=10.0) as client:
                response = await client.get(metadata_url)
                response.raise_for_status()
                metadata = response.json()
            
            chapters = []
            for file_info in metadata.get("files", []):
                file_name = file_info.get("name", "")
                if file_name.endswith((".mp3", ".ogg")) and "64kb" not in file_name and "128kb" not in file_name:
                    chapter_title = file_info.get("title") or file_name.split('/')[-1]
                    chapter_url = f"https://archive.org/download/{identifier}/{file_name}"
                    chapters.append(Chapter(title=chapter_title.strip(), url=chapter_url))

            if not chapters:
                return None
            
            chapters.sort(key=lambda c: c.title)
            
            # --- THIS IS THE UPGRADE ---
            # Construct the cover art URL using the archive.org thumbnail service
            cover_url = f"https://archive.org/services/img/{identifier}"
            
            return Audiobook(
                title=metadata.get("metadata", {}).get("title", item.title),
                author=metadata.get("metadata", {}).get("creator", "Unknown"),
                description=metadata.get("metadata", {}).get("description", ""),
                url=item.url,
                source_name=self.name,
                chapters=chapters,
                cover_image_url=cover_url  # Set the cover art URL
            )
        except Exception as e:
            logger.error(f"Error getting details from Archive.org for {identifier}: {e}")
            return None


def get_source(source_config: Dict[str, Any]) -> Optional[AudioSource]:
    """
    Factory function that creates and returns an AudioSource instance based on
    the provided configuration dictionary.
    """
    if not isinstance(source_config, dict):
        logger.error(f"Source config is not a dict: {source_config}")
        return None
    source_type = source_config.get("type")
    name = source_config.get("name")
    base_url = source_config.get("base_url")
    # Defensive: Only require base_url for custom/youtube, not archive
    if source_type == "archive":
        if not name:
            logger.error(f"Archive source config missing required fields: {source_config}")
            return None
        # base_url is not used for archive, but ArchiveSource expects a string
        return ArchiveSource(str(name), base_url or "")
    if not all([source_type, name, base_url]):
        logger.error(f"Source config missing required fields: {source_config}")
        return None
    if source_type == "custom":
        rules = source_config.get("rules")
        if not rules:
            logger.error(f"Custom source '{name}' is missing 'rules'.")
            return None
        return CustomSource(str(name), str(base_url), rules)
    elif source_type == "youtube":
        return None # Removed YouTubeSource, so return None
    else:
        logger.warning(f"Unknown source type: '{source_type}'")
        return None

async def get_all_sources(filepath: str) -> List[AudioSource]:
    """
    Loads all source configurations from a YAML file and returns a list of
    initialized AudioSource objects.
    """
    source_configs = load_sources_from_yaml(filepath)
    
    sources = []
    for config in source_configs:
        source = get_source(config)
        if source:
            sources.append(source)
            
    return sources

async def close_all_sources(sources: List[AudioSource]):
    """Gracefully closes all provided audio sources."""
    for source in sources:
        await source.close()

