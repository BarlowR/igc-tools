from dash import Dash, html, dcc, callback, Output, Input
import plotly.express as px
import plotly.graph_objects as go

import planar
import numpy as np

DASHBOARD_WIDTH = 1000

def main_altitude_selector(df):
    plot = px.line(df, x='time_pandas', y='pressure_altitude', height=150)
    plot.update_xaxes(visible=False)
    plot.update_yaxes(visible=False)
    plot.layout.xaxis.fixedrange = True
    plot.layout.yaxis.fixedrange = True
    plot.layout.margin=dict(l=20, r=20, t=20, b=20)
    return plot


def altitude_plot(slider_value, df):
    plot = px.line(df.iloc[slider_value[0]:slider_value[1]],
            x='time_pandas', y='pressure_altitude',
            width=DASHBOARD_WIDTH/2, height=DASHBOARD_WIDTH/3)
    plot.layout.xaxis.fixedrange = True
    plot.layout.yaxis.fixedrange = True
    plot.layout.xaxis.visible=False

    plot.layout.margin=dict(l=20, r=20, t=20, b=20)
    return plot

def top_down_plot(slider_value, df):
    df_sub = df.iloc[slider_value[0]:slider_value[1]]
    zoom, bbox_center = determine_zoom_level(list(df_sub["lat"]), list(df_sub["lon"]))
    plot = px.line_mapbox(df_sub,
            lat='lat', lon='lon',
            width=DASHBOARD_WIDTH/2, height=DASHBOARD_WIDTH/3,
            zoom=zoom, center=bbox_center)

    plot.update_layout(mapbox_style="open-street-map")
    plot.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return plot

def determine_zoom_level(latitudes, longitudes):
    all_pairs=[]
    if not latitudes or not longitudes:
        return 0, (0,0)
    for lon, lat in zip(longitudes, latitudes):
        all_pairs.append((lon,lat))
    b_box = planar.BoundingBox(all_pairs)
    if b_box.is_empty:
        return 0, (0, 0)
    area = b_box.height * b_box.width
    zoom = np.interp(area, [0, 5**-10, 4**-10, 3**-10, 2**-10, 1**-10, 1**-5], 
                           [19,    16,     15,     14,     11.8,     11,      5])    
    return zoom, {"lat": b_box.center[1], "lon": b_box.center[0]}


def plot_3d(slider_value, df):
    df_sub = df.iloc[slider_value[0]:slider_value[1]]
    plot = go.Figure()
    line = px.line_3d(df_sub, x='meters_east', y='meters_north', z='pressure_altitude')
    scatter = px.scatter_3d(df_sub, x='meters_east', y='meters_north', z='pressure_altitude', 
                            color='sink_rate_pa', color_continuous_scale='Magma', color_continuous_midpoint=0)
    plot.layout.width = DASHBOARD_WIDTH
    plot.add_trace(line.data[0])
    plot.add_trace(scatter.data[0])
    plot.update_scenes(aspectmode='data')
    plot.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return plot
    