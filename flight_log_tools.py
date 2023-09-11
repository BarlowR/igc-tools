from igc_tools import *
from math_utils import *
import pandas as pd
import numpy as np
import dateutil.parser.isoparser as isoparser


@dataclass
class IGCLog:
    filename: str
    header_info = None
    footer_info = None
    fixes: None
    start_time: datetime.datetime=None
    dataframe: pd.DataFrame=None

    def __init__(self, filename: str):
        self.filename = filename
        self.load_from_file()
        self.build_computed_metrics()


    def load_from_file(self):
        self.fixes = []
        self.header_info, fixes_list, self.footer_info = injest_igc_file(self.filename)
        for fix in fixes_list:
            self.fixes.append(parse_bfix(fix))

        self.dataframe = pd.DataFrame.from_dict([bfix.to_dict() for bfix in self.fixes])
            

    def build_computed_metrics(self):
        self.dataframe["time_pandas"] = pd.to_datetime(self.dataframe["time_iso"], format="%H:%M:%S")
        self.dataframe["seconds_delta"] = self.dataframe["time_pandas"].diff().dt.total_seconds()
        self.dataframe["pressure_altitude_delta"] = self.dataframe["pressure_altitude"].diff()
        self.dataframe["gnss_altitude_delta"] = self.dataframe["gnss_altitude"].diff()
        self.dataframe["sink_rate_pa"] = self.dataframe["pressure_altitude_delta"]/self.dataframe["seconds_delta"]
        self.dataframe["sink_rate_gnss"] = self.dataframe["gnss_altitude_delta"]/self.dataframe["seconds_delta"]
        self.dataframe["meters_north"] = self.dataframe["lat"] * 111000
        self.dataframe["meters_east"] = np.cos(self.dataframe["lat"] * DEGREES_TO_RADS) * self.dataframe["lon"] * 111000
        
        self.dataframe = build_distance_field(self.dataframe)
        self.dataframe["speed_ms"] = self.dataframe["distance_m"]/self.dataframe["seconds_delta"]
        self.dataframe["glide_pa"] = self.dataframe["distance_m"]/self.dataframe["pressure_altitude_delta"]
        self.dataframe["glide_gnss"] = self.dataframe["distance_m"]/self.dataframe["gnss_altitude_delta"]
        
        # remove intermediaries 
        self.dataframe.drop(columns=['pressure_altitude_delta', 'gnss_altitude_delta'])
        print(self.dataframe.columns)
        
        print(self.dataframe)


    
    
