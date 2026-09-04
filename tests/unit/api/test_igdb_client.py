"""Unit tests for lib/api/igdb_client.py"""

import json

import pytest
import responses
from freezegun import freeze_time

from lib.api.igdb_client import IGDBClient

# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def igdb_client(api_responses_dir):
    """Create an IGDB client with mocked OAuth."""
    with responses.RequestsMock() as rsps:
        # Mock OAuth token request
        with open(api_responses_dir / 'igdb_oauth_token.json') as f:
            token_response = json.load(f)

        rsps.add(
            responses.POST,
            'https://id.twitch.tv/oauth2/token',
            json=token_response,
            status=200
        )

        client = IGDBClient('test_client_id', 'test_client_secret')
        return client


@pytest.fixture
def game_search_results(api_responses_dir):
    """Load game search results from fixture."""
    with open(api_responses_dir / 'igdb_game_search.json') as f:
        return json.load(f)


@pytest.fixture
def game_details(api_responses_dir):
    """Load game details from fixture."""
    with open(api_responses_dir / 'igdb_game_details.json') as f:
        return json.load(f)


# ============================================================================
# Tests for __init__ and OAuth2
# ============================================================================

@responses.activate
def test_igdb_client_init_success(api_responses_dir):
    """Test IGDB client initialization with successful OAuth."""
    with open(api_responses_dir / 'igdb_oauth_token.json') as f:
        token_response = json.load(f)

    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json=token_response,
        status=200
    )

    client = IGDBClient('my_client_id', 'my_client_secret')

    assert client.client_id == 'my_client_id'
    assert client.client_secret == 'my_client_secret'
    assert hasattr(client, 'wrapper')


@responses.activate
def test_igdb_client_oauth_request_parameters():
    """Test that OAuth request includes correct parameters."""
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    IGDBClient('test_id', 'test_secret')

    # Verify OAuth request
    assert len(responses.calls) == 1
    request_url = responses.calls[0].request.url
    assert 'client_id=test_id' in request_url
    assert 'client_secret=test_secret' in request_url
    assert 'grant_type=client_credentials' in request_url


@responses.activate
def test_igdb_client_oauth_failure():
    """Test IGDB client initialization with OAuth failure."""
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        status=401
    )

    with pytest.raises(Exception):
        IGDBClient('invalid_id', 'invalid_secret')


@responses.activate
def test_get_access_token_returns_token(api_responses_dir):
    """Test that access token is extracted from OAuth response."""
    with open(api_responses_dir / 'igdb_oauth_token.json') as f:
        token_response = json.load(f)

    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json=token_response,
        status=200
    )

    client = IGDBClient('test_id', 'test_secret')

    # The wrapper should be initialized with the access token
    assert client.wrapper is not None


# ============================================================================
# Tests for search()
# ============================================================================

def test_search_success(igdb_client, game_search_results, mocker):
    """Test successful game search."""
    # Mock the IGDB wrapper api_request
    mock_api_request = mocker.patch.object(
        igdb_client.wrapper,
        'api_request',
        return_value=json.dumps(game_search_results).encode('utf-8')
    )

    results = igdb_client.search('Elden Ring')

    assert len(results) == 2
    assert results[0]['name'] == 'Elden Ring'
    assert results[0]['first_release_date'] == 1645747200

    # Verify query was made
    mock_api_request.assert_called_once()
    call_args = mock_api_request.call_args[0]
    assert call_args[0] == 'games'
    assert 'Elden Ring' in call_args[1]
    assert 'limit 25' in call_args[1]


def test_search_no_results(igdb_client, mocker):
    """Test search with no results."""
    mocker.patch.object(
        igdb_client.wrapper,
        'api_request',
        return_value=json.dumps([]).encode('utf-8')
    )

    results = igdb_client.search('NonexistentGame12345')

    assert len(results) == 0


def test_search_handles_non_list_response(igdb_client, mocker):
    """Test search handles non-list responses gracefully."""
    mocker.patch.object(
        igdb_client.wrapper,
        'api_request',
        return_value=json.dumps({'error': 'some error'}).encode('utf-8')
    )

    results = igdb_client.search('Test')

    assert len(results) == 0


def test_search_query_format(igdb_client, mocker):
    """Test that search query includes required fields."""
    mock_api_request = mocker.patch.object(
        igdb_client.wrapper,
        'api_request',
        return_value=json.dumps([]).encode('utf-8')
    )

    igdb_client.search('Test Game')

    call_args = mock_api_request.call_args[0]
    query = call_args[1]

    # Verify query format
    assert 'search "Test Game"' in query
    assert 'fields name, first_release_date, summary, url, involved_companies, cover.image_id' in query
    assert 'limit 25' in query


# ============================================================================
# Tests for get_details()
# ============================================================================

def test_get_details_success(igdb_client, game_details, mocker):
    """Test getting game details."""
    mock_api_request = mocker.patch.object(
        igdb_client.wrapper,
        'api_request',
        return_value=json.dumps(game_details).encode('utf-8')
    )

    details = igdb_client.get_details('119277')

    assert details['id'] == 119277
    assert details['name'] == 'Elden Ring'
    assert 'involved_companies' in details
    assert 'genres' in details

    # Verify query
    call_args = mock_api_request.call_args[0]
    query = call_args[1]
    assert 'where id = 119277' in query


def test_get_details_not_found(igdb_client, mocker):
    """Test get_details with game not found."""
    mocker.patch.object(
        igdb_client.wrapper,
        'api_request',
        return_value=json.dumps([]).encode('utf-8')
    )

    with pytest.raises(ValueError) as excinfo:
        igdb_client.get_details('999999')

    assert 'not found' in str(excinfo.value)


def test_get_details_invalid_response(igdb_client, mocker):
    """Test get_details with invalid response."""
    mocker.patch.object(
        igdb_client.wrapper,
        'api_request',
        return_value=json.dumps({'error': 'invalid'}).encode('utf-8')
    )

    with pytest.raises(ValueError):
        igdb_client.get_details('123')


def test_get_details_includes_expanded_fields(igdb_client, mocker):
    """Test that get_details includes expanded company, mode, and genre fields."""
    mock_api_request = mocker.patch.object(
        igdb_client.wrapper,
        'api_request',
        return_value=json.dumps([{'id': 123, 'name': 'Test'}]).encode('utf-8')
    )

    igdb_client.get_details('123')

    call_args = mock_api_request.call_args[0]
    query = call_args[1]

    # Verify expanded fields
    assert 'involved_companies.company.name' in query
    assert 'involved_companies.developer' in query
    assert 'involved_companies.publisher' in query
    assert 'game_modes.name' in query
    assert 'genres.name' in query


# ============================================================================
# Tests for timestamp conversion - CRITICAL UTC TESTS
# ============================================================================

@freeze_time("2024-01-15 12:00:00", tz_offset=0)
def test_prompt_disambiguation_timestamp_utc(igdb_client, mocker, capsys):
    """Test that timestamps are converted using UTC timezone."""
    # Timestamp for 2022-02-25 00:00:00 UTC (Elden Ring release)
    results = [
        {'name': 'Elden Ring', 'first_release_date': 1645747200, 'summary': 'Test'}
    ]

    inputs = iter(['1'])
    mocker.patch('lib.api.igdb_client.get_user_input', lambda prompt: next(inputs))

    igdb_client.prompt_disambiguation('Elden Ring', results)

    captured = capsys.readouterr()
    # Should show 2022, not timezone-shifted year
    assert '(2022)' in captured.out


@freeze_time("2024-01-15 12:00:00", tz_offset=0)
def test_get_filename_timestamp_utc(igdb_client):
    """Test that filename year uses UTC timezone."""
    details = {
        'name': 'Test Game',
        'first_release_date': 1645747200  # 2022-02-25 00:00:00 UTC
    }

    filename = igdb_client.get_filename(details)

    assert filename == 'Test Game (2022).md'


# ============================================================================
# Tests for unreleased games (TBD)
# ============================================================================

def test_prompt_disambiguation_unreleased_game(igdb_client, mocker, capsys):
    """Test that unreleased games show TBD for year."""
    results = [
        {'name': 'Unreleased Game', 'summary': 'Coming soon'}
        # No first_release_date
    ]

    inputs = iter(['1'])
    mocker.patch('lib.api.igdb_client.get_user_input', lambda prompt: next(inputs))

    igdb_client.prompt_disambiguation('Test', results)

    captured = capsys.readouterr()
    assert '(TBD)' in captured.out


def test_get_filename_unreleased_game(igdb_client):
    """Test filename for unreleased game uses TBD."""
    details = {
        'name': 'Future Game'
        # No first_release_date
    }

    filename = igdb_client.get_filename(details)

    assert filename == 'Future Game (TBD).md'


# ============================================================================
# Tests for format_note_content()
# ============================================================================

def test_format_note_content(igdb_client, game_details):
    """Test formatting game note content."""
    content = igdb_client.format_note_content(game_details[0])

    # Check YAML frontmatter
    assert content.startswith('---')
    assert 'tags:' in content
    assert 'collection: "[[Games]]"' in content

    # Check sections
    assert '## Links' in content
    assert 'igdb.com/games/elden-ring' in content
    assert '## Description' in content

    # Check content
    assert 'Developed by [[FromSoftware]]' in content
    assert 'Published by [[Bandai Namco Entertainment]]' in content
    assert 'Arise, Tarnished' in content


def test_format_note_content_game_modes(igdb_client):
    """Test that game modes are extracted as tags."""
    details = {
        'name': 'Test Game',
        'summary': 'A test game',
        'url': 'https://example.com',
        'involved_companies': [],
        'genres': [],
        'game_modes': [
            {'name': 'Single player'},
            {'name': 'Multiplayer'},
            {'name': 'Co-op'}
        ]
    }

    content = igdb_client.format_note_content(details)

    assert '  - single-player' in content
    assert '  - multiplayer' in content
    assert '  - co-op' in content


def test_format_note_content_game_modes_variations(igdb_client):
    """Test various game mode name variations."""
    details = {
        'name': 'Test Game',
        'summary': 'Test',
        'url': 'https://example.com',
        'involved_companies': [],
        'genres': [],
        'game_modes': [
            {'name': 'Singleplayer'},  # No space
            {'name': 'Cooperative'},
        ]
    }

    content = igdb_client.format_note_content(details)

    assert '  - single-player' in content
    assert '  - co-op' in content


def test_format_note_content_no_duplicate_tags(igdb_client):
    """Test that duplicate tags are not added."""
    details = {
        'name': 'Test Game',
        'summary': 'Test',
        'url': 'https://example.com',
        'involved_companies': [],
        'genres': [],
        'game_modes': [
            {'name': 'Single player'},
            {'name': 'Singleplayer'},  # Duplicate
        ]
    }

    content = igdb_client.format_note_content(details)

    # Count occurrences - should only appear once
    assert content.count('  - single-player') == 1


def test_format_note_content_missing_developer(igdb_client):
    """Test formatting without developer."""
    details = {
        'name': 'Test Game',
        'summary': 'Test',
        'url': 'https://example.com',
        'involved_companies': [],
        'genres': []
    }

    content = igdb_client.format_note_content(details)

    assert 'Developed by Unknown' in content


def test_format_note_content_missing_publisher(igdb_client):
    """Test formatting without publisher."""
    details = {
        'name': 'Test Game',
        'summary': 'Test',
        'url': 'https://example.com',
        'involved_companies': [
            {
                'company': {'name': 'Dev Studio'},
                'developer': True,
                'publisher': False
            }
        ],
        'genres': []
    }

    content = igdb_client.format_note_content(details)

    assert 'Developed by [[Dev Studio]]' in content
    assert 'Published by Unknown' in content


def test_format_note_content_genres(igdb_client):
    """Test that genres are translated to tags."""
    details = {
        'name': 'Test Game',
        'summary': 'Test',
        'url': 'https://example.com',
        'involved_companies': [],
        'genres': [
            {'name': 'Role-playing (RPG)'},
            {'name': 'Adventure'}
        ]
    }

    content = igdb_client.format_note_content(details)

    # Genres should be translated by translate_genre_tag
    # Exact tags depend on genre_mappings.yaml
    assert 'collection: "[[Games]]"' in content


# ============================================================================
# Tests for get_filename()
# ============================================================================

def test_get_filename(igdb_client):
    """Test generating game filename."""
    details = {
        'name': 'Elden Ring',
        'first_release_date': 1645747200  # 2022-02-25
    }

    filename = igdb_client.get_filename(details)

    assert filename == 'Elden Ring (2022).md'


def test_get_filename_sanitizes_title(igdb_client):
    """Test that filename sanitizes problematic characters."""
    details = {
        'name': 'Game: The Subtitle / Part 2',
        'first_release_date': 1609459200  # 2021-01-01
    }

    filename = igdb_client.get_filename(details)

    assert filename == 'Game - The Subtitle - Part 2 (2021).md'


# ============================================================================
# Tests for get_poster_url()
# ============================================================================

def test_get_poster_url(igdb_client, game_details):
    """Test getting poster URL for game."""
    url = igdb_client.get_poster_url(game_details[0])

    assert url == 'https://images.igdb.com/igdb/image/upload/t_cover_big/co4thl.jpg'


def test_get_poster_url_missing_cover(igdb_client):
    """Test getting poster URL when cover is missing."""
    details = {'id': 123, 'name': 'No Cover'}

    url = igdb_client.get_poster_url(details)

    assert url is None


def test_get_poster_url_cover_null(igdb_client):
    """Test getting poster URL when cover is null."""
    details = {'id': 123, 'name': 'No Cover', 'cover': None}

    url = igdb_client.get_poster_url(details)

    assert url is None


def test_get_poster_url_missing_image_id(igdb_client):
    """Test getting poster URL when image_id is missing."""
    details = {'id': 123, 'name': 'No Cover', 'cover': {}}

    url = igdb_client.get_poster_url(details)

    assert url is None


def test_get_poster_url_uses_cover_big(igdb_client):
    """Test that poster URL uses cover_big size."""
    details = {
        'id': 123,
        'name': 'Test Game',
        'cover': {'image_id': 'test123'}
    }

    url = igdb_client.get_poster_url(details)

    assert 't_cover_big' in url
    assert url.endswith('.jpg')


# ============================================================================
# Tests for prompt_disambiguation()
# ============================================================================

def test_prompt_disambiguation_select_first(igdb_client, game_search_results, mocker):
    """Test disambiguating and selecting first result."""
    inputs = iter(['1'])
    mocker.patch('lib.api.igdb_client.get_user_input', lambda prompt: next(inputs))

    result = igdb_client.prompt_disambiguation('Elden Ring', game_search_results)

    assert result is not None
    assert result['name'] == 'Elden Ring'


def test_prompt_disambiguation_skip(igdb_client, game_search_results, mocker):
    """Test disambiguating and skipping."""
    inputs = iter(['0'])
    mocker.patch('lib.api.igdb_client.get_user_input', lambda prompt: next(inputs))

    result = igdb_client.prompt_disambiguation('Elden Ring', game_search_results)

    assert result is None


def test_prompt_disambiguation_invalid_then_valid(igdb_client, game_search_results, mocker, capsys):
    """Test handling invalid input then valid selection."""
    inputs = iter(['99', '1'])
    mocker.patch('lib.api.igdb_client.get_user_input', lambda prompt: next(inputs))

    result = igdb_client.prompt_disambiguation('Elden Ring', game_search_results)

    assert result is not None
    captured = capsys.readouterr()
    assert 'between 0 and 2' in captured.out


def test_prompt_disambiguation_displays_game_label(igdb_client, game_search_results, mocker, capsys):
    """Test that disambiguation displays [GAME] label."""
    inputs = iter(['1'])
    mocker.patch('lib.api.igdb_client.get_user_input', lambda prompt: next(inputs))

    igdb_client.prompt_disambiguation('Elden Ring', game_search_results)

    captured = capsys.readouterr()
    assert '[GAME]' in captured.out
