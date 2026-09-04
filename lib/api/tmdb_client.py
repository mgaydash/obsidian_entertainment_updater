"""TMDB API client for movies and TV shows."""

from typing import Dict, List, Optional

import requests

from ..obsidian_utils import (
    build_frontmatter,
    format_wikilink,
    get_user_input,
    sanitize_filename,
    translate_genre_tag,
)
from .base import MediaAPIClient


class TMDBClient(MediaAPIClient):
    """TMDB API client implementation."""

    def __init__(self, api_key: str, media_type: str):
        """
        Initialize TMDB client.

        Args:
            api_key: TMDB API key
            media_type: 'movie' or 'tv'
        """
        self.api_key = api_key
        self.media_type = media_type
        self.tmdb_base_url = "https://api.themoviedb.org/3"

    def search(self, title: str) -> List[Dict]:
        """Search TMDB for a title."""
        url = f"{self.tmdb_base_url}/search/{self.media_type}"
        params = {
            'api_key': self.api_key,
            'query': title,
            'language': 'en-US'
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        return data.get('results', [])

    def get_details(self, media_id: str) -> Dict:
        """Get detailed information from TMDB."""
        url = f"{self.tmdb_base_url}/{self.media_type}/{media_id}"
        params = {
            'api_key': self.api_key,
            'language': 'en-US',
            'append_to_response': 'credits,external_ids'
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def prompt_disambiguation(self, title: str, results: List[Dict]) -> Optional[Dict]:
        """Show results and prompt user to select the correct one."""
        print(f"\n📽️  Multiple results found for '{title}':")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            name = result.get('title') or result.get('name', 'Unknown')
            year = ''

            if 'release_date' in result and result['release_date']:
                year = result['release_date'][:4]
            elif 'first_air_date' in result and result['first_air_date']:
                year = result['first_air_date'][:4]

            overview = result.get('overview', 'No description available')[:100]

            media_label = 'MOVIE' if self.media_type == 'movie' else 'TV'
            print(f"{idx}. {name} ({year}) [{media_label}]")
            print(f"   {overview}...")
            print()

        print("0. Skip this file")
        print("-" * 80)

        while True:
            try:
                choice = get_user_input("Select the correct match (0 to skip): ").strip()
                choice_num = int(choice)

                if choice_num == 0:
                    return None
                if 1 <= choice_num <= len(results):
                    return results[choice_num - 1]
                else:
                    print(f"Please enter a number between 0 and {len(results)}")
            except ValueError:
                print("Please enter a valid number")

    def format_cast_as_wikilink(self, cast_member: Dict) -> str:
        """Format cast member as 'Character ([[Actor Name]])'."""
        actor_name = cast_member.get('name', 'Unknown')
        character = cast_member.get('character', 'Unknown')
        return f"{character} ({format_wikilink(actor_name)})"

    def format_note_content(self, details: Dict) -> str:
        """Generate markdown content for the note."""
        # Get IMDB ID and construct link
        imdb_id = details.get('external_ids', {}).get('imdb_id', '')
        imdb_link = f"https://www.imdb.com/title/{imdb_id}" if imdb_id else "Not available"

        # Get overview/synopsis
        overview = details.get('overview', 'No description available.')

        # Get director (for movies) or creator (for TV shows)
        crew = details.get('credits', {}).get('crew', [])
        directors = [c['name'] for c in crew if c.get('job') == 'Director']
        director_text = format_wikilink(directors[0]) if directors else "Unknown"

        # Get top 3 cast members
        cast = details.get('credits', {}).get('cast', [])[:3]
        cast_text = ", ".join([self.format_cast_as_wikilink(c) for c in cast])

        # Build description
        if self.media_type == 'movie':
            description = f"{overview} Directed by {director_text}. Starring {cast_text}."
        else:
            # For TV shows, creators instead of directors
            creators = details.get('created_by', [])
            creator_text = format_wikilink(creators[0]['name']) if creators else "Unknown"
            description = f"{overview} Created by {creator_text}. Starring {cast_text}."

        # Build tags list
        tags = []

        # Add genre tags
        genres = details.get('genres', [])
        for genre in genres:
            genre_name = genre.get('name', '')
            if genre_name:
                tag = translate_genre_tag(genre_name)
                if tag and tag not in tags:
                    tags.append(tag)

        # Format the content
        collection = 'Movies' if self.media_type == 'movie' else 'Series'
        content = f"""{build_frontmatter(collection, tags)}

## Links
{imdb_link}

## Description
{description}
"""
        return content

    def get_filename(self, details: Dict) -> str:
        """Generate filename in 'Title (Year).md' format."""
        # Get the year
        if self.media_type == 'movie':
            year = details.get('release_date', '')[:4]
            proper_title = details.get('title', 'Unknown')
        else:  # tv
            year = details.get('first_air_date', '')[:4]
            proper_title = details.get('name', 'Unknown')

        if not year:
            raise ValueError("Could not determine release year")

        # Sanitize title for filesystem
        proper_title = sanitize_filename(proper_title)

        # Generate filename
        return f"{proper_title} ({year}).md"

    def get_poster_url(self, details: Dict) -> Optional[str]:
        """Get full poster URL from TMDB details."""
        poster_path = details.get('poster_path')
        if not poster_path:
            return None
        return f"https://image.tmdb.org/t/p/original{poster_path}"
