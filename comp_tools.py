import argparse
import os
import numpy as np
import pandas as pd
from igc_tools import IGCLog
from xctsk_tools import xctsk
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import itertools

COMP_SUBSET = {
    "name" : (None, "Pilot Name"),
    "completion_time" : ("least_positive", "Completion Time (s)"),
    "comp_total_time_climbing_s" : ("least_positive", "Total Climbing (s) "),
    "comp_average_climb_rate" : ("most_positive", "Average Climb Rate (m/s)"),
    "comp_total_meters_climbed" : (None, "Total Meters Climbed (m)"),
    "comp_total_time_stopped_and_climbing_s" : ("least_positive", "Stopped and Climbing (s)"),
    "comp_total_time_stopped_and_not_climbing_s" : ("most_negative", "Stopped and Not Climbing (s)"),
    "comp_total_distance" : ("least_positive", "Total Distance Flown (m)"),
    "comp_total_time_gliding_s" : ("least_positive", "Total Gliding (s)"),
    "comp_total_time_climbing_on_glide_s" : ("most_positive", "Climbing on Glide (s)"),
    "comp_average_altitude" : ("most_positive", "Average Altitude (m)"),
}
class CompetitionFlight():
    def __init__(self, xctsk_filepath):
        self.task = xctsk(xctsk_filepath)
        self.pilot_list = {}

    def add_pilot(self, igc_path):
        new_pilot = IGCLog(igc_path)
        new_pilot.build_computed_comp_metrics(self.task)
        self.pilot_list[new_pilot.pilot_name] = new_pilot
        print(f"Loaded {new_pilot.pilot_name}")

    def plot_climb_rates(self, pilot_list = None):
        fig = go.Figure()
        if pilot_list is None:
            pilot_list = list(self.pilot_list.keys())

        markers = itertools.cycle(['circle', 'cross', 'diamond', 'square', 'x'])
        colors = itertools.cycle(['red', 'orange', 'green', 'blue', 'violet'])

        climb_rate_label = ["1ms", "2ms", "3ms", "4ms", "5ms", ">5ms"]
        # Use numeric x-axis positions (1, 2, 3, 4, 5, 6)
        x_positions = [1, 2, 3, 4, 5, 6]

        for pilot in pilot_list:
            pilot_stats = self.pilot_list[pilot].stats
            climb_rates = []
            c = next(colors)
            m = next(markers)

            for climb_rate in climb_rate_label:
                climb_rates.append(pilot_stats[f"comp_percentage_time_{climb_rate}_climb"] * 100)

            # Add line trace - grouped with pilot, hidden from legend
            fig.add_trace(go.Scatter(
                x=x_positions,
                y=climb_rates,
                mode='lines',
                line=dict(color=c, width=2),
                opacity=0.4,
                showlegend=False,
                hoverinfo='skip',
                legendgroup=pilot
            ))

            # Add scatter trace with markers - main legend entry
            fig.add_trace(go.Scatter(
                x=x_positions,
                y=climb_rates,
                mode='markers',
                marker=dict(color=c, size=10, symbol=m),
                name=pilot,
                opacity=1.0,
                legendgroup=pilot
            ))

            # Add vertical line for average climb rate
            avg_climb_rate = float(pilot_stats[f"comp_average_climb_rate"])

            # Create a vertical line using a scatter trace for proper legend grouping
            fig.add_trace(go.Scatter(
                x=[avg_climb_rate, avg_climb_rate],
                y=[0, 100],
                mode='lines',
                line=dict(color=c, width=2, dash='dash'),
                opacity=0.8,
                showlegend=False,
                hoverinfo='skip',
                legendgroup=pilot
            ))

        # Update layout with custom tick labels
        fig.update_layout(
            xaxis_title="Climb Rate",
            yaxis_title="Percentage of Time Spent",
            hovermode='closest',
            legend=dict(orientation="v", title="Click to toggle pilots"),
            xaxis=dict(
                tickmode='array',
                tickvals=x_positions,
                ticktext=climb_rate_label
            ),
            height=600
        )

        return fig
    
    def save_stats_csv(self, pilot_list = None, subset = True, savepath="stats.csv"):
        if pilot_list is None:
            pilot_list = list(self.pilot_list.keys())

        output = pd.DataFrame()

        for pilot in pilot_list:
            new_row = pd.DataFrame([self.pilot_list[pilot].stats])
            new_row["name"] = pilot
            output = pd.concat([output, new_row])

        if subset:
            output[list(COMP_SUBSET.keys())].to_csv(savepath, index=False)
        else:
            output.to_csv(savepath, index=False)

    def plot_stats_table(self, pilot_list = None, subset = True):
        """
        Create plotly tables with color gradients for each column.
        Splits pilots into completed and incomplete groups.
        Color gradients calculated only for pilots who completed the task.
        """
        if pilot_list is None:
            pilot_list = list(self.pilot_list.keys())

        output = pd.DataFrame()

        for pilot in pilot_list:
            new_row = pd.DataFrame([self.pilot_list[pilot].stats])
            new_row["name"] = pilot
            output = pd.concat([output, new_row])

        # Split into completed and not completed FIRST (using full output dataframe)
        completed_df = output[output['completed'] == True].copy()
        incomplete_df = output[output['completed'] == False].copy()

        # Sort completed pilots by completion time (fastest first)
        if len(completed_df) > 0 and 'completion_time' in completed_df.columns:
            completed_df = completed_df.sort_values('completion_time')

        # Select columns based on subset parameter
        if subset:
            completed_df = completed_df[list(COMP_SUBSET.keys())]
            incomplete_df = incomplete_df[list(COMP_SUBSET.keys())]

        def generate_colors_for_df(df, use_gradients=True):
            """Generate color arrays for a dataframe (before renaming columns)"""
            cell_colors = []
            for col in df.columns:
                if COMP_SUBSET[col][0] and use_gradients:
                    col_data = df[col].values
                    min_val = np.min(col_data)
                    max_val = np.max(col_data)

                    # Normalize values to 0-1 range
                    if max_val > min_val:
                        normalized = (col_data - min_val) / (max_val - min_val)
                    else:
                        normalized = np.zeros(len(col_data))

                    ascending = COMP_SUBSET[col][0].split("_")[0] == "most"
                    color_green = COMP_SUBSET[col][0].split("_")[1] == "positive"

                    colors = []
                    for norm_val in normalized:
                        if ascending:
                            norm_val = 1 - norm_val
                        shade_of_grey = 230
                        r = int(shade_of_grey * norm_val) if color_green else shade_of_grey
                        g = shade_of_grey if color_green else int(shade_of_grey * norm_val)
                        b = int(shade_of_grey * norm_val)
                        colors.append(f'rgb({r},{g},{b})')
                    cell_colors.append(colors)
                else:
                    # Non-numeric columns or no gradients get lavender
                    cell_colors.append(['lavender'] * len(df))
            return cell_colors

        def format_values(df):
            """Format dataframe values for display (after renaming columns)"""
            formatted = []
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    formatted.append([f"{val:.2f}" for val in df[col]])
                else:
                    formatted.append(df[col].tolist())
            return formatted

        # Generate colors BEFORE renaming columns
        completed_colors = generate_colors_for_df(completed_df, use_gradients=True) if len(completed_df) > 0 else []
        incomplete_colors = generate_colors_for_df(incomplete_df, use_gradients=False) if len(incomplete_df) > 0 else []

        # Rename columns for both dataframes
        for key, val in COMP_SUBSET.items():
            if key in completed_df.columns:
                completed_df.rename(columns={key: val[1]}, inplace=True)
            if key in incomplete_df.columns:
                incomplete_df.rename(columns={key: val[1]}, inplace=True)

        # Determine layout based on what data we have
        has_completed = len(completed_df) > 0
        has_incomplete = len(incomplete_df) > 0

        if has_completed and has_incomplete:
            # Create subplots with both tables
            from plotly.subplots import make_subplots
            fig = make_subplots(
                rows=2, cols=1,
                row_heights=[len(completed_df) / (len(completed_df) + len(incomplete_df)),
                             len(incomplete_df) / (len(completed_df) + len(incomplete_df))],
                specs=[[{"type": "table"}], [{"type": "table"}]],
                vertical_spacing=0.02,
                subplot_titles=("Completed Task", "Did Not Complete Task")
            )

            # Add completed table
            fig.add_trace(go.Table(
                header=dict(
                    values=list(completed_df.columns),
                    fill_color='paleturquoise',
                    align='left',
                    font=dict(size=12, color='black')
                ),
                cells=dict(
                    values=format_values(completed_df),
                    fill_color=completed_colors,
                    align='left',
                    font=dict(size=11),
                    height=50
                )
            ), row=1, col=1)

            # Add incomplete table
            fig.add_trace(go.Table(
                header=dict(
                    values=list(incomplete_df.columns),
                    fill_color='paleturquoise',
                    align='left',
                    font=dict(size=12, color='black')
                ),
                cells=dict(
                    values=format_values(incomplete_df),
                    fill_color=incomplete_colors,
                    align='left',
                    font=dict(size=11),
                    height=50
                )
            ), row=2, col=1)

            fig.update_layout(height=(len(completed_df) + len(incomplete_df)) * 80 + 100)

        elif has_completed:
            # Only completed pilots
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=list(completed_df.columns),
                    fill_color='paleturquoise',
                    align='left',
                    font=dict(size=12, color='black')
                ),
                cells=dict(
                    values=format_values(completed_df),
                    fill_color=completed_colors,
                    align='left',
                    font=dict(size=11),
                    height=50
                )
            )])
            fig.update_layout(height=len(completed_df) * 80 + 100)

        else:
            # Only incomplete pilots
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=list(incomplete_df.columns),
                    fill_color='lightcoral',
                    align='left',
                    font=dict(size=12, color='black')
                ),
                cells=dict(
                    values=format_values(incomplete_df),
                    fill_color=incomplete_colors,
                    align='left',
                    font=dict(size=11),
                    height=50
                )
            )])
            fig.update_layout(height=len(incomplete_df) * 80 + 100)

        return fig

def generate_html_page(stats_table, climb_rate_plot, output):
    # Create HTML with both figures
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Competition Analysis Report</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    </head>
    <body>
        <h1>Competition Analysis Report</h1>
        <h2>Pilot Statistics</h2>
        <div id="stats_table"></div>
        <h2>Climb Rate Distribution</h2>
        <div id="climb_rates"></div>
        <style>
            .modebar {{ display: none !important; }}
            h1 {{text-align: center;}}
            h2 {{text-align: center;}}
        </style>

        <script>
            var stats_data = {stats_table.to_json()};
            Plotly.newPlot('stats_table', stats_data.data, stats_data.layout);

            var climb_data = {climb_rate_plot.to_json()};
            Plotly.newPlot('climb_rates', climb_data.data, climb_data.layout);
        </script>
    </body>
    </html>
    """

    with open(output, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    """CLI interface for * 80 analysis"""
    parser = argparse.ArgumentParser(
        description='Generate competition analysis report from IGC files and task definition'
    )
    parser.add_argument(
        '--pilots_dir',
        type=str,
        required=True,
        help='Directory containing pilot IGC files'
    )
    parser.add_argument(
        '--task_file',
        type=str,
        required=True,
        help='Path to xctsk task file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='competition_report.html',
        help='Output HTML file path (default: competition_report.html)'
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.isdir(args.pilots_dir):
        print(f"Error: {args.pilots_dir} is not a valid directory")
        return

    if not os.path.isfile(args.task_file):
        print(f"Error: {args.task_file} is not a valid file")
        return

    # Initialize competition
    print(f"Loading task from {args.task_file}")
    comp = CompetitionFlight(args.task_file)

    # Load all IGC files from directory
    igc_files = [f for f in os.listdir(args.pilots_dir) if f.endswith('.igc')]

    if not igc_files:
        print(f"Error: No IGC files found in {args.pilots_dir}")
        return 1

    print(f"Found {len(igc_files)} IGC files")
    for igc_file in igc_files:
        igc_path = os.path.join(args.pilots_dir, igc_file)
        comp.add_pilot(igc_path)

    # Generate plots
    print("Generating statistics table...")
    stats_table = comp.plot_stats_table()

    print("Generating climb rate plot...")
    climb_rate_plot = comp.plot_climb_rates()

    # Combine plots into HTML
    print(f"Writing report to {args.output}")

    generate_html_page(stats_table, climb_rate_plot, args.output)

    print(f"Report generated successfully: {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
