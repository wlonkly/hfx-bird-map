# Halifax Bird Parking Nest Map — Design Spec

## Overview
A self-contained interactive web map showing all Bird scooter/bike parking nest locations in Halifax/Dartmouth, NS, enriched with real-time vehicle availability data from Bird's public GBFS feed.

## Goals
- Answer the question: *"If I use a Bird scooter, where can I park when I get where I'm going?"*
- Show all designated parking nests on an easy-to-use interactive map
- Indicate which nests currently have vehicles available
- Work offline as a single HTML file once generated

## Data Strategy

### Source
Bird publishes a public GBFS v2.3 feed for Halifax at:
```
https://mds.bird.co/gbfs/v2/public/halifax/gbfs.json
```

### Endpoints Used
| Endpoint | Purpose |
|----------|---------|
| `station_information.json` | All parking nests: `station_id`, `name`, `lat`, `lon`, `address`, `station_area` (15m radius polygon) |
| `station_status.json` | Real-time vehicle count per nest: `num_bikes_available` |

### Important Constraint
In Halifax, scooters and bikes can **only** be parked in designated nests. There is no free-floating parking. Therefore, we do not display individual vehicle locations — we only enrich the nest markers with availability data.

## Architecture

### Files
| File | Purpose |
|------|---------|
| `fetch_bird_nests.py` | Python script that downloads GBFS data and generates the HTML map |
| `bird_nests.html` | Self-contained interactive HTML map (output of the script) |
| `README.md` | Setup instructions, Mapbox token guidance, license info |

### Data Flow
```
fetch_bird_nests.py
  ├── GET station_information.json
  ├── GET station_status.json
  ├── Merge by station_id
  ├── Embed into HTML template
  └── Write bird_nests.html
```

## Map Specifications

### Basemap
- **Default:** Free/open streetmap tiles (e.g., CartoDB Positron or standard OSM tiles) — no API token required
- **Optional:** Mapbox Streets or other Mapbox style if a token is provided
- **No satellite imagery**

### Layers
- **Parking Nests:** Circle markers (`circle` type in Mapbox GL JS)
  - One marker per nest (dynamic count from feed — not hardcoded)
  - **Size:** Scaled by `num_bikes_available` (larger = more vehicles)
  - **Color:** Scaled by `num_bikes_available` (brighter/intenser = more vehicles)
  - Empty nests shown with a distinct muted color
- **Boundary Rings (optional):** Faint 15m-radius polygon rings derived from `station_area`

### Interactions
- **Popup on click:** Street address + "X vehicles available" (or "Empty")
- **Initial view:** Fit-to-bounds so all nests are visible on load
- **Legend:** Explains marker size/color meaning

## Error Handling
- **Network/API failure:** Print clear error message to stderr; do not overwrite existing `bird_nests.html`
- **Malformed data:** Log warning, skip malformed records, continue with available data
- **Missing station_status:** Fall back to showing nests without availability data

## Configuration
- **Default behavior:** Uses free/open tile provider; no token needed
- **Optional Mapbox override:** Public access token supplied via:
  - Command-line argument: `--mapbox-token <TOKEN>`
  - Environment variable: `MAPBOX_TOKEN`
- README will explain both options and how to obtain a free Mapbox token if desired

## License
Open source license to be selected by the user.

## Future Enhancements (Out of Scope)
- Adding a separate layer for current free-floating vehicle locations (not applicable in Halifax)
- Periodic auto-refresh in the browser
- Mobile-responsive UI optimizations
- Deploying as a public website
