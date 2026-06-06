# Agent Notes

## Project
Single Python script (`fetch_bird_nests.py`) fetches Bird scooter/bike GBFS data for Halifax and bakes it into a self-contained `bird_nests.html` using MapLibre GL JS + CartoDB tiles.

## Critical: Generated Output
- **`bird_nests.html` is generated and `.gitignore`d.** Never commit it.
- **The real source of the map UI is `HTML_TEMPLATE` inside `fetch_bird_nests.py`.** Any change to HTML, CSS, or JS must be made in the Python string template, not in the generated file.

## Development Commands
```bash
# Generate the map (uses stdlib only; no deps to install)
python fetch_bird_nests.py

# Run tests
pytest

# Run a single test class
pytest tests/test_fetch_bird_nests.py -k TestGenerateHtml
```

## Architecture
- No package manager files (`pyproject.toml`, `requirements.txt`, etc.). The script uses only the Python stdlib (requires 3.9+ for `zoneinfo`).
- `.venv` exists locally but is gitignored. The project does not enforce a specific venv workflow.
- `fetch_bird_nests.py` contains both the data-pipeline logic and the entire HTML/JS/CSS template (`HTML_TEMPLATE`).
- The script writes atomically: it creates a temp file next to the output, then `os.replace`s it. A crash mid-write never leaves a corrupt `bird_nests.html`.

## Testing
- Tests live in `tests/test_fetch_bird_nests.py` and import functions directly from `fetch_bird_nests.py`.
- Tests cover data merging, GeoJSON generation, HTML generation, and style JSON. They do not hit the network.

## Style & Workflow
- **Never update `bird_nests.html` directly.** The real source of the map UI is `HTML_TEMPLATE` inside `fetch_bird_nests.py`. Generate a new `bird_nests.html` only by running `python fetch_bird_nests.py`, and only when necessary to show the human the results of a change.
- No CI, no pre-commit, no lint/typecheck config. Keep it simple.

## Data Source
Bird public GBFS feed: `https://mds.bird.co/gbfs/v2/public/halifax/gbfs.json`

## References
- Original design spec: `docs/superpowers/specs/2026-05-31-halifax-bird-parking-nest-map-design.md`
