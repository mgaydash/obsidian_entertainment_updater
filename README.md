# Obsidian Tools

[![CI](https://github.com/mgaydash/obsidian-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/mgaydash/obsidian-tools/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

Collection of CLI tools for managing and organizing media notes (movies, TV shows, games, albums, books) in Obsidian vaults. Fetches metadata from TMDB (movies/TV), IGDB (games), MusicBrainz (albums), and Google Books (books), creates formatted notes, downloads posters and cover art, and provides utilities for standardizing and enhancing your media library.

## Installation

Editable install (recommended — keeps the tool runnable from the source tree
so `genre_mappings.yaml` resolves correctly):

```bash
pip install -e ".[dev]"     # runtime + test/dev dependencies
# or, for runtime only:
pip install -e .
```

This registers an `obsidian-tools` console command. Dependencies and tooling
config live in `pyproject.toml`.

## Setup

Set environment variables for the APIs you'll use. You only need the keys for
the media types you actually add — albums require no credentials:

```bash
# For movies and TV shows
export TMDB_API_KEY='your_key_here'

# For games
export IGDB_CLIENT_ID='your_client_id'
export IGDB_CLIENT_SECRET='your_client_secret'

# For books
export GOOGLE_BOOKS_API_KEY='your_key_here'
```

Where to get each:

- **TMDB** (movies/TV): https://www.themoviedb.org/ — Settings > API
- **IGDB** (games): https://api-docs.igdb.com/#getting-started
- **Google Books** (books): https://console.cloud.google.com/ — enable the "Books API", then create an API key
- **MusicBrainz** (albums): no credentials required

### Configure a default vault (optional)

Save your vault path once so you can omit it from every command:

```bash
obsidian-tools configure --vault-path ~/vault
obsidian-tools configure --show          # print saved settings
obsidian-tools configure                 # prompt interactively
```

Settings are stored at `~/.config/obsidian-tools/config.json` (respecting
`XDG_CONFIG_HOME`). After configuring, the vault path is optional on `add` and
`posters`; passing one explicitly always overrides the saved value.

## Usage

### Add Media Notes

Create new notes from titles. The media type is the positional argument;
titles can follow as arguments, or (if none are given) are read from stdin,
one per line. The vault path defaults to the configured value, and
`--vault-path` overrides it:

```bash
# Titles as arguments (uses the configured vault path)
obsidian-tools add movie "Inception (2010)" "The Matrix (1999)"

# Titles from stdin (used when no title arguments are given)
echo -e "Inception (2010)\nThe Matrix (1999)" | \
  obsidian-tools add movie

# TV shows, to an explicit vault
echo "Breaking Bad (2008)" | \
  obsidian-tools add tv --vault-path ~/vault

# Games
echo "Elden Ring (2022)" | \
  obsidian-tools add game

# Albums (no credentials required)
echo "The Dark Side of the Moon (1973)" | \
  obsidian-tools add album

# Books
echo -e "Dune\nThe Hobbit (1937)" | \
  obsidian-tools add book

# Interactive mode (paste titles, then Ctrl+D)
obsidian-tools add movie

# Back up the vault first (optional, off by default)
echo "Inception (2010)" | \
  obsidian-tools add movie -b backup.zip
```

Posters and cover art are downloaded and embedded automatically as notes are
created (for every media type that has an image available).

### Download Posters & Cover Art

Retroactively download and embed posters or cover art for existing notes
(movies, TV, games, albums, books) that don't have one yet. Uses the configured
vault path; `--vault-path` overrides it:

```bash
# Default: process every media type at 200px width
obsidian-tools posters

# Restrict to one media type (movie, tv, game, album, or book)
obsidian-tools posters --media-type book

# Custom width
obsidian-tools posters --width 300

# Explicit vault + backup (both optional)
obsidian-tools posters --vault-path ~/vault -b backup.zip
```

## Features

- **Multiple sources**: movies/TV (TMDB), games (IGDB), albums (MusicBrainz), books (Google Books)
- **Smart disambiguation**: include a year in parentheses (e.g., "Loot (2022)") for automatic matching
- **Optional backups**: pass `-b/--backup <file.zip>` to zip the vault before making changes (off by default)
- **Rich metadata**: source links, descriptions, and people (directors, cast, authors, artists) as wikilinks
- **Tag-based**: works with files tagged `movie`, `series`, `game`, `album`, or `book`

## What It Creates

For "Inception (2010)":

```markdown
---
collection: "[[Movies]]"
---

## Links
https://www.imdb.com/title/tt1375666

## Description
A thief who steals corporate secrets... Directed by [[Christopher Nolan]].
Starring Cobb ([[Leonardo DiCaprio]]), Arthur ([[Joseph Gordon-Levitt]]), ...
```

Books use an `Author - Title (Year).md` filename (the author disambiguates
titles shared by different books) and link to Google Books:

```markdown
---
collection: "[[Books]]"
tags:
  - fiction
  - sci-fi
---

## Links
https://books.google.com/books/about/Dune.html?id=B1hSG45JCX4C

## Description
Set on the desert planet Arrakis, Dune is the story of Paul Atreides.

By [[Frank Herbert]].
```

When a poster or cover is downloaded, it's saved next to the note and
referenced in the frontmatter:

```yaml
poster: [[Inception (2010).jpg]]
```
