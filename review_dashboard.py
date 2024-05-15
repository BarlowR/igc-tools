from dash import Dash, html, dcc, callback, Output, Input
import plotly.express as px
import pandas as pd
import flight_log_tools
from dashboard_plots import *

# df = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/gapminder_unfiltered.csv')

IGC_file = "igc_data/Tollhouse_day_2.igc"
flight_log = flight_log_tools.IGCLog(IGC_file)

app = Dash(__name__)

app.layout = html.Div([
    html.H1(children='IGC Review', style={'textAlign':'center'}),
    html.Div([
        dcc.Graph(figure=main_altitude_selector(flight_log.dataframe), config={'displayModeBar': False}),
        dcc.RangeSlider(0, len(flight_log.dataframe), 0, value=[0, len(flight_log.dataframe)], id='slider'),
        
        dcc.Graph(id="subset_altitude", config={'displayModeBar': False}, style={"float": "left"}),
        dcc.Graph(id="map", config={'displayModeBar': False}, style={"float": "left"}),
        dcc.Graph(id="3D_plot", config={'displayModeBar': False}, style={"float": "left"}),

    ], style = {"width": DASHBOARD_WIDTH, "margin": "auto"}),
    # dcc.Dropdown(df.country.unique(), 'Canada', id='dropdown-selection'),
    # dcc.Graph(id='graph-content')
])

@callback(
    Output('subset_altitude', 'figure'),
    Input('slider', 'value')
)
def update_graph(slider_value):
    return altitude_plot(slider_value, flight_log.dataframe)

@callback(
    Output('map', 'figure'),
    Input('slider', 'value')
)
def update_top_down(slider_value):
    return top_down_plot(slider_value, flight_log.dataframe)

@callback(
    Output('3D_plot', 'figure'),
    Input('slider', 'value')
)
def update_3d(slider_value):
    return plot_3d(slider_value, flight_log.dataframe)

if __name__ == '__main__':
    app.run(debug=True)
