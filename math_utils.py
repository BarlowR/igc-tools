import numpy as np
import pandas as pd

SEMIMAJOR_AXIS_M = 6378137.0
DEGREES_TO_RADS = np.pi/180.0

def haversine(theta):
    return np.sin((theta)/2.0)**2

def distance_between_points_m(lat1, lon1, lat2, lon2):
    # Haversine formaula (https://en.wikipedia.org/wiki/Haversine_formula)
    lat1_rads = lat1 * DEGREES_TO_RADS
    lon1_rads = lon1 * DEGREES_TO_RADS
    lat2_rads = lat2 * DEGREES_TO_RADS
    lon2_rads = lon2 * DEGREES_TO_RADS

    h = haversine(lat2_rads - lat1_rads) + \
        np.cos(lat1_rads) * np.cos(lat2_rads) * haversine(lon2_rads - lon1_rads)    
    
    dist_m = 2.0 * SEMIMAJOR_AXIS_M *  np.arcsin(np.sqrt(h))
    return dist_m

def dist_two_points(lat1, lon1, lat2, lon2):
        # Haversine formaula (https://en.wikipedia.org/wiki/Haversine_formula)
        lat1 *= np.pi/180.0
        lon1 *= np.pi/180.0
        lat2 *= np.pi/180.0
        lon2 *= np.pi/180.0
        h = np.sin((lat2 - lat1)/2.0)**2 + np.cos(lat1) * \
            np.cos(lat2)*np.sin((lon2 - lon1)/2.0)**2
        
        dist_ft = 2.0*SEMIMAJOR_AXIS_M*np.arcsin(np.sqrt(h))
        return dist_ft

def build_direction_heading_fields(df):
    df["prev_lat"] = df["lat"].shift(periods = 1)
    df["prev_lon"] = df["lon"].shift(periods = 1)
    
    # Distance
    df = df.assign(distance_m=distance_between_points_m(df["lat"], df["lon"], df["prev_lat"], df["prev_lon"]))
    
    # Heading
    delta_lon = (df["lon"] - df["prev_lon"])
    y_component = np.sin(delta_lon) * np.cos(df["lat"])
    x_component = np.cos(df["prev_lat"]) * np.sin(df["lat"]) - np.sin(df["prev_lat"]) \
        * np.cos(np.sin(df["lat"])) * np.cos(delta_lon);    
    brng = np.arctan2(y_component, x_component) #radians
    brng = (brng + (2*np.pi)) % (2*np.pi)
    df["direction_radians"] = brng


    df.drop(columns=['prev_lat', 'prev_lon'])
    return df


def idx_min(x):
    return x.index.values[np.argmin(x.values)]

def idx_max(x):
    return x.index.values[np.argmax(x.values)]


def build_apparent_wind(df):
    max_min = df['speed_ms'].rolling(30).agg([idx_max, 'max', idx_min, "min"])

    min_dir = df["direction_radians"].iloc[max_min["idx_min"]]
    max_dir = df["direction_radians"].iloc[max_min["idx_max"]]

    max_min["max_dir"] = list(max_dir)
    max_min["min_dir"] = list(min_dir)

    max_min["vel"] = max_min["max"] - max_min["min"]

    
    # difference of direction between the max speed direction and min speed direction
    max_min["seperation"] = max_min["max_dir"] - max_min["min_dir"]
    # normalize to 0 - 2pi
    max_min["seperation"] = (max_min["seperation"] + np.pi*2) % (np.pi*2)

    # center about pi (180 degrees) and apply abs to normalized
    max_min["seperation"] = np.abs(max_min["seperation"] - np.pi)

    # look for times where the seperation is +- 22.5 degrees off of 180 (where we can)
    max_min["filter"] = max_min["seperation"] < np.pi/4


    return max_min
