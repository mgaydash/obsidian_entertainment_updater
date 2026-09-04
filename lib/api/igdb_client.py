"""IGDB API client for games."""

import json
from typing import Dict, List, Optional

import requests
from igdb.wrapper import IGDBWrapper

from ..obsidian_utils import (
    build_frontmatter,
    format_wikilink,
    get_user_input,
    sanitize_filename,
    translate_genre_tag,
)
from .base import MediaAPIClient


class IGDBClient(MediaAPIClient):
    """IGDB API client implementation."""

    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize IGDB client.

        Args:
            client_id: Twitch application client ID
            client_secret: Twitch application client secret
        """
        self.client_id = client_id
        self.client_secret = client_secret

        # Generate access token via OAuth2
        access_token = self._get_access_token()
        self.wrapper = IGDBWrapper(client_id, access_token)

    def _get_access_token(self) -> str:
        """
        Generate OAuth2 access token from Twitch.

        Returns:
            Access token string

        Raises:
            Exception if token generation fails
        """
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }

        response = requests.post(url, params=params)
        response.raise_for_status()

        data = response.json()
        return data['access_token']

    def search(self, title: str) -> List[Dict]:
        """Search IGDB for a game title."""
        # IGDB uses Apicalypse query language
        # Use higher limit to ensure exact title matches aren't cut off (e.g., "Fate")
        query = f'''
            search "{title}";
            fields name, first_release_date, summary, url, involved_companies, cover.image_id;
            limit 25;
        '''

        byte_array = self.wrapper.api_request('games', query)
        results = json.loads(byte_array.decode('utf-8'))

        return results if isinstance(results, list) else []

    def get_details(self, media_id: str) -> Dict:
        """Get detailed information from IGDB."""
        # Get game details with expanded company, game mode, and genre information
        query = f'''
            fields name, first_release_date, summary, url, involved_companies.company.name,
                   involved_companies.developer, involved_companies.publisher, game_modes.name, genres.name, cover.image_id;
            where id = {media_id};
        '''
        byte_array = self.wrapper.api_request('games', query)
        results = json.loads(byte_array.decode('utf-8'))

        if not results or not isinstance(results, list):
            raise ValueError(f"Game with ID {media_id} not found")

        return results[0]

    def prompt_disambiguation(self, title: str, results: List[Dict]) -> Optional[Dict]:
        """Show results and prompt user to select the correct one."""
        print(f"\n🎮 Multiple results found for '{title}':")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            name = result.get('name', 'Unknown')
            year = 'TBD'

            # Convert Unix timestamp to year (use UTC to avoid timezone issues)
            if 'first_release_date' in result:
                from datetime import datetime, timezone
                timestamp = result['first_release_date']
                year = str(datetime.fromtimestamp(timestamp, tz=timezone.utc).year)

            summary = result.get('summary', 'No description available')[:100]

            print(f"{idx}. {name} ({year}) [GAME]")
            print(f"   {summary}...")
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

    def format_note_content(self, details: Dict) -> str:
        """Generate markdown content for the note."""
        # Get IGDB URL
        igdb_url = details.get('url', 'Not available')

        # Get summary
        summary = details.get('summary', 'No description available.')

        # Get developers and publishers
        involved_companies = details.get('involved_companies', [])
        developers = []
        publishers = []

        for ic in involved_companies:
            company_name = ic.get('company', {}).get('name', 'Unknown')
            if ic.get('developer'):
                developers.append(company_name)
            if ic.get('publisher'):
                publishers.append(company_name)

        # Format developer/publisher text
        dev_text = format_wikilink(developers[0]) if developers else "Unknown"
        pub_text = format_wikilink(publishers[0]) if publishers else "Unknown"

        # Build description
        description = f"{summary} Developed by {dev_text}. Published by {pub_text}."

        # Build tags list
        tags = []

        # Add game mode tags
        game_modes = details.get('game_modes', [])
        for mode in game_modes:
            mode_name = mode.get('name', '').lower()
            if 'single player' in mode_name or 'singleplayer' in mode_name:
                if 'single-player' not in tags:
                    tags.append('single-player')
            if 'multiplayer' in mode_name and 'mmo' not in mode_name:
                if 'multiplayer' not in tags:
                    tags.append('multiplayer')
            if 'co-op' in mode_name or 'cooperative' in mode_name:
                if 'co-op' not in tags:
                    tags.append('co-op')

        # Add genre tags
        genres = details.get('genres', [])
        for genre in genres:
            genre_name = genre.get('name', '')
            if genre_name:
                tag = translate_genre_tag(genre_name)
                if tag and tag not in tags:
                    tags.append(tag)

        # Format the content
        content = f"""{build_frontmatter('Games', tags)}

## Links
{igdb_url}

## Description
{description}
"""
        return content

    def get_filename(self, details: Dict) -> str:
        """Generate filename in 'Title (Year).md' format."""
        # Get the year (use UTC to avoid timezone issues)
        year = ''
        if 'first_release_date' in details:
            from datetime import datetime, timezone
            timestamp = details['first_release_date']
            year = str(datetime.fromtimestamp(timestamp, tz=timezone.utc).year)

        # Use 'TBD' for games without a release date
        if not year:
            year = 'TBD'

        # Get title
        title = details.get('name', 'Unknown')

        # Sanitize title for filesystem
        title = sanitize_filename(title)

        # Generate filename
        return f"{title} ({year}).md"

    def get_poster_url(self, details: Dict) -> Optional[str]:
        """
        Get full poster URL from IGDB cover data.

        Returns:
            Full URL to poster image, or None if no cover available
        """
        if 'cover' not in details or not details['cover']:
            return None

        image_id = details['cover'].get('image_id')
        if not image_id:
            return None

        # Use cover_big (227x320) for good quality at 200-300px width
        return f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
