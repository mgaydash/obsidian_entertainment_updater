"""Unit tests for lib/poster_downloader.py"""

import json

import pytest
import responses

from lib.poster_downloader import PosterDownloader

# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def poster_downloader_tmdb(tmp_path):
    """Create poster downloader with TMDB + Google Books credentials."""
    return PosterDownloader(
        vault_path=tmp_path,
        tmdb_api_key='test_tmdb_key',
        google_books_api_key='test_google_books_key',
        poster_width=200
    )


@pytest.fixture
def poster_downloader_igdb(tmp_path):
    """Create poster downloader with IGDB credentials."""
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            'https://id.twitch.tv/oauth2/token',
            json={'access_token': 'test_token'},
            status=200
        )

        return PosterDownloader(
            vault_path=tmp_path,
            igdb_client_id='test_id',
            igdb_client_secret='test_secret',
            poster_width=200
        )


@pytest.fixture
def poster_downloader_mb(tmp_path, mocker):
    """Create poster downloader with MusicBrainz (no creds needed)."""
    # Mock set_useragent to avoid issues
    mocker.patch('musicbrainzngs.set_useragent')
    return PosterDownloader(vault_path=tmp_path, poster_width=200)


# ============================================================================
# Tests for __init__
# ============================================================================

def test_init_with_tmdb(tmp_path):
    """Test initialization with TMDB credentials."""
    pd = PosterDownloader(
        vault_path=tmp_path,
        tmdb_api_key='test_key',
        poster_width=250
    )

    assert pd.vault_path == tmp_path
    assert pd.tmdb_api_key == 'test_key'
    assert pd.poster_width == 250
    assert pd.igdb_wrapper is None


@responses.activate
def test_init_with_igdb(tmp_path):
    """Test initialization with IGDB credentials."""
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    pd = PosterDownloader(
        vault_path=tmp_path,
        igdb_client_id='test_id',
        igdb_client_secret='test_secret'
    )

    assert pd.igdb_client_id == 'test_id'
    assert pd.igdb_client_secret == 'test_secret'
    assert pd.igdb_wrapper is not None


def test_init_musicbrainz_sets_useragent(tmp_path, mocker):
    """Test that initialization sets MusicBrainz user agent."""
    mock_set_useragent = mocker.patch('musicbrainzngs.set_useragent')

    PosterDownloader(vault_path=tmp_path)

    mock_set_useragent.assert_called_once_with(
        'ObsidianTools',
        '1.0',
        'https://github.com/anthropics/obsidian-tools'
    )


# ============================================================================
# Tests for get_media_type() - collection property
# ============================================================================

def test_get_media_type_movie(poster_downloader_tmdb, tmp_path):
    """Test detecting movie from the collection property."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[Movies]]"
tags:
  - example
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'movie'


def test_get_media_type_series(poster_downloader_tmdb, tmp_path):
    """Test detecting series from the collection property."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[Series]]"
tags:
  - example
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'series'


def test_get_media_type_game(poster_downloader_tmdb, tmp_path):
    """Test detecting game from the collection property."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[Games]]"
tags:
  - example
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'game'


def test_get_media_type_album(poster_downloader_tmdb, tmp_path):
    """Test detecting album from the collection property."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[Albums]]"
tags:
  - example
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'album'


def test_get_media_type_book(poster_downloader_tmdb, tmp_path):
    """Test detecting book from the collection property."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[Books]]"
tags:
  - example
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'book'


def test_get_media_type_case_insensitive(poster_downloader_tmdb, tmp_path):
    """Test that collection matching is case insensitive."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[movies]]"
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'movie'


def test_get_media_type_with_alias(poster_downloader_tmdb, tmp_path):
    """Test that a wikilink alias is stripped before matching."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[Movies|Films]]"
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'movie'


def test_get_media_type_with_folder_prefix(poster_downloader_tmdb, tmp_path):
    """Test that a folder prefix is stripped before matching."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[Collections/Movies]]"
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'movie'


def test_get_media_type_unquoted(poster_downloader_tmdb, tmp_path):
    """Test an unquoted collection value."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: [[Games]]
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) == 'game'


def test_get_media_type_non_media_collection(poster_downloader_tmdb, tmp_path):
    """Test that a non-media collection yields no media type."""
    file = tmp_path / 'test.md'
    file.write_text("""---
collection: "[[Lookups]]"
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) is None


def test_get_media_type_no_collection(poster_downloader_tmdb, tmp_path):
    """Test file with frontmatter but no collection."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags:
  - note
  - general
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) is None


def test_get_media_type_type_tag_is_not_enough(poster_downloader_tmdb, tmp_path):
    """Test that a legacy type tag alone no longer identifies media."""
    file = tmp_path / 'test.md'
    file.write_text("""---
tags:
  - movie
  - action
---

# Content
""")

    assert poster_downloader_tmdb.get_media_type(file) is None


def test_get_media_type_no_frontmatter(poster_downloader_tmdb, tmp_path):
    """Test file with no frontmatter at all."""
    file = tmp_path / 'test.md'
    file.write_text("# Just a note\n\nSome prose.\n")

    assert poster_downloader_tmdb.get_media_type(file) is None


# ============================================================================
# Tests for already_has_poster()
# ============================================================================

def test_already_has_poster_true(poster_downloader_tmdb, tmp_path):
    """Test detecting file with existing poster."""
    file = tmp_path / 'test.md'
    file.write_text("""---
title: Test Movie
poster: [[movie.jpg]]
---

# Content
""")

    assert poster_downloader_tmdb.already_has_poster(file) is True


def test_already_has_poster_false(poster_downloader_tmdb, tmp_path):
    """Test detecting file without poster."""
    file = tmp_path / 'test.md'
    file.write_text("""---
title: Test Movie
---

# Content
""")

    assert poster_downloader_tmdb.already_has_poster(file) is False


def test_already_has_poster_empty_value(poster_downloader_tmdb, tmp_path):
    """Test that empty poster value is treated as no poster."""
    file = tmp_path / 'test.md'
    file.write_text("""---
title: Test Movie
poster: ""
---

# Content
""")

    assert poster_downloader_tmdb.already_has_poster(file) is False


# ============================================================================
# Tests for find_media_files()
# ============================================================================

def test_find_media_files(poster_downloader_tmdb, tmp_path, capsys):
    """Test finding media files in vault."""
    # Create test files
    movie1 = tmp_path / 'Movie1.md'
    movie1.write_text('---\ncollection: "[[Movies]]"\n---\n# Movie1')

    movie2 = tmp_path / 'Movie2.md'
    movie2.write_text('---\ncollection: "[[Movies]]"\nposter: [[movie2.jpg]]\n---\n# Movie2')

    series1 = tmp_path / 'Series1.md'
    series1.write_text('---\ncollection: "[[Series]]"\n---\n# Series1')

    other = tmp_path / 'Other.md'
    other.write_text('---\ncollection: "[[Lookups]]"\n---\n# Other')

    files = poster_downloader_tmdb.find_media_files()

    # Should find Movie1 and Series1, skip Movie2 (has poster) and Other (no media tag)
    assert len(files) == 2
    file_names = [f[0].name for f in files]
    assert 'Movie1.md' in file_names
    assert 'Series1.md' in file_names

    # Check output messages
    captured = capsys.readouterr()
    assert 'Movie1.md [MOVIE]' in captured.out
    assert 'Series1.md [SERIES]' in captured.out
    assert 'Skipping (already has poster): Movie2.md' in captured.out


def test_find_media_files_recursive(poster_downloader_tmdb, tmp_path):
    """Test finding files in subdirectories."""
    subdir = tmp_path / 'Movies'
    subdir.mkdir()

    movie = subdir / 'Movie.md'
    movie.write_text('---\ncollection: "[[Movies]]"\n---\n# Movie')

    files = poster_downloader_tmdb.find_media_files()

    assert len(files) == 1
    assert files[0][0].name == 'Movie.md'


# ============================================================================
# Tests for search_tmdb()
# ============================================================================

@responses.activate
def test_search_tmdb_movie(poster_downloader_tmdb):
    """Test searching TMDB for a movie."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': [{'title': 'Inception', 'id': 27205}]},
        status=200
    )

    results = poster_downloader_tmdb.search_tmdb('Inception', 'movie')

    assert len(results) == 1
    assert results[0]['title'] == 'Inception'


@responses.activate
def test_search_tmdb_series_converts_to_tv(poster_downloader_tmdb):
    """Test that 'series' is converted to 'tv' for TMDB API."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/tv',
        json={'results': [{'name': 'Loot', 'id': 156482}]},
        status=200
    )

    results = poster_downloader_tmdb.search_tmdb('Loot', 'series')

    assert len(results) == 1
    assert results[0]['name'] == 'Loot'


# ============================================================================
# Tests for search_igdb()
# ============================================================================

@responses.activate
def test_search_igdb(tmp_path):
    """Test searching IGDB for a game."""
    # Mock OAuth
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )

    pd = PosterDownloader(
        vault_path=tmp_path,
        igdb_client_id='test_id',
        igdb_client_secret='test_secret'
    )

    # Mock IGDB search
    mock_results = [{'name': 'Elden Ring', 'id': 119277}]

    pd.igdb_wrapper.api_request = lambda endpoint, query: json.dumps(mock_results).encode('utf-8')

    results = pd.search_igdb('Elden Ring')

    assert len(results) == 1
    assert results[0]['name'] == 'Elden Ring'


def test_search_igdb_no_wrapper(poster_downloader_tmdb):
    """Test IGDB search without wrapper returns empty."""
    results = poster_downloader_tmdb.search_igdb('Test')

    assert len(results) == 0


# ============================================================================
# Tests for search_musicbrainz()
# ============================================================================

def test_search_musicbrainz(poster_downloader_mb, mocker):
    """Test searching MusicBrainz for an album."""
    mock_result = {
        'release-list': [
            {
                'id': 'test-mbid',
                'title': 'Abbey Road',
                'artist-credit': [{'artist': {'name': 'The Beatles'}}],
                'date': '1969-09-26'
            }
        ]
    }

    mocker.patch('musicbrainzngs.search_releases', return_value=mock_result)

    results = poster_downloader_mb.search_musicbrainz('Abbey Road')

    assert len(results) == 1
    assert results[0]['title'] == 'Abbey Road'
    assert results[0]['artist'] == 'The Beatles'


# ============================================================================
# Tests for search_api()
# ============================================================================

@responses.activate
def test_search_api_routes_movie_to_tmdb(poster_downloader_tmdb):
    """Test that movie searches route to TMDB."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': [{'title': 'Test'}]},
        status=200
    )

    results, api_used = poster_downloader_tmdb.search_api('Test', 'movie')

    assert api_used == 'tmdb'
    assert len(results) > 0


@responses.activate
def test_search_api_routes_series_to_tmdb(poster_downloader_tmdb):
    """Test that series searches route to TMDB."""
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/tv',
        json={'results': [{'name': 'Test'}]},
        status=200
    )

    results, api_used = poster_downloader_tmdb.search_api('Test', 'series')

    assert api_used == 'tmdb'


# ============================================================================
# Tests for get_poster_url_from_result()
# ============================================================================

def test_get_poster_url_from_result_tmdb(poster_downloader_tmdb):
    """Test extracting poster URL from TMDB result."""
    result = {'poster_path': '/abc123.jpg'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'tmdb')

    assert url == 'https://image.tmdb.org/t/p/original/abc123.jpg'


def test_get_poster_url_from_result_tmdb_missing(poster_downloader_tmdb):
    """Test TMDB result without poster."""
    result = {'title': 'No Poster'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'tmdb')

    assert url is None


def test_get_poster_url_from_result_igdb(poster_downloader_tmdb):
    """Test extracting poster URL from IGDB result."""
    result = {'cover': {'image_id': 'co4thl'}}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'igdb')

    assert url == 'https://images.igdb.com/igdb/image/upload/t_cover_big/co4thl.jpg'


def test_get_poster_url_from_result_igdb_missing(poster_downloader_tmdb):
    """Test IGDB result without cover."""
    result = {'name': 'No Cover'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'igdb')

    assert url is None


def test_get_poster_url_from_result_musicbrainz(poster_downloader_tmdb):
    """Test extracting poster URL from MusicBrainz result."""
    result = {'id': 'test-mbid'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'musicbrainz')

    assert url == 'https://coverartarchive.org/release/test-mbid/front'


def test_get_poster_url_from_result_musicbrainz_missing(poster_downloader_tmdb):
    """Test MusicBrainz result without ID."""
    result = {'title': 'No ID'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'musicbrainz')

    assert url is None


def test_get_poster_url_from_result_googlebooks(poster_downloader_tmdb):
    """Test extracting cover URL from a Google Books result."""
    result = {'cover_url': 'https://books.google.com/cover.jpg'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'googlebooks')

    assert url == 'https://books.google.com/cover.jpg'


def test_get_poster_url_from_result_googlebooks_missing(poster_downloader_tmdb):
    """Test a Google Books result without a cover_url."""
    result = {'title': 'No Cover'}

    url = poster_downloader_tmdb.get_poster_url_from_result(result, 'googlebooks')

    assert url is None


@responses.activate
def test_search_googlebooks(poster_downloader_tmdb):
    """Test searching Google Books for a book."""
    responses.add(
        responses.GET,
        'https://www.googleapis.com/books/v1/volumes',
        json={'items': [{
            'id': 'vol1',
            'volumeInfo': {
                'title': 'Dune',
                'authors': ['Frank Herbert'],
                'publishedDate': '1965-08',
                'imageLinks': {
                    'thumbnail': 'http://books.google.com/books/content?id=vol1&img=1&zoom=1&edge=curl&source=gbs_api',
                },
            },
        }]},
        status=200,
    )

    results = poster_downloader_tmdb.search_googlebooks('Dune')

    assert len(results) == 1
    assert results[0]['id'] == 'vol1'
    assert results[0]['title'] == 'Dune'
    assert results[0]['author'] == 'Frank Herbert'
    assert results[0]['first_publish_year'] == 1965
    assert results[0]['cover_url'] == 'https://books.google.com/books/content?id=vol1&img=1&zoom=1&source=gbs_api'


@responses.activate
def test_search_googlebooks_dedupes_editions(poster_downloader_tmdb):
    """Editions collapse to one entry: first edition's id, earliest edition's year."""
    responses.add(
        responses.GET,
        'https://www.googleapis.com/books/v1/volumes',
        json={'items': [
            {'id': 'a', 'volumeInfo': {'title': 'Dune', 'authors': ['Frank Herbert'], 'publishedDate': '1990'}},
            {'id': 'b', 'volumeInfo': {'title': 'Dune', 'authors': ['Frank Herbert'], 'publishedDate': '1965'}},
        ]},
        status=200,
    )

    results = poster_downloader_tmdb.search_googlebooks('Dune')

    assert len(results) == 1
    assert results[0]['id'] == 'a'  # most-relevant edition
    assert results[0]['first_publish_year'] == 1965  # earliest edition's year


@responses.activate
def test_search_googlebooks_error_returns_empty(poster_downloader_tmdb):
    """Search errors should yield an empty list, not raise."""
    responses.add(
        responses.GET,
        'https://www.googleapis.com/books/v1/volumes',
        status=429,
    )

    results = poster_downloader_tmdb.search_googlebooks('Dune')

    assert results == []


@responses.activate
def test_search_api_routes_book_to_googlebooks(poster_downloader_tmdb):
    """Book searches should route to Google Books."""
    responses.add(
        responses.GET,
        'https://www.googleapis.com/books/v1/volumes',
        json={'items': []},
        status=200,
    )

    results, api_used = poster_downloader_tmdb.search_api('Dune', 'book')

    assert api_used == 'googlebooks'
    assert results == []


# ============================================================================
# Tests for prompt_disambiguation()
# ============================================================================

def test_prompt_disambiguation_movie(poster_downloader_tmdb, mocker):
    """Test disambiguating movie results."""
    results = [
        {'title': 'Movie 1', 'release_date': '2020-01-01', 'overview': 'Test movie'},
        {'title': 'Movie 2', 'release_date': '2021-01-01', 'overview': 'Another movie'}
    ]

    inputs = iter(['1'])
    mocker.patch('lib.poster_downloader.get_user_input', lambda prompt: next(inputs))

    result = poster_downloader_tmdb.prompt_disambiguation('Movie', results, 'movie', 'tmdb')

    assert result is not None
    assert result['title'] == 'Movie 1'


def test_prompt_disambiguation_displays_emoji(poster_downloader_tmdb, mocker, capsys):
    """Test that disambiguation displays appropriate emoji."""
    results = [{'title': 'Test', 'release_date': '2020-01-01', 'overview': 'Test'}]

    inputs = iter(['1'])
    mocker.patch('lib.poster_downloader.get_user_input', lambda prompt: next(inputs))

    poster_downloader_tmdb.prompt_disambiguation('Test', results, 'movie', 'tmdb')

    captured = capsys.readouterr()
    assert '🎬' in captured.out  # Movie emoji


def test_prompt_disambiguation_skip(poster_downloader_tmdb, mocker):
    """Test skipping disambiguation."""
    results = [{'title': 'Test', 'release_date': '2020-01-01', 'overview': 'Test'}]

    inputs = iter(['0'])
    mocker.patch('lib.poster_downloader.get_user_input', lambda prompt: next(inputs))

    result = poster_downloader_tmdb.prompt_disambiguation('Test', results, 'movie', 'tmdb')

    assert result is None


# ============================================================================
# Tests for process_file() - End-to-end workflow
# ============================================================================

@responses.activate
def test_process_file_success(poster_downloader_tmdb, tmp_path, mocker):
    """Test successful end-to-end file processing."""
    # Create test file
    file = tmp_path / 'Inception (2010).md'
    file.write_text('---\ntags: [movie]\n---\n# Inception')

    # Mock TMDB search
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={
            'results': [
                {
                    'title': 'Inception',
                    'release_date': '2010-07-16',
                    'poster_path': '/test.jpg'
                }
            ]
        },
        status=200
    )

    # Mock poster download
    responses.add(
        responses.GET,
        'https://image.tmdb.org/t/p/original/test.jpg',
        body=b'fake image data',
        status=200
    )

    # Mock image processing (PIL)

    from PIL import Image
    test_img = Image.new('RGB', (200, 300), color='red')
    mocker.patch('PIL.Image.open', return_value=test_img)

    result = poster_downloader_tmdb.process_file(file, 'movie')

    assert result is True
    # The poster file may not actually exist due to mocking, but the code path ran.


@responses.activate
def test_process_file_no_results(poster_downloader_tmdb, tmp_path, capsys):
    """Test processing file with no search results."""
    file = tmp_path / 'Unknown Movie (2020).md'
    file.write_text('---\ntags: [movie]\n---\n# Unknown')

    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': []},
        status=200
    )

    result = poster_downloader_tmdb.process_file(file, 'movie')

    assert result is False
    captured = capsys.readouterr()
    assert 'No results found' in captured.out


@responses.activate
def test_process_file_year_filtering(poster_downloader_tmdb, tmp_path, mocker, capsys):
    """Test that file processing filters by year."""
    file = tmp_path / 'Movie (2020).md'
    file.write_text('---\ntags: [movie]\n---\n# Movie')

    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={
            'results': [
                {'title': 'Movie', 'release_date': '2020-01-01', 'poster_path': '/test.jpg'},
                {'title': 'Movie', 'release_date': '2019-01-01', 'poster_path': '/test2.jpg'}
            ]
        },
        status=200
    )

    # Mock the rest of the process
    mocker.patch('lib.poster_downloader.download_and_resize_poster', return_value=True)
    mocker.patch('lib.poster_downloader.update_frontmatter_with_poster', return_value=True)

    poster_downloader_tmdb.process_file(file, 'movie')

    captured = capsys.readouterr()
    assert 'Detected year: 2020' in captured.out
    assert 'Filtered to 1 result(s) matching year 2020' in captured.out


@responses.activate
def test_process_file_exact_match_auto_select(poster_downloader_tmdb, tmp_path, mocker, capsys):
    """Test that exact title match is auto-selected."""
    file = tmp_path / 'Loot (2022).md'
    file.write_text('---\ntags: [series]\n---\n# Loot')

    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/tv',
        json={
            'results': [
                {'name': 'Loot', 'first_air_date': '2022-06-24', 'poster_path': '/test.jpg'},
                {'name': 'Loot - Blood Treasure', 'first_air_date': '2022-03-15', 'poster_path': '/test2.jpg'}
            ]
        },
        status=200
    )

    # Mock the rest
    mocker.patch('lib.poster_downloader.download_and_resize_poster', return_value=True)
    mocker.patch('lib.poster_downloader.update_frontmatter_with_poster', return_value=True)

    poster_downloader_tmdb.process_file(file, 'series')

    captured = capsys.readouterr()
    assert 'Auto-selected exact title match' in captured.out


@responses.activate
def test_process_file_no_poster_available(poster_downloader_tmdb, tmp_path, capsys):
    """Test processing file when no poster is available."""
    file = tmp_path / 'Movie (2020).md'
    file.write_text('---\ntags: [movie]\n---\n# Movie')

    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={
            'results': [
                {'title': 'Movie', 'release_date': '2020-01-01', 'poster_path': None}
            ]
        },
        status=200
    )

    result = poster_downloader_tmdb.process_file(file, 'movie')

    assert result is False
    captured = capsys.readouterr()
    assert 'No poster available' in captured.out
