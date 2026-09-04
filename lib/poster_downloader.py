"""Poster downloader for Obsidian media notes."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import musicbrainzngs
import requests

from .obsidian_utils import (
    extract_title_and_year,
    filter_results_by_year,
    find_exact_title_match,
    get_user_input,
)
from .poster_utils import (
    download_and_resize_poster,
    extract_yaml_frontmatter,
    update_frontmatter_with_poster,
)

MEDIA_TYPE_BY_COLLECTION = {
    'movies': 'movie',
    'series': 'series',
    'games': 'game',
    'books': 'book',
    'albums': 'album',
}


class PosterDownloader:
    """Download and manage posters for media notes."""

    def __init__(
        self,
        vault_path: Path,
        tmdb_api_key: str = None,
        igdb_client_id: str = None,
        igdb_client_secret: str = None,
        google_books_api_key: str = None,
        poster_width: int = 200
    ):
        """
        Initialize poster downloader.

        Args:
            vault_path: Path to Obsidian vault
            tmdb_api_key: TMDB API key (optional)
            igdb_client_id: IGDB client ID (optional)
            igdb_client_secret: IGDB client secret (optional)
            google_books_api_key: Google Books API key (optional, for book covers)
            poster_width: Width to resize posters to (default: 200px)
        """
        self.vault_path = vault_path
        self.tmdb_api_key = tmdb_api_key
        self.igdb_client_id = igdb_client_id
        self.igdb_client_secret = igdb_client_secret
        self.google_books_api_key = google_books_api_key
        self.poster_width = poster_width
        self.tmdb_base_url = "https://api.themoviedb.org/3"

        # Initialize IGDB wrapper if credentials provided
        self.igdb_wrapper = None
        if igdb_client_id and igdb_client_secret:
            access_token = self._get_igdb_access_token()
            from igdb.wrapper import IGDBWrapper
            self.igdb_wrapper = IGDBWrapper(igdb_client_id, access_token)

        # Initialize MusicBrainz (no credentials needed)
        musicbrainzngs.set_useragent(
            "ObsidianTools",
            "1.0",
            "https://github.com/anthropics/obsidian-tools"
        )

    def _get_igdb_access_token(self) -> str:
        """Generate OAuth2 access token from Twitch."""
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            'client_id': self.igdb_client_id,
            'client_secret': self.igdb_client_secret,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url, params=params)
        response.raise_for_status()
        return response.json()['access_token']

    def get_media_type(self, file_path: Path) -> Optional[str]:
        """
        Get media type from the note's `collection` property.

        Collection is the note's identity — `collection: "[[Movies]]"` and so
        on — so it, not a tag, is what says which API can describe the note.

        Args:
            file_path: Path to markdown file

        Returns:
            'movie', 'series', 'game', 'album', 'book', or None if the note
            has no collection or belongs to a non-media one
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, remaining = extract_yaml_frontmatter(content)
            if not frontmatter:
                return None

            collection = frontmatter.get('collection')
            if not collection:
                return None

            # Unquoted `collection: [[Movies]]` is a nested list to YAML, not a
            # string, so flatten before treating it as a wikilink
            while isinstance(collection, list) and collection:
                collection = collection[0]

            # Strip the wikilink, plus any alias or folder prefix
            name = str(collection).strip().strip('"\'')
            if name.startswith('[[') and name.endswith(']]'):
                name = name[2:-2]
            name = name.split('|')[0].split('/')[-1].strip()

            return MEDIA_TYPE_BY_COLLECTION.get(name.lower())
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None

    def already_has_poster(self, file_path: Path) -> bool:
        """Check if the file already has a poster property in frontmatter."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, _ = extract_yaml_frontmatter(content)
            if frontmatter and 'poster' in frontmatter:
                poster_value = frontmatter['poster']
                if poster_value and str(poster_value).strip():
                    return True

            return False
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return False

    def find_media_files(self) -> List[Tuple[Path, str]]:
        """
        Find all markdown files in a media collection that need posters.

        Returns:
            List of tuples (file_path, media_type)
        """
        media_files = []

        for md_file in self.vault_path.rglob('*.md'):
            media_type = self.get_media_type(md_file)
            if not media_type:
                continue

            if self.already_has_poster(md_file):
                print(f"⊘ Skipping (already has poster): {md_file.name}")
                continue

            media_files.append((md_file, media_type))
            print(f"✓ Found: {md_file.name} [{media_type.upper()}]")

        return media_files

    def search_tmdb(self, title: str, media_type: str) -> List[Dict]:
        """
        Search TMDB for a title.

        Args:
            title: Title to search for
            media_type: 'movie' or 'series' (will be converted to 'tv' for TMDB)

        Returns:
            List of results
        """
        # Convert 'series' to 'tv' for TMDB API
        tmdb_media_type = 'tv' if media_type == 'series' else 'movie'

        url = f"{self.tmdb_base_url}/search/{tmdb_media_type}"
        params = {
            'api_key': self.tmdb_api_key,
            'query': title,
            'language': 'en-US'
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        return data.get('results', [])

    def search_igdb(self, title: str) -> List[Dict]:
        """
        Search IGDB for a game title.

        Args:
            title: Title to search for

        Returns:
            List of game results with standardized fields
        """
        if not self.igdb_wrapper:
            return []

        # IGDB uses Apicalypse query language
        query = f'''
            search "{title}";
            fields name, first_release_date, summary, url, cover.image_id;
            limit 10;
        '''

        try:
            import json
            byte_array = self.igdb_wrapper.api_request('games', query)
            results = json.loads(byte_array.decode('utf-8'))
            return results if isinstance(results, list) else []
        except Exception as e:
            print(f"❌ IGDB search error: {e}")
            return []

    def search_googlebooks(self, title: str) -> List[Dict]:
        """
        Search Google Books for a book title.

        Args:
            title: Title to search for

        Returns:
            List of book results with standardized fields (including cover_url)
        """
        try:
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {
                'q': f'intitle:{title}',
                'maxResults': 25,
                'printType': 'books',
                'country': 'US',
                'key': self.google_books_api_key,
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            representatives = {}
            order = []
            for item in data.get('items', []) or []:
                info = item.get('volumeInfo', {}) or {}

                authors = info.get('authors', []) or []
                author = ' & '.join(authors) if authors else 'Unknown'

                published = info.get('publishedDate', '') or ''
                year_match = re.search(r'\b(\d{4})\b', published)
                first_publish_year = int(year_match.group(1)) if year_match else None

                book_title = info.get('title', 'Unknown')

                # Collapse duplicate editions by (title, author): keep the first
                # (most relevant) edition but report the earliest year in the group.
                key = (book_title.lower(), author.lower())
                if key not in representatives:
                    representatives[key] = {
                        'id': item.get('id', ''),
                        'title': book_title,
                        'author': author,
                        'first_publish_year': first_publish_year,
                        'cover_url': self._googlebooks_cover_url(info.get('imageLinks')),
                    }
                    order.append(key)
                elif first_publish_year is not None:
                    rep = representatives[key]
                    if rep['first_publish_year'] is None or first_publish_year < rep['first_publish_year']:
                        rep['first_publish_year'] = first_publish_year

            return [representatives[key] for key in order]

        except Exception as e:
            print(f"❌ Google Books search error: {e}")
            return []

    @staticmethod
    def _googlebooks_cover_url(image_links: Optional[Dict]) -> Optional[str]:
        """Pick the largest available cover, force HTTPS, drop the page-curl overlay."""
        if not image_links:
            return None
        for size in ('extraLarge', 'large', 'medium', 'small', 'thumbnail', 'smallThumbnail'):
            url = image_links.get(size)
            if url:
                return url.replace('http://', 'https://').replace('&edge=curl', '')
        return None

    def search_musicbrainz(self, title: str) -> List[Dict]:
        """
        Search MusicBrainz for an album title.

        Args:
            title: Title to search for

        Returns:
            List of album results with standardized fields
        """
        try:
            result = musicbrainzngs.search_releases(
                release=title,
                status='official',
                primarytype='album',
                limit=10
            )

            releases = result.get('release-list', [])

            # Standardize the results format
            standardized = []
            for release in releases:
                # Get primary artist name
                artist_credit = release.get('artist-credit', [])
                artist_name = 'Various Artists'
                if artist_credit:
                    artist_name = ' & '.join([
                        ac.get('artist', {}).get('name', 'Unknown')
                        for ac in artist_credit
                        if isinstance(ac, dict) and 'artist' in ac
                    ])

                standardized.append({
                    'id': release.get('id'),
                    'title': release.get('title', 'Unknown'),
                    'artist': artist_name,
                    'date': release.get('date', ''),
                })

            return standardized

        except Exception as e:
            print(f"❌ MusicBrainz search error: {e}")
            return []

    def search_api(self, title: str, media_type: str) -> Tuple[List[Dict], str]:
        """
        Route search to appropriate API based on media type.

        Args:
            title: Title to search for
            media_type: 'movie', 'series', 'game', 'album', or 'book'

        Returns:
            Tuple of (results, api_used) where api_used is 'tmdb', 'igdb', 'musicbrainz',
            or 'googlebooks'
        """
        if media_type == 'game':
            return self.search_igdb(title), 'igdb'
        elif media_type == 'album':
            return self.search_musicbrainz(title), 'musicbrainz'
        elif media_type == 'book':
            return self.search_googlebooks(title), 'googlebooks'
        else:
            return self.search_tmdb(title, media_type), 'tmdb'

    def get_poster_url_from_result(self, result: Dict, api_used: str) -> Optional[str]:
        """
        Extract poster URL from API result.

        Args:
            result: API result dictionary
            api_used: 'tmdb', 'igdb', or 'musicbrainz'

        Returns:
            Full poster URL or None
        """
        if api_used == 'tmdb':
            poster_path = result.get('poster_path')
            if not poster_path:
                return None
            return f"https://image.tmdb.org/t/p/original{poster_path}"

        elif api_used == 'igdb':
            if 'cover' not in result or not result['cover']:
                return None
            image_id = result['cover'].get('image_id')
            if not image_id:
                return None
            return f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"

        elif api_used == 'musicbrainz':
            mbid = result.get('id')
            if not mbid:
                return None
            # Cover Art Archive provides direct access to front cover
            return f"https://coverartarchive.org/release/{mbid}/front"

        elif api_used == 'googlebooks':
            return result.get('cover_url')

        return None

    def prompt_disambiguation(self, title: str, results: List[Dict], media_type: str, api_used: str) -> Optional[Dict]:
        """Show results and prompt user to select the correct one."""
        emoji_map = {'movie': '🎬', 'series': '📺', 'game': '🎮', 'album': '🎵', 'book': '📚'}
        emoji = emoji_map.get(media_type, '📝')

        print(f"\n{emoji} Multiple results found for '{title}':")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            # Extract name based on API
            if api_used == 'igdb':
                name = result.get('name', 'Unknown')
                # Convert Unix timestamp to year
                year = 'TBD'
                if 'first_release_date' in result:
                    from datetime import datetime
                    timestamp = result['first_release_date']
                    year = str(datetime.fromtimestamp(timestamp).year)
                summary = result.get('summary', 'No description')[:100]
            elif api_used == 'musicbrainz':
                album_title = result.get('title', 'Unknown')
                artist = result.get('artist', 'Unknown')
                name = f"{album_title} - {artist}"
                year = result.get('date', 'TBD')[:4] if result.get('date') else 'TBD'
                summary = ""  # MusicBrainz doesn't provide album descriptions
            elif api_used == 'googlebooks':
                book_title = result.get('title', 'Unknown')
                author = result.get('author', 'Unknown')
                name = f"{book_title} - {author}"
                year = str(result.get('first_publish_year') or 'TBD')
                summary = ""
            else:  # tmdb
                name = result.get('title') or result.get('name', 'Unknown')
                year = ''
                if 'release_date' in result and result['release_date']:
                    year = result['release_date'][:4]
                elif 'first_air_date' in result and result['first_air_date']:
                    year = result['first_air_date'][:4]
                summary = result.get('overview', 'No description')[:100]

            type_label = media_type.upper()
            print(f"{idx}. {name} ({year}) [{type_label}]")
            if summary:
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

    def process_file(self, file_path: Path, media_type: str) -> bool:
        """
        Process a single file: search API, download poster, update frontmatter.

        Args:
            file_path: Path to markdown file
            media_type: 'movie', 'series', 'game', or 'album'

        Returns:
            True if successful, False if skipped or failed
        """
        # Extract title and year from filename (remove .md extension first)
        filename_without_ext = file_path.name.replace('.md', '')
        title, year = extract_title_and_year(filename_without_ext)

        print(f"\n{'='*80}")
        print(f"Processing: {file_path.name}")
        print(f"{'='*80}")

        if year:
            print(f"📅 Detected year: {year} - will use for auto-disambiguation")

        # Search API (without year in query)
        try:
            results, api_used = self.search_api(title, media_type)
        except Exception as e:
            print(f"❌ Error searching API: {e}")
            return False

        if not results:
            print(f"❌ No results found for '{title}'")
            return False

        # Filter by year if provided
        if year:
            year_filtered = filter_results_by_year(results, year, media_type)
            if year_filtered:
                results = year_filtered
                print(f"✓ Filtered to {len(results)} result(s) matching year {year}")
            else:
                print(f"⚠️  No results found for year {year}, showing all results")

        # Check for exact title match
        exact_match = find_exact_title_match(results, title, media_type)
        if exact_match:
            print("✓ Auto-selected exact title match")
            selected = exact_match
        # Handle disambiguation
        elif len(results) > 1:
            selected = self.prompt_disambiguation(title, results, media_type, api_used)
            if selected is None:
                print("⊘ Skipped by user")
                return False
        else:
            selected = results[0]
            if year:
                print(f"✓ Auto-selected the only result matching year {year}")

        # Check if poster is available
        poster_url = self.get_poster_url_from_result(selected, api_used)
        if not poster_url:
            print(f"❌ No poster available for this {media_type}")
            return False

        # Generate poster filename based on markdown filename
        poster_filename = file_path.stem + '.jpg'
        poster_file_path = file_path.parent / poster_filename

        # Download and resize poster
        print("📥 Downloading poster...")
        if not download_and_resize_poster(poster_url, poster_file_path, self.poster_width):
            return False

        print(f"✓ Poster saved: {poster_filename}")

        # Update frontmatter with wikilink
        if not update_frontmatter_with_poster(file_path, poster_filename):
            return False

        print("✓ Frontmatter updated with poster wikilink")
        print(f"✓ Successfully processed: {file_path.name}")
        return True
