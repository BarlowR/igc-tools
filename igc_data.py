import pandas as pd
import numpy as np
import dateutil.parser.isoparser as isoparser
from dataclasses import dataclass
import datetime
import gpxpy

import igc_tools
import math_utils

MS_TO_KMH = 3.6

@dataclass
class IGCLog:
    file_path: str
    header_info = None
    footer_info = None
    fixes: None
    start_time: datetime.datetime=None
    dataframe: pd.DataFrame=None

    def __init__(self, file_path: str):
        """ Build an IGCLog file from a given file path"""
        self.file_path = file_path
        self.load_from_file()
        self.build_computed_metrics()

    def load_from_file(self):
        """ Using the object's file_path, load the igc file"""
        self.fixes = []
        self.header_info, fixes_list, self.footer_info = igc_tools.injest_igc_file(self.file_path)
        for fix in fixes_list:
            self.fixes.append(igc_tools.parse_bfix(fix))
        self.dataframe = pd.DataFrame.from_dict([bfix.to_dict() for bfix in self.fixes])
            

    def build_computed_metrics(self):
        self.dataframe["time_pandas"] = pd.to_datetime(self.dataframe["time_iso"], format="%H:%M:%S")
        self.dataframe["seconds_delta"] = self.dataframe["time_pandas"].diff().dt.total_seconds()
        self.dataframe["pressure_altitude_m_delta"] = self.dataframe["pressure_altitude_m"].diff()
        # self.dataframe["pressure_altitude_m_delta"] = f'rgb({self.dataframe["pressure_altitude_m"]/5 + 0.5}, 1, 1)'
        self.dataframe["gnss_altitude_m_delta"] = self.dataframe["gnss_altitude_m"].diff()
        self.dataframe["vertical_speed_ms"] = self.dataframe["pressure_altitude_m_delta"]/self.dataframe["seconds_delta"]
        self.dataframe["vertical_speed_gnss_ms"] = self.dataframe["gnss_altitude_m_delta"]/self.dataframe["seconds_delta"]
        
        self.dataframe = math_utils.build_direction_heading_fields(self.dataframe)
        self.dataframe["speed_ms"] = self.dataframe["distance_m"]/self.dataframe["seconds_delta"]
        self.dataframe["speed_kmh"] = self.dataframe["speed_ms"] * MS_TO_KMH
        self.dataframe["glide"] = self.dataframe["distance_m"]/self.dataframe["pressure_altitude_m_delta"]
        self.dataframe["glide_gnss"] = self.dataframe["distance_m"]/self.dataframe["gnss_altitude_m_delta"]
        
        self.dataframe["glide_5s"] = (self.dataframe["distance_m"].rolling(window=10).mean() /
                                      self.dataframe["pressure_altitude_m_delta"].rolling(window=10).mean())
        self.dataframe["glide_15s"] = (self.dataframe["distance_m"].rolling(window=30).mean() /
                                      self.dataframe["pressure_altitude_m_delta"].rolling(window=30).mean())
        # remove intermediaries 
        self.dataframe.drop(columns=["seconds_delta", 'pressure_altitude_m_delta', 'gnss_altitude_m_delta'])


        # print(self.dataframe.columns)

    def export_gpx(self, filename):
        gpx_out = gpxpy.gpx.GPX()
        # Create track:
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_out.tracks.append(gpx_track)
        # Create segment in our track:
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        for index, row in self.dataframe.iterrows():
            gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                row["lat"], 
                row["lon"], 
                elevation=row["pressure_altitude_m"]))

        with open(filename, "w") as xml:
            xml.write(gpx_out.to_xml())




    
    
