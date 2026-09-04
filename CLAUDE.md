# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Maintaining This File

**IMPORTANT: Keep CLAUDE.md synchronized with the codebase.**

When making changes to the project, you MUST update this file if:
- Adding new commands, features, or API clients
- Changing project architecture or design patterns
- Modifying existing workflows or behavior
- Adding new dependencies or requirements
- Updating testing patterns or requirements
- Changing file structure or organization
- Discovering new edge cases or important implementation details
- Adding new common patterns that future developers should follow

Update the relevant sections immediately after implementing changes. This ensures CLAUDE.md remains an accurate reference for future development work. Treat CLAUDE.md updates as part of the feature implementation, not an afterthought.

**Example:** If you add a new API client for books, update:
1. Code Structure diagram (add bookdb_client.py)
2. Factory Pattern section (add 'book' media type)
3. Commands section (add book examples)
4. Common Patterns → Adding New API Clients (verify instructions are still correct)
5. Environment Variables (add any new required keys)
6. Testing section (document any new testing patterns for books API)

## Project Overview

**Obsidian Tools** - Collection of Python-based CLI tools for managing and organizing media notes (movies, TV shows, games, albums, books) in Obsidian vaults. Uses TMDB API for movies/TV, IGDB API for games, MusicBrainz for albums, and Google Books for books to fetch metadata, create notes, download cover art, and provide utilities for standardizing and enhancing your media library.

## Architecture

### Code Structure

```
lib/                              # Shared library modules
├── api/                          # API client implementations
│   ├── __init__.py              # MediaAPIFactory for routing
│   ├── base.py                  # Abstract MediaAPIClient interface
│   ├── tmdb_client.py           # TMDB implementation (movies/TV)
│   ├── igdb_client.py           # IGDB implementation (games)
│   ├── musicbrainz_client.py    # MusicBrainz implementation (albums)
│   └── googlebooks_client.py    # Google Books implementation (books)
├── backup.py                    # Vault backup utilities
├── config.py                    # Persistent user settings (JSON in XDG config dir)
├── obsidian_utils.py            # YAML, wikilinks, year extraction, disambiguation
├── poster_utils.py              # Shared poster download/resize utilities
└── poster_downloader.py         # Standalone poster command implementation

tests/                            # Test suite (398 tests)
├── conftest.py                  # Shared test fixtures
├── fixtures/                    # Test data (JSON, images, markdown)
├── unit/                        # Unit tests (~3,100 lines)
│   ├── api/                     # API client tests
│   └── test_*.py                # Module tests
└── integration/                 # Integration tests (future)

obsidian_tools.py                # Main CLI with subcommands (entry point: obsidian_tools:main)
pyproject.toml                   # Deps, build config, pytest/coverage config
genre_mappings.yaml              # Genre → tag mappings (loaded relative to lib/)
```

### Key Design Patterns

**Factory Pattern (`lib/api/__init__.py`):**
- `MediaAPIFactory.create_client(media_type)` routes to appropriate API client
- Returns TMDB client for 'movie'/'tv', IGDB client for 'game', MusicBrainz for 'album', Google Books for 'book'
- Validates environment variables (TMDB_API_KEY, IGDB_CLIENT_ID, IGDB_CLIENT_SECRET, GOOGLE_BOOKS_API_KEY)
- MusicBrainz requires no credentials; Google Books requires GOOGLE_BOOKS_API_KEY

**Abstract Base Class (`lib/api/base.py`):**
All API clients implement `MediaAPIClient` interface:
- `search(title)` - Search API for title
- `get_details(media_id)` - Fetch full details
- `prompt_disambiguation(title, results)` - Interactive selection
- `format_note_content(details)` - Generate markdown
- `get_filename(details)` - Generate "Title (Year).md" filename
- `get_poster_url(details)` - Get full poster URL from details (returns None if no poster available)

**Shared Disambiguation Logic (`lib/obsidian_utils.py`):**
- `extract_title_and_year(input)` - Extracts year from "Title (Year)" format
- `filter_results_by_year(results, year, media_type)` - Filters API results by year
- `find_exact_title_match(results, title, media_type)` - Auto-selects exact matches

This shared logic ensures consistent behavior across both 'add' and 'posters' commands.

**Shared Poster Utilities (`lib/poster_utils.py`):**
- `download_and_resize_poster(poster_url, output_path, width)` - Downloads from any URL (TMDB, IGDB, etc.), resizes, converts to JPEG
- `extract_yaml_frontmatter(content)` - Parses YAML frontmatter from markdown
- `update_frontmatter_with_poster(file_path, poster_filename)` - Updates frontmatter with poster wikilink

Used by both the integrated 'add' command poster download and the standalone 'posters' command to avoid code duplication. URL-agnostic design works with any image source.

## Commands

### Setup

Dependencies and tooling config live in `pyproject.toml` (there is no
`requirements.txt` or `pytest.ini`). Install editable so the tool runs from the
source tree — `genre_mappings.yaml` is loaded relative to `lib/` and only
resolves under an editable install:

```bash
pip install -e ".[dev]"     # runtime + test/dev deps; registers the `obsidian-tools` command

# Set environment variables
export TMDB_API_KEY='your_key'              # For movies/TV
export IGDB_CLIENT_ID='your_client_id'      # For games
export IGDB_CLIENT_SECRET='your_secret'     # For games
export GOOGLE_BOOKS_API_KEY='your_key'      # For books
```

Both `obsidian-tools <command> ...` (console entry point, `obsidian_tools:main`)
and `python obsidian_tools.py <command> ...` (from the repo root) work; examples
below use the module form but the installed command is equivalent.

### Main CLI Commands

**Configure a default vault path (persisted):**
```bash
# Save the vault path so later commands can omit it
python obsidian_tools.py configure --vault-path ~/vault

# Prompt interactively for the path (works even with piped stdin, via /dev/tty)
python obsidian_tools.py configure

# Print saved configuration
python obsidian_tools.py configure --show
```

Config is stored as JSON at `$XDG_CONFIG_HOME/obsidian-tools/config.json`
(default `~/.config/obsidian-tools/config.json`). Once set, `vault_path` is
optional on `add`/`posters`; an explicit CLI argument always overrides it.

**Add new media notes:** (media type is the positional argument; titles follow
as positional arguments or, if none are given, are read from stdin; vault path
is the `--vault-path` option, defaulting to the configured value)
```bash
# Titles as arguments; uses the configured vault path
# Automatically downloads posters for movies/TV during creation
python obsidian_tools.py add movie "Inception" "The Matrix (1999)"

# Titles from stdin (used when no title arguments are given), newline-separated
echo -e "Inception\nThe Matrix" | python obsidian_tools.py add movie

# Explicit vault path (overrides the configured one)
echo "The Matrix" | python obsidian_tools.py add movie --vault-path ~/vault

# TV shows with custom poster width
python obsidian_tools.py add tv --poster-width 300
# Then paste titles and press Ctrl+D

# Games with poster download
echo "Elden Ring" | python obsidian_tools.py add game --poster-width 200

# Books (requires GOOGLE_BOOKS_API_KEY)
echo -e "Dune\nThe Hobbit (1937)" | python obsidian_tools.py add book

# Back up the vault before adding (optional, off by default)
echo "Inception" | python obsidian_tools.py add movie -b backup.zip
```

**Download posters for existing notes (retroactive):** (options only; vault path
is the `--vault-path` option, defaulting to the configured value)
```bash
# Default: process all media types (movies, TV, games)
python obsidian_tools.py posters

# Filter by media type
python obsidian_tools.py posters --media-type game
python obsidian_tools.py posters --media-type movie

# Custom width for all types
python obsidian_tools.py posters --width 300

# Explicit vault path and a backup (both optional)
python obsidian_tools.py posters --vault-path ~/vault -b backup.zip
```

### Check syntax
```bash
python3 -m py_compile obsidian_tools.py lib/*.py lib/api/*.py
```

### Lint
Linting uses `ruff` (config in `pyproject.toml`, `[tool.ruff]`). CI runs it on
every push/PR, so run it before committing:
```bash
ruff check .          # or: uvx ruff check .
ruff check . --fix    # auto-fix import order, unused imports, etc.
```

### Continuous Integration
`.github/workflows/ci.yml` runs the test suite on Python 3.9–3.13 and `ruff check`
on every push to `main` and every pull request. Tests need no secrets (all API
calls are mocked), so CI runs without credentials.

## Testing

### Overview

The project has comprehensive test coverage with **398 test cases**. All tests must pass before committing changes.

**Test Structure:**
```
tests/
├── conftest.py                      # Shared fixtures
│                                    # (pytest/coverage config lives in pyproject.toml)
├── fixtures/                        # Test data
│   └── api_responses/*.json        # Mock API responses
├── test_cli.py                      # CLI parsing + command handlers (configure, backup, vault fallback)
├── unit/                            # Unit tests
│   ├── test_obsidian_utils.py     # Core utilities (100+ tests)
│   ├── test_poster_utils.py       # Poster download/resize
│   ├── test_backup.py             # Backup functionality
│   ├── test_config.py             # Persistent config (lib/config.py)
│   ├── test_poster_downloader.py  # Poster command workflow
│   └── api/
│       ├── test_factory.py        # MediaAPIFactory routing
│       ├── test_tmdb_client.py    # TMDB client (movies/TV)
│       ├── test_igdb_client.py    # IGDB client (games)
│       ├── test_musicbrainz_client.py  # MusicBrainz client (albums)
│       └── test_googlebooks_client.py  # Google Books client (books)
└── integration/                    # Integration tests (future)
```

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/unit/test_obsidian_utils.py -v

# Run only unit tests (fast)
pytest tests/unit/ -m unit

# Generate HTML coverage report
pytest --cov=lib --cov-report=html
# Open htmlcov/index.html to view

# Run tests without coverage (faster)
pytest --no-cov

# Quick summary without verbose output
pytest tests/unit/ --tb=no -q
```

### Writing Tests - CRITICAL REQUIREMENTS

**⚠️ MANDATORY: All new features and bug fixes MUST include tests.**

When adding or modifying code:

1. **New Features** - Write tests BEFORE or immediately after implementation:
   - Add unit tests for all new functions/methods
   - Test happy path AND edge cases
   - Mock external dependencies (APIs, file I/O)
   - Aim for 95%+ coverage on new code

2. **Bug Fixes** - Write a failing test first:
   - Create test that reproduces the bug
   - Verify test fails
   - Fix the bug
   - Verify test passes
   - This prevents regressions

3. **Refactoring** - Ensure all existing tests still pass:
   - Run full test suite before refactoring
   - Run tests frequently during refactoring
   - Update tests if behavior intentionally changes
   - Do NOT delete tests to make refactoring easier

4. **API Client Changes** - Update corresponding test fixtures:
   - Modify JSON fixtures in `tests/fixtures/api_responses/`
   - Add @responses.activate decorator for HTTP mocking
   - Test OAuth flows for authenticated APIs (IGDB)

### Critical Testing Patterns

**HTTP Mocking (responses library):**
```python
import responses

@responses.activate
def test_tmdb_search():
    responses.add(
        responses.GET,
        'https://api.themoviedb.org/3/search/movie',
        json={'results': [...]},
        status=200
    )
    # Test code that makes HTTP request
```

**OAuth Mocking (IGDB):**
```python
@responses.activate
def test_igdb_feature():
    # Mock OAuth token request FIRST
    responses.add(
        responses.POST,
        'https://id.twitch.tv/oauth2/token',
        json={'access_token': 'test_token'},
        status=200
    )
    # Then test IGDB functionality
```

**Time-Sensitive Tests (freezegun):**
```python
from freezegun import freeze_time

@freeze_time("2024-01-15 12:00:00", tz_offset=0)
def test_igdb_timestamp_conversion():
    # Test UTC timezone handling for IGDB timestamps
```

**Parametrized Tests (multiple inputs):**
```python
@pytest.mark.parametrize("input,expected", [
    ("Title (2020)", "Title"),
    ("Title", "Title"),
    ("Title (20XX)", "Title (20XX)"),
])
def test_extract_title(input, expected):
    assert extract_title_and_year(input)[0] == expected
```

### Test Coverage Requirements

| Module | Target | Status |
|--------|--------|--------|
| Core utilities (obsidian_utils.py) | 95%+ | 87% |
| API clients (api/*.py) | 95%+ | 95-100% ✓ |
| Poster utilities (poster_utils.py) | 95%+ | 94% |
| Backup (backup.py) | 100% | 100% ✓ |
| **Overall Project** | **95%** | **88%** |

### Edge Cases That MUST Be Tested

- **UTC Timezone Handling** - IGDB timestamps must use UTC (not local timezone)
- **Image Format Conversion** - RGBA → RGB, PNG → JPEG, grayscale, palette modes
- **Date Format Variations** - TMDB (YYYY-MM-DD), IGDB (Unix timestamp), MusicBrainz (YYYY, YYYY-MM, YYYY-MM-DD)
- **Year-Based Disambiguation** - "Title (2020)" auto-filtering
- **Missing Optional Fields** - Developer, publisher, director, creator = "Unknown" (not "[[Unknown]]")
- **URL Encoding** - Handle %2C and other encoded characters
- **YAML Frontmatter** - Incomplete (no closing ---), malformed, empty
- **Filename Sanitization** - Colons, slashes, question marks, special characters

### Test Maintenance

**Before Committing:**
```bash
# Verify all tests pass
pytest

# Check coverage hasn't decreased
pytest --cov=lib --cov-report=term

# Fix any failing tests - DO NOT commit with failing tests
```

**Common Issues:**
- **HTTP 400 errors** - Missing OAuth mock for IGDB tests
- **Assertion failures** - Check for YAML quoting: `poster: '[[file.jpg]]'` not `poster: [[file.jpg]]`
- **Timezone failures** - Use `freeze_time` with `tz_offset=0` for UTC tests
- **Import errors** - Ensure test imports match actual module structure

## Important Implementation Details

### Title Input (add command)

`add` takes titles from either source, via `args.titles` (`nargs='*'`):
- **Command-line arguments:** `add <media-type> "Title 1" "Title 2" ...` — used whenever `args.titles` is non-empty.
- **stdin:** when no title arguments are given, `read_titles_from_stdin()` reads one title per line until EOF (Ctrl+D).

Both paths funnel through `normalize_titles()`, which strips whitespace, drops empty entries, and de-duplicates while preserving order — so behavior is identical regardless of source.

### Year-Based Auto-Disambiguation

Both 'add' and 'posters' commands use intelligent disambiguation:

1. Extract year from input: "Inception (2010)" → title="Inception", year="2010"
2. Search API with title only (without year)
3. Filter results by year if provided
4. Check for exact title match (case-insensitive)
5. If exact match found → auto-select
6. Else if multiple results → prompt user
7. Else if single result → auto-select

**Example:** "Loot (2022)" automatically selects "Loot" over "Loot - Blood Treasure" due to exact title match.

### API Response Formats

**TMDB (movies/TV):**
- Movies use 'title' and 'release_date'
- TV uses 'name' and 'first_air_date'
- Both return 'credits' (cast/crew) and 'external_ids' (IMDB)
- Both return 'poster_path' for poster downloads (used automatically in 'add' command)

**IGDB (games):**
- Uses 'name' and 'first_release_date' (Unix timestamp)
- Returns 'involved_companies' with developer/publisher flags
- Returns 'url' instead of external_ids
- Returns 'cover.image_id' for poster downloads (used automatically in 'add' command)
- Cover art downloaded using `cover_big` size (227x320) from IGDB image CDN

**Google Books (books):**
- Requires `GOOGLE_BOOKS_API_KEY` (Google Cloud API key). Every request sends `key` and `country=US` params.
- Search endpoint: `https://www.googleapis.com/books/v1/volumes?q=intitle:{title}&maxResults=25&printType=books` — one fast request that already contains full volume metadata (title, authors, publishedDate, description, categories, imageLinks)
- Google returns one entry **per edition**, so `search()` de-duplicates by `(title, author)`, keeping the first (most relevant) edition as the representative (its `id`/`cover_url` are used). This keeps disambiguation clean and lets exact-match auto-select work.
- `first_publish_year` is set to the **earliest** year across all editions in the `(title, author)` group — the closest proxy to a first-edition year, since Google Books has no first-publication field. `search()` also stashes `representative_id → earliest_year` on the client (`self._earliest_years`) so `get_details()` can report that year for the representative volume (whose own `publishedDate` is usually later).
- Standardized search result fields: `id` (volume ID, e.g. 'B1hSG45JCX4C'), `title`, `author` (from `volumeInfo.authors`, joined with ' & '), `first_publish_year` (int, earliest across editions), `subjects` (from `volumeInfo.categories`), `cover_url`
- Volume details: `https://www.googleapis.com/books/v1/volumes/{volume_id}` — a single request with no extra author/edition lookups. Descriptions may contain simple HTML, which is stripped. Year comes from `self._earliest_years` (populated by `search()`), falling back to the volume's own `publishedDate` when called outside a search flow.
- Covers come from `volumeInfo.imageLinks` (largest of `extraLarge`→`smallThumbnail`), forced to HTTPS with the `&edge=curl` page-curl overlay stripped (returns None when the volume has no cover)
- Filename format: `Author - Title (Year).md` (matches album convention, since duplicate book titles by different authors are common)
- Collection: `collection: "[[Books]]"`

### Media Type Detection

Media type comes from the note's `collection` property, not from a tag:

| Collection | Media type |
| --- | --- |
| `[[Movies]]` | movie |
| `[[Series]]` | series |
| `[[Games]]` | game |
| `[[Albums]]` | album |
| `[[Books]]` | book |

`collection` is the note's identity — exactly one, always — so it, not a tag,
is what says which API can describe a note. Matching is case-insensitive and
strips any alias (`[[Movies|Films]]`) or folder prefix. A note in a non-media
collection, or with no collection, yields no media type.

Note: the `movie`/`series`/`game`/`album`/`book` type tags and the
`entertainment` tag were retired when the vault moved to collections; `tags`
now carry only facets (genre, play-mode, and so on).

### Poster Download Workflow

**Integrated in 'add' command (all media types):**
1. After creating note, call `client.get_poster_url(details)` to get poster URL
2. Download poster from URL (TMDB for movies/TV, IGDB for games)
3. Resize maintaining aspect ratio to specified width (default: 200px)
4. Convert to JPEG (quality=85)
5. Save as "Title (Year).jpg" in same directory as note
6. Update YAML frontmatter: `poster: [[filename.jpg]]`
7. Embed poster at beginning of content: `![[filename.jpg]]` with proper spacing

**Standalone 'posters' command (retroactive):**
1. Scan vault for files tagged 'movie', 'series', or 'game' without 'poster' property
2. Apply optional `--media-type` filter (movie, tv, game, or all)
3. Extract title and year from filename
4. Search appropriate API (TMDB for movie/tv, IGDB for games)
5. Follow same download/resize/save workflow as above

The 'posters' command supports `--media-type` filter to selectively process files. Default is 'all', which processes all media types but skips files that already have posters.

Both workflows use shared utilities from `lib/poster_utils.py`.

### Wikilink Formatting

- Cast: `Character ([[Actor Name]])`
- Director/Creator: `[[Name]]`
- Poster: `poster: [[filename.jpg]]` (in YAML, not embedded)

### Filename Sanitization

Replaces problematic characters:
- `:` → ` -`
- `/` and `\` → `-`

Applied to all generated filenames.

### Vault Backup

Backup is **opt-in** on both the `add` and `posters` commands via the `-b/--backup FILE` option (`args.backup_filename`, defaults to `None`). When the flag is omitted, the header prints `Backup: disabled`, `create_vault_backup()` is not called, and the summary omits the backup line. When a path is provided, the vault is zipped to that path before any notes are created/modified. There is no positional backup argument.

### Persistent Configuration

Persistent settings live in `lib/config.py`, stored as JSON at
`$XDG_CONFIG_HOME/obsidian-tools/config.json` (default `~/.config/obsidian-tools/config.json`).

- `get_config_path()`, `load_config()`, `save_config(dict)`, `set_value(key, value)`, `get_value(key, default)`. All reads are tolerant: a missing, malformed, or non-dict file yields `{}`.
- The `configure` subcommand (`handle_configure_command`) saves settings: `--vault-path PATH` validates the directory and persists it; with no flag it prompts via `get_user_input()` (reads `/dev/tty`, so it works with piped stdin); `--show` prints the saved config. Only `vault_path` is stored today, but the module is a generic key/value store.
- On `add`/`posters` the vault path is the **`--vault-path PATH` option** (not a positional; `add`'s positional is the media type). `resolve_vault_path(cli_value)` returns the option value if given, else the saved `vault_path`, else `None` (handlers then exit with a message pointing at `configure`). An explicit `--vault-path` always wins over the saved value.

**Testing note:** always set `XDG_CONFIG_HOME` to a `tmp_path` (via `monkeypatch.setenv`) in tests that touch config so the real `~/.config` file is never read or written.

## Environment Variables

**Required for movies/TV:**
- `TMDB_API_KEY` - Get from https://www.themoviedb.org/ (Settings > API)

**Required for games:**
- `IGDB_CLIENT_ID` - Twitch application client ID
- `IGDB_CLIENT_SECRET` - Twitch application client secret
- Setup: https://api-docs.igdb.com/#getting-started

**Required for books:**
- `GOOGLE_BOOKS_API_KEY` - Google Cloud API key with the Books API enabled
- Setup: https://console.cloud.google.com/ (enable "Books API", create an API key). The free tier allows 1,000 queries/day; the keyless/anonymous quota is a shared global bucket and is unreliable (returns HTTP 429 when exhausted), so a key is required.

**Albums (MusicBrainz):** No credentials required.

## Common Patterns

### Adding New Subcommands

1. Create handler function in `obsidian_tools.py`: `def handle_<name>_command(args):`
2. Add subparser in `main()`:
   ```python
   parser = subparsers.add_parser('<name>', help='...')
   parser.add_argument(...)
   ```
3. Route in main: `if args.command == '<name>': handle_<name>_command(args)`
4. **REQUIRED:** Add tests in `tests/test_cli.py` for argument parsing
5. **REQUIRED:** Add integration tests for command workflow

### Adding New API Clients

1. Create client in `lib/api/<name>_client.py`
2. Implement `MediaAPIClient` abstract methods
3. Add to factory in `lib/api/__init__.py`
4. Update `media_type` choices in CLI arguments
5. **REQUIRED:** Create comprehensive test file `tests/unit/api/test_<name>_client.py`:
   - Mock all HTTP requests with `@responses.activate`
   - Test search, get_details, format_note_content, get_filename, get_poster_url
   - Test edge cases: missing fields, API errors, date format handling
   - Add API response fixtures in `tests/fixtures/api_responses/`
   - Aim for 95%+ coverage

### Extending Disambiguation Logic

Shared logic in `lib/obsidian_utils.py` used by all commands. Modify `find_exact_title_match()` or `filter_results_by_year()` to affect both 'add' and 'posters' commands simultaneously.

**REQUIRED:** When modifying these functions, update tests in `tests/unit/test_obsidian_utils.py`:
- Test all media types (movie, tv, game, album, book)
- Test date format variations (especially IGDB Unix timestamps with UTC and Google Books' int `first_publish_year` parsed from `publishedDate`)
- Add parametrized tests for edge cases

### Working with Poster Utilities

Common poster functionality lives in `lib/poster_utils.py` to avoid duplication:

```python
from lib.poster_utils import download_and_resize_poster, update_frontmatter_with_poster

# Download and save poster
if download_and_resize_poster(poster_path, output_file, tmdb_api_key, width):
    # Update note's frontmatter with wikilink
    update_frontmatter_with_poster(note_file, poster_filename)
```

Both the integrated 'add' command and standalone 'posters' command use these utilities. Any changes to poster download logic should be made in `poster_utils.py` to benefit both workflows.

**REQUIRED:** When modifying poster utilities, update tests in `tests/unit/test_poster_utils.py`:
- Test all image formats (RGB, RGBA, grayscale, palette)
- Test YAML frontmatter updates (with quotes: `poster: '[[file.jpg]]'`)
- Mock HTTP requests with `@responses.activate`
