"""MusicBrainz API client for music albums."""

from typing import Dict, List, Optional

import musicbrainzngs

from ..obsidian_utils import (
    build_frontmatter,
    format_wikilink,
    get_user_input,
    sanitize_filename,
    translate_genre_tag,
)
from .base import MediaAPIClient


class MusicBrainzClient(MediaAPIClient):
    """MusicBrainz API client implementation."""

    def __init__(self):
        """Initialize MusicBrainz client."""
        # Set user agent (required by MusicBrainz API)
        musicbrainzngs.set_useragent(
            "ObsidianTools",
            "1.0",
            "https://github.com/anthropics/obsidian-tools"
        )

    def search(self, title: str) -> List[Dict]:
        """Search MusicBrainz for an album title."""
        try:
            # Search for official releases with the given title
            # Query filters: status:official ensures we get proper releases
            # primarytype:album includes all album types (Album, EP, Live, etc.)
            result = musicbrainzngs.search_releases(
                release=title,
                status='official',
                primarytype='album',
                limit=25
            )

            releases = result.get('release-list', [])

            # Standardize the results format
            standardized = []
            for release in releases:
                # Get primary artist name
                artist_credit = release.get('artist-credit', [])
                artist_name = 'Various Artists'
                if artist_credit:
                    # Join multiple artists with ' & '
                    artist_name = ' & '.join([
                        ac.get('artist', {}).get('name', 'Unknown')
                        for ac in artist_credit
                        if isinstance(ac, dict) and 'artist' in ac
                    ])

                standardized.append({
                    'id': release.get('id'),  # MusicBrainz ID (MBID)
                    'title': release.get('title', 'Unknown'),
                    'artist': artist_name,
                    'date': release.get('date', ''),  # Format: YYYY-MM-DD, YYYY-MM, or YYYY
                    'disambiguation': release.get('disambiguation', ''),
                    'type': release.get('release-group', {}).get('primary-type', 'Album'),
                    'secondary-types': release.get('release-group', {}).get('secondary-type-list', [])
                })

            return standardized

        except musicbrainzngs.WebServiceError as e:
            raise Exception(f"MusicBrainz API error: {e}")

    def get_details(self, media_id: str) -> Dict:
        """Get detailed information from MusicBrainz."""
        try:
            # Get release details with expanded information
            result = musicbrainzngs.get_release_by_id(
                media_id,
                includes=['artists', 'labels', 'release-groups', 'tags']
            )

            release = result.get('release', {})

            # Get artist credits
            artist_credit = release.get('artist-credit', [])
            artist_name = 'Various Artists'
            if artist_credit:
                artist_name = ' & '.join([
                    ac.get('artist', {}).get('name', 'Unknown')
                    for ac in artist_credit
                    if isinstance(ac, dict) and 'artist' in ac
                ])

            # Get label information
            label_info = release.get('label-info-list', [])
            label = 'Independent'
            if label_info and len(label_info) > 0:
                label_obj = label_info[0].get('label')
                if label_obj:
                    label = label_obj.get('name', 'Independent')

            # Get release group for type information
            release_group = release.get('release-group', {})
            primary_type = release_group.get('primary-type', 'Album')
            secondary_types = release_group.get('secondary-type-list', [])

            # Get tags from release-group (more reliable than release tags)
            tags = []
            rg_tags = release_group.get('tag-list', [])
            if rg_tags:
                # Sort by vote count and take top tags
                sorted_tags = sorted(rg_tags, key=lambda t: int(t.get('count', 0)), reverse=True)
                tags = [t['name'] for t in sorted_tags if int(t.get('count', 0)) > 5][:5]

            return {
                'id': release.get('id'),
                'title': release.get('title', 'Unknown'),
                'artist': artist_name,
                'date': release.get('date', ''),
                'label': label,
                'primary_type': primary_type,
                'secondary_types': secondary_types,
                'tags': tags,
                'disambiguation': release.get('disambiguation', '')
            }

        except musicbrainzngs.WebServiceError as e:
            raise Exception(f"MusicBrainz API error: {e}")

    def prompt_disambiguation(self, title: str, results: List[Dict]) -> Optional[Dict]:
        """Show results and prompt user to select the correct one."""
        print(f"\n🎵 Multiple results found for '{title}':")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            album_title = result.get('title', 'Unknown')
            artist = result.get('artist', 'Unknown')
            year = result.get('date', 'TBD')[:4] if result.get('date') else 'TBD'

            # Get album type
            album_type = result.get('type', 'Album').upper()
            secondary = result.get('secondary-types', [])
            if secondary:
                album_type = f"{album_type}/{'/'.join(secondary).upper()}"

            disambiguation = result.get('disambiguation', '')
            disambig_text = f" [{disambiguation}]" if disambiguation else ""

            print(f"{idx}. {album_title} - {artist} ({year}) [{album_type}]{disambig_text}")
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
        # Get MusicBrainz URL
        mbid = details.get('id')
        mb_url = f"https://musicbrainz.org/release/{mbid}" if mbid else "Not available"

        # Build tags list
        tags = []

        # Add type-based tags
        secondary_types = details.get('secondary_types', [])

        # Add secondary type tags (EP, Live, Compilation, etc.)
        for sec_type in secondary_types:
            type_tag = sec_type.lower().replace(' ', '-')
            if type_tag not in tags:
                tags.append(type_tag)

        # Add genre tags from MusicBrainz folksonomy
        mb_tags = details.get('tags', [])
        for tag in mb_tags:
            genre_tag = translate_genre_tag(tag)
            if genre_tag and genre_tag not in tags:
                tags.append(genre_tag)

        # Build description
        artist = details.get('artist', 'Unknown')
        label = details.get('label', 'Independent')

        # Create basic description
        description = f"By {format_wikilink(artist)}. Released by {format_wikilink(label)}."

        # Format the content
        content = f"""{build_frontmatter('Albums', tags)}

## Links
{mb_url}

## Description
{description}
"""
        return content

    def get_filename(self, details: Dict) -> str:
        """Generate filename in 'Artist - Album (Year).md' format."""
        # Get artist and title
        artist = details.get('artist', 'Unknown')
        title = details.get('title', 'Unknown')

        # Get year from date field
        date = details.get('date', '')
        year = 'TBD'
        if date:
            # Date can be YYYY-MM-DD, YYYY-MM, or YYYY
            year = date[:4]

        # Sanitize for filesystem
        artist = sanitize_filename(artist)
        title = sanitize_filename(title)

        # Generate filename: "Artist - Album (Year).md"
        return f"{artist} - {title} ({year}).md"

    def get_poster_url(self, details: Dict) -> Optional[str]:
        """
        Get full poster URL from Cover Art Archive.

        Returns:
            Full URL to cover art image, or None if no cover available
        """
        mbid = details.get('id')
        if not mbid:
            return None

        # Cover Art Archive provides direct access to front cover
        # This will return the front cover image directly
        # If no cover exists, the download will fail gracefully
        return f"https://coverartarchive.org/release/{mbid}/front"
