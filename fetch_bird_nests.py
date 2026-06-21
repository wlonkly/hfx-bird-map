#!/usr/bin/env python3
"""Fetch Bird GBFS data for Halifax and generate an interactive parking nest map."""

import argparse
import datetime
import json
import os
import sys
import tempfile
import urllib.request
from zoneinfo import ZoneInfo

GBFS_BASE_URL = "https://mds.bird.co/gbfs/v2/public/halifax/gbfs.json"


def fetch_json(url: str) -> dict:
    """Download and parse JSON from a URL."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (hfx-bird-nests map generator)"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_feed_url(feeds: list, name: str) -> str | None:
    """Extract a specific feed URL from the GBFS feed discovery list."""
    return next(
        (feed.get("url") for feed in feeds if feed.get("name") == name),
        None,
    )


def build_vehicle_type_map(vt_data: dict) -> dict[str, str]:
    """Build a map of vehicle_type_id to form_factor (e.g. 'scooter', 'bicycle')."""
    return {
        vt["vehicle_type_id"]: vt.get("form_factor", vt.get("name", "unknown"))
        for vt in vt_data["data"]["vehicle_types"]
    }


def merge_station_data(station_info: list, station_status: list, vehicle_type_map: dict[str, str] | None = None) -> list:
    """Merge station info with status by station_id, including per-type vehicle counts."""
    status_by_id = {s["station_id"]: s for s in station_status if s.get("station_id")}
    merged = []
    for info in station_info:
        sid = info.get("station_id")
        if sid is None:
            print(f"WARNING: Skipping station record without station_id: {info.get('name', 'unknown')!r}", file=sys.stderr)
            continue
        status = status_by_id.get(sid, {})
        raw_types = status.get("vehicle_types_available") or []
        if vehicle_type_map:
            vehicle_types_available = [
                {"name": vehicle_type_map.get(vt["vehicle_type_id"], vt["vehicle_type_id"]), "count": vt["count"]}
                for vt in raw_types
            ]
        else:
            vehicle_types_available = raw_types
        # num_bikes_available is GBFS terminology; it counts all vehicle types (scooters, bikes, etc.)
        merged.append({
            **info,
            "num_bikes_available": status.get("num_bikes_available", 0),
            "vehicle_types_available": vehicle_types_available,
            "is_installed": status.get("is_installed", True),
        })
    return merged


def merge_duplicate_stations(stations: list) -> list:
    """Merge stations with the same address into a single entry, summing counts."""
    merged = {}
    for s in stations:
        address = s.get("address") or s.get("name", "")
        if address in merged:
            existing = merged[address]
            existing["num_bikes_available"] += s.get("num_bikes_available", 0)
            existing_vt = {vt["name"]: vt for vt in existing.get("vehicle_types_available", [])}
            for vt in s.get("vehicle_types_available", []):
                name = vt["name"]
                if name in existing_vt:
                    existing_vt[name]["count"] += vt["count"]
                else:
                    existing_vt[name] = dict(vt)
            existing["vehicle_types_available"] = list(existing_vt.values())
        else:
            merged[address] = dict(s)
    return list(merged.values())


def format_breakdown(vehicle_types: list) -> str:
    """Build a human-readable breakdown string from vehicle types."""
    if not vehicle_types:
        return ""
    total = sum(vt.get("count", 0) for vt in vehicle_types)
    if total == 0:
        return ""
    parts = []
    for vt in vehicle_types:
        count = vt.get("count", 0)
        name = vt.get("name", "unknown")
        parts.append(f"{count} {name}{'s' if count != 1 else ''}")
    return f" ({', '.join(parts)})"


def snap_vehicles_to_stations(stations: list, free_vehicles: list, vehicle_type_map: dict, max_dist: float = 0.0003) -> int:
    """Match free-floating vehicles to nearest station within max_dist (~30m)."""
    matched = 0
    for v in free_vehicles:
        if v.get("is_reserved") or v.get("is_disabled"):
            continue
        vlat = v.get("lat")
        vlon = v.get("lon")
        if vlat is None or vlon is None:
            print(f"WARNING: Skipping vehicle without location: {v.get('bike_id', 'unknown')!r}", file=sys.stderr)
            continue
        vt_id = v.get("vehicle_type_id")
        vt_name = vehicle_type_map.get(vt_id, "unknown") if vt_id else "unknown"

        nearest = None
        nearest_dist = float("inf")
        for s in stations:
            dist = ((s["lat"] - vlat) ** 2 + (s["lon"] - vlon) ** 2) ** 0.5
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = s

        if nearest and nearest_dist <= max_dist:
            nearest["num_bikes_available"] = nearest.get("num_bikes_available", 0) + 1
            found = False
            for vt in nearest.get("vehicle_types_available", []):
                if vt.get("name") == vt_name:
                    vt["count"] = vt.get("count", 0) + 1
                    found = True
                    break
            if not found:
                nearest.setdefault("vehicle_types_available", []).append({"name": vt_name, "count": 1})
            matched += 1
    return matched


def stations_to_geojson(stations: list) -> dict:
    """Convert merged station list to GeoJSON FeatureCollection."""
    features = []
    for s in stations:
        lon = s.get("lon")
        lat = s.get("lat")
        station_id = s.get("station_id")
        if lon is None or lat is None or station_id is None:
            continue
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "station_id": station_id,
                "name": s.get("name", ""),
                "address": s.get("address", s.get("name", "")),
                "num_bikes_available": s.get("num_bikes_available", 0),
                "vehicle_types_available": s.get("vehicle_types_available") or [],
                "breakdown": format_breakdown(s.get("vehicle_types_available") or []),
                "is_installed": s.get("is_installed", True),
            },
        }
        if "station_area" in s:
            feature["properties"]["station_area"] = s["station_area"]
        features.append(feature)

    # Mark the single station with the most vehicles (first in case of ties)
    if features:
        max_count = max(f["properties"]["num_bikes_available"] for f in features)
        if max_count > 0:
            for f in features:
                if f["properties"]["num_bikes_available"] == max_count:
                    f["properties"]["is_top_station"] = True
                    break

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def build_style_json() -> str:
    """Return a JSON string of the map style using free CartoDB raster tiles."""
    style = {
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
                "maxzoom": 19,
            }
        ],
    }
    return json.dumps(style)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
<meta http-equiv="Pragma" content="no-cache" />
<meta http-equiv="Expires" content="0" />
<meta name="description" content="Interactive map of Bird scooter and bike parking nests in Halifax and Dartmouth, NS. See availability by location." />
<meta name="keywords" content="Halifax, Dartmouth, Bird scooter, bike share, parking nest, scooter map, bike map, Nova Scotia" />
<meta property="og:title" content="Halifax Bird Parking Nest Map" />
<meta property="og:description" content="Interactive map of Bird scooter and bike parking nests in Halifax and Dartmouth, NS." />
<meta property="og:image" content="https://www.lafferty.ca/hfxbirdmap/images/screenshot.png" />
<meta property="og:url" content="https://www.lafferty.ca/hfxbirdmap/" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Halifax Bird Parking Nest Map" />
<meta name="twitter:description" content="Interactive map of Bird scooter and bike parking nests in Halifax and Dartmouth, NS." />
<meta name="twitter:image" content="images/screenshot.png" />
<title>Halifax Bird Parking Nests</title>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
<style>
  body {{ margin: 0; padding: 0; }}
  #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
  .title-box {{
    position: absolute; top: 20px; left: 20px;
    background: rgba(255,255,255,0.95);
    padding: 12px 16px; border-radius: 6px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px; line-height: 1.5;
    box-shadow: 0 1px 4px rgba(0,0,0,0.2); z-index: 10;
    max-width: 320px; pointer-events: auto;
  }}
  .title-box h1 {{ margin: 0 0 4px; font-size: 16px; }}
  .title-box p {{ margin: 0; }}
  .title-box .updated {{ color: #666; font-size: 11px; margin-top: 4px; }}
  .title-box .disclaimer {{ color: #888; font-size: 11px; margin-top: 6px; }}
  .legend {{
    position: absolute; bottom: 20px; right: 20px; background: rgba(255,255,255,0.9);
    padding: 10px; border-radius: 6px; font-family: sans-serif; font-size: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.2); pointer-events: none;
  }}
  .legend h4 {{ margin: 0 0 6px; }}
  .legend-item {{ display: flex; align-items: center; margin-bottom: 4px; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; border: 1px solid #fff; }}
  .user-dot {{
    width: 14px; height: 14px; border-radius: 50%;
    background: #000; border: 2px solid #fff;
    box-shadow: 0 0 4px rgba(0,0,0,0.4);
  }}
  .locate-btn svg {{ width: 16px; height: 16px; display: block; }}
  .locate-btn:disabled {{ opacity: 0.5; cursor: default; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="title-box">
  <h1>Halifax Bird Map 🐦</h1>
  <p>Nests show available vehicles at this parking zone. Empty nests are valid parking — they just have no vehicles right now.</p>
  <p class="updated">Last updated: {generated_at}</p>
  <p class="disclaimer">Not affiliated with Bird Canada. <a href="https://github.com/wlonkly/hfx-bird-map">Source</a></p>
</div>
<div class="legend">
  <h4>Vehicles Available</h4>
  <div class="legend-item"><div class="dot" style="background:#f59e0b;width:16px;height:16px;"></div> Many (10+)</div>
  <div class="legend-item"><div class="dot" style="background:#10b981;width:12px;height:12px;"></div> Some (5–9)</div>
  <div class="legend-item"><div class="dot" style="background:#3b82f6;width:8px;height:8px;"></div> Few (1–4)</div>
  <div class="legend-item"><div class="dot" style="background:#9ca3af;width:6px;height:6px;"></div> Empty</div>
</div>
<script>
  var geojsonData = {geojson};

  var map = new maplibregl.Map({{
    container: 'map',
    style: {style_json},
    center: [-63.58, 44.65],
    zoom: 12
  }});

  map.addControl(new maplibregl.NavigationControl({{ showCompass: false }}), 'top-right');

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
          'step', ['get', 'num_bikes_available'],
          '#9ca3af',
          1, '#3b82f6',
          5, '#10b981',
          10, '#f59e0b'
        ],
        'circle-opacity': 0.85,
        'circle-stroke-width': 1,
        'circle-stroke-color': '#ffffff'
      }}
    }});

    map.on('click', 'nests', function (e) {{
      var props = e.features[0].properties;
      var count = props.num_bikes_available || 0;
      var html = '<strong>' + (props.address || props.name) + '</strong><br/>' +
                 count + ' vehicle' + (count === 1 ? '' : 's') + ' available' +
                 (props.breakdown || '');
      new maplibregl.Popup()
        .setLngLat(e.features[0].geometry.coordinates)
        .setHTML(html)
        .addTo(map);
    }});

    map.on('mouseenter', 'nests', function () {{ map.getCanvas().style.cursor = 'pointer'; }});
    map.on('mouseleave', 'nests', function () {{ map.getCanvas().style.cursor = ''; }});

    // Add star marker for the station with the most vehicles
    var topFeature = geojsonData.features.find(function (f) {{
      return f.properties.is_top_station;
    }});
    if (topFeature) {{
      var starEl = document.createElement('div');
      starEl.innerHTML = '⭐';
      starEl.style.fontSize = '14px';
      starEl.style.lineHeight = '1';
      starEl.style.textAlign = 'center';
      starEl.style.width = '20px';
      starEl.style.height = '20px';
      starEl.style.display = 'flex';
      starEl.style.alignItems = 'center';
      starEl.style.justifyContent = 'center';
      var starMarker = new maplibregl.Marker({{ element: starEl }})
        .setLngLat(topFeature.geometry.coordinates)
        .addTo(map);
      function updateStarVisibility() {{
        var zoom = map.getZoom();
        starMarker.getElement().style.display = (zoom > 14.5) ? 'flex' : 'none';
      }}
      updateStarVisibility();
      map.on('zoom', updateStarVisibility);
      document.addEventListener('keydown', function(e) {{
        if (e.key === '*') {{
          map.flyTo({{ center: topFeature.geometry.coordinates, zoom: 15.5 }});
        }}
      }});
    }}

    // Goose easter egg at Sullivan's Pond
    var gooseEl = document.createElement('div');
    gooseEl.innerHTML = '🪿';
    gooseEl.style.fontSize = '18px';
    gooseEl.style.lineHeight = '1';
    gooseEl.style.textAlign = 'center';
    gooseEl.style.width = '20px';
    gooseEl.style.height = '20px';
    gooseEl.style.display = 'flex';
    gooseEl.style.alignItems = 'center';
    gooseEl.style.justifyContent = 'center';
    gooseEl.style.cursor = 'pointer';
    var gooseMarker = new maplibregl.Marker({{ element: gooseEl }})
      .setLngLat([-63.56326113429952, 44.6721396812563])
      .addTo(map);
    gooseEl.addEventListener('click', function(e) {{
      e.stopPropagation();
      new maplibregl.Popup()
        .setLngLat([-63.56326113429952, 44.6721396812563])
        .setHTML('<strong>Sullivan\\'s Pond, Dartmouth, NS</strong><br/>13 geese available (honk!)')
        .addTo(map);
    }});
    function updateGooseVisibility() {{
      var zoom = map.getZoom();
      gooseMarker.getElement().style.display = (zoom > 14.5) ? 'flex' : 'none';
    }}
    updateGooseVisibility();
    map.on('zoom', updateGooseVisibility);

    var bounds = new maplibregl.LngLatBounds();
    geojsonData.features.forEach(function (f) {{
      bounds.extend(f.geometry.coordinates);
    }});
    map.fitBounds(bounds, {{ padding: 60, maxZoom: 16 }});
  }});
</script>
</body>
</html>"""


def generate_html(geojson_data: dict, generated_at: str) -> str:
    """Bake GeoJSON into the HTML template."""
    style_json = build_style_json()
    return HTML_TEMPLATE.format(
        geojson=json.dumps(geojson_data),
        style_json=style_json,
        generated_at=generated_at,
    )


def main():
    parser = argparse.ArgumentParser(description="Generate a map of Bird parking nests in Halifax.")
    parser.add_argument(
        "--output",
        default="bird_nests.html",
        help="Output HTML file path (default: bird_nests.html)",
    )
    args = parser.parse_args()

    try:
        print("Fetching GBFS feed discovery...")
        gbfs = fetch_json(GBFS_BASE_URL)
    except Exception as e:
        print(f"ERROR: Could not fetch GBFS feed: {e}", file=sys.stderr)
        sys.exit(1)

    feeds = gbfs.get("data", {}).get("en", {}).get("feeds", [])
    info_url = get_feed_url(feeds, "station_information")
    status_url = get_feed_url(feeds, "station_status")
    fb_url = get_feed_url(feeds, "free_bike_status")
    vt_url = get_feed_url(feeds, "vehicle_types")

    if not info_url:
        print("ERROR: station_information feed not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(feeds)} feeds. Downloading station data...")

    try:
        info_data = fetch_json(info_url)
    except Exception as e:
        print(f"ERROR: Could not fetch station_information: {e}", file=sys.stderr)
        sys.exit(1)

    # Optional feeds — continue gracefully if missing or malformed
    status_data = {}
    if status_url:
        try:
            status_data = fetch_json(status_url)
        except Exception as e:
            print(f"WARNING: Could not fetch station_status: {e}", file=sys.stderr)
    else:
        print("WARNING: station_status feed not found. Nests will show without availability data.", file=sys.stderr)

    fb_data = {}
    if fb_url:
        try:
            fb_data = fetch_json(fb_url)
        except Exception as e:
            print(f"WARNING: Could not fetch free_bike_status: {e}", file=sys.stderr)
    else:
        print("WARNING: free_bike_status feed not found. Skipping free-floating vehicle snap.", file=sys.stderr)

    vt_data = {}
    if vt_url:
        try:
            vt_data = fetch_json(vt_url)
        except Exception as e:
            print(f"WARNING: Could not fetch vehicle_types: {e}", file=sys.stderr)
    else:
        print("WARNING: vehicle_types feed not found. Vehicle type names may be raw IDs.", file=sys.stderr)

    vehicle_type_map = {}
    if vt_data:
        try:
            vehicle_type_map = build_vehicle_type_map(vt_data)
            print(f"Vehicle types: {', '.join(f'{k}={v}' for k, v in vehicle_type_map.items())}")
        except Exception as e:
            print(f"WARNING: Could not parse vehicle_types: {e}", file=sys.stderr)

    stations = merge_station_data(
        info_data.get("data", {}).get("stations", []),
        status_data.get("data", {}).get("stations", []),
        vehicle_type_map,
    )
    print(f"Merged {len(stations)} stations from station_status.")

    if fb_data and vehicle_type_map:
        free_vehicles = fb_data.get("data", {}).get("bikes", [])
        matched = snap_vehicles_to_stations(stations, free_vehicles, vehicle_type_map)
        print(f"Snapped {matched} free-floating vehicles to nearest nests (total free: {len(free_vehicles)}).")

    before = len(stations)
    stations = merge_duplicate_stations(stations)
    if len(stations) < before:
        print(f"Merged {before - len(stations)} duplicate-address stations.")

    geojson = stations_to_geojson(stations)
    generated_at = datetime.datetime.now(datetime.timezone.utc).astimezone(ZoneInfo("America/Halifax")).strftime("%B %d, %Y at %I:%M %p %Z")
    html = generate_html(geojson, generated_at)

    # Atomic write so a crash mid-write never leaves a corrupt or empty output file
    output_path = os.path.abspath(args.output)
    output_dir = os.path.dirname(output_path)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output_dir, suffix=".tmp", delete=False
    ) as f:
        f.write(html)
        tmp_path = f.name
    os.replace(tmp_path, output_path)
    print(f"Wrote map to {args.output}")


if __name__ == "__main__":
    main()
