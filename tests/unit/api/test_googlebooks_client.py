"""Unit tests for lib/api/googlebooks_client.py"""

import json

import pytest
import responses

from lib.api.googlebooks_client import GoogleBooksClient

SEARCH_URL = 'https://www.googleapis.com/books/v1/volumes'
VOLUME_URL = 'https://www.googleapis.com/books/v1/volumes/B1hSG45JCX4C'


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def gb_client():
    """Create a Google Books client with a test API key."""
    return GoogleBooksClient('test_google_books_key')


@pytest.fixture
def book_search_payload(api_responses_dir):
    with open(api_responses_dir / 'googlebooks_search.json') as f:
        return json.load(f)


@pytest.fixture
def book_volume_payload(api_responses_dir):
    with open(api_responses_dir / 'googlebooks_volume.json') as f:
        return json.load(f)


# ============================================================================
# search()
# ============================================================================

@responses.activate
def test_search_success(gb_client, book_search_payload):
    responses.add(responses.GET, SEARCH_URL, json=book_search_payload, status=200)

    results = gb_client.search('Dune')

    # Two "Dune" editions collapse into one; "Dune Messiah" stays separate.
    assert len(results) == 2
    assert results[0]['id'] == 'B1hSG45JCX4C'
    assert results[0]['title'] == 'Dune'
    assert results[0]['author'] == 'Frank Herbert'
    assert results[0]['first_publish_year'] == 1990
    assert 'Fiction' in results[0]['subjects']
    assert results[1]['title'] == 'Dune Messiah'


@responses.activate
def test_search_uses_earliest_year_across_editions(gb_client):
    """The representative keeps the first edition's id but the earliest year."""
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={'items': [
            {'id': 'rep', 'volumeInfo': {
                'title': 'Dune', 'authors': ['Frank Herbert'], 'publishedDate': '1990'}},
            {'id': 'older', 'volumeInfo': {
                'title': 'Dune', 'authors': ['Frank Herbert'], 'publishedDate': '1965'}},
        ]},
        status=200,
    )

    results = gb_client.search('Dune')

    assert len(results) == 1
    assert results[0]['id'] == 'rep'  # most-relevant edition drives get_details
    assert results[0]['first_publish_year'] == 1965  # earliest edition's year


@responses.activate
def test_get_details_reports_earliest_year_after_search(gb_client):
    """get_details reports the earliest year recorded by search(), not the
    representative volume's own (later) publishedDate."""
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={'items': [
            {'id': 'rep', 'volumeInfo': {
                'title': 'Dune', 'authors': ['Frank Herbert'], 'publishedDate': '1990'}},
            {'id': 'older', 'volumeInfo': {
                'title': 'Dune', 'authors': ['Frank Herbert'], 'publishedDate': '1965'}},
        ]},
        status=200,
    )
    responses.add(
        responses.GET,
        'https://www.googleapis.com/books/v1/volumes/rep',
        json={'id': 'rep', 'volumeInfo': {
            'title': 'Dune', 'authors': ['Frank Herbert'], 'publishedDate': '1990'}},
        status=200,
    )

    gb_client.search('Dune')
    details = gb_client.get_details('rep')

    assert details['first_publish_year'] == 1965


@responses.activate
def test_search_sends_api_key_and_intitle(gb_client, book_search_payload):
    responses.add(responses.GET, SEARCH_URL, json=book_search_payload, status=200)

    gb_client.search('Dune')

    request_url = responses.calls[0].request.url
    assert 'key=test_google_books_key' in request_url
    assert 'intitle' in request_url
    assert 'country=US' in request_url


@responses.activate
def test_search_cover_url_is_https_without_edge_curl(gb_client, book_search_payload):
    responses.add(responses.GET, SEARCH_URL, json=book_search_payload, status=200)

    results = gb_client.search('Dune')

    cover = results[0]['cover_url']
    assert cover.startswith('https://')
    assert 'edge=curl' not in cover


@responses.activate
def test_search_no_items_key(gb_client):
    responses.add(responses.GET, SEARCH_URL, json={'totalItems': 0}, status=200)

    assert gb_client.search('zzzzz_no_such_book') == []


@responses.activate
def test_search_multiple_authors_joined(gb_client):
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={'items': [{
            'id': 'x1',
            'volumeInfo': {
                'title': 'Collab',
                'authors': ['Alice', 'Bob', 'Carol'],
                'publishedDate': '2020',
            },
        }]},
        status=200,
    )

    results = gb_client.search('Collab')

    assert results[0]['author'] == 'Alice & Bob & Carol'


@responses.activate
def test_search_missing_author_defaults_to_unknown(gb_client):
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={'items': [{
            'id': 'x1',
            'volumeInfo': {'title': 'Anonymous Book', 'publishedDate': '1800'},
        }]},
        status=200,
    )

    results = gb_client.search('Anonymous Book')

    assert results[0]['author'] == 'Unknown'


@responses.activate
def test_search_missing_publish_date_year_is_none(gb_client):
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={'items': [{
            'id': 'x1',
            'volumeInfo': {'title': 'Undated', 'authors': ['A']},
        }]},
        status=200,
    )

    results = gb_client.search('Undated')

    assert results[0]['first_publish_year'] is None


@responses.activate
def test_search_caps_subjects_to_five(gb_client):
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={'items': [{
            'id': 'x1',
            'volumeInfo': {
                'title': 'Tagged Book',
                'authors': ['Author'],
                'publishedDate': '2000',
                'categories': [f'cat-{i}' for i in range(20)],
            },
        }]},
        status=200,
    )

    results = gb_client.search('Tagged Book')

    assert len(results[0]['subjects']) == 5


@responses.activate
def test_search_non_transient_error_raises_immediately(gb_client):
    """A non-transient status (e.g. bad key -> 403) is not retried."""
    responses.add(responses.GET, SEARCH_URL, json={'error': 'forbidden'}, status=403)

    with pytest.raises(Exception) as excinfo:
        gb_client.search('Dune')

    assert 'Google Books API error' in str(excinfo.value)
    assert len(responses.calls) == 1  # no retries for a 403


@responses.activate
def test_search_retries_transient_error_then_succeeds(gb_client, book_search_payload, mocker):
    """Google Books' intermittent 503s are retried until one succeeds."""
    sleep = mocker.patch('lib.api.googlebooks_client.time.sleep')
    responses.add(responses.GET, SEARCH_URL, json={'error': 'unavailable'}, status=503)
    responses.add(responses.GET, SEARCH_URL, json={'error': 'unavailable'}, status=503)
    responses.add(responses.GET, SEARCH_URL, json=book_search_payload, status=200)

    results = gb_client.search('Dune')

    assert len(results) == 2  # succeeded on the third attempt
    assert len(responses.calls) == 3
    assert sleep.call_count == 2  # backed off before each retry


@responses.activate
def test_search_retries_exhausted_raises(gb_client, mocker):
    """After MAX_RETRIES transient failures the error is surfaced."""
    mocker.patch('lib.api.googlebooks_client.time.sleep')
    for _ in range(gb_client.MAX_RETRIES + 1):
        responses.add(responses.GET, SEARCH_URL, json={'error': 'unavailable'}, status=503)

    with pytest.raises(Exception) as excinfo:
        gb_client.search('Dune')

    assert 'Google Books API error' in str(excinfo.value)
    assert len(responses.calls) == gb_client.MAX_RETRIES + 1


# ============================================================================
# get_details()
# ============================================================================

@responses.activate
def test_get_details_success(gb_client, book_volume_payload):
    responses.add(responses.GET, VOLUME_URL, json=book_volume_payload, status=200)

    details = gb_client.get_details('B1hSG45JCX4C')

    assert details['id'] == 'B1hSG45JCX4C'
    assert details['title'] == 'Dune'
    assert details['author'] == 'Frank Herbert'
    assert 'desert planet' in details['description']
    # HTML tags are stripped from the description.
    assert '<b>' not in details['description']
    assert details['first_publish_year'] == 1990
    assert 'Science Fiction' in details['subjects']
    assert details['cover_url'].startswith('https://')
    assert details['info_link'].startswith('https://books.google.com')


@responses.activate
def test_get_details_missing_description(gb_client):
    responses.add(
        responses.GET,
        VOLUME_URL,
        json={'id': 'B1hSG45JCX4C', 'volumeInfo': {
            'title': 'Bare', 'authors': ['A'], 'publishedDate': '2001',
        }},
        status=200,
    )

    details = gb_client.get_details('B1hSG45JCX4C')

    assert details['description'] == ''


@responses.activate
def test_get_details_no_authors(gb_client):
    responses.add(
        responses.GET,
        VOLUME_URL,
        json={'id': 'B1hSG45JCX4C', 'volumeInfo': {
            'title': 'Anonymous Work', 'publishedDate': '1850',
        }},
        status=200,
    )

    details = gb_client.get_details('B1hSG45JCX4C')

    assert details['author'] == 'Unknown'


@responses.activate
def test_get_details_no_image_links(gb_client):
    responses.add(
        responses.GET,
        VOLUME_URL,
        json={'id': 'B1hSG45JCX4C', 'volumeInfo': {
            'title': 'No Cover', 'authors': ['A'], 'publishedDate': '2001',
        }},
        status=200,
    )

    details = gb_client.get_details('B1hSG45JCX4C')

    assert details['cover_url'] is None


@responses.activate
def test_get_details_prefers_largest_cover(gb_client):
    responses.add(
        responses.GET,
        VOLUME_URL,
        json={'id': 'B1hSG45JCX4C', 'volumeInfo': {
            'title': 'Big Cover', 'authors': ['A'], 'publishedDate': '2001',
            'imageLinks': {
                'smallThumbnail': 'http://x/small',
                'thumbnail': 'http://x/thumb',
                'large': 'http://x/large',
            },
        }},
        status=200,
    )

    details = gb_client.get_details('B1hSG45JCX4C')

    assert details['cover_url'] == 'https://x/large'


@responses.activate
def test_get_details_http_error_raises(gb_client):
    responses.add(responses.GET, VOLUME_URL, json={'error': 'not found'}, status=404)

    with pytest.raises(Exception) as excinfo:
        gb_client.get_details('B1hSG45JCX4C')

    assert 'Google Books API error' in str(excinfo.value)


@responses.activate
def test_get_details_retries_transient_error_then_succeeds(gb_client, book_volume_payload, mocker):
    """get_details shares the retry helper, so it recovers from a transient 503."""
    mocker.patch('lib.api.googlebooks_client.time.sleep')
    responses.add(responses.GET, VOLUME_URL, json={'error': 'unavailable'}, status=503)
    responses.add(responses.GET, VOLUME_URL, json=book_volume_payload, status=200)

    details = gb_client.get_details('B1hSG45JCX4C')

    assert details['title'] == 'Dune'
    assert len(responses.calls) == 2


# ============================================================================
# _extract_year()
# ============================================================================

@pytest.mark.parametrize("published,expected", [
    ('1965', 1965),
    ('1965-08', 1965),
    ('1965-08-01', 1965),
    ('', None),
    ('no digits here', None),
])
def test_extract_year(gb_client, published, expected):
    assert gb_client._extract_year(published) == expected


# ============================================================================
# format_note_content()
# ============================================================================

def test_format_note_content_full(gb_client):
    details = {
        'id': 'B1hSG45JCX4C',
        'title': 'Dune',
        'author': 'Frank Herbert',
        'description': 'A desert planet.',
        'subjects': ['Fiction'],
        'first_publish_year': 1990,
        'info_link': 'https://books.google.com/books/about/Dune.html?id=B1hSG45JCX4C',
    }

    content = gb_client.format_note_content(details)

    assert content.startswith('---')
    assert 'collection: "[[Books]]"' in content
    assert '## Links' in content
    assert 'books.google.com' in content
    assert '## Description' in content
    assert 'A desert planet.' in content
    assert 'By [[Frank Herbert]].' in content


def test_format_note_content_no_description(gb_client):
    details = {
        'id': 'x',
        'title': 'Bare Book',
        'author': 'Author',
        'description': '',
        'subjects': [],
        'first_publish_year': 2000,
        'info_link': 'https://books.google.com/x',
    }

    content = gb_client.format_note_content(details)

    assert 'By [[Author]].' in content
    assert content.count('## Description') == 1


def test_format_note_content_no_info_link_renders_not_available(gb_client):
    details = {
        'title': 'Anon',
        'author': 'A',
        'description': 'd',
        'subjects': [],
        'first_publish_year': 1900,
        'info_link': '',
    }

    content = gb_client.format_note_content(details)

    assert 'Not available' in content


# ============================================================================
# get_filename()
# ============================================================================

def test_get_filename_basic(gb_client):
    details = {'author': 'Frank Herbert', 'title': 'Dune', 'first_publish_year': 1965}

    assert gb_client.get_filename(details) == 'Frank Herbert - Dune (1965).md'


def test_get_filename_missing_year_uses_tbd(gb_client):
    details = {'author': 'Author', 'title': 'Unknown Year Book', 'first_publish_year': None}

    assert gb_client.get_filename(details) == 'Author - Unknown Year Book (TBD).md'


def test_get_filename_sanitizes_special_characters(gb_client):
    details = {'author': 'A/B:C', 'title': 'Title: Subtitle?', 'first_publish_year': 1999}

    assert gb_client.get_filename(details) == 'A-B -C - Title - Subtitle (1999).md'


def test_get_filename_multiple_authors(gb_client):
    details = {'author': 'Alice & Bob', 'title': 'Joint Work', 'first_publish_year': 2020}

    assert gb_client.get_filename(details) == 'Alice & Bob - Joint Work (2020).md'


# ============================================================================
# get_poster_url()
# ============================================================================

def test_get_poster_url(gb_client):
    details = {'cover_url': 'https://books.google.com/cover.jpg'}

    assert gb_client.get_poster_url(details) == 'https://books.google.com/cover.jpg'


def test_get_poster_url_missing(gb_client):
    assert gb_client.get_poster_url({}) is None


def test_get_poster_url_none(gb_client):
    assert gb_client.get_poster_url({'cover_url': None}) is None


# ============================================================================
# prompt_disambiguation()
# ============================================================================

def test_prompt_disambiguation_select(gb_client, mocker):
    results = [
        {'title': 'Dune', 'author': 'Frank Herbert', 'first_publish_year': 1965},
        {'title': 'Dune Messiah', 'author': 'Frank Herbert', 'first_publish_year': 1969},
    ]

    inputs = iter(['2'])
    mocker.patch('lib.api.googlebooks_client.get_user_input', lambda prompt: next(inputs))

    selected = gb_client.prompt_disambiguation('Dune', results)

    assert selected['title'] == 'Dune Messiah'


def test_prompt_disambiguation_skip(gb_client, mocker):
    results = [{'title': 'Dune', 'author': 'Frank Herbert', 'first_publish_year': 1965}]

    inputs = iter(['0'])
    mocker.patch('lib.api.googlebooks_client.get_user_input', lambda prompt: next(inputs))

    assert gb_client.prompt_disambiguation('Dune', results) is None


def test_prompt_disambiguation_invalid_then_valid(gb_client, mocker, capsys):
    results = [{'title': 'Dune', 'author': 'Frank Herbert', 'first_publish_year': 1965}]

    inputs = iter(['99', 'abc', '1'])
    mocker.patch('lib.api.googlebooks_client.get_user_input', lambda prompt: next(inputs))

    selected = gb_client.prompt_disambiguation('Dune', results)

    assert selected is not None
    captured = capsys.readouterr()
    assert 'between 0 and 1' in captured.out
    assert 'valid number' in captured.out


def test_prompt_disambiguation_displays_tbd_for_missing_year(gb_client, mocker, capsys):
    results = [{'title': 'Future Book', 'author': 'A', 'first_publish_year': None}]

    inputs = iter(['1'])
    mocker.patch('lib.api.googlebooks_client.get_user_input', lambda prompt: next(inputs))

    gb_client.prompt_disambiguation('Future Book', results)

    captured = capsys.readouterr()
    assert '(TBD)' in captured.out
