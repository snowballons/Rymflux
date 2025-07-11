import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import questionary
from rymflux.core.logging import get_logger
from rymflux.core.models import Audiobook

console = Console()
logger = get_logger(__name__)

def load_playback_history() -> dict:
    """Loads the playback history from a file or returns an empty dict."""
    try:
        with open(".rymflux_history.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_playback_history(history: dict) -> None:
    """Saves the playback history to a file."""
    with open(".rymflux_history.json", "w") as f:
        json.dump(history, f)

def display_search_results(results: list) -> int | None:
    """Displays search results in a table with pagination and prompts for selection."""
    if not results or not isinstance(results, list):
        console.print("[yellow]No results found.[/yellow]")
        return None

    PAGE_SIZE = 36
    total_pages = (len(results) + PAGE_SIZE - 1) // PAGE_SIZE
    current_page = 1

    while True:
        start_idx = (current_page - 1) * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, len(results))
        page_results = results[start_idx:end_idx]

        if len(results) > PAGE_SIZE:
            console.print(f"[yellow]Page {current_page} of {total_pages}. Use 'Next' or 'Prev' to navigate.[/yellow]")

        table = Table(title="Search Results", show_lines=True)
        table.add_column("ID", style="cyan", justify="center")
        table.add_column("Title", style="magenta")
        table.add_column("Source", style="green")
        
        choices = []
        for i, item in enumerate(page_results, start_idx + 1):
            table.add_row(str(i - start_idx), item.title, item.source_name)
            choices.append(f"{i}: {item.title} ({item.source_name})")

        choices.extend(["Next" if current_page < total_pages else None, 
                       "Prev" if current_page > 1 else None, "Cancel"])
        choices = [c for c in choices if c is not None]

        console.print(Panel(table, title="Available Audiobooks", border_style="blue"))
        console.print("[dim]Enter the number to select, 'Next'/'Prev' to navigate, or 'Cancel'[/dim]")

        use_shortcuts = len(choices) <= 36  # Only use shortcuts if 36 or fewer choices (including Cancel)
        selected_choice = questionary.select(
            "Select an item to view chapters:", choices=choices,
            use_shortcuts=use_shortcuts
        ).ask()

        if not selected_choice or selected_choice == "Cancel":
            return None
        elif selected_choice == "Next":
            current_page += 1
        elif selected_choice == "Prev":
            current_page -= 1
        else:
            return int(selected_choice.split(':')[0]) - 1

def display_chapters(audiobook: Audiobook) -> int | None:
    """Displays chapters and prompts for selection."""
    if not audiobook or not hasattr(audiobook, 'chapters') or not audiobook.chapters:
        console.print("[red]No chapters available.[/red]")
        return None

    choices = [f"{i}: {chapter.title}" for i, chapter in enumerate(audiobook.chapters, 1)]
    choices.append("Cancel")
    selected_choice = questionary.select(
        "Select a chapter to play:", choices=choices,
        use_shortcuts=True
    ).ask()

    if not selected_choice or selected_choice == "Cancel":
        return None
    return int(selected_choice.split(':')[0]) - 1

def display_player_ui(title: str, chapter: str, position: float, duration: float, is_playing: bool, volume: int) -> None:
    """Displays the current playback status in a focused layout."""
    status = "▶️" if is_playing else "⏸️"
    progress = f"{position:.1f}/{duration:.1f}s" if duration > 0 else "Unknown"

    table = Table.grid(padding=1)
    table.add_row(f"{status} {title}")
    table.add_row(f"Chapter: {chapter}")
    table.add_row(f"Progress: {progress}")
    table.add_row(f"Volume: {volume}%")
    table.add_row("[dim]Controls: Space (Play/Pause), n (Next), b (Prev), +/- (Volume), q (Quit)[/dim]")

    console.print(Panel(table, border_style="blue"))