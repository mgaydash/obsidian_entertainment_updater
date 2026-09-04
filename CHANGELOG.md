# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Breaking:** new notes declare a collection (`collection: "[[Movies]]"`) instead of carrying a media type tag. `tags` now hold only facets — genre, play-mode, and so on — and the key is omitted entirely when a note has none.
- **Breaking:** media type is read from `collection` rather than from `movie`/`series`/`game`/`album`/`book` tags or `#hashtag` text. Matching is case-insensitive and tolerates a wikilink alias (`[[Movies|Films]]`) or folder prefix.
- `PosterDownloader.get_media_type_from_tags()` renamed to `get_media_type()`, since it no longer reads tags.

### Added
- `build_frontmatter()` in `lib/obsidian_utils.py`, shared by all four API clients.

### Fixed
- Poster downloading silently found no files in a vault migrated to `collection`: detection still required the retired type tags, so every note returned no media type.

## [1.3.0] - 2026-07-20

### Added
- MIT `LICENSE`.
- GitHub Actions CI running the test suite on Python 3.9–3.13 and `ruff` linting.
- Packaging metadata: project URLs, Trove classifiers, and keywords.
- `ruff` configuration for linting.
- This changelog.

### Changed
- Ignore `*.zip` (vault backups) in git.

### Removed
- Stale `TEST_FIXES.md` / `TESTING_SUMMARY.md` working notes; current testing docs live in `CLAUDE.md`.

## [1.2.1] - 2026-07-20

### Fixed
- Retry transient Google Books API errors (5xx / 429 and network failures) with exponential backoff instead of failing the whole book lookup on a single hiccup.

### Documentation
- README now documents albums (MusicBrainz) and books (Google Books), the `GOOGLE_BOOKS_API_KEY`, and the `posters --media-type` filter.

## [1.2.0] - 2026-07-19

### Changed
- Switched the book metadata source from Open Library to Google Books: a single fast search request instead of up to five, with reliable descriptions, categories, and covers. Editions are de-duplicated by title/author, keeping the most-relevant edition while reporting the earliest edition's year.

### Note
- Books now require a `GOOGLE_BOOKS_API_KEY` (previously no credentials were needed).

## [1.1.0] - 2026-07-11

### Added
- `add` accepts titles as positional arguments in addition to reading them from stdin.

## [1.0.0] - 2026-07-11

Initial release.

### Added
- `add` command to create Obsidian notes from titles for movies and TV (TMDB), games (IGDB), albums (MusicBrainz), and books (Open Library).
- Automatic poster / cover-art download, resizing, and embedding when notes are created.
- `posters` command to retroactively download covers for existing notes, with a `--media-type` filter.
- Year-based auto-disambiguation and exact-title matching.
- Genre → tag translation via `genre_mappings.yaml`.
- `configure` command to persist a default vault path.
- Optional vault backup via `-b/--backup`.

[Unreleased]: https://github.com/mgaydash/obsidian-tools/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/mgaydash/obsidian-tools/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/mgaydash/obsidian-tools/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/mgaydash/obsidian-tools/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/mgaydash/obsidian-tools/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/mgaydash/obsidian-tools/releases/tag/v1.0.0
