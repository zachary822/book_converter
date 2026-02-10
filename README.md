# book-convert

Converts EPUB files for Traditional Chinese vertical text reading. Sets vertical right-to-left writing mode, maps font families to system CJK fonts, and strips per-paragraph font overrides for uniform body text.

## Requirements

- macOS with [Homebrew](https://brew.sh)
- [uv](https://docs.astral.sh/uv/)

## Setup

```sh
brew install uv
```

## Usage

```sh
uv run main.py input.epub
```

This produces `input_vertical.epub` in the same directory.

To specify an output path:

```sh
uv run main.py input.epub -o output.epub
```
