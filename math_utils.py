import numpy as np
import pandas as pd

SEMIMAJOR_AXIS_M = 6378137.0
DEGREES_TO_RADS = np.pi / 180.0


def clip(value, low, high):
    """ Clip the given value to be between the two bounds"""
    if value < low:
        return low
    if value > high:
        return high
    return value


def three_point_normalizer(value, bottom, midpoint, topend):
    range_low = midpoint - bottom
    range_high = topend - midpoint

    # set NaN  to 0
    if value != value:
        value = midpoint

    normalized_value = 0
    if value > midpoint:
        domain = value - midpoint
        normalized_value = 0.5 + (domain / (2 * range_high))
        #          (speed - midpoint)
        #  0.5 + ----------------------
        #         2 * (top - midpoint)
    else:
        domain = value - bottom
        normalized_value = domain / (2 * range_low)
        #   (speed - bottom)
        # ----------------------
        # 2 * (midpont - bottom)

    normalized_value = clip(normalized_value, 0, 1)

    return normalized_value

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lat1_rads = lat1 * DEGREES_TO_RADS
    lon1_rads = lon1 * DEGREES_TO_RADS
    lat2_rads = lat2 * DEGREES_TO_RADS
    lon2_rads = lon2 * DEGREES_TO_RADS
    # haversine formula
    dlon = lon2_rads - lon1_rads
    dlat = lat2_rads - lat1_rads
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rads) * np.cos(lat2_rads) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371000  # Radius of earth in meters. Use 3956 for miles. Determines return value units.
    return c * r


def build_direction_heading_fields(df):
    """ Build out distance and heading fields from position data """
    df["prev_lat_1s"] = df["lat"].shift(periods=1)
    df["prev_lon_1s"] = df["lon"].shift(periods=1)
    df["prev_lat_4s"] = df["lat"].shift(periods=4)
    df["prev_lon_4s"] = df["lon"].shift(periods=4)

    # Distance
    df = df.assign(distance_traveled_m_1s=haversine(df["lat"], df["lon"], df["prev_lat_1s"], df["prev_lon_1s"]))
    df = df.assign(distance_traveled_m_4s=haversine(df["lat"], df["lon"], df["prev_lat_4s"], df["prev_lon_4s"]))

    df["distance_traveled_m_16s"] = df["distance_traveled_m_4s"].rolling(4).sum()
    df["distance_traveled_m_60s"] = df["distance_traveled_m_1s"].rolling(15).sum()

    # TODO: Heading

    df.drop(columns=["prev_lat_1s", "prev_lon_1s", "prev_lat_4s", "prev_lon_4s"])
    return df


def idx_min(x):
    return x.index.values[np.argmin(x.values)]


def idx_max(x):
    return x.index.values[np.argmax(x.values)]


# TODO: Apparent wind calc. See https://blueflyvario.blogspot.com/2012/09/calculating-wind-speed-from-gps-track.html
