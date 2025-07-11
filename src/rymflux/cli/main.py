import asyncio
import sys
import os
import argparse
import nest_asyncio
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.panel import Panel
from contextlib import nullcontext

from rymflux.core.config import load_sources_from_yaml
from rymflux.core.sources import CustomSource, ArchiveSource
from rymflux.core.models import AudioItem, Audiobook
from .player import CLIPlayer
from . import ui
import questionary
from rymflux.core.logging import setup_logging

nest_asyncio.apply()

# Set up console and logging
console = Console()
setup_logging("--debug" in sys.argv or os.environ.get("RYMFLUX_DEBUG", "false").lower() == "true")

class CLIApp:
    def __init__(self):
        self.sources = []
        self.is_running = True
        self.player = CLIPlayer()
        self.search_results = []
        self.current_audiobook = None
        self.current_chapter_index = -1
        self.history = ui.load_playback_history()
        self.prompt_session = self._create_prompt_session()

    def _create_prompt_session(self) -> PromptSession:
        """Create a prompt session with basic bindings (q to quit)."""
        bindings = KeyBindings()

        @bindings.add('q')
        def _(event):
            self.player.stop()
            self.is_running = False
            event.app.exit(result='q')

        return PromptSession(multiline=False, key_bindings=bindings)

    def _load_sources(self):
        """Loads all sources from the config file."""
        console.print("[cyan]Loading sources...[/cyan]")
        source_configs = load_sources_from_yaml("sources.yaml")
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

    async def _handle_search(self, query: str):
        if not query.strip():
            console.print("[yellow]Please enter a valid search query.[/yellow]")
            return

        tasks = [source.search(query) for source in self.sources]
        with console.status("[bold green]Searching all sources...") if "--debug" in sys.argv else nullcontext() as status:
            try:
                results_from_all_sources = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=10.0)
            except asyncio.TimeoutError:
                console.print("[yellow]Search timed out for some sources.[/yellow]")
                results_from_all_sources = [e if isinstance(e, Exception) else e for e in await asyncio.gather(*tasks, return_exceptions=True)]
        
        self.search_results = []
        for i, sublist in enumerate(results_from_all_sources):
            if isinstance(sublist, Exception):
                console.print(f"[yellow]Warning: Source {self.sources[i].name} failed to respond.[/yellow]")
            elif isinstance(sublist, list):
                self.search_results.extend(item for item in sublist if isinstance(item, AudioItem))
        
        selected_index = ui.display_search_results(self.search_results)
        if selected_index is None:
            return

        self.history["last_search"] = query
        self.history["last_selected"] = self.search_results[selected_index].title
        ui.save_playback_history(self.history)

        await self._handle_chapter_selection(selected_index)
        
    async def _handle_chapter_selection(self, book_index: int):
        """Fetches and displays chapters for a selected book."""
        selected_book = self.search_results[book_index]
        source = next(s for s in self.sources if s.name == selected_book.source_name)

        with console.status(f"[bold green]Fetching details for '{selected_book.title}'...") if "--debug" in sys.argv else nullcontext() as status:
            self.current_audiobook = await source.get_details(selected_book)

        if not self.current_audiobook or not self.current_audiobook.chapters:
            console.print("[red]Could not load chapters for this item.[/red]")
            return

        selected_chapter_idx = ui.display_chapters(self.current_audiobook)
        if selected_chapter_idx is None:
            return

        self.current_chapter_index = selected_chapter_idx
        self.history["last_audiobook"] = self.current_audiobook.title
        self.history["last_chapter_index"] = self.current_chapter_index
        ui.save_playback_history(self.history)
        await self._run_player_loop()

    def _get_current_chapter(self):
        """Helper to safely get the current chapter."""
        if self.current_audiobook and 0 <= self.current_chapter_index < len(self.current_audiobook.chapters):
            return self.current_audiobook.chapters[self.current_chapter_index]
        return None

    def _next_chapter(self):
        """Load the next chapter."""
        if self.current_audiobook and self.current_audiobook.chapters:
            self.current_chapter_index = (self.current_chapter_index + 1) % len(self.current_audiobook.chapters)
            chapter = self._get_current_chapter()
            if chapter:
                self.player.load_file(chapter.url, f"{self.current_audiobook.title} - {chapter.title}")
                self.history["last_chapter_index"] = self.current_chapter_index
                ui.save_playback_history(self.history)

    def _prev_chapter(self):
        """Load the previous chapter."""
        if self.current_audiobook and self.current_audiobook.chapters:
            self.current_chapter_index = (self.current_chapter_index - 1) if self.current_chapter_index > 0 else len(self.current_audiobook.chapters) - 1
            chapter = self._get_current_chapter()
            if chapter:
                self.player.load_file(chapter.url, f"{self.current_audiobook.title} - {chapter.title}")
                self.history["last_chapter_index"] = self.current_chapter_index
                ui.save_playback_history(self.history)

    async def _run_player_loop(self):
        """The main loop for the interactive player with playback controls."""
        chapter = self._get_current_chapter()
        if not chapter:
            return
        self.player.start(getattr(chapter, 'url', ''), f"{getattr(self.current_audiobook, 'title', '')} - {getattr(chapter, 'title', '')}")

        # Update prompt session with playback bindings
        bindings = KeyBindings()

        @bindings.add(' ')
        def _(event):
            self.player.play_pause()

        @bindings.add('n')
        def _(event):
            self._next_chapter()

        @bindings.add('b')
        def _(event):
            self._prev_chapter()

        @bindings.add(Keys.Right)
        def _(event):
            self.player.seek(10)

        @bindings.add(Keys.Left)
        def _(event):
            self.player.seek(-10)

        @bindings.add('+')
        def _(event):
            self.player.set_volume(self.player.volume + 5)

        @bindings.add('-')
        def _(event):
            self.player.set_volume(self.player.volume - 5)

        @bindings.add('s')
        def _(event):
            self.player.stop()
            event.app.exit(result='s')

        @bindings.add('h')
        def _(event):
            chapter = self._get_current_chapter()
            chapter_title = getattr(chapter, 'title', 'Unknown Chapter')
            ui.display_player_ui(
                self.current_audiobook.title if self.current_audiobook and hasattr(self.current_audiobook, 'title') else '',
                chapter_title,
                *self.player.get_playback_status()
            )

        @bindings.add('q')
        def _(event):
            self.player.stop()
            self.is_running = False
            event.app.exit(result='q')

        self.prompt_session = PromptSession(multiline=False, key_bindings=bindings)

        while True:
            # Clear the terminal
            os.system('clear' if os.name == 'posix' else 'cls')
            chapter = self._get_current_chapter()
            chapter_title = getattr(chapter, 'title', 'Unknown Chapter')
            ui.display_player_ui(
                self.current_audiobook.title if self.current_audiobook and hasattr(self.current_audiobook, 'title') else '',
                chapter_title,
                *self.player.get_playback_status()
            )
            try:
                result = await self.prompt_session.prompt_async()
                if result == 's':
                    break
                if result == 'q':
                    self.is_running = False
                    break
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error in player loop: {e}[/red]")
                break
            await asyncio.sleep(0.1)

    async def run(self):
        # Parse command-line arguments
        parser = argparse.ArgumentParser(description="Rymflux: Stream audiobooks from the web.")
        parser.add_argument("--debug", action="store_true", help="Enable debug output.")
        args = parser.parse_args()

        self._load_sources()
        console.print(Panel("Welcome to Rymflux!\nSearch for audiobook or podcast", border_style="green"))
        
        if "last_search" in self.history:
            console.print(f"[dim]Last search: {self.history['last_search']}[/dim]")
        if "last_audiobook" in self.history and "last_chapter_index" in self.history:
            if questionary.confirm(f"Resume last audiobook: {self.history['last_audiobook']}?").ask():
                self.current_audiobook = Audiobook(
                    title=self.history["last_audiobook"],
                    source_name="unknown",  # Placeholder
                    url="unknown",         # Placeholder
                    chapters=[]
                )
                self.current_chapter_index = self.history["last_chapter_index"]
                if not self.current_audiobook.chapters:
                    console.print("[yellow]No chapters available to resume.[/yellow]")
                else:
                    await self._run_player_loop()

        while self.is_running:
            try:
                query = await self.prompt_session.prompt_async("🔎 ")
                if query.lower() in ["quit", "exit", "q"]:
                    if questionary.confirm("Are you sure you want to quit?").ask():
                        self.is_running = False
                        self.player.stop()
                        break
                    continue
                if not query:
                    continue

                await self._handle_search(query)
            except (KeyboardInterrupt, EOFError):
                if questionary.confirm("Are you sure you want to quit?").ask():
                    self.is_running = False
                    self.player.stop()
                    break
        
        self.player.stop()
        console.print("\nGoodbye!")

def start():
    """Function to be called by the entry point."""
    app = CLIApp()
    asyncio.run(app.run())