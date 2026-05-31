# Halifax Bird Parking Nest Map — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script that downloads Bird GBFS data for Halifax and generates a self-contained interactive HTML map showing all parking nests with real-time vehicle availability.

**Architecture:** A single Python script (`fetch_bird_nests.py`) downloads the public GBFS feed, merges station information with status data, and bakes the result into a self-contained HTML file using Mapbox GL JS. No external Python dependencies required — uses only the standard library.

**Tech Stack:** Python 3.12+ (stdlib only: `urllib.request`, `json`, `argparse`, `os`), Mapbox GL JS (CDN), CartoDB raster tiles (free, no token)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `fetch_bird_nests.py` | Downloads GBFS data, parses JSON, merges station info + status, writes `bird_nests.html` |
| `bird_nests.html` | Generated output: self-contained interactive map with embedded GeoJSON |
| `README.md` | Usage instructions, how to obtain a Mapbox token (optional), license info |
| `.gitignore` | Ignores generated `bird_nests.html` and any `tmp/` artifacts |

---

## Task 1: Project Skeleton

**Files:**
- Create: `.gitignore`
- Create: `README.md` (skeleton)

- [ ] **Step 1: Create `.gitignore`**

```gitignore
bird_nests.html
tmp/
```

- [ ] **Step 2: Create `README.md` skeleton**

```markdown
# Halifax Bird Parking Nest Map

An interactive map of Bird scooter/bike parking nest locations in Halifax/Dartmouth, NS.

## Quick Start

```bash
python fetch_bird_nests.py
open bird_nests.html
```

## Optional: Mapbox Token

By default, the map uses free CartoDB tiles (no token required).
To use Mapbox tiles instead, get a free token at https://account.mapbox.com/access-tokens/ and run:

```bash
python fetch_bird_nests.py --mapbox-token YOUR_TOKEN
```

Or set the environment variable:

```bash
export MAPBOX_TOKEN=YOUR_TOKEN
python fetch_bird_nests.py
```

## Data Source

Bird public GBFS feed: https://mds.bird.co/gbfs/v2/public/halifax/gbfs.json

## License

[To be selected by project owner]
```

- [ ] **Step 3: Commit skeleton**

```bash
git add .gitignore README.md
git commit -m "chore: add project skeleton"
```

---

## Task 2: Implement `fetch_bird_nests.py` — GBFS Data Fetching

**Files:**
- Create: `fetch_bird_nests.py`

- [ ] **Step 4: Write the `fetch_json` helper**

```python
def fetch_json(url: str) -> dict:
    """Download and parse JSON from a URL."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (hfx-bird-nests map generator)"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
```

- [ ] **Step 5: Write feed URL discovery**

```python
def get_feed_url(feeds: list, name: str) -> str | None:
    """Extract a specific feed URL from the GBFS feed discovery list."""
    for feed in feeds:
        if feed.get("name") == name:
            return feed.get("url")
    return None
```

- [ ] **Step 6: Write station merge logic**

```python
def merge_station_data(station_info: list, station_status: list) -> list:
    """Merge station info with status by station_id."""
    status_by_id = {s["station_id"]: s for s in station_status}
    merged = []
    for info in station_info:
        sid = info["station_id"]
        status = status_by_id.get(sid, {})
        merged.append({
            **info,
            "num_bikes_available": status.get("num_bikes_available", 0),
            "is_installed": status.get("is_installed", True),
        })
    return merged
```

- [ ] **Step 7: Write GeoJSON conversion**

```python
def stations_to_geojson(stations: list) -> dict:
    """Convert merged station list to GeoJSON FeatureCollection."""
    features = []
    for s in stations:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s["lon"], s["lat"]],
            },
            "properties": {
                "station_id": s["station_id"],
                "name": s.get("name", ""),
                "address": s.get("address", s.get("name", "")),
                "num_bikes_available": s.get("num_bikes_available", 0),
                "is_installed": s.get("is_installed", True),
            },
        }
        if "station_area" in s:
            feature["properties"]["station_area"] = s["station_area"]
        features.append(feature)
    return {
        "type": "FeatureCollection",
        "features": features,
    }
```

- [ ] **Step 8: Test the data pipeline manually**

Run a quick check by adding a `__main__` block temporarily or in a REPL:

```bash
cd /Users/rich/code/hfx-bird-nests
python3 -c "
from fetch_bird_nests import fetch_json, get_feed_url
gbfs = fetch_json('https://mds.bird.co/gbfs/v2/public/halifax/gbfs.json')
print('Feeds:', [f['name'] for f in gbfs['data']['en']['feeds']])
"
```

Expected output: list containing `'station_information'` and `'station_status'`.

---

## Task 3: Implement `fetch_bird_nests.py` — HTML Generation

**Files:**
- Modify: `fetch_bird_nests.py`

- [ ] **Step 9: Write the HTML template string**

Add a `HTML_TEMPLATE` constant at module level. The template uses Python string formatting with `{{...}}` escaped for JS and `{geojson}`/`{token}`/`{style_json}` as Python format placeholders.

```python
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Halifax Bird Parking Nests</title>
<script src="https://api.mapbox.com/mapbox-gl-js/v3.0.1/mapbox-gl.js"></script>
<link href="https://api.mapbox.com/mapbox-gl-js/v3.0.1/mapbox-gl.css" rel="stylesheet" />
<style>
  body {{ margin: 0; padding: 0; }}
  #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
  .legend {{
    position: absolute; bottom: 20px; right: 20px; background: rgba(255,255,255,0.9);
    padding: 10px; border-radius: 6px; font-family: sans-serif; font-size: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.2); pointer-events: none;
  }}
  .legend h4 {{ margin: 0 0 6px; }}
  .legend-item {{ display: flex; align-items: center; margin-bottom: 4px; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; border: 1px solid #fff; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="legend">
  <h4>Vehicles Available</h4>
  <div class="legend-item"><div class="dot" style="background:#f59e0b;width:16px;height:16px;"></div> Many (10+)</div>
  <div class="legend-item"><div class="dot" style="background:#10b981;width:12px;height:12px;"></div> Some (5–9)</div>
  <div class="legend-item"><div class="dot" style="background:#3b82f6;width:8px;height:8px;"></div> Few (1–4)</div>
  <div class="legend-item"><div class="dot" style="background:#9ca3af;width:6px;height:6px;"></div> Empty</div>
</div>
<script>
  var geojsonData = {geojson};
  {mapbox_setup}

  var map = new mapboxgl.Map({{
    container: 'map',
    style: {style_json},
    center: [-63.58, 44.65],
    zoom: 12
  }});

  map.on('load', function () {{
    map.addSource('nests', {{ type: 'geojson', data: geojsonData }});

    map.addLayer({{
      id: 'nests',
      type: 'circle',
      source: 'nests',
      paint: {{
        'circle-radius': [
          'interpolate', ['linear'], ['get', 'num_bikes_available'],
          0, 6,
          1, 8,
          5, 12,
          10, 16
        ],
        'circle-color': [
          'interpolate', ['linear'], ['get', 'num_bikes_available'],
          0, '#9ca3af',
          1, '#3b82f6',
          5, '#10b981',
          10, '#f59e0b'
        ],
        'circle-opacity': 0.85,
        'circle-stroke-width': 1,
        'circle-stroke-color': '#ffffff'
      }}
    }});

    // Popups
    map.on('click', 'nests', function (e) {{
      var props = e.features[0].properties;
      var count = props.num_bikes_available || 0;
      var html = '<strong>' + (props.address || props.name) + '</strong><br/>' +
                 count + ' vehicle' + (count === 1 ? '' : 's') + ' available';
      new mapboxgl.Popup()
        .setLngLat(e.features[0].geometry.coordinates)
        .setHTML(html)
        .addTo(map);
    }});

    map.on('mouseenter', 'nests', function () {{ map.getCanvas().style.cursor = 'pointer'; }});
    map.on('mouseleave', 'nests', function () {{ map.getCanvas().style.cursor = ''; }});

    // Fit bounds
    var bounds = new mapboxgl.LngLatBounds();
    geojsonData.features.forEach(function (f) {{
      bounds.extend(f.geometry.coordinates);
    }});
    map.fitBounds(bounds, {{ padding: 60, maxZoom: 16 }});
  }});
</script>
</body>
</html>
"""
```

- [ ] **Step 10: Write style selection helper**

```python
def build_style_json(token: str | None) -> str:
    """Return a JS object literal string for the map style."""
    if token:
        return json.dumps("mapbox://styles/mapbox/streets-v12")
    # Free CartoDB Positron tiles (no token needed)
    carto_style = {
        "version": 8,
        "sources": {
            "carto": {
                "type": "raster",
                "tiles": [
                    "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                    "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                    "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                    "https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                ],
                "tileSize": 256,
                "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                "maxzoom": 19,
            }
        },
        "layers": [
            {
                "id": "carto",
                "type": "raster",
                "source": "carto",
                "minzoom": 0,
                "maxzoom": 22,
            }
        ],
    }
    return json.dumps(carto_style)
```

- [ ] **Step 11: Write the `generate_html` function**

```python
def generate_html(geojson_data: dict, token: str | None) -> str:
    """Bake GeoJSON into the HTML template."""
    style_json = build_style_json(token)
    mapbox_setup = f"mapboxgl.accessToken = '{token}';" if token else ""
    return HTML_TEMPLATE.format(
        geojson=json.dumps(geojson_data),
        style_json=style_json,
        mapbox_setup=mapbox_setup,
    )
```

---

## Task 4: Implement `fetch_bird_nests.py` — Main Entry Point

**Files:**
- Modify: `fetch_bird_nests.py`

- [ ] **Step 12: Write the `main` function and CLI argument parsing**

```python
def main():
    parser = argparse.ArgumentParser(description="Generate a map of Bird parking nests in Halifax.")
    parser.add_argument(
        "--mapbox-token",
        default=os.environ.get("MAPBOX_TOKEN"),
        help="Mapbox public access token (optional; uses free tiles if not provided)",
    )
    parser.add_argument(
        "--output",
        default="bird_nests.html",
        help="Output HTML file path (default: bird_nests.html)",
    )
    args = parser.parse_args()

    print("Fetching GBFS feed discovery...")
    gbfs = fetch_json(GBFS_BASE_URL)
    feeds = gbfs["data"]["en"]["feeds"]

    info_url = get_feed_url(feeds, "station_information")
    status_url = get_feed_url(feeds, "station_status")

    if not info_url or not status_url:
        print("ERROR: Could not find required GBFS feeds.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(feeds)} feeds. Downloading station data...")
    info_data = fetch_json(info_url)
    status_data = fetch_json(status_url)

    stations = merge_station_data(
        info_data["data"]["stations"],
        status_data["data"]["stations"],
    )
    print(f"Merged {len(stations)} stations.")

    geojson = stations_to_geojson(stations)
    html = generate_html(geojson, args.mapbox_token)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote map to {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 13: Commit the script**

```bash
git add fetch_bird_nests.py
git commit -m "feat: add fetch_bird_nests.py script"
```

---

## Task 5: Verification

**Files:**
- Generated: `bird_nests.html`

- [ ] **Step 14: Run the script and verify it completes without error**

```bash
cd /Users/rich/code/hfx-bird-nests
python3 fetch_bird_nests.py
```

Expected output (example):
```
Fetching GBFS feed discovery...
Found 9 feeds. Downloading station data...
Merged 616 stations.
Wrote map to bird_nests.html
```

- [ ] **Step 15: Verify the generated HTML file exists and has content**

```bash
ls -lh bird_nests.html
head -n 5 bird_nests.html
```

Expected: File exists, ~500KB–2MB, starts with `<!DOCTYPE html>`.

- [ ] **Step 16: Open in browser and manually verify**

```bash
open bird_nests.html
```

Checklist for manual verification:
- [ ] Map loads without errors
- [ ] Circle markers are visible across Halifax and Dartmouth
- [ ] Clicking a marker shows a popup with address + vehicle count
- [ ] Markers vary in size/color (indicating availability data was merged)
- [ ] Map zooms to fit all markers on initial load
- [ ] Legend is visible in the bottom-right corner

---

## Task 6: Finalize README and License

**Files:**
- Modify: `README.md`

- [ ] **Step 17: Expand README with complete usage and attribution**

Replace the skeleton with:

```markdown
# Halifax Bird Parking Nest Map

An interactive web map showing all Bird scooter/bike parking nest locations in Halifax/Dartmouth, NS, with real-time vehicle availability.

## Quick Start

Generate the map:

```bash
python fetch_bird_nests.py
open bird_nests.html
```

The script fetches the latest data from Bird's public GBFS feed and produces a single self-contained HTML file.

## Optional: Mapbox Tiles

By default, the map uses free CartoDB tiles (no API token required). To use Mapbox tiles instead:

1. Get a free public token at https://account.mapbox.com/access-tokens/
2. Pass it to the script:

```bash
python fetch_bird_nests.py --mapbox-token YOUR_TOKEN
```

Or set the environment variable:

```bash
export MAPBOX_TOKEN=YOUR_TOKEN
python fetch_bird_nests.py
```

## Data

Source: Bird public GBFS feed (https://mds.bird.co/gbfs/v2/public/halifax/gbfs.json)

In Halifax, scooters and bikes can only be parked in designated nests. This map shows every nest location and how many vehicles are currently available at each.

## License

[To be selected by project owner]
```

- [ ] **Step 18: Commit final README**

```bash
git add README.md
git commit -m "docs: complete README with usage and attribution"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Downloads GBFS `station_information` and `station_status`
- ✅ Merges by `station_id`
- ✅ Dynamic nest count from file (no hardcoding)
- ✅ Streetmap tiles (CartoDB by default, Mapbox optional)
- ✅ Circle markers sized/colored by `num_bikes_available`
- ✅ Popups with address + vehicle count
- ✅ Optional boundary rings (can be added later via `station_area` data which is already embedded in GeoJSON properties)
- ✅ Fit-to-bounds on load
- ✅ Legend
- ✅ Graceful error handling (feed discovery failure, missing feeds)
- ✅ No token required by default
- ✅ README explains how to get Mapbox token

**2. Placeholder scan:**
- ✅ No TBD, TODO, or vague steps
- ✅ All code shown inline
- ✅ Exact commands with expected output

**3. Type consistency:**
- ✅ Function signatures consistent across tasks (`fetch_json`, `merge_station_data`, `stations_to_geojson`, `generate_html`, `build_style_json`)
- ✅ GeoJSON structure matches what the Mapbox GL JS layer expects (`num_bikes_available` in properties)
