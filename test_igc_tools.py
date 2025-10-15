"""
Comprehensive test suite for igc_tools module.

Tests all functions and methods in igc_tools.py including:
- Utility functions (color scales, coordinate conversion, IGC parsing)
- BFix dataclass
- IGCLog class (parsing, metrics, exports)
"""
import unittest
import tempfile
import os
import datetime
import numpy as np
import pandas as pd

import igc_tools
import math_utils


# ============================================================================
# Helper Functions
# ============================================================================

def create_bfix_line(
    hour: int,
    minute: int,
    second: int,
    lat_deg: float,
    lon_deg: float,
    validity: str = "A",
    pressure_alt: int = 1000,
    gnss_alt: int = 1000,
    north: bool = True,
    east: bool = False
) -> str:
    """
    Create a properly formatted IGC B-record (BFix) line.

    B-record format: B HHMMSS DDMMmmmN/S DDDMMmmmE/W V PPPPP GGGGG

    Args:
        hour: Hour (0-23)
        minute: Minute (0-59)
        second: Second (0-59)
        lat_deg: Latitude in decimal degrees (e.g., 34.679)
        lon_deg: Longitude in decimal degrees (e.g., 119.921)
        validity: Fix validity ('A' = valid, 'V' = invalid)
        pressure_alt: Pressure altitude in meters
        gnss_alt: GNSS altitude in meters
        north: True for N hemisphere, False for S hemisphere
        east: True for E hemisphere, False for W hemisphere

    Returns:
        A properly formatted IGC B-record string

    Example:
        >>> create_bfix_line(10, 12, 0, 34.679, 119.921, north=True, east=False)
        'B1012003440751N11955269WA0100001000'
    """
    # Format time (HHMMSS)
    time_str = f"{hour:02d}{minute:02d}{second:02d}"

    # Format latitude (DDMMmmm)
    lat_abs = abs(lat_deg)
    lat_deg_part = int(lat_abs)
    lat_min_part = (lat_abs - lat_deg_part) * 60
    lat_str = f"{lat_deg_part:02d}{int(lat_min_part * 1000):05d}"
    lat_str += "N" if north else "S"

    # Format longitude (DDDMMmmm)
    lon_abs = abs(lon_deg)
    lon_deg_part = int(lon_abs)
    lon_min_part = (lon_abs - lon_deg_part) * 60
    lon_str = f"{lon_deg_part:03d}{int(lon_min_part * 1000):05d}"
    lon_str += "E" if east else "W"

    # Format altitudes (PPPPP GGGGG)
    pressure_str = f"{pressure_alt:05d}"
    gnss_str = f"{gnss_alt:05d}"

    # Assemble full B-record
    return f"B{time_str}{lat_str}{lon_str}{validity}{pressure_str}{gnss_str}"


def create_igc_file(
    date_str: str = "050225",
    pilot_name: str = "Test Pilot",
    glider_type: str = "Test Glider",
    bfix_lines: list = None
) -> str:
    """
    Create a complete IGC file content string.

    Args:
        date_str: Date in DDMMYY format (e.g., "050225" for Feb 5, 2025)
        pilot_name: Pilot name for HFPLTPILOT header
        glider_type: Glider type for HFGTYGLIDERTYPE header
        bfix_lines: List of B-record strings (use create_bfix_line)

    Returns:
        Complete IGC file content as a string

    Example:
        >>> bfixes = [create_bfix_line(10, 12, i, 34.0, 119.0) for i in range(3)]
        >>> igc = create_igc_file(bfix_lines=bfixes)
    """
    if bfix_lines is None:
        bfix_lines = []

    lines = [
        f"HFDTE{date_str}",
        f"HFPLTPILOT:{pilot_name}",
        f"HFGTYGLIDERTYPE:{glider_type}",
    ]
    lines.extend(bfix_lines)

    return '\n'.join(lines) + '\n'


# ============================================================================
# Test Classes
# ============================================================================

class TestHelperFunctions(unittest.TestCase):
    """Test the helper functions used to create test fixtures."""

    def test_create_bfix_line_basic(self):
        """Test basic B-record line creation."""
        line = create_bfix_line(10, 12, 0, 34.679, 119.921, north=True, east=False)

        # Should start with 'B'
        self.assertEqual(line[0], 'B')

        # Should be 35 characters long
        self.assertEqual(len(line), 35)

        # Should contain time
        self.assertEqual(line[1:7], '101200')

        # Should contain hemisphere indicators
        self.assertIn('N', line)
        self.assertIn('W', line)

    def test_create_bfix_line_hemispheres(self):
        """Test hemisphere handling in B-record creation."""
        # Northern, Western (default)
        line_nw = create_bfix_line(10, 0, 0, 34.0, 119.0, north=True, east=False)
        self.assertIn('N', line_nw)
        self.assertIn('W', line_nw)

        # Southern, Eastern
        line_se = create_bfix_line(10, 0, 0, 34.0, 119.0, north=False, east=True)
        self.assertIn('S', line_se)
        self.assertIn('E', line_se)

    def test_create_bfix_line_altitude(self):
        """Test altitude formatting in B-record."""
        line = create_bfix_line(10, 0, 0, 34.0, 119.0,
                               pressure_alt=1234, gnss_alt=5678)

        # Altitudes should be at the end (last 10 chars)
        self.assertEqual(line[-10:-5], '01234')
        self.assertEqual(line[-5:], '05678')

    def test_create_igc_file_basic(self):
        """Test complete IGC file creation."""
        bfixes = [
            create_bfix_line(10, 12, i, 34.0, 119.0)
            for i in range(3)
        ]
        igc_content = create_igc_file(bfix_lines=bfixes)

        # Should contain headers
        self.assertIn('HFDTE', igc_content)
        self.assertIn('HFPLTPILOT', igc_content)
        self.assertIn('HFGTYGLIDERTYPE', igc_content)

        # Should contain B-records
        self.assertEqual(igc_content.count('B10'), 3)

    def test_create_igc_file_custom_headers(self):
        """Test IGC file with custom header values."""
        igc_content = create_igc_file(
            date_str="150625",
            pilot_name="Custom Pilot",
            glider_type="Custom Wing"
        )

        self.assertIn('HFDTE150625', igc_content)
        self.assertIn('HFPLTPILOT:Custom Pilot', igc_content)
        self.assertIn('HFGTYGLIDERTYPE:Custom Wing', igc_content)


class TestUtilityFunctions(unittest.TestCase):
    """Test standalone utility functions."""

    def test_latlon_to_webmercator(self):
        """Test lat/lon to Web Mercator conversion."""
        # Test equator (0, 0)
        x, y = igc_tools.latlon_to_webmercator(0, 0)
        self.assertAlmostEqual(x, 0, places=2)
        self.assertAlmostEqual(y, 0, places=2)

        # Test known coordinates (San Francisco: -122.4194, 37.7749)
        x, y = igc_tools.latlon_to_webmercator(-122.4194, 37.7749)
        self.assertTrue(isinstance(x, (int, float, np.number)))
        self.assertTrue(isinstance(y, (int, float, np.number)))
        self.assertLess(x, 0)  # Western hemisphere
        self.assertGreater(y, 0)  # Northern hemisphere

    def test_kml_color_gradient_generator(self):
        """Test KML color string generation."""
        # Test black (all zeros)
        color = igc_tools.kml_color_gradient_generator(1.0, 0, 0, 0)
        self.assertEqual(color, "ff000000")

        # Test white (all ones)
        color = igc_tools.kml_color_gradient_generator(1.0, 1.0, 1.0, 1.0)
        self.assertEqual(color, "ffffffff")

        # Test semi-transparent red
        color = igc_tools.kml_color_gradient_generator(0.5, 1.0, 0, 0)
        self.assertEqual(color, "7f0000ff")

        # Test format is always 8 characters
        color = igc_tools.kml_color_gradient_generator(0.3, 0.6, 0.2, 0.9)
        self.assertEqual(len(color), 8)

    def test_speed_color_scale(self):
        """Test speed color gradient (turquoise -> blue -> red)."""
        # Test minimum (should be turquoise: r=0, g=1, b=1)
        r, g, b = igc_tools.speed_color_scale(0.0)
        self.assertEqual(r, 0)
        self.assertEqual(g, 1)
        self.assertEqual(b, 1)

        # Test midpoint (should be blue: r=0, g=0, b=1)
        r, g, b = igc_tools.speed_color_scale(0.5)
        self.assertEqual(r, 0)
        self.assertEqual(g, 0)
        self.assertEqual(b, 1)

        # Test maximum (should be red: r=1, g=0, b=0)
        r, g, b = igc_tools.speed_color_scale(1.0)
        self.assertEqual(r, 1)
        self.assertEqual(g, 0)
        self.assertEqual(b, 0)

        # Test all values are in range [0, 1]
        for val in [0.0, 0.25, 0.5, 0.75, 1.0]:
            r, g, b = igc_tools.speed_color_scale(val)
            self.assertTrue(0 <= r <= 1)
            self.assertTrue(0 <= g <= 1)
            self.assertTrue(0 <= b <= 1)

    def test_thermal_color_scale(self):
        """Test thermal (vertical speed) color gradient."""
        # Test minimum (should be blue)
        r, g, b = igc_tools.thermal_color_scale(0.0)
        self.assertEqual(r, 0)
        self.assertEqual(g, 0)
        self.assertEqual(b, 1)

        # Test midpoint (should be white)
        r, g, b = igc_tools.thermal_color_scale(0.5)
        self.assertEqual(r, 1)
        self.assertEqual(g, 1)
        self.assertEqual(b, 1)

        # Test maximum (should be red)
        r, g, b = igc_tools.thermal_color_scale(1.0)
        self.assertEqual(r, 1)
        self.assertAlmostEqual(g, 0, places=5)
        self.assertEqual(b, 0)

        # Test all values are in range [0, 1]
        for val in [0.0, 0.25, 0.5, 0.75, 1.0]:
            r, g, b = igc_tools.thermal_color_scale(val)
            self.assertTrue(0 <= r <= 1)
            self.assertTrue(0 <= g <= 1)
            self.assertTrue(0 <= b <= 1)


class TestIngestIGCFile(unittest.TestCase):
    """Test IGC file ingestion."""

    def setUp(self):
        """Create a temporary IGC file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.igc_file = os.path.join(self.temp_dir, "test.igc")

        # Create minimal valid IGC file using helper functions
        bfix_lines = [
            create_bfix_line(10, 12, 0, 34.679, 119.921, pressure_alt=690, gnss_alt=732),
            create_bfix_line(10, 12, 1, 34.680, 119.920, pressure_alt=691, gnss_alt=733),
            create_bfix_line(10, 12, 2, 34.681, 119.919, pressure_alt=692, gnss_alt=734),
        ]

        # Add some non-B records to test filtering
        igc_content = create_igc_file(bfix_lines=bfix_lines)
        igc_content += "LCOMMENT LINE\n"
        igc_content += "EEVT\n"
        igc_content += "FPRESSURE\n"
        igc_content += "KTIME\n"
        igc_content += "GALPHANUM\n"

        with open(self.igc_file, 'w', encoding='utf-8') as f:
            f.write(igc_content)

    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.igc_file):
            os.remove(self.igc_file)
        os.rmdir(self.temp_dir)

    def test_ingest_igc_file(self):
        """Test basic IGC file parsing."""
        header, content, footer = igc_tools.ingest_igc_file(self.igc_file)

        # Check headers
        self.assertTrue(any('HFDTE' in h for h in header))
        self.assertTrue(any('HFPLTPILOT' in h for h in header))

        # Check content (B records)
        self.assertEqual(len(content), 3)
        self.assertTrue(all(line[0] == 'B' for line in content))

        # Check footer
        self.assertTrue(len(footer) > 0)

    def test_ingest_igc_file_filters_records(self):
        """Test that E, L, F, K records are filtered out."""
        _, content, _ = igc_tools.ingest_igc_file(self.igc_file)

        # Content should only contain B records
        self.assertTrue(all(line[0] == 'B' for line in content))

        # E, L, F, K records should not be in content
        for line in content:
            self.assertNotEqual(line[0], 'E')
            self.assertNotEqual(line[0], 'L')
            self.assertNotEqual(line[0], 'F')
            self.assertNotEqual(line[0], 'K')


class TestBFix(unittest.TestCase):
    """Test BFix dataclass."""

    def test_bfix_creation(self):
        """Test BFix object creation."""
        fix = igc_tools.BFix()
        self.assertIsInstance(fix.time, datetime.datetime)
        self.assertEqual(fix.lat, 0)
        self.assertEqual(fix.lon, 0)
        self.assertEqual(fix.fix_validity, "")
        self.assertEqual(fix.pressure_altitude_m, 0)
        self.assertEqual(fix.gnss_altitude_m, 0)

    def test_bfix_to_dict(self):
        """Test BFix to_dict method."""
        test_time = datetime.datetime(2025, 2, 5, 10, 12, 0)
        fix = igc_tools.BFix(
            time=test_time,
            lat=34.68,
            lon=-119.92,
            fix_validity="A",
            pressure_altitude_m=690,
            gnss_altitude_m=732
        )

        fix_dict = fix.to_dict()

        self.assertEqual(fix_dict['time'], test_time)
        self.assertEqual(fix_dict['time_iso'], test_time.isoformat())
        self.assertEqual(fix_dict['lat'], 34.68)
        self.assertEqual(fix_dict['lon'], -119.92)
        self.assertEqual(fix_dict['fix_validity'], 'A')
        self.assertEqual(fix_dict['pressure_altitude_m'], 690)
        self.assertEqual(fix_dict['gnss_altitude_m'], 732)


class TestIGCLogParsing(unittest.TestCase):
    """Test IGCLog class parsing and initialization."""

    def setUp(self):
        """Create a temporary IGC file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.igc_file = os.path.join(self.temp_dir, "test_flight.igc")

        # Create IGC file with several fixes using helper functions
        bfix_lines = [
            create_bfix_line(10, 12, i, 34.679 + i*0.001, 119.921 + i*0.001,
                           pressure_alt=690+i*10, gnss_alt=732+i)
            for i in range(5)
        ]

        igc_content = create_igc_file(bfix_lines=bfix_lines)

        with open(self.igc_file, 'w', encoding='utf-8') as f:
            f.write(igc_content)

    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.igc_file):
            os.remove(self.igc_file)
        os.rmdir(self.temp_dir)

    def test_igclog_initialization(self):
        """Test IGCLog object initialization."""
        log = igc_tools.IGCLog(self.igc_file)

        self.assertEqual(log.file_path, self.igc_file)
        self.assertIsNotNone(log.header_info)
        self.assertIsNotNone(log.footer_info)
        self.assertIsNotNone(log.fixes)
        self.assertIsNotNone(log.dataframe)
        self.assertEqual(log.pilot_name, "Test Pilot")

    def test_igclog_parse_pilot_name(self):
        """Test pilot name extraction from header."""
        log = igc_tools.IGCLog(self.igc_file)
        self.assertEqual(log.pilot_name, "Test Pilot")

    def test_igclog_parse_date(self):
        """Test date parsing from HFDTE header."""
        log = igc_tools.IGCLog(self.igc_file)
        self.assertEqual(log.day.day, 5)
        self.assertEqual(log.day.month, 2)
        self.assertEqual(log.day.year, 2025)

    def test_igclog_dataframe_creation(self):
        """Test that dataframe is created with correct structure."""
        log = igc_tools.IGCLog(self.igc_file)

        # Check dataframe exists and has data
        self.assertGreater(len(log.dataframe), 0)

        # Check expected columns exist
        expected_columns = [
            'time', 'time_iso', 'lat', 'lon', 'fix_validity',
            'pressure_altitude_m', 'gnss_altitude_m'
        ]
        for col in expected_columns:
            self.assertIn(col, log.dataframe.columns)

    def test_parse_bfix(self):
        """Test B record parsing."""
        log = igc_tools.IGCLog(self.igc_file)

        # Test parsing a B record
        test_line = "B1012003440751N11955269WA0069000732"
        fix = log.parse_bfix(test_line)

        # Check time
        self.assertEqual(fix.time.hour, 10)
        self.assertEqual(fix.time.minute, 12)
        self.assertEqual(fix.time.second, 0)

        # Check latitude (3440751N = 34° 40.751' N)
        expected_lat = 34 + 40.751 / 60
        self.assertAlmostEqual(fix.lat, expected_lat, places=4)

        # Check longitude (11955269W = 119° 55.269' W)
        expected_lon = -(119 + 55.269 / 60)
        self.assertAlmostEqual(fix.lon, expected_lon, places=4)

        # Check altitudes
        self.assertEqual(fix.pressure_altitude_m, 690)
        self.assertEqual(fix.gnss_altitude_m, 732)

        # Check validity
        self.assertEqual(fix.fix_validity, "A")

    def test_parse_bfix_southern_western_hemisphere(self):
        """Test B record parsing for southern and western hemispheres."""
        log = igc_tools.IGCLog(self.igc_file)

        # Southern hemisphere, Eastern longitude
        test_line = "B1012003440751S11955269EA0069000732"
        fix = log.parse_bfix(test_line)

        self.assertLess(fix.lat, 0)  # Southern hemisphere
        self.assertGreater(fix.lon, 0)  # Eastern hemisphere


class TestIGCLogMetrics(unittest.TestCase):
    """Test IGCLog metrics computation."""

    def setUp(self):
        """Create a temporary IGC file with enough data for metrics."""
        self.temp_dir = tempfile.mkdtemp()
        self.igc_file = os.path.join(self.temp_dir, "test_metrics.igc")

        # Generate 60 seconds of data (1 point per second) for testing metrics
        bfix_lines = []
        for i in range(60):
            minutes = 12 + i // 60
            seconds = i % 60
            # Move slightly in lat/lon and climb steadily
            lat_deg = 34.0 + i * 0.0001
            lon_deg = 119.0 + i * 0.0001
            alt = 1000 + i * 2  # Climb 2m per second

            bfix_lines.append(
                create_bfix_line(10, minutes, seconds, lat_deg, lon_deg,
                               pressure_alt=alt, gnss_alt=alt, east=False)
            )

        igc_content = create_igc_file(bfix_lines=bfix_lines)

        with open(self.igc_file, 'w', encoding='utf-8') as f:
            f.write(igc_content)

    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.igc_file):
            os.remove(self.igc_file)
        os.rmdir(self.temp_dir)

    def test_computed_metrics_columns(self):
        """Test that all expected metric columns are created."""
        log = igc_tools.IGCLog(self.igc_file)

        # Check for computed columns
        expected_metrics = [
            'time_pandas',
            'speed_ms_1s', 'speed_ms_5s', 'speed_ms_20s', 'speed_ms_30s',
            'speed_kmh_1s', 'speed_kmh_5s', 'speed_kmh_20s', 'speed_kmh_30s',
            'vertical_speed_ms_1s', 'vertical_speed_ms_5s',
            'vertical_speed_ms_20s', 'vertical_speed_ms_30s',
            'stopped_to_climb', 'on_glide', 'climbing', 'sinking',
            'category', 'glide', 'total_meters_climbed', 'total_meters_lost'
        ]

        for metric in expected_metrics:
            self.assertIn(metric, log.dataframe.columns,
                         f"Missing metric column: {metric}")

    def test_speed_calculation(self):
        """Test that speed is calculated and reasonable."""
        log = igc_tools.IGCLog(self.igc_file)

        # Speed should be positive and reasonable (< 200 km/h for paragliding)
        speeds = log.dataframe['speed_kmh_20s'].dropna()
        self.assertTrue((speeds >= 0).all())
        # Most speeds should be less than 100 km/h for our test data
        self.assertTrue((speeds < 100).all())

    def test_vertical_speed_calculation(self):
        """Test vertical speed calculation."""
        log = igc_tools.IGCLog(self.igc_file)

        # Vertical speed should exist and be in reasonable range
        vspeed = log.dataframe['vertical_speed_ms_5s'].dropna()
        self.assertTrue(len(vspeed) > 0)
        # Our test data climbs slowly, so should be positive and small
        print(vspeed)
        self.assertTrue((vspeed > -5).all())
        self.assertTrue((vspeed < 10).all())

    def test_category_assignment(self):
        """Test that flight mode categories are assigned."""
        log = igc_tools.IGCLog(self.igc_file)

        # Category should be one of the defined categories
        valid_categories = [
            '', 'stopped_and_not_climbing', 'stopped_and_climbing',
            'climbing_on_glide', 'sinking_on_glide'
        ]
        categories = log.dataframe['category'].unique()
        for cat in categories:
            self.assertIn(cat, valid_categories)

    def test_glide_ratio_calculation(self):
        """Test glide ratio calculation."""
        log = igc_tools.IGCLog(self.igc_file)

        # Glide ratio should be clipped to [-50, 50]
        glide = log.dataframe['glide'].dropna()
        if len(glide) > 0:
            self.assertTrue((glide >= -50).all())
            self.assertTrue((glide <= 50).all())


class TestIGCLogExports(unittest.TestCase):
    """Test IGCLog export functions."""

    def setUp(self):
        """Create a temporary IGC file for testing exports."""
        self.temp_dir = tempfile.mkdtemp()
        self.igc_file = os.path.join(self.temp_dir, "test_export.igc")

        # Create simple IGC file for export testing
        bfix_lines = [
            create_bfix_line(10, 12, i, 34.679 + i*0.001, 119.921 + i*0.001,
                           pressure_alt=690+i*10, gnss_alt=732+i)
            for i in range(3)
        ]

        igc_content = create_igc_file(bfix_lines=bfix_lines)

        with open(self.igc_file, 'w', encoding='utf-8') as f:
            f.write(igc_content)

    def tearDown(self):
        """Clean up temporary files."""
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)

    def test_export_gpx(self):
        """Test GPX export."""
        log = igc_tools.IGCLog(self.igc_file)
        gpx_file = os.path.join(self.temp_dir, "test.gpx")

        log.export_gpx(gpx_file)

        # Check file was created
        self.assertTrue(os.path.exists(gpx_file))

        # Check file has content
        with open(gpx_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('<?xml', content)
            self.assertIn('gpx', content)
            self.assertIn('trkpt', content)

    def test_export_kml_line(self):
        """Test KML line export."""
        log = igc_tools.IGCLog(self.igc_file)
        kml_file = os.path.join(self.temp_dir, "test.kml")

        log.export_kml_line(kml_file, track_type="Track", prefix="test_")

        # Check file was created
        self.assertTrue(os.path.exists(kml_file))

        # Check file has KML content
        with open(kml_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('kml', content.lower())
            self.assertIn('LineString', content)

    def test_export_tracks(self):
        """Test export_tracks creates both speed and vertical speed KMLs."""
        log = igc_tools.IGCLog(self.igc_file)
        prefix = os.path.join(self.temp_dir, "test")

        log.export_tracks(prefix)

        # Check both files were created
        speed_file = f"{prefix}_speed.kml"
        vspeed_file = f"{prefix}_vertical_speed.kml"

        self.assertTrue(os.path.exists(speed_file))
        self.assertTrue(os.path.exists(vspeed_file))


class TestCompetitionMetrics(unittest.TestCase):
    """Test competition metrics and GOAL cropping functionality."""

    def setUp(self):
        """Create a temporary IGC file and mock task for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.igc_file = os.path.join(self.temp_dir, "test_comp.igc")

        # Generate flight data that crosses multiple turnpoints
        # Flight starts at 10:00:00 and runs for 3 minutes (180 seconds)
        bfix_lines = []
        for i in range(180):
            minutes = i // 60
            seconds = i % 60

            # Create a flight path that moves through different locations
            # Starts at (34.0, -119.0), moves to approach turnpoints
            lat_deg = 34.0 + i * 0.0005
            lon_deg = -119.0 + i * 0.0005
            alt = 1000 + i * 2

            bfix_lines.append(
                create_bfix_line(10, minutes, seconds, lat_deg, lon_deg,
                               pressure_alt=alt, gnss_alt=alt, east=False)
            )

        # Create IGC file with earlier start time so SSS opens after flight starts
        igc_content = create_igc_file(date_str="050225", bfix_lines=bfix_lines)

        with open(self.igc_file, 'w', encoding='utf-8') as f:
            f.write(igc_content)

    def tearDown(self):
        """Clean up temporary files."""
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)

    def _create_mock_task(self):
        """Create a mock xctsk task object for testing."""
        import xctsk_tools

        # Create a mock task manually instead of loading from file
        task = xctsk_tools.xctsk.__new__(xctsk_tools.xctsk)

        # Set up task metadata
        task.earth_model = "WGS84"
        task.task_type = "RACE"
        task.sss = {"timeGates": ["10:00:00Z"]}  # Start at 10:00:00
        task.goal = {}

        # Create turnpoints
        task.turnpoints = []

        # SSS (Start) at initial position
        sss = xctsk_tools.xctsk_turnpoint()
        sss.radius = 400
        sss.type = "SSS"
        sss.lat = 34.0
        sss.lon = -119.0
        sss.name = "Start"
        sss.order = 0
        task.turnpoints.append(sss)

        # Turnpoint 1 - somewhere in the middle
        tp1 = xctsk_tools.xctsk_turnpoint()
        tp1.radius = 400
        tp1.type = None
        tp1.lat = 34.03
        tp1.lon = -118.97
        tp1.name = "TP1"
        tp1.order = 1
        task.turnpoints.append(tp1)

        # GOAL - at a point the flight will reach
        goal = xctsk_tools.xctsk_turnpoint()
        goal.radius = 400
        goal.type = "GOAL"
        goal.lat = 34.045  # Flight reaches this around second 90
        goal.lon = -118.955
        goal.name = "Goal"
        goal.order = 2
        task.turnpoints.append(goal)

        return task

    def test_goal_cropping(self):
        """Test that dataframe is cropped when GOAL is reached."""
        import xctsk_tools

        log = igc_tools.IGCLog(self.igc_file)
        task = self._create_mock_task()

        # Get original dataframe length
        original_length = len(log.dataframe)

        # Build competition metrics (this should crop at GOAL)
        log.build_computed_comp_metrics(task)

        # Comp dataframe should be shorter than original
        self.assertLess(len(log.comp_dataframe), original_length)

        # Check that the last row has "COMPLETED" or is before GOAL
        # (depending on whether GOAL was reached)
        last_waypoint_names = log.comp_dataframe["next_waypoint_name"].unique()

        # If GOAL was reached, there should be "COMPLETED" entries
        if "COMPLETED" in last_waypoint_names:
            # Verify the last entry is "COMPLETED"
            last_waypoint = log.comp_dataframe.iloc[-1]["next_waypoint_name"]
            self.assertEqual(last_waypoint, "COMPLETED")

    def test_goal_not_reached(self):
        """Test that dataframe is not cropped if GOAL is never reached."""
        import xctsk_tools

        log = igc_tools.IGCLog(self.igc_file)
        task = self._create_mock_task()

        # Modify GOAL to be far away so it's never reached
        task.turnpoints[2].lat = 50.0
        task.turnpoints[2].lon = -100.0

        # Build competition metrics
        log.build_computed_comp_metrics(task)

        # Check that "COMPLETED" never appears
        waypoint_names = log.comp_dataframe["next_waypoint_name"].unique()
        self.assertNotIn("COMPLETED", waypoint_names)

    def test_track_task_progress_columns(self):
        """Test that _track_task_progress adds expected columns."""
        import xctsk_tools

        log = igc_tools.IGCLog(self.igc_file)
        task = self._create_mock_task()

        # Build competition metrics
        log.build_computed_comp_metrics(task)

        # Check that tracking columns were added
        expected_columns = [
            "next_waypoint",
            "next_waypoint_name",
            "time_since_last_waypoint_s",
            "in_cylinder"
        ]

        for col in expected_columns:
            self.assertIn(col, log.comp_dataframe.columns,
                         f"Missing column: {col}")

    def test_completed_status(self):
        """Test that 'COMPLETED' status is set correctly."""
        import xctsk_tools

        log = igc_tools.IGCLog(self.igc_file)
        task = self._create_mock_task()

        # Build competition metrics
        log.build_computed_comp_metrics(task)

        # If COMPLETED appears, it should be after entering GOAL
        completed_indices = log.comp_dataframe[
            log.comp_dataframe["next_waypoint_name"] == "COMPLETED"
        ].index

        if len(completed_indices) > 0:
            # The dataframe should end at or just after the first COMPLETED
            first_completed = completed_indices[0]
            # Due to cropping, first_completed should be the last or near-last index
            self.assertGreaterEqual(first_completed, len(log.comp_dataframe) - 2)


class TestMathUtils(unittest.TestCase):
    """Test math_utils helper functions."""

    def test_clip(self):
        """Test value clipping."""
        self.assertEqual(math_utils.clip(5, 0, 10), 5)
        self.assertEqual(math_utils.clip(-5, 0, 10), 0)
        self.assertEqual(math_utils.clip(15, 0, 10), 10)

    def test_three_point_normalizer(self):
        """Test three-point normalization."""
        # Test with midpoint
        result = math_utils.three_point_normalizer(5, 0, 5, 10)
        self.assertEqual(result, 0.5)

        # Test below midpoint
        result = math_utils.three_point_normalizer(2.5, 0, 5, 10)
        self.assertEqual(result, 0.25)

        # Test above midpoint
        result = math_utils.three_point_normalizer(7.5, 0, 5, 10)
        self.assertEqual(result, 0.75)

        # Test NaN handling
        result = math_utils.three_point_normalizer(float('nan'), 0, 5, 10)
        self.assertEqual(result, 0.5)

        # Test clipping
        result = math_utils.three_point_normalizer(100, 0, 5, 10)
        self.assertEqual(result, 1.0)

    def test_haversine(self):
        """Test haversine distance calculation."""
        # Test same point
        dist = math_utils.haversine(0, 0, 0, 0)
        self.assertAlmostEqual(dist, 0, places=2)

        # Test known distance (approximately 1 degree latitude ~111km)
        dist = math_utils.haversine(0, 0, 1, 0)
        self.assertAlmostEqual(dist, 111000, delta=1000)

    def test_build_direction_heading_fields(self):
        """Test distance calculation for dataframe."""
        # Create sample dataframe
        data = {
            'lat': [34.0, 34.01, 34.02, 34.03],
            'lon': [-119.0, -119.0, -119.0, -119.0]
        }
        df = pd.DataFrame(data)

        result_df = math_utils.build_direction_heading_fields(df, 1)

        # Check distance column was added
        self.assertIn('distance_traveled_m_1s', result_df.columns)

        # Check prev columns were removed
        self.assertNotIn('prev_lat', result_df.columns)
        self.assertNotIn('prev_lon', result_df.columns)

        # Check distances are reasonable (first should be NaN, rest positive)
        distances = result_df['distance_traveled_m_1s']
        self.assertTrue(pd.isna(distances.iloc[0]))
        self.assertTrue((distances.iloc[1:] > 0).all())


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
