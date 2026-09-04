"""Unit tests for lib/api/tmdb_client.py"""

import json

import pytest
import responses

from lib.api.tmdb_client import TMDBClient

# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def tmdb_client():
    """Create a TMDB client for movies."""
    return TMDBClient('test_api_key', 'movie')


@pytest.fixture
def tmdb_tv_client():
    """Create a TMDB client for TV shows."""
    return TMDBClient('test_api_key', 'tv')


@pytest.fixture
def movie_search_results(api_responses_dir):
    """Load movie search results from fixture."""
    with open(api_responses_dir / 'tmdb_movie_search.json') as f:
        return json.load(f)


@pytest.fixture
def movie_details(api_responses_dir):
    """Load movie details from fixture."""
    with open(api_responses_dir / 'tmdb_movie_details.json') as f:
        return json.load(f)


@pytest.fixture
def tv_search_results(api_responses_dir):
    """Load TV search results from fixture."""
    with open(api_responses_dir / 'tmdb_tv_search.json') as f:
        return json.load(f)


@pytest.fixture
def tv_details(api_responses_dir):
    """Load TV details from fixture."""
    with open(api_responses_dir / 'tmdb_tv_details.json') as f:
        return json.load(f)


# ============================================================================
# Tests for __init__
# ============================================================================

def test_tmdb_client_init_movie():
    """Test TMDB client initialization for movies."""
    client = TMDBClient('my_api_key', 'movie')

    assert client.api_key == 'my_api_key'
    assert client.media_type == 'movie'
    assert client.tmdb_base_url == 'https://api.themoviedb.org/3'


def test_tmdb_client_init_tv():
    """Test TMDB client initialization for TV."""
    client = TMDBClient('my_api_key', 'tv')

    assert client.api_key == 'my_api_key'
    assert client.media_type == 'tv'
    assert client.tmdb_base_url == 'https://api.themoviedb.org/3'


# ============================================================================
# Tests for search()
# ============================================================================

@responses.activate
def test_search_movie_success(tmdb_client, movie_search_results):
    """Test successful movie search."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json=movie_search_results,
        status=200
    )

    results = tmdb_client.search('Inception')

    assert len(results) == 2
    assert results[0]['title'] == 'Inception'
    assert results[0]['release_date'] == '2010-07-16'


@responses.activate
def test_search_tv_success(tmdb_tv_client, tv_search_results):
    """Test successful TV show search."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/tv',
        json=tv_search_results,
        status=200
    )

    results = tmdb_tv_client.search('Loot')

    assert len(results) == 2
    assert results[0]['name'] == 'Loot'
    assert results[0]['first_air_date'] == '2022-06-24'


@responses.activate
def test_search_no_results(tmdb_client):
    """Test search with no results."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': [], 'total_results': 0},
        status=200
    )

    results = tmdb_client.search('NonexistentMovie12345')

    assert len(results) == 0


@responses.activate
def test_search_http_error(tmdb_client):
    """Test search with HTTP error."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        status=401
    )

    with pytest.raises(Exception):
        tmdb_client.search('Inception')


@responses.activate
def test_search_includes_api_key(tmdb_client):
    """Test that search includes API key in request."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': []},
        status=200
    )

    tmdb_client.search('Test')

    # Verify API key was sent
    assert len(responses.calls) == 1
    assert 'api_key=test_api_key' in responses.calls[0].request.url


# ============================================================================
# Tests for get_details()
# ============================================================================

@responses.activate
def test_get_details_movie_success(tmdb_client, movie_details):
    """Test getting movie details."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/movie/27205',
        json=movie_details,
        status=200
    )

    details = tmdb_client.get_details('27205')

    assert details['id'] == 27205
    assert details['title'] == 'Inception'
    assert 'credits' in details
    assert 'external_ids' in details


@responses.activate
def test_get_details_tv_success(tmdb_tv_client, tv_details):
    """Test getting TV show details."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/tv/156482',
        json=tv_details,
        status=200
    )

    details = tmdb_tv_client.get_details('156482')

    assert details['id'] == 156482
    assert details['name'] == 'Loot'
    assert 'credits' in details


@responses.activate
def test_get_details_appends_credits_and_external_ids(tmdb_client):
    """Test that get_details appends credits and external_ids."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/movie/123',
        json={'id': 123},
        status=200
    )

    tmdb_client.get_details('123')

    # Verify append_to_response was sent (comma is URL-encoded as %2C)
    assert len(responses.calls) == 1
    assert 'append_to_response=' in responses.calls[0].request.url
    assert 'credits' in responses.calls[0].request.url
    assert 'external_ids' in responses.calls[0].request.url


@responses.activate
def test_get_details_http_error(tmdb_client):
    """Test get_details with HTTP error."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/movie/999999',
        status=404
    )

    with pytest.raises(Exception):
        tmdb_client.get_details('999999')


# ============================================================================
# Tests for format_cast_as_wikilink()
# ============================================================================

def test_format_cast_as_wikilink(tmdb_client):
    """Test formatting cast member as wikilink."""
    cast_member = {
        'name': 'Leonardo DiCaprio',
        'character': 'Cobb'
    }

    result = tmdb_client.format_cast_as_wikilink(cast_member)

    assert result == 'Cobb ([[Leonardo DiCaprio]])'


def test_format_cast_as_wikilink_missing_character(tmdb_client):
    """Test formatting cast with missing character."""
    cast_member = {'name': 'Actor Name'}

    result = tmdb_client.format_cast_as_wikilink(cast_member)

    assert result == 'Unknown ([[Actor Name]])'


def test_format_cast_as_wikilink_missing_name(tmdb_client):
    """Test formatting cast with missing name."""
    cast_member = {'character': 'Character Name'}

    result = tmdb_client.format_cast_as_wikilink(cast_member)

    assert result == 'Character Name ([[Unknown]])'


# ============================================================================
# Tests for format_note_content() - Movies
# ============================================================================

def test_format_note_content_movie(tmdb_client, movie_details):
    """Test formatting movie note content."""
    content = tmdb_client.format_note_content(movie_details)

    # Check YAML frontmatter
    assert content.startswith('---')
    assert 'tags:' in content
    assert 'collection: "[[Movies]]"' in content

    # Check sections
    assert '## Links' in content
    assert 'imdb.com/title/tt1375666' in content
    assert '## Description' in content

    # Check content
    assert 'Directed by [[Christopher Nolan]]' in content
    assert 'Cobb ([[Leonardo DiCaprio]])' in content
    assert 'corporate secrets' in content


def test_format_note_content_movie_genre_tags(tmdb_client, movie_details):
    """Test that movie genres are translated to tags."""
    content = tmdb_client.format_note_content(movie_details)

    # Should include movie tag and genres
    assert 'collection: "[[Movies]]"' in content
    # Genres should be translated by translate_genre_tag
    # (exact tags depend on genre_mappings.yaml)


def test_format_note_content_movie_missing_imdb(tmdb_client):
    """Test formatting movie without IMDB ID."""
    details = {
        'title': 'Test Movie',
        'overview': 'A test movie',
        'credits': {'cast': [], 'crew': []},
        'external_ids': {},
        'genres': []
    }

    content = tmdb_client.format_note_content(details)

    assert 'Not available' in content


def test_format_note_content_movie_missing_director(tmdb_client):
    """Test formatting movie without director."""
    details = {
        'title': 'Test Movie',
        'overview': 'A test movie',
        'credits': {'cast': [], 'crew': []},
        'external_ids': {'imdb_id': 'tt1234567'},
        'genres': []
    }

    content = tmdb_client.format_note_content(details)

    assert 'Directed by Unknown' in content


def test_format_note_content_movie_missing_cast(tmdb_client):
    """Test formatting movie without cast."""
    details = {
        'title': 'Test Movie',
        'overview': 'A test movie',
        'credits': {
            'cast': [],
            'crew': [{'name': 'Director Name', 'job': 'Director'}]
        },
        'external_ids': {'imdb_id': 'tt1234567'},
        'genres': []
    }

    content = tmdb_client.format_note_content(details)

    # Should still have "Starring" but empty
    assert 'Directed by [[Director Name]]. Starring .' in content


# ============================================================================
# Tests for format_note_content() - TV Shows
# ============================================================================

def test_format_note_content_tv(tmdb_tv_client, tv_details):
    """Test formatting TV show note content."""
    content = tmdb_tv_client.format_note_content(tv_details)

    # Check YAML frontmatter
    assert content.startswith('---')
    assert 'tags:' in content
    assert 'collection: "[[Series]]"' in content

    # Check sections
    assert '## Links' in content
    assert 'imdb.com/title/tt15398010' in content
    assert '## Description' in content

    # Check content - should have "Created by" not "Directed by"
    assert 'Created by [[Alan Yang]]' in content
    assert 'Molly Novak ([[Maya Rudolph]])' in content


def test_format_note_content_tv_missing_creator(tmdb_tv_client):
    """Test formatting TV show without creator."""
    details = {
        'name': 'Test Show',
        'overview': 'A test show',
        'created_by': [],
        'credits': {'cast': []},
        'external_ids': {'imdb_id': 'tt1234567'},
        'genres': []
    }

    content = tmdb_tv_client.format_note_content(details)

    assert 'Created by Unknown' in content


# ============================================================================
# Tests for get_filename() - Movies
# ============================================================================

def test_get_filename_movie(tmdb_client, movie_details):
    """Test generating movie filename."""
    filename = tmdb_client.get_filename(movie_details)

    assert filename == 'Inception (2010).md'


def test_get_filename_movie_sanitizes_title(tmdb_client):
    """Test that movie filename sanitizes problematic characters."""
    details = {
        'title': 'Movie: The Subtitle',
        'release_date': '2020-01-01'
    }

    filename = tmdb_client.get_filename(details)

    assert filename == 'Movie - The Subtitle (2020).md'


def test_get_filename_movie_missing_year(tmdb_client):
    """Test movie filename without release date."""
    details = {'title': 'Test Movie', 'release_date': ''}

    with pytest.raises(ValueError) as excinfo:
        tmdb_client.get_filename(details)

    assert 'release year' in str(excinfo.value)


# ============================================================================
# Tests for get_filename() - TV Shows
# ============================================================================

def test_get_filename_tv(tmdb_tv_client, tv_details):
    """Test generating TV show filename."""
    filename = tmdb_tv_client.get_filename(tv_details)

    assert filename == 'Loot (2022).md'


def test_get_filename_tv_sanitizes_title(tmdb_tv_client):
    """Test that TV filename sanitizes problematic characters."""
    details = {
        'name': 'Show/Name: Subtitle',
        'first_air_date': '2021-03-15'
    }

    filename = tmdb_tv_client.get_filename(details)

    assert filename == 'Show-Name - Subtitle (2021).md'


def test_get_filename_tv_missing_year(tmdb_tv_client):
    """Test TV filename without first air date."""
    details = {'name': 'Test Show', 'first_air_date': ''}

    with pytest.raises(ValueError) as excinfo:
        tmdb_tv_client.get_filename(details)

    assert 'release year' in str(excinfo.value)


# ============================================================================
# Tests for get_poster_url()
# ============================================================================

def test_get_poster_url_movie(tmdb_client, movie_details):
    """Test getting poster URL for movie."""
    url = tmdb_client.get_poster_url(movie_details)

    assert url == 'https://image.tmdb.org/t/p/original/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg'


def test_get_poster_url_tv(tmdb_tv_client, tv_details):
    """Test getting poster URL for TV show."""
    url = tmdb_tv_client.get_poster_url(tv_details)

    assert url == 'https://image.tmdb.org/t/p/original/loot_poster.jpg'


def test_get_poster_url_missing(tmdb_client):
    """Test getting poster URL when poster_path is missing."""
    details = {'id': 123, 'title': 'No Poster'}

    url = tmdb_client.get_poster_url(details)

    assert url is None


def test_get_poster_url_null(tmdb_client):
    """Test getting poster URL when poster_path is null."""
    details = {'id': 123, 'title': 'No Poster', 'poster_path': None}

    url = tmdb_client.get_poster_url(details)

    assert url is None


# ============================================================================
# Tests for prompt_disambiguation()
# ============================================================================

def test_prompt_disambiguation_select_first(tmdb_client, movie_search_results, monkeypatch):
    """Test disambiguating and selecting first result."""
    # Mock user input to select first option
    inputs = iter(['1'])
    monkeypatch.setattr('lib.api.tmdb_client.get_user_input', lambda prompt: next(inputs))

    result = tmdb_client.prompt_disambiguation('Inception', movie_search_results['results'])

    assert result is not None
    assert result['title'] == 'Inception'
    assert result['release_date'] == '2010-07-16'


def test_prompt_disambiguation_select_second(tmdb_client, movie_search_results, monkeypatch):
    """Test disambiguating and selecting second result."""
    inputs = iter(['2'])
    monkeypatch.setattr('lib.api.tmdb_client.get_user_input', lambda prompt: next(inputs))

    result = tmdb_client.prompt_disambiguation('Inception', movie_search_results['results'])

    assert result is not None
    assert result['title'] == 'Inception: The Documentary'


def test_prompt_disambiguation_skip(tmdb_client, movie_search_results, monkeypatch):
    """Test disambiguating and skipping."""
    inputs = iter(['0'])
    monkeypatch.setattr('lib.api.tmdb_client.get_user_input', lambda prompt: next(inputs))

    result = tmdb_client.prompt_disambiguation('Inception', movie_search_results['results'])

    assert result is None


def test_prompt_disambiguation_invalid_then_valid(tmdb_client, movie_search_results, monkeypatch, capsys):
    """Test handling invalid input then valid selection."""
    inputs = iter(['99', '1'])  # Invalid, then valid
    monkeypatch.setattr('lib.api.tmdb_client.get_user_input', lambda prompt: next(inputs))

    result = tmdb_client.prompt_disambiguation('Inception', movie_search_results['results'])

    assert result is not None
    # Check error message was printed
    captured = capsys.readouterr()
    assert 'between 0 and 2' in captured.out


def test_prompt_disambiguation_non_numeric_then_valid(tmdb_client, movie_search_results, monkeypatch, capsys):
    """Test handling non-numeric input then valid selection."""
    inputs = iter(['abc', '1'])  # Non-numeric, then valid
    monkeypatch.setattr('lib.api.tmdb_client.get_user_input', lambda prompt: next(inputs))

    result = tmdb_client.prompt_disambiguation('Inception', movie_search_results['results'])

    assert result is not None
    # Check error message was printed
    captured = capsys.readouterr()
    assert 'valid number' in captured.out


def test_prompt_disambiguation_tv_shows(tmdb_tv_client, tv_search_results, monkeypatch, capsys):
    """Test disambiguation displays TV label."""
    inputs = iter(['1'])
    monkeypatch.setattr('lib.api.tmdb_client.get_user_input', lambda prompt: next(inputs))

    result = tmdb_tv_client.prompt_disambiguation('Loot', tv_search_results['results'])

    assert result is not None
    # Check TV label was displayed
    captured = capsys.readouterr()
    assert '[TV]' in captured.out
