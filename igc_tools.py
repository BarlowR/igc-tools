import pandas as pd
import numpy as np
from dataclasses import dataclass
import datetime
import gpxpy
import os
from simplekml import Kml, Color
from copy import deepcopy
import argparse


import igc_tools
import math_utils

MS_TO_KMH = 3.6

parser = argparse.ArgumentParser()
parser.add_argument('--in_file', type=str, required=True)
parser.add_argument('--out_file', type=str, required=False)

@dataclass
class BFix:
    """BFix IGC Data Type
    See https://xp-soaring.github.io/igc_file_format/igc_format_2008.html#link_4.1
    """

    time: datetime = datetime.datetime.now()
    lat: float = 0
    lon: float = 0
    fix_validity: str = ""
    pressure_altitude_m: int = 0
    gnss_altitude_m: int = 0

    def to_dict(self):
        return {
            "time": self.time,
            "time_iso": self.time.isoformat(),
            "lat": self.lat,
            "lon": self.lon,
            "fix_validity": self.fix_validity,
            "pressure_altitude_m": self.pressure_altitude_m,
            "gnss_altitude_m": self.gnss_altitude_m,
        }


def ingest_igc_file(igc_file: str):
    """Parse a IGC file into header lines, fix lines and footer lines
    TODO: this could be much better
    """
    header_lines = []
    content_lines = []
    footer_lines = []
    with open(igc_file, "r") as igc_file:
        header = True
        contents = False
        footer = False

        for line in igc_file:
            # remove the \n
            line = line[:-1]
            if header:
                if line[0] == "B":
                    content_lines.append(line)
                    header = False
                    contents = True
                header_lines.append(line)
                continue
            if contents:
                if line[0] != "B":
                    if line[0] == "E":
                        continue
                    if line[0] == "L":
                        continue
                    if line[0] == "F":
                        continue
                    if line[0] == "K":
                        continue
                    contents = False
                    footer = True
                    footer_lines.append(line)
                    continue
                content_lines.append(line)
                continue
            if footer:
                footer_lines.append(line)
    return (header_lines, content_lines, footer_lines)


def parse_bfix(line: str):
    """Parse a b fix line to a BFix object
    See https://xp-soaring.github.io/igc_file_format/igc_format_2008.html#link_4.1
    Spec:    B HHMMSS DDMMmmmN DDDMMmmmE V PPPPP GGGGG CK
    Example: B 235531 3440751N 11955269W A 00690 00732 54
    """

    fix = BFix()
    assert line[0] == "B"

    # parse time to datetime
    hour = int(line[1:3])
    min = int(line[3:5])
    sec = int(line[5:7])
    fix.time = datetime.time(hour=hour, minute=min, second=sec)

    # pull latitude
    lat_degrees = int(line[7:9])
    lat_minutes = int(line[9:14]) / 1000
    north = line[14] == "N"
    fix.lat = lat_degrees + lat_minutes / 60
    fix.lat *= 1 if north else -1

    # pull longitude
    lon_degrees = int(line[15:18])
    lon_minutes = int(line[18:23]) / 1000

    east = line[23] == "E"
    fix.lon = lon_degrees + lon_minutes / 60
    fix.lon *= 1 if east else -1
    fix.fix_validity = line[24]

    # pressure altitude
    fix.pressure_altitude_m = int(line[25:30])
    # gps altitude
    fix.gnss_altitude_m = int(line[30:35])
    return fix


def kml_color_gradient_generator(a, r, g, b):
    """Takes in alpha, red, green and blue values between 0-1 and returns a KML color string"""
    return "%02x%02x%02x%02x" % (int(a * 255), int(b * 255), int(g * 255), int(r * 255))


def speed_color_scale(speed):
    """Takes in a normalized speed value (0-1) and returns an RGB color tuple."""
    r, g, b = (0, 0, 0)

    # Low range, turquise to blue
    if speed < 0.5:
        # scale to 0-1
        speed *= 2

        r = 0
        g = 1 - speed
        b = 1
    # high range, blue to red
    else:
        speed = (speed - 0.5) * 2
        r = speed
        g = 0
        b = 1 - speed

    return (r, g, b)


def thermal_color_scale(speed):
    """
    Takes in a normalized vertical speed value (0-1) and returns an RGB color tuple.
    """
    r, g, b = (0, 0, 0)

    # Low range, blue to white
    if speed < 0.5:
        # scale to 0-1
        speed *= 2

        r = speed
        g = speed
        b = 1
    # mid-high range, white to orange
    elif speed < 0.75:
        speed = (speed - 0.5) * 4
        r = 1
        g = 1 - (speed / 2)
        b = 1 - speed
    # high range, orange to red
    else:
        speed = (speed - 0.75) * 4
        r = 1
        g = 0.5 - (speed / 2)
        b = 0

    return (r, g, b)


@dataclass
class IGCLog:
    file_path: str
    header_info = None
    # TODO: Parse headers. Specifically datetime so we can do timestamped kml tracks
    footer_info = None
    fixes: None
    start_time: datetime.datetime = None
    dataframe: pd.DataFrame = None

    def __init__(self, file_path: str):
        """Build an IGCLog file from a given file path"""
        self.file_path = file_path
        self.load_from_file()
        self.build_computed_metrics()

    def load_from_file(self):
        """Using the object's file_path, load the igc file"""
        self.fixes = []
        self.header_info, fixes_list, self.footer_info = igc_tools.ingest_igc_file(self.file_path)

        for fix in fixes_list:
            self.fixes.append(igc_tools.parse_bfix(fix))
        self.dataframe = pd.DataFrame.from_dict([bfix.to_dict() for bfix in self.fixes])

    def build_computed_metrics(self):
        self.dataframe["time_pandas"] = pd.to_datetime(self.dataframe["time_iso"], format="%H:%M:%S")

        self.dataframe["seconds_delta"] = self.dataframe["time_pandas"].diff().dt.total_seconds()
        self.dataframe = self.dataframe[self.dataframe["seconds_delta"] > 0]
        self.dataframe["pressure_altitude_m_delta"] = self.dataframe["pressure_altitude_m"].diff()

        self.dataframe["gnss_altitude_m_delta"] = self.dataframe["gnss_altitude_m"].diff()

        self.dataframe["vertical_speed_ms"] = (
            self.dataframe["pressure_altitude_m_delta"] / self.dataframe["seconds_delta"]
        )
        self.dataframe["vertical_speed_gnss_ms"] = (
            self.dataframe["gnss_altitude_m_delta"] / self.dataframe["seconds_delta"]
        )
        self.dataframe["vertical_speed_gnss_average_ms"] = (
            self.dataframe["vertical_speed_gnss_ms"].rolling(4, center=True).mean()
        )

        self.dataframe = math_utils.build_direction_heading_fields(self.dataframe)
        self.dataframe["speed_ms"] = self.dataframe["distance_traveled_m_4s"] / (
            self.dataframe["seconds_delta"].rolling(4).sum()
        )
        self.dataframe["speed_kmh"] = self.dataframe["speed_ms"] * MS_TO_KMH
        self.dataframe["speed_kmh_average"] = self.dataframe["speed_ms"].rolling(20, center=True).mean() * MS_TO_KMH
        self.dataframe["glide"] = self.dataframe["speed_ms"] / -self.dataframe["vertical_speed_gnss_average_ms"]
        self.dataframe["glide"][self.dataframe["vertical_speed_gnss_average_ms"] > -0.4] = np.nan

        self.dataframe["glide_60s"] = self.dataframe["glide"].rolling(120, center=True, min_periods=30).mean()
        # remove intermediaries
        self.dataframe.drop(
            columns=[
                "seconds_delta",
                "pressure_altitude_m_delta",
                "gnss_altitude_m_delta",
            ]
        )

        self.dataframe.dropna()

    def export_gpx(self, filename):
        gpx_out = gpxpy.gpx.GPX()
        # Create track:
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_out.tracks.append(gpx_track)
        # Create segment in our track:
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        for index, row in self.dataframe.iterrows():
            gpx_segment.points.append(
                gpxpy.gpx.GPXTrackPoint(row["lat"], row["lon"], elevation=row["pressure_altitude_m"])
            )

        with open(filename, "w") as xml:
            xml.write(gpx_out.to_xml())

    def export_kml_line(self, filename, track_type="Track", prefix=None, visibility=True):
        kml = Kml()
        multipnt = kml.newfolder(name=f"{prefix}{track_type}")
        last_point = [0, 0, 0]
        init = False

        for idx, row in self.dataframe.iterrows():
            longitude = row["lon"]
            latitude = row["lat"]
            altitude = row["gnss_altitude_m"]
            if init == False:
                init = True
                last_point = [longitude, latitude, altitude]

            current_point = [longitude, latitude, altitude]
            ls = multipnt.newlinestring(coords=[current_point, last_point], altitudemode="absolute")

            ls.style.linestyle.width = 2

            if track_type == "Speed":
                norm_val = math_utils.three_point_normalizer(row["speed_kmh_average"], 20, 35, 55)
                r, g, b = speed_color_scale(norm_val)
                ls.style.linestyle.color = kml_color_gradient_generator(1, r, g, b)

            elif track_type == "VerticalSpeed":
                norm_val = math_utils.three_point_normalizer(row["vertical_speed_gnss_average_ms"], -4, -1, 4)
                r, g, b = thermal_color_scale(norm_val)
                ls.style.linestyle.color = kml_color_gradient_generator(1, r, g, b)

            else:
                ls.style.linestyle.color = Color.red

            ls.visible = visibility
            last_point = current_point

        kml.save(filename)

    def export_tracks(self, file_prefix):
        """Export both types of colored kml track
        TODO: Merge into one KML file
        """

        self.export_kml_line(f"{file_prefix}_speed.kml", "Speed", prefix=file_prefix, visibility=False)
        self.export_kml_line(f"{file_prefix}_vertical_speed.kml", "VerticalSpeed", prefix=file_prefix)



if __name__ == "__main__":
    args = parser.parse_args()

    in_file = args.in_file
    out_file = args.out_file

    # Make the output file name the same as the input if none is given
    if not out_file:
        out_file = in_file[:-6]

    # strip the ".kml" if it is passed in the string
    elif out_file[-4:] == ".kml":
        out_file = out_file[:-4]

    flight_log = igc_tools.IGCLog(in_file)
    flight_log.export_tracks(f"{out_file}")
