"""Unit tests for lib/api/musicbrainz_client.py"""

import json

import pytest

from lib.api.musicbrainz_client import MusicBrainzClient

# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mb_client():
    """Create a MusicBrainz client."""
    return MusicBrainzClient()


@pytest.fixture
def album_search_results(api_responses_dir):
    """Load album search results from fixture."""
    with open(api_responses_dir / 'musicbrainz_album_search.json') as f:
        return json.load(f)


@pytest.fixture
def album_details(api_responses_dir):
    """Load album details from fixture."""
    with open(api_responses_dir / 'musicbrainz_album_details.json') as f:
        return json.load(f)


# ============================================================================
# Tests for __init__
# ============================================================================

def test_mb_client_init(mb_client, mocker):
    """Test MusicBrainz client initialization sets user agent."""
    # Verify client was created
    assert mb_client is not None


def test_mb_client_sets_user_agent(mocker):
    """Test that client sets user agent on initialization."""
    mock_set_useragent = mocker.patch('musicbrainzngs.set_useragent')

    MusicBrainzClient()

    # Verify set_useragent was called
    mock_set_useragent.assert_called_once_with(
        'ObsidianTools',
        '1.0',
        'https://github.com/anthropics/obsidian-tools'
    )


# ============================================================================
# Tests for search()
# ============================================================================

def test_search_success(mb_client, album_search_results, mocker):
    """Test successful album search."""
    mock_search = mocker.patch(
        'musicbrainzngs.search_releases',
        return_value=album_search_results
    )

    results = mb_client.search('Abbey Road')

    assert len(results) == 2
    assert results[0]['title'] == 'Abbey Road'
    assert results[0]['artist'] == 'The Beatles'
    assert results[0]['date'] == '1969-09-26'

    # Verify search parameters
    mock_search.assert_called_once_with(
        release='Abbey Road',
        status='official',
        primarytype='album',
        limit=25
    )


def test_search_no_results(mb_client, mocker):
    """Test search with no results."""
    mocker.patch(
        'musicbrainzngs.search_releases',
        return_value={'release-list': []}
    )

    results = mb_client.search('NonexistentAlbum12345')

    assert len(results) == 0


def test_search_api_error(mb_client, mocker):
    """Test search with API error."""
    import musicbrainzngs

    mocker.patch(
        'musicbrainzngs.search_releases',
        side_effect=musicbrainzngs.WebServiceError('API error')
    )

    with pytest.raises(Exception) as excinfo:
        mb_client.search('Test Album')

    assert 'MusicBrainz API error' in str(excinfo.value)


def test_search_artist_credit_joining(mb_client, mocker):
    """Test that multiple artists are joined with '&'."""
    mock_result = {
        'release-list': [
            {
                'id': 'test-id',
                'title': 'Collaboration Album',
                'artist-credit': [
                    {'artist': {'name': 'Artist One'}},
                    {'artist': {'name': 'Artist Two'}},
                    {'artist': {'name': 'Artist Three'}}
                ],
                'date': '2020-01-01'
            }
        ]
    }

    mocker.patch('musicbrainzngs.search_releases', return_value=mock_result)

    results = mb_client.search('Collaboration Album')

    assert results[0]['artist'] == 'Artist One & Artist Two & Artist Three'


def test_search_various_artists(mb_client, mocker):
    """Test that albums without artist credit show 'Various Artists'."""
    mock_result = {
        'release-list': [
            {
                'id': 'test-id',
                'title': 'Compilation',
                'artist-credit': [],
                'date': '2020-01-01'
            }
        ]
    }

    mocker.patch('musicbrainzngs.search_releases', return_value=mock_result)

    results = mb_client.search('Compilation')

    assert results[0]['artist'] == 'Various Artists'


def test_search_standardizes_format(mb_client, album_search_results, mocker):
    """Test that search results are standardized."""
    mocker.patch('musicbrainzngs.search_releases', return_value=album_search_results)

    results = mb_client.search('Abbey Road')

    # Verify standardized fields
    result = results[0]
    assert 'id' in result
    assert 'title' in result
    assert 'artist' in result
    assert 'date' in result
    assert 'disambiguation' in result
    assert 'type' in result
    assert 'secondary-types' in result


@pytest.mark.parametrize("date_input", [
    "1969-09-26",  # Full date
    "1969-09",     # Month precision
    "1969",        # Year only
    "",            # No date
])
def test_search_date_formats(mb_client, mocker, date_input):
    """Test that search handles various date formats."""
    mock_result = {
        'release-list': [
            {
                'id': 'test-id',
                'title': 'Test Album',
                'artist-credit': [{'artist': {'name': 'Test Artist'}}],
                'date': date_input
            }
        ]
    }

    mocker.patch('musicbrainzngs.search_releases', return_value=mock_result)

    results = mb_client.search('Test Album')

    assert results[0]['date'] == date_input


# ============================================================================
# Tests for get_details()
# ============================================================================

def test_get_details_success(mb_client, album_details, mocker):
    """Test getting album details."""
    mocker.patch(
        'musicbrainzngs.get_release_by_id',
        return_value=album_details
    )

    details = mb_client.get_details('a3b7f0e5-7e7d-4e4f-8e5c-1a2b3c4d5e6f')

    assert details['id'] == 'a3b7f0e5-7e7d-4e4f-8e5c-1a2b3c4d5e6f'
    assert details['title'] == 'Abbey Road'
    assert details['artist'] == 'The Beatles'
    assert details['date'] == '1969-09-26'
    assert details['label'] == 'Apple Records'


def test_get_details_includes_expanded_info(mb_client, mocker):
    """Test that get_details requests expanded information."""
    mock_get = mocker.patch(
        'musicbrainzngs.get_release_by_id',
        return_value={'release': {'id': 'test', 'title': 'Test'}}
    )

    mb_client.get_details('test-id')

    # Verify includes parameter
    mock_get.assert_called_once_with(
        'test-id',
        includes=['artists', 'labels', 'release-groups', 'tags']
    )


def test_get_details_api_error(mb_client, mocker):
    """Test get_details with API error."""
    import musicbrainzngs

    mocker.patch(
        'musicbrainzngs.get_release_by_id',
        side_effect=musicbrainzngs.WebServiceError('API error')
    )

    with pytest.raises(Exception) as excinfo:
        mb_client.get_details('test-id')

    assert 'MusicBrainz API error' in str(excinfo.value)


def test_get_details_no_label(mb_client, mocker):
    """Test details with no label information."""
    mock_result = {
        'release': {
            'id': 'test-id',
            'title': 'Test Album',
            'artist-credit': [{'artist': {'name': 'Test Artist'}}],
            'date': '2020-01-01',
            'label-info-list': [],
            'release-group': {}
        }
    }

    mocker.patch('musicbrainzngs.get_release_by_id', return_value=mock_result)

    details = mb_client.get_details('test-id')

    assert details['label'] == 'Independent'


def test_get_details_tags_filtered_by_vote_count(mb_client, mocker):
    """Test that tags are filtered by vote count > 5."""
    mock_result = {
        'release': {
            'id': 'test-id',
            'title': 'Test Album',
            'artist-credit': [{'artist': {'name': 'Test Artist'}}],
            'date': '2020-01-01',
            'release-group': {
                'tag-list': [
                    {'name': 'rock', 'count': 10},
                    {'name': 'pop', 'count': 8},
                    {'name': 'obscure', 'count': 2},  # Should be filtered out
                    {'name': 'unpopular', 'count': 1},  # Should be filtered out
                ]
            }
        }
    }

    mocker.patch('musicbrainzngs.get_release_by_id', return_value=mock_result)

    details = mb_client.get_details('test-id')

    # Only tags with count > 5 should be included
    assert 'rock' in details['tags']
    assert 'pop' in details['tags']
    assert 'obscure' not in details['tags']
    assert 'unpopular' not in details['tags']


def test_get_details_tags_sorted_by_vote_count(mb_client, mocker):
    """Test that tags are sorted by vote count."""
    mock_result = {
        'release': {
            'id': 'test-id',
            'title': 'Test Album',
            'artist-credit': [{'artist': {'name': 'Test Artist'}}],
            'date': '2020-01-01',
            'release-group': {
                'tag-list': [
                    {'name': 'least', 'count': 6},
                    {'name': 'most', 'count': 20},
                    {'name': 'middle', 'count': 10},
                ]
            }
        }
    }

    mocker.patch('musicbrainzngs.get_release_by_id', return_value=mock_result)

    details = mb_client.get_details('test-id')

    # Tags should be sorted by count descending
    assert details['tags'][0] == 'most'
    assert details['tags'][1] == 'middle'
    assert details['tags'][2] == 'least'


def test_get_details_max_five_tags(mb_client, mocker):
    """Test that maximum 5 tags are returned."""
    mock_result = {
        'release': {
            'id': 'test-id',
            'title': 'Test Album',
            'artist-credit': [{'artist': {'name': 'Test Artist'}}],
            'date': '2020-01-01',
            'release-group': {
                'tag-list': [
                    {'name': f'tag{i}', 'count': 10} for i in range(10)
                ]
            }
        }
    }

    mocker.patch('musicbrainzngs.get_release_by_id', return_value=mock_result)

    details = mb_client.get_details('test-id')

    assert len(details['tags']) == 5


def test_get_details_secondary_types(mb_client, mocker):
    """Test that secondary types are included."""
    mock_result = {
        'release': {
            'id': 'test-id',
            'title': 'Live Album',
            'artist-credit': [{'artist': {'name': 'Test Artist'}}],
            'date': '2020-01-01',
            'release-group': {
                'primary-type': 'Album',
                'secondary-type-list': ['Live', 'Compilation']
            }
        }
    }

    mocker.patch('musicbrainzngs.get_release_by_id', return_value=mock_result)

    details = mb_client.get_details('test-id')

    assert details['primary_type'] == 'Album'
    assert details['secondary_types'] == ['Live', 'Compilation']


# ============================================================================
# Tests for format_note_content()
# ============================================================================

def test_format_note_content(mb_client):
    """Test formatting album note content."""
    details = {
        'id': 'test-mbid',
        'title': 'Test Album',
        'artist': 'Test Artist',
        'date': '2020-01-01',
        'label': 'Test Records',
        'primary_type': 'Album',
        'secondary_types': [],
        'tags': ['rock', 'pop']
    }

    content = mb_client.format_note_content(details)

    # Check YAML frontmatter
    assert content.startswith('---')
    assert 'tags:' in content
    assert 'collection: "[[Albums]]"' in content

    # Check sections
    assert '## Links' in content
    assert 'musicbrainz.org/release/test-mbid' in content
    assert '## Description' in content

    # Check content
    assert 'By [[Test Artist]]' in content
    assert 'Released by [[Test Records]]' in content


def test_format_note_content_secondary_type_tags(mb_client):
    """Test that secondary types become tags."""
    details = {
        'id': 'test-mbid',
        'title': 'Live Album',
        'artist': 'Test Artist',
        'date': '2020-01-01',
        'label': 'Test Records',
        'primary_type': 'Album',
        'secondary_types': ['Live', 'Compilation'],
        'tags': []
    }

    content = mb_client.format_note_content(details)

    assert '  - live' in content
    assert '  - compilation' in content


def test_format_note_content_genre_tags(mb_client):
    """Test that MusicBrainz tags are translated to genre tags."""
    details = {
        'id': 'test-mbid',
        'title': 'Test Album',
        'artist': 'Test Artist',
        'date': '2020-01-01',
        'label': 'Test Records',
        'primary_type': 'Album',
        'secondary_types': [],
        'tags': ['rock', 'pop']  # Will be translated by translate_genre_tag
    }

    content = mb_client.format_note_content(details)

    # Tags should be included (exact format depends on translate_genre_tag)
    assert 'tags:' in content


def test_format_note_content_no_mbid(mb_client):
    """Test formatting content without MBID."""
    details = {
        'title': 'Test Album',
        'artist': 'Test Artist',
        'date': '2020-01-01',
        'label': 'Test Records',
        'primary_type': 'Album',
        'secondary_types': [],
        'tags': []
    }

    content = mb_client.format_note_content(details)

    assert 'Not available' in content


# ============================================================================
# Tests for get_filename()
# ============================================================================

def test_get_filename(mb_client):
    """Test generating album filename."""
    details = {
        'artist': 'The Beatles',
        'title': 'Abbey Road',
        'date': '1969-09-26'
    }

    filename = mb_client.get_filename(details)

    assert filename == 'The Beatles - Abbey Road (1969).md'


@pytest.mark.parametrize("date_input,expected_year", [
    ("1969-09-26", "1969"),  # Full date
    ("1969-09", "1969"),     # Month precision
    ("1969", "1969"),        # Year only
    ("", "TBD"),             # No date
])
def test_get_filename_date_formats(mb_client, date_input, expected_year):
    """Test filename with various date formats."""
    details = {
        'artist': 'Test Artist',
        'title': 'Test Album',
        'date': date_input
    }

    filename = mb_client.get_filename(details)

    assert f'({expected_year}).md' in filename


def test_get_filename_sanitizes_names(mb_client):
    """Test that filename sanitizes problematic characters."""
    details = {
        'artist': 'Artist: The Band',
        'title': 'Album/Title: Subtitle',
        'date': '2020-01-01'
    }

    filename = mb_client.get_filename(details)

    assert filename == 'Artist - The Band - Album-Title - Subtitle (2020).md'


def test_get_filename_multiple_artists(mb_client):
    """Test filename with multiple artists (joined with &)."""
    details = {
        'artist': 'Artist One & Artist Two',
        'title': 'Collaboration',
        'date': '2020-01-01'
    }

    filename = mb_client.get_filename(details)

    assert filename == 'Artist One & Artist Two - Collaboration (2020).md'


# ============================================================================
# Tests for get_poster_url()
# ============================================================================

def test_get_poster_url(mb_client):
    """Test getting poster URL for album."""
    details = {
        'id': 'a3b7f0e5-7e7d-4e4f-8e5c-1a2b3c4d5e6f',
        'title': 'Abbey Road'
    }

    url = mb_client.get_poster_url(details)

    assert url == 'https://coverartarchive.org/release/a3b7f0e5-7e7d-4e4f-8e5c-1a2b3c4d5e6f/front'


def test_get_poster_url_missing_id(mb_client):
    """Test getting poster URL when MBID is missing."""
    details = {'title': 'No ID'}

    url = mb_client.get_poster_url(details)

    assert url is None


def test_get_poster_url_none_id(mb_client):
    """Test getting poster URL when MBID is None."""
    details = {'id': None, 'title': 'No ID'}

    url = mb_client.get_poster_url(details)

    assert url is None


# ============================================================================
# Tests for prompt_disambiguation()
# ============================================================================

def test_prompt_disambiguation_select_first(mb_client, mocker):
    """Test disambiguating and selecting first result."""
    results = [
        {
            'title': 'Abbey Road',
            'artist': 'The Beatles',
            'date': '1969-09-26',
            'type': 'Album',
            'secondary-types': [],
            'disambiguation': ''
        }
    ]

    inputs = iter(['1'])
    mocker.patch('lib.api.musicbrainz_client.get_user_input', lambda prompt: next(inputs))

    result = mb_client.prompt_disambiguation('Abbey Road', results)

    assert result is not None
    assert result['title'] == 'Abbey Road'


def test_prompt_disambiguation_skip(mb_client, mocker):
    """Test disambiguating and skipping."""
    results = [{'title': 'Test', 'artist': 'Test', 'date': '2020'}]

    inputs = iter(['0'])
    mocker.patch('lib.api.musicbrainz_client.get_user_input', lambda prompt: next(inputs))

    result = mb_client.prompt_disambiguation('Test', results)

    assert result is None


def test_prompt_disambiguation_displays_secondary_types(mb_client, mocker, capsys):
    """Test that disambiguation displays secondary types."""
    results = [
        {
            'title': 'Live Album',
            'artist': 'Test Artist',
            'date': '2020-01-01',
            'type': 'Album',
            'secondary-types': ['Live', 'Compilation'],
            'disambiguation': ''
        }
    ]

    inputs = iter(['1'])
    mocker.patch('lib.api.musicbrainz_client.get_user_input', lambda prompt: next(inputs))

    mb_client.prompt_disambiguation('Live Album', results)

    captured = capsys.readouterr()
    assert '[ALBUM/LIVE/COMPILATION]' in captured.out


def test_prompt_disambiguation_displays_disambiguation_text(mb_client, mocker, capsys):
    """Test that disambiguation text is displayed."""
    results = [
        {
            'title': 'Abbey Road',
            'artist': 'The Beatles',
            'date': '1969-09-26',
            'type': 'Album',
            'secondary-types': [],
            'disambiguation': 'original UK release'
        }
    ]

    inputs = iter(['1'])
    mocker.patch('lib.api.musicbrainz_client.get_user_input', lambda prompt: next(inputs))

    mb_client.prompt_disambiguation('Abbey Road', results)

    captured = capsys.readouterr()
    assert '[original UK release]' in captured.out


def test_prompt_disambiguation_invalid_then_valid(mb_client, mocker, capsys):
    """Test handling invalid input then valid selection."""
    results = [
        {'title': 'Test', 'artist': 'Test', 'date': '2020', 'type': 'Album', 'secondary-types': []}
    ]

    inputs = iter(['99', '1'])
    mocker.patch('lib.api.musicbrainz_client.get_user_input', lambda prompt: next(inputs))

    result = mb_client.prompt_disambiguation('Test', results)

    assert result is not None
    captured = capsys.readouterr()
    assert 'between 0 and 1' in captured.out
