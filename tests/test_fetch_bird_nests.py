import json

from fetch_bird_nests import (
    build_vehicle_type_map,
    format_breakdown,
    get_feed_url,
    merge_duplicate_stations,
    merge_station_data,
    snap_vehicles_to_stations,
    stations_to_geojson,
    build_style_json,
    generate_html,
)


class TestBuildVehicleTypeMap:
    def test_maps_type_id_to_form_factor(self):
        data = {"data": {"vehicle_types": [
            {"vehicle_type_id": "abc123", "form_factor": "scooter"},
            {"vehicle_type_id": "def456", "form_factor": "bicycle"},
        ]}}
        result = build_vehicle_type_map(data)
        assert result == {"abc123": "scooter", "def456": "bicycle"}

    def test_falls_back_to_name_when_no_form_factor(self):
        data = {"data": {"vehicle_types": [
            {"vehicle_type_id": "abc123", "name": "Bird Scooter"},
        ]}}
        result = build_vehicle_type_map(data)
        assert result == {"abc123": "Bird Scooter"}

    def test_handles_empty_types(self):
        data = {"data": {"vehicle_types": []}}
        assert build_vehicle_type_map(data) == {}


class TestGetFeedUrl:
    def test_returns_url_for_matching_name(self):
        feeds = [
            {"name": "station_information", "url": "https://example.com/stations.json"},
        ]
        result = get_feed_url(feeds, "station_information")
        assert result == "https://example.com/stations.json"

    def test_returns_none_for_missing_name(self):
        feeds = [
            {"name": "station_information", "url": "https://example.com/stations.json"},
        ]
        result = get_feed_url(feeds, "nonexistent")
        assert result is None

    def test_returns_none_for_empty_feeds(self):
        assert get_feed_url([], "anything") is None

    def test_matches_exact_name_only(self):
        feeds = [
            {"name": "station_information", "url": "https://example.com/stations.json"},
            {"name": "station_status", "url": "https://example.com/status.json"},
        ]
        result = get_feed_url(feeds, "station")
        assert result is None


class TestMergeStationData:
    def test_merges_status_by_station_id(self):
        info = [
            {"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0},
            {"station_id": "2", "name": "B", "lat": 45.0, "lon": -64.0},
        ]
        status = [
            {"station_id": "1", "num_bikes_available": 3, "is_installed": True},
            {"station_id": "2", "num_bikes_available": 0, "is_installed": True},
        ]
        result = merge_station_data(info, status)
        assert len(result) == 2
        assert result[0]["num_bikes_available"] == 3
        assert result[1]["num_bikes_available"] == 0

    def test_defaults_when_status_missing(self):
        info = [
            {"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0},
        ]
        status = []
        result = merge_station_data(info, status)
        assert result[0]["num_bikes_available"] == 0
        assert result[0]["is_installed"] is True

    def test_preserves_all_info_fields(self):
        info = [
            {"station_id": "1", "name": "A", "address": "123 Main St", "lat": 44.0, "lon": -63.0},
        ]
        result = merge_station_data(info, [{"station_id": "1", "num_bikes_available": 2}])
        assert result[0]["address"] == "123 Main St"
        assert result[0]["lat"] == 44.0

    def test_handles_empty_inputs(self):
        assert merge_station_data([], []) == []

    def test_resolves_vehicle_type_ids(self):
        info = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0}]
        status = [{"station_id": "1", "vehicle_types_available": [
            {"vehicle_type_id": "abc123", "count": 2},
            {"vehicle_type_id": "def456", "count": 0},
        ]}]
        vtype_map = {"abc123": "scooter", "def456": "bicycle"}
        result = merge_station_data(info, status, vtype_map)
        types = result[0]["vehicle_types_available"]
        assert {"name": "scooter", "count": 2} in types
        assert {"name": "bicycle", "count": 0} in types

    def test_defaults_vehicle_types_without_map(self):
        info = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0}]
        status = [{"station_id": "1", "vehicle_types_available": [
            {"vehicle_type_id": "abc123", "count": 1},
        ]}]
        result = merge_station_data(info, status)
        assert result[0]["vehicle_types_available"] == [{"vehicle_type_id": "abc123", "count": 1}]

    def test_handles_none_vehicle_types(self):
        info = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0}]
        status = [{"station_id": "1", "vehicle_types_available": None}]
        result = merge_station_data(info, status)
        assert result[0]["vehicle_types_available"] == []

    def test_handles_missing_vehicle_types_key(self):
        info = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0}]
        status = [{"station_id": "1"}]
        result = merge_station_data(info, status)
        assert result[0]["vehicle_types_available"] == []


class TestFormatBreakdown:
    def test_formats_single_type(self):
        types = [{"name": "scooter", "count": 2}]
        assert format_breakdown(types) == " (2 scooters)"

    def test_formats_multiple_types(self):
        types = [{"name": "scooter", "count": 2}, {"name": "bicycle", "count": 1}]
        assert format_breakdown(types) == " (2 scooters, 1 bicycle)"

    def test_singular(self):
        types = [{"name": "scooter", "count": 1}]
        assert format_breakdown(types) == " (1 scooter)"

    def test_empty_list(self):
        assert format_breakdown([]) == ""

    def test_zero_counts(self):
        assert format_breakdown([{"name": "scooter", "count": 0}]) == ""

    def test_none(self):
        assert format_breakdown(None) == ""


class TestSnapVehiclesToStations:
    def test_snaps_nearby_vehicle_to_station(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0,
                     "num_bikes_available": 0, "vehicle_types_available": []}]
        free = [{"lat": 44.0002, "lon": -63.0002, "vehicle_type_id": "abc",
                 "is_reserved": False, "is_disabled": False}]
        vtype_map = {"abc": "scooter"}
        matched = snap_vehicles_to_stations(stations, free, vtype_map)
        assert matched == 1
        assert stations[0]["num_bikes_available"] == 1
        assert stations[0]["vehicle_types_available"] == [{"name": "scooter", "count": 1}]

    def test_does_not_snap_distant_vehicle(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0,
                     "num_bikes_available": 2, "vehicle_types_available": []}]
        free = [{"lat": 44.01, "lon": -63.01, "vehicle_type_id": "abc",
                 "is_reserved": False, "is_disabled": False}]
        matched = snap_vehicles_to_stations(stations, free, {"abc": "scooter"})
        assert matched == 0
        assert stations[0]["num_bikes_available"] == 2

    def test_skips_reserved_vehicles(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0,
                     "num_bikes_available": 0, "vehicle_types_available": []}]
        free = [{"lat": 44.0002, "lon": -63.0002, "vehicle_type_id": "abc",
                 "is_reserved": True, "is_disabled": False}]
        matched = snap_vehicles_to_stations(stations, free, {"abc": "scooter"})
        assert matched == 0

    def test_adds_vehicle_to_existing_type(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0,
                     "num_bikes_available": 2, "vehicle_types_available": [{"name": "scooter", "count": 2}]}]
        free = [{"lat": 44.0002, "lon": -63.0002, "vehicle_type_id": "abc",
                 "is_reserved": False, "is_disabled": False}]
        matched = snap_vehicles_to_stations(stations, free, {"abc": "scooter"})
        assert matched == 1
        assert stations[0]["num_bikes_available"] == 3
        assert stations[0]["vehicle_types_available"] == [{"name": "scooter", "count": 3}]


class TestMergeDuplicateStations:
    def test_merges_duplicate_addresses(self):
        stations = [
            {"address": "123 Main St", "num_bikes_available": 3, "vehicle_types_available": [{"name": "scooter", "count": 3}], "lat": 44.0, "lon": -63.0},
            {"address": "123 Main St", "num_bikes_available": 1, "vehicle_types_available": [{"name": "bicycle", "count": 1}], "lat": 44.0, "lon": -63.0},
        ]
        result = merge_duplicate_stations(stations)
        assert len(result) == 1
        assert result[0]["num_bikes_available"] == 4
        assert len(result[0]["vehicle_types_available"]) == 2

    def test_preserves_unique_addresses(self):
        stations = [
            {"address": "123 Main St", "num_bikes_available": 3, "vehicle_types_available": [], "lat": 44.0, "lon": -63.0},
            {"address": "456 Oak Ave", "num_bikes_available": 1, "vehicle_types_available": [], "lat": 45.0, "lon": -64.0},
        ]
        result = merge_duplicate_stations(stations)
        assert len(result) == 2

    def test_handles_missing_address(self):
        stations = [
            {"name": "Unknown Spot", "num_bikes_available": 0, "vehicle_types_available": [], "lat": 44.0, "lon": -63.0},
        ]
        result = merge_duplicate_stations(stations)
        assert len(result) == 1


class TestStationsToGeoJSON:
    def test_returns_feature_collection(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0}]
        result = stations_to_geojson(stations)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1

    def test_converts_lat_lon_to_geojson_coordinates(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.64, "lon": -63.58}]
        result = stations_to_geojson(stations)
        feature = result["features"][0]
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [-63.58, 44.64]

    def test_copies_relevant_properties(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0,
                     "address": "123 Main St", "num_bikes_available": 5,
                     "is_installed": True}]
        result = stations_to_geojson(stations)
        props = result["features"][0]["properties"]
        assert props["address"] == "123 Main St"
        assert props["num_bikes_available"] == 5
        assert props["is_installed"] is True
        assert "breakdown" in props

    def test_includes_station_area_when_present(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0,
                     "station_area": {"type": "Polygon", "coordinates": [[[0, 0]]]}}]
        result = stations_to_geojson(stations)
        props = result["features"][0]["properties"]
        assert "station_area" in props

    def test_omits_station_area_when_not_present(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0}]
        result = stations_to_geojson(stations)
        assert "station_area" not in result["features"][0]["properties"]

    def test_handles_empty_list(self):
        result = stations_to_geojson([])
        assert result == {"type": "FeatureCollection", "features": []}

    def test_skips_station_without_coordinates(self):
        stations = [
            {"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0},
            {"station_id": "2", "name": "B"},
        ]
        result = stations_to_geojson(stations)
        assert len(result["features"]) == 1

    def test_skips_station_without_station_id(self):
        stations = [
            {"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0},
            {"name": "B", "lat": 45.0, "lon": -64.0},
        ]
        result = stations_to_geojson(stations)
        assert len(result["features"]) == 1

    def test_includes_vehicle_types_in_properties(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0,
                     "vehicle_types_available": [{"name": "scooter", "count": 2}]}]
        result = stations_to_geojson(stations)
        props = result["features"][0]["properties"]
        assert props["vehicle_types_available"] == [{"name": "scooter", "count": 2}]

    def test_defaults_vehicle_types_to_empty_list(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0}]
        result = stations_to_geojson(stations)
        assert result["features"][0]["properties"]["vehicle_types_available"] == []

    def test_handles_none_vehicle_types_in_feature(self):
        stations = [{"station_id": "1", "name": "A", "lat": 44.0, "lon": -63.0,
                     "vehicle_types_available": None}]
        result = stations_to_geojson(stations)
        assert result["features"][0]["properties"]["vehicle_types_available"] == []


class TestBuildStyleJson:
    def test_returns_carto_style(self):
        result = build_style_json()
        parsed = json.loads(result)
        assert parsed["version"] == 8
        assert "carto" in parsed["sources"]
        assert "layers" in parsed

    def test_carto_tiles_use_light_all_style(self):
        result = build_style_json()
        parsed = json.loads(result)
        tiles = parsed["sources"]["carto"]["tiles"]
        assert all("light_all" in t for t in tiles)

    def test_carto_uses_raster_type(self):
        result = build_style_json()
        parsed = json.loads(result)
        assert parsed["sources"]["carto"]["type"] == "raster"

    def test_layer_maxzoom_matches_source_maxzoom(self):
        result = build_style_json()
        parsed = json.loads(result)
        source_maxzoom = parsed["sources"]["carto"]["maxzoom"]
        layer_maxzoom = parsed["layers"][0]["maxzoom"]
        assert layer_maxzoom <= source_maxzoom


TS = "January 1, 2025 at 12:00 PM AST"


class TestGenerateHtml:
    def test_returns_html_string(self):
        geojson = {"type": "FeatureCollection", "features": []}
        html = generate_html(geojson, TS)
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")

    def test_contains_maplibre_gl_js_script(self):
        html = generate_html({"type": "FeatureCollection", "features": []}, TS)
        assert "maplibre-gl" in html

    def test_embeds_geojson_data(self):
        geojson = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-63.58, 44.64]},
             "properties": {"station_id": "1"}}
        ]}
        html = generate_html(geojson, TS)
        assert "-63.58" in html
        assert '"station_id": "1"' in html

    def test_uses_maplibre_api_constructors(self):
        html = generate_html({"type": "FeatureCollection", "features": []}, TS)
        assert "maplibregl.Map" in html
        assert "maplibregl.Popup" in html
        assert "maplibregl.LngLatBounds" in html

    def test_no_mapbox_access_token_setup(self):
        html = generate_html({"type": "FeatureCollection", "features": []}, TS)
        assert "mapboxgl.accessToken" not in html

    def test_includes_legend(self):
        html = generate_html({"type": "FeatureCollection", "features": []}, TS)
        assert "Vehicles Available" in html
        assert "Empty" in html

    def test_popup_uses_breakdown_property(self):
        geojson = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-63.58, 44.64]},
             "properties": {"station_id": "1", "address": "123 Main St",
                            "num_bikes_available": 3,
                            "breakdown": " (2 scooters, 1 bicycle)"}}
        ]}
        html = generate_html(geojson, TS)
        assert "props.breakdown" in html
        assert " (2 scooters, 1 bicycle)" in html

    def test_contains_title_box(self):
        html = generate_html({"type": "FeatureCollection", "features": []}, TS)
        assert "Halifax Bird Map" in html
        assert "Empty nests are valid parking" in html
        assert "Not affiliated with Bird Canada" in html
        assert "github.com/wlonkly/hfx-bird-map" in html
        assert TS in html
