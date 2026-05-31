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
