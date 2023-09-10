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

def build_distance_field(df):
    df["prev_lat"] = df["lat"].shift(periods = 1)
    df["prev_lon"] = df["lon"].shift(periods = 1)

    df = df.assign(distance_m=distance_between_points_m(df["lat"], df["lon"], df["prev_lat"], df["prev_lon"]))
    df.drop(columns=['prev_lat', 'prev_lon'])
    return df

