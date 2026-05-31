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

## How It Works

In Halifax, Bird scooters and bikes can **only** be parked in designated nests. This map shows every nest location and how many vehicles are currently available at each. Markers are sized and colored by availability — larger and brighter = more vehicles.

The script fetches data from Bird's public GBFS feed and bakes it into a self-contained HTML file using Mapbox GL JS and free CartoDB streetmap tiles.

## Refreshing Data

Re-run the script whenever you want updated availability:

```bash
python fetch_bird_nests.py
```

The script won't overwrite the HTML if fetching fails, so you'll never accidentally lose your working map.

## Data Source

Bird public GBFS feed: https://mds.bird.co/gbfs/v2/public/halifax/gbfs.json

Map tiles by CartoDB under CC BY 3.0. Map data by OpenStreetMap contributors under ODbL.

## License

MIT — see [LICENSE](LICENSE) for details.
