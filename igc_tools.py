"""IGC flight log parsing and analysis tools for paragliding."""
import argparse
import datetime
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
import gpxpy
from simplekml import Kml, Color

import igc_tools
import math_utils
import xctsk_tools

MS_TO_KMH = 3.6

FORWARD_TRAVEL_THRESHOLD_20S = 200
CLIMBING_THRESHOLD = -0.5

parser = argparse.ArgumentParser()
parser.add_argument('--in_file', type=str, required=True)
parser.add_argument('--out_file', type=str, required=False, default="")
parser.add_argument('--use_name', action='store_true', required=False)

def latlon_to_webmercator(lon, lat):
    """Convert lat/lon to Web Mercator x/y"""
    x = lon * 20037508.34 / 180
    y = np.log(np.tan((90 + lat) * np.pi / 360)) / (np.pi / 180)
    y = y * 20037508.34 / 180
    return x, y

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
    comp_dataframe: pd.DataFrame = None
    last_hour = None
    pilot_name = None

    def __init__(self, file_path: str):
        """Build an IGCLog file from a given file path"""
        self.file_path = file_path
        self.load_from_file()
        self.build_computed_metrics()

    def load_from_file(self):
        """Using the object's file_path, load the igc file"""
        self.fixes = []
        self.header_info, fixes_list, self.footer_info = igc_tools.ingest_igc_file(self.file_path)

        for header in self.header_info:
            if header[0:5] == "HFDTE":
                # HFDTE050225
                # or HFDTEDATE:080624,01

                date_string = ""
                if header.find("DATE:") != -1:
                    date_string = header.split(":")[1][:6]
                else:
                    date_string = header[5:]
                self.day = datetime.datetime.strptime(date_string, "%d%m%y")
            if header[0:10] == "HFPLTPILOT":
                # HFPLTPILOT:Robert Barlow
                self.pilot_name = header.split(":")[1]

        for fix in fixes_list:
            self.fixes.append(self.parse_bfix(fix))
        self.dataframe = pd.DataFrame.from_dict([bfix.to_dict() for bfix in self.fixes])

    def build_computed_metrics(self):
        self.dataframe["time_pandas"] = pd.to_datetime(self.dataframe["time_iso"], format="%Y-%m-%dT%H:%M:%S")

        self.dataframe["seconds_delta"] = self.dataframe["time_pandas"].diff().dt.total_seconds()
        self.dataframe = self.dataframe[self.dataframe["seconds_delta"] > 0].reset_index(drop=True)

        for time_interval in [1, 5, 20, 30]:
            self.dataframe[f"gnss_altitude_m_delta_{time_interval}s"] = self.dataframe["gnss_altitude_m"].diff(periods=time_interval)
            self.dataframe[f"seconds_delta_{time_interval}s"] = self.dataframe["time_pandas"].diff(periods=time_interval).dt.total_seconds()

            self.dataframe[f"vertical_speed_ms_{time_interval}s"] = (
                self.dataframe[f"gnss_altitude_m_delta_{time_interval}s"] / self.dataframe[f"seconds_delta_{time_interval}s"]
            )

            self.dataframe = math_utils.build_direction_heading_fields(self.dataframe, time_interval)


            self.dataframe[f"speed_ms_{time_interval}s"] = (
                self.dataframe[f"distance_traveled_m_{time_interval}s"] / self.dataframe[f"seconds_delta_{time_interval}s"]
            )

            self.dataframe[f"speed_kmh_{time_interval}s"] = self.dataframe[f"speed_ms_{time_interval}s"] * MS_TO_KMH

        self.dataframe["stopped_to_climb"] = self.dataframe["distance_traveled_m_30s"] < FORWARD_TRAVEL_THRESHOLD_20S
        self.dataframe["on_glide"] = ~self.dataframe["stopped_to_climb"]
        self.dataframe["climbing"] = self.dataframe["vertical_speed_ms_5s"] >= CLIMBING_THRESHOLD
        self.dataframe["sinking"] = ~self.dataframe["climbing"]

        self.dataframe["stopped_and_not_climbing"] = (
            self.dataframe["stopped_to_climb"] & self.dataframe["sinking"]
        )
        self.dataframe["stopped_and_climbing"] = (
            self.dataframe["stopped_to_climb"] & self.dataframe["climbing"]
        )

        self.dataframe["climbing_on_glide"] = self.dataframe["on_glide"] & self.dataframe["climbing"]
        self.dataframe["sinking_on_glide"] = self.dataframe["on_glide"] & self.dataframe["sinking"]

        # Assign categories using loc to avoid SettingWithCopyWarning
        self.dataframe["category"] = ""
        self.dataframe.loc[self.dataframe["stopped_and_not_climbing"], "category"] = "stopped_and_not_climbing"
        self.dataframe.loc[self.dataframe["stopped_and_climbing"], "category"] = "stopped_and_climbing"
        self.dataframe.loc[self.dataframe["climbing_on_glide"], "category"] = "climbing_on_glide"
        self.dataframe.loc[self.dataframe["sinking_on_glide"], "category"] = "sinking_on_glide"
        
        self.dataframe["stopped_and_not_climbing_s"] = self.dataframe["stopped_and_not_climbing"].cumsum()
        self.dataframe["stopped_and_climbing_s"] = self.dataframe["stopped_and_climbing"].cumsum()
        self.dataframe["climbing_on_glide_s"] = self.dataframe["climbing_on_glide"].cumsum()
        self.dataframe["sinking_on_glide_s"] = self.dataframe["sinking_on_glide"].cumsum()

        # Calculate glide ratio only when sinking (negative vertical speed < -0.4 m/s)
        # Glide ratio = horizontal speed / abs(vertical speed)
        self.dataframe["glide"] = np.nan
        self.dataframe.loc[ self.dataframe["on_glide"], "glide"] = (
            self.dataframe.loc[ self.dataframe["on_glide"], "speed_ms_20s"] /
            -self.dataframe.loc[ self.dataframe["on_glide"], "vertical_speed_ms_20s"]
        )
        self.dataframe["glide"] = self.dataframe["glide"].clip(lower=-50, upper=50)

        # Calculate per-second altitude changes
        # Use 5s interval divided by 5 to smooth GPS noise
        self.dataframe["altitude_gain_m"] = (self.dataframe["gnss_altitude_m_delta_5s"] / 5).clip(lower=0)
        self.dataframe["altitude_loss_m"] = (self.dataframe["gnss_altitude_m_delta_5s"] / 5).clip(upper=0)

        # Calculate per-second time spent in each mode
        self.dataframe["time_climbing_s"] = self.dataframe["seconds_delta_1s"].where(self.dataframe["stopped_to_climb"], 0)
        self.dataframe["time_gliding_s"] = self.dataframe["seconds_delta_1s"].where(self.dataframe["on_glide"], 0)

        # Calculate cumulative metrics
        self._calculate_cumulative_metrics(self.dataframe)

        self.dataframe["climb_rate_avg"] = self.dataframe["vertical_speed_ms_5s"].where(self.dataframe["climbing"]).rolling(10).mean()
        
        self.dataframe['lon_wm'], self.dataframe['lat_wm'] = latlon_to_webmercator(self.dataframe['lon'], self.dataframe['lat'])

        # remove intermediaries
        self.dataframe = self.dataframe.drop(
            columns=[
                "seconds_delta",
                "altitude_gain_m"
            ]
        )

    def _calculate_cumulative_metrics(self, df):
        """
        Calculate cumulative metrics for a dataframe.
        This is a helper function to avoid code duplication between
        build_computed_metrics and build_computed_comp_metrics.

        Args:
            df: DataFrame with altitude_gain_m, altitude_loss_m, time_climbing_s,
                time_gliding_s, and category boolean columns

        Modifies the dataframe in place to add cumulative columns.
        """
        # Calculate cumulative altitude metrics
        df["total_meters_climbed"] = df["altitude_gain_m"].cumsum()
        df["total_meters_lost"] = df["altitude_loss_m"].cumsum()

        # Calculate cumulative time spent in each category
        df["stopped_and_not_climbing_s"] = df["stopped_and_not_climbing"].cumsum()
        df["stopped_and_climbing_s"] = df["stopped_and_climbing"].cumsum()
        df["climbing_on_glide_s"] = df["climbing_on_glide"].cumsum()
        df["sinking_on_glide_s"] = df["sinking_on_glide"].cumsum()

        # Calculate cumulative time spent climbing and gliding
        df["cumulative_time_climbing_s"] = df["time_climbing_s"].cumsum()
        df["cumulative_time_gliding_s"] = df["time_gliding_s"].cumsum()

        df["cumulative_distance"] = (df["distance_traveled_m_20s"] / 20).cumsum()

    def build_computed_comp_metrics(self, task: xctsk_tools.xctsk):
        """
        Build competition metrics by filtering the dataframe to only include data
        from the task start time to when GOAL is reached, then recalculating cumulative values.

        Args:
            task: An xctsk object containing the task definition

        Returns:
            pandas.DataFrame: A copy of the dataframe filtered from start to GOAL
                             with recalculated cumulative metrics
        """
        # Extract the first time gate from sss.timeGates
        start_time_str = task.sss['timeGates'][0]

        # Parse the time string (format: "13:00:00Z" or "19:30:00Z")
        # Convert to datetime by combining with the flight date
        time_parts = start_time_str.replace('Z', '').split(':')
        start_hour = int(time_parts[0])
        start_minute = int(time_parts[1])
        start_second = int(time_parts[2])

        # Combine with the flight date
        start_datetime = datetime.datetime.combine(
            self.day.date(),
            datetime.time(hour=start_hour, minute=start_minute, second=start_second)
        )

        # Create a copy of the dataframe and filter to only include data from start time onwards
        self.comp_dataframe = self.dataframe.copy()
        self.comp_dataframe = self.comp_dataframe[
            self.comp_dataframe['time_pandas'] >= start_datetime
        ].reset_index(drop=True)

        # Recalculate per-second altitude changes for the competition window
        self.comp_dataframe["altitude_gain_m"] = (
            self.comp_dataframe["gnss_altitude_m_delta_5s"] / 5
        ).clip(lower=0)
        self.comp_dataframe["altitude_loss_m"] = (
            self.comp_dataframe["gnss_altitude_m_delta_5s"] / 5
        ).clip(upper=0)

        # Recalculate cumulative metrics from the start of the competition window
        self._calculate_cumulative_metrics(self.comp_dataframe)

        # Remove the temporary altitude_gain_m column to match main dataframe
        self.comp_dataframe = self.comp_dataframe.drop(columns=["altitude_gain_m"])

        # Track progress around the task
        self._track_task_progress(self.comp_dataframe, task)

        # Crop dataframe after GOAL waypoint is reached (first instance of "COMPLETED")
        completed_indices = self.comp_dataframe[
            self.comp_dataframe["next_waypoint_name"] == "COMPLETED"
        ].index
        if len(completed_indices) > 0:
            # Get the first index where "COMPLETED" appears
            goal_idx = completed_indices[0]
            # Keep data up to and including when GOAL was reached
            self.comp_dataframe = self.comp_dataframe.iloc[:goal_idx + 1].reset_index(drop=True)

        return self.comp_dataframe

    def _track_task_progress(self, dataframe, task):
        """
        Track progress around the task by determining which waypoint is next
        and how long since entering the last waypoint cylinder.

        Args:
            dataframe: Competition dataframe
            task: xctsk object with turnpoints

        Modifies the dataframe in place to add:
            - next_waypoint: Index of the next turnpoint to reach
            - next_waypoint_name: Name of the next turnpoint
            - time_since_last_waypoint_s: Seconds since first entering the last waypoint cylinder
            - in_cylinder: Boolean indicating if currently inside a turnpoint cylinder
        """
        # Initialize columns
        dataframe["next_waypoint"] = 0
        dataframe["next_waypoint_name"] = ""
        dataframe["time_since_last_waypoint_s"] = 0.0
        dataframe["in_cylinder"] = False

        next_waypoint_index = 0
        turnpoint = task.turnpoints[next_waypoint_index]
        if turnpoint.type == "TAKEOFF":
            next_waypoint_index += 1
        last_waypoint_entry_time = None

        for idx in range(len(dataframe)):
            lat = dataframe.loc[idx, "lat"]
            lon = dataframe.loc[idx, "lon"]
            current_time = dataframe.loc[idx, "time_pandas"]

            # Check if we've reached the ESS waypoint already
            if next_waypoint_index >= (len(task.turnpoints) -1):
                # Finished the task
                dataframe.loc[idx, "next_waypoint"] = len(task.turnpoints)
                dataframe.loc[idx, "next_waypoint_name"] = "COMPLETED"
                continue

            turnpoint = task.turnpoints[next_waypoint_index]
            distance = math_utils.haversine(lat, lon, turnpoint.lat, turnpoint.lon)

            # Check if we're inside the cylinder
            in_cylinder = distance <= turnpoint.radius
            dataframe.loc[idx, "in_cylinder"] = in_cylinder

            # If we enter the cylinder, record the entry time
            if in_cylinder and last_waypoint_entry_time is None:
                last_waypoint_entry_time = current_time

            # Check if we should advance to the next waypoint
            # For SSS, we advance when we EXIT the cylinder
            # For other turnpoints, we advance when we exit after entering
            if turnpoint.type == "SSS":
                # For start, check if we've entered and are now exiting
                if last_waypoint_entry_time is not None and not in_cylinder:
                    # We've exited the start cylinder
                    next_waypoint_index += 1
                    last_waypoint_entry_time = None
            else:
                # For regular turnpoints, advance when exiting after entering
                if in_cylinder and last_waypoint_entry_time is not None:
                    # Check if we're about to exit on the next point
                    if idx < len(dataframe) - 1:
                        next_distance = math_utils.haversine(
                            dataframe.loc[idx + 1, "lat"],
                            dataframe.loc[idx + 1, "lon"],
                            turnpoint.lat,
                            turnpoint.lon
                        )
                        if next_distance > turnpoint.radius:
                            # We're exiting, advance to next waypoint
                            next_waypoint_index += 1
                            last_waypoint_entry_time = None

            # Record current waypoint info (only if not already completed)
            dataframe.loc[idx, "next_waypoint"] = next_waypoint_index
            dataframe.loc[idx, "next_waypoint_name"] = task.turnpoints[next_waypoint_index].name

            # Calculate time since last waypoint entry
            if last_waypoint_entry_time is not None:
                time_delta = (current_time - last_waypoint_entry_time).total_seconds()
                dataframe.loc[idx, "time_since_last_waypoint_s"] = time_delta


    def export_gpx(self, filename):
        gpx_out = gpxpy.gpx.GPX()
        # Create track:
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_out.tracks.append(gpx_track)
        # Create segment in our track:
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        for _, row in self.dataframe.iterrows():
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

        for _, row in self.dataframe.iterrows():
            longitude = row["lon"]
            latitude = row["lat"]
            altitude = row["gnss_altitude_m"]
            time = row["time_iso"]
            if not init:
                init = True
                last_point = [longitude, latitude, altitude]

            current_point = [longitude, latitude, altitude]
            ls = multipnt.newlinestring(coords=[current_point, last_point], altitudemode="absolute")

            ls.style.linestyle.width = 2
            ls.timestamp.when = time


            if track_type == "Speed":
                norm_val = math_utils.three_point_normalizer(row["speed_kmh_20s"], 20, 35, 55)
                r, g, b = speed_color_scale(norm_val)
                ls.style.linestyle.color = kml_color_gradient_generator(1, r, g, b)

            elif track_type == "VerticalSpeed":
                norm_val = math_utils.three_point_normalizer(row["vertical_speed_ms_5s"], -4, -1, 4)
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

    def parse_bfix(self, line: str):
        """Parse a b fix line to a BFix object
        See https://xp-soaring.github.io/igc_file_format/igc_format_2008.html#link_4.1
        Spec:    B HHMMSS DDMMmmmN DDDMMmmmE V PPPPP GGGGG CK
        Example: B 235531 3440751N 11955269W A 00690 00732 54
        """

        fix = BFix()
        assert line[0] == "B"

        # parse time to datetime
        hour = int(line[1:3])
        minute = int(line[3:5])
        sec = int(line[5:7])
        # Check for day rollover
        if self.last_hour == 23 and hour == 0:
            self.day += datetime.timedelta(days=1)

        self.last_hour = hour
        fix.time = datetime.datetime.combine(
            self.day, datetime.time(hour=hour, minute=minute, second=sec)
        )

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




if __name__ == "__main__":
    args = parser.parse_args()

    in_file = args.in_file
    out_file = args.out_file
    use_name = args.use_name

    # strip the ".kml" if it is passed in the string
    if out_file[-4:] == ".kml":
        out_file = out_file[:-4]

    flight_log = igc_tools.IGCLog(in_file)
    if use_name:
        if flight_log.pilot_name is None:
            print("No pilot name found in file, using default filename")
        elif out_file:
            in_dir = os.path.dirname(in_file)
            prefix = f"{in_dir}/{out_file}_"
            prefix += flight_log.pilot_name.lower().replace(" ", "_")
            flight_log.export_tracks(f"{prefix}")
        else:
            in_dir = os.path.dirname(in_file)
            prefix = f"{in_dir}/"
            prefix += flight_log.pilot_name.lower().replace(" ", "_")
            flight_log.export_tracks(f"{prefix}")
    else:
        # Make the output file name the same as the input if none is given
        if not out_file:
            out_file = in_file[:-4]
        flight_log.export_tracks(f"{out_file}")
