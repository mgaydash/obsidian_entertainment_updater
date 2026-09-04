"""Utilities for working with Obsidian markdown files."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


def extract_yaml_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
    """Extract YAML frontmatter and return it with the remaining content."""
    if not content.startswith('---'):
        return None, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return None, content

    try:
        frontmatter = yaml.safe_load(parts[1])
        remaining_content = parts[2]
        return frontmatter, remaining_content
    except yaml.YAMLError:
        return None, content


COLLECTION_BY_MEDIA_TYPE = {
    'movie': 'Movies',
    'tv': 'Series',
    'series': 'Series',
    'game': 'Games',
    'book': 'Books',
    'album': 'Albums',
}


def build_frontmatter(collection: str, tags: List[str]) -> str:
    """
    Build YAML frontmatter declaring the note's collection, plus any facet tags.

    `collection` is the note's identity — exactly one, always. `tags` carry
    everything else (genre, play-mode, and so on) and the key is omitted
    entirely when there are none.

    Args:
        collection: Collection note name, e.g. 'Movies'
        tags: Facet tags, excluding the media type

    Returns:
        Frontmatter block, including the delimiting '---' lines
    """
    lines = ['---', f'collection: "[[{collection}]]"']
    if tags:
        lines.append('tags:')
        lines.extend(f'  - {tag}' for tag in tags)
    lines.append('---')
    return '\n'.join(lines)


def sanitize_filename(title: str) -> str:
    """Sanitize title for filesystem (remove problematic characters)."""
    return title.replace(':', ' -').replace('/', '-').replace('\\', '-').replace('?', '')


def format_wikilink(text: str) -> str:
    """Format text as an Obsidian wikilink."""
    return f"[[{text}]]"


def get_user_input(prompt: str) -> str:
    """
    Get user input from terminal, even when stdin is piped.

    This function reads from the controlling terminal (/dev/tty on Unix, CON on Windows)
    instead of stdin, allowing interactive prompts to work when stdin is piped.

    Args:
        prompt: The prompt to display to the user

    Returns:
        User input as a string (with trailing newline removed)

    Raises:
        EOFError: If unable to read from terminal
    """
    # Try to open the controlling terminal
    try:
        # Unix-like systems
        with open('/dev/tty', 'r') as tty:
            print(prompt, end='', flush=True)
            return tty.readline().rstrip('\n\r')
    except (OSError, IOError, FileNotFoundError):
        try:
            # Windows
            with open('CON', 'r') as tty:
                print(prompt, end='', flush=True)
                return tty.readline().rstrip('\n\r')
        except (OSError, IOError, FileNotFoundError):
            # If both fail, raise an error
            raise EOFError(
                "Cannot read from terminal. Interactive prompts are not available "
                "when stdin is piped and terminal access is unavailable."
            )


def extract_title_and_year(input_string: str) -> Tuple[str, Optional[str]]:
    """
    Extract title and year from input string in 'Title (Year)' format.

    Args:
        input_string: Input string, possibly with year in parentheses

    Returns:
        Tuple of (title, year) where year is None if not found

    Examples:
        "Inception (2010)" -> ("Inception", "2010")
        "Inception" -> ("Inception", None)
        "The Matrix (1999)" -> ("The Matrix", "1999")
    """
    # Match pattern: Title (Year) where Year is 4 digits
    match = re.match(r'^(.+?)\s*\((\d{4})\)\s*$', input_string)
    if match:
        return match.group(1).strip(), match.group(2)
    else:
        return input_string.strip(), None


def filter_results_by_year(results: List[Dict], year: str, media_type: str) -> List[Dict]:
    """
    Filter search results by year.

    Args:
        results: List of API search results
        year: Year to filter by (4 digits)
        media_type: 'movie', 'tv', 'series', 'game', 'album', or 'book'

    Returns:
        Filtered list of results matching the year
    """
    filtered = []
    for result in results:
        result_year = None

        if media_type in ['movie', 'tv', 'series']:
            # TMDB format
            if media_type == 'movie' and 'release_date' in result:
                result_year = result['release_date'][:4] if result['release_date'] else None
            elif media_type in ['tv', 'series'] and 'first_air_date' in result:
                result_year = result['first_air_date'][:4] if result['first_air_date'] else None
        elif media_type == 'game':
            # IGDB format - convert timestamp to year (use UTC to avoid timezone issues)
            if 'first_release_date' in result:
                from datetime import datetime, timezone
                timestamp = result['first_release_date']
                result_year = str(datetime.fromtimestamp(timestamp, tz=timezone.utc).year)
        elif media_type == 'album':
            # MusicBrainz date format: 'YYYY-MM-DD', 'YYYY-MM', or 'YYYY'
            if 'date' in result:
                result_year = result['date'][:4] if result['date'] else None
        elif media_type == 'book':
            # Google Books: first_publish_year is an int
            if 'first_publish_year' in result and result['first_publish_year']:
                result_year = str(result['first_publish_year'])

        if result_year == year:
            filtered.append(result)

    return filtered


def find_exact_title_match(results: List[Dict], title: str, media_type: str) -> Optional[Dict]:
    """
    Find an exact title match in results.

    Args:
        results: List of API search results
        title: Title to match (case-insensitive)
        media_type: 'movie', 'tv', 'series', 'game', 'album', or 'book'

    Returns:
        The result if exactly one exact match is found, None otherwise
    """
    exact_matches = []
    title_lower = title.lower().strip()

    for result in results:
        result_title = None

        if media_type in ['movie', 'tv', 'series']:
            # TMDB format: movies use 'title', TV uses 'name'
            result_title = result.get('title') or result.get('name')
        elif media_type == 'game':
            # IGDB format: uses 'name'
            result_title = result.get('name')
        elif media_type == 'album':
            # MusicBrainz uses 'title' field
            result_title = result.get('title')
        elif media_type == 'book':
            # Google Books standardized result uses 'title'
            result_title = result.get('title')

        if result_title and result_title.lower().strip() == title_lower:
            exact_matches.append(result)

    # Only return if exactly one exact match found
    if len(exact_matches) == 1:
        return exact_matches[0]
    return None


def is_game_unreleased(game_result: Dict) -> bool:
    """
    Check if a game result is unreleased (no release date).

    Args:
        game_result: IGDB game result dictionary

    Returns:
        True if the game has no release date, False otherwise
    """
    return 'first_release_date' not in game_result


def prompt_unreleased_confirmation(game_title: str) -> bool:
    """
    Prompt user to confirm if they want to add an unreleased game.

    Args:
        game_title: Name of the unreleased game

    Returns:
        True if user wants to add the game, False otherwise
    """
    print(f"⚠️  '{game_title}' has no release date (TBD)")
    response = get_user_input("Add this unreleased game? (y/n): ").strip().lower()
    return response == 'y'


# Cache for genre mappings config
_GENRE_MAPPINGS_CACHE: Optional[Dict[str, List[str]]] = None


def _load_genre_mappings() -> Dict[str, List[str]]:
    """
    Load genre mappings from YAML config file.

    Returns:
        Dictionary mapping obsidian tags to list of API genre strings
    """
    global _GENRE_MAPPINGS_CACHE

    if _GENRE_MAPPINGS_CACHE is not None:
        return _GENRE_MAPPINGS_CACHE

    # Get path to config file (in project root)
    config_path = Path(__file__).parent.parent / 'genre_mappings.yaml'

    if not config_path.exists():
        # Return empty dict if config doesn't exist
        _GENRE_MAPPINGS_CACHE = {}
        return _GENRE_MAPPINGS_CACHE

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            mappings = yaml.safe_load(f) or {}
            _GENRE_MAPPINGS_CACHE = mappings
            return mappings
    except Exception:
        # Return empty dict on error
        _GENRE_MAPPINGS_CACHE = {}
        return _GENRE_MAPPINGS_CACHE


def translate_genre_tag(genre: str) -> str:
    """
    Translate API genre string to Obsidian-friendly tag.

    Uses genre_mappings.yaml config to map API genre strings to clean tags.
    Falls back to sanitizing the genre if no mapping found.

    Args:
        genre: Genre string from API (TMDB or IGDB)

    Returns:
        Obsidian-friendly tag string (lowercase, no spaces/special chars)

    Examples:
        "Role-Playing (RPG)" -> "rpg"
        "Science Fiction" -> "sci-fi"
        "Action/Adventure" -> "action-adventure"
        "Unknown Genre" -> "unknown-genre"
    """
    mappings = _load_genre_mappings()
    genre_lower = genre.lower().strip()

    # Check if genre matches any mapping
    for tag, source_genres in mappings.items():
        if genre_lower in [g.lower() for g in source_genres]:
            return tag

    # No mapping found - sanitize the genre
    # Convert to lowercase and replace spaces/special chars with hyphens
    sanitized = re.sub(r'[^\w\s-]', ' ', genre_lower)  # Convert special chars to spaces (preserves word boundaries)
    sanitized = re.sub(r'[\s_]+', '-', sanitized)      # Replace spaces/underscores with hyphens
    sanitized = re.sub(r'-+', '-', sanitized)          # Collapse multiple hyphens
    sanitized = sanitized.strip('-')                    # Remove leading/trailing hyphens

    result = sanitized if sanitized else 'unknown'

    # Warn user about missing mapping so they can add it to genre_mappings.yaml
    print(f"⚠️  No genre mapping for '{genre}' - using sanitized value: '{result}'")

    return result
