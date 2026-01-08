"""Video overlay generation tools for IGC flight data visualization."""
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import igc_lib
import xctsk_lib

ground_color = "#833AB4"
top_color = "#FF7112"

future_track_width = lambda x : int(x/200)
track_line_width = lambda x : int(x/200)
point_line_width = lambda x : int(x/50)

def hex_to_rgb(hex_color):
    # Remove the '#' prefix if it exists
    hex_color = hex_color.lstrip('#')
    
    # Handle shorthand hex codes (e.g., #ABC becomes #AABBCC)
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])

    # Slice the string into R, G, B components and convert from base 16 to integer
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    return (r, g, b)

def lerp(colors, value):
    return (
        int(colors[0][0] + (colors[1][0] - colors[0][0]) * value),
        int(colors[0][1] + (colors[1][1] - colors[0][1]) * value),
        int(colors[0][2] + (colors[1][2] - colors[0][2]) * value)
    )

def alt_to_color(alt, min_alt = 2000, max_alt = 3000):
    normalized_alt = (alt - min_alt)/(max_alt - min_alt)
    if normalized_alt > 1:
        normalized_alt = 1
    elif normalized_alt < 0:
        normalized_alt = 0
    colors = [hex_to_rgb(ground_color), hex_to_rgb(top_color)]
    return lerp(colors, normalized_alt)




def calculate_padded_bounds(lats, lons, padding=0.1):
    """
    Calculate padded bounds for lat/lon coordinates.

    Args:
        lats: Array of latitudes
        lons: Array of longitudes
        padding: Padding percentage (0.1 = 10%)

    Returns:
        tuple: (min_lat, max_lat, min_lon, max_lon) with padding applied
    """
    min_lat, max_lat = lats.min(), lats.max()
    min_lon, max_lon = lons.min(), lons.max()

    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon

    min_lat -= lat_range * padding
    max_lat += lat_range * padding
    min_lon -= lon_range * padding
    max_lon += lon_range * padding

    return min_lat, max_lat, min_lon, max_lon


def latlon_to_pixel(lat, lon, bounds, img_width, img_height, x_offset=0, y_offset=0):
    """
    Convert lat/lon to pixel coordinates.

    Args:
        lat: Latitude
        lon: Longitude
        bounds: Tuple of (min_lat, max_lat, min_lon, max_lon)
        img_width: Image width in pixels
        img_height: Image height in pixels
        x_offset: X offset in pixels
        y_offset: Y offset in pixels

    Returns:
        tuple: (x, y) pixel coordinates
    """
    min_lat, max_lat, min_lon, max_lon = bounds

    # Normalize to 0-1 range
    x_norm = (lon - min_lon) / (max_lon - min_lon)
    # Flip y because image coordinates start at top
    y_norm = 1 - ((lat - min_lat) / (max_lat - min_lat))

    # Scale to image dimensions
    x = int(x_norm * img_width)
    y = int(y_norm * img_height)

    # Clamp to image bounds
    x = max(0, min(img_width - 1, x))
    y = max(0, min(img_height - 1, y))

    return [(x + x_offset), (y + y_offset)]


def draw_turnpoint_cylinders(draw, task, bounds, track_width, track_height, current_waypoint_idx=None):
    """
    Draw task turnpoint cylinders on the image.

    Args:
        draw: ImageDraw object
        task: xctsk task object with turnpoints
        bounds: Tuple of (min_lat, max_lat, min_lon, max_lon) padded bounds
        track_width: Width of track area
        track_height: Height of track area
        current_waypoint_idx: Index of next waypoint to reach (None if no task progress)

    Turnpoint colors:
        - Completed: White
        - Next (current): Blue
        - Uncompleted: Gray
    """
    if task is None or not hasattr(task, 'turnpoints'):
        return

    # Draw turnpoints in priority order so overlapping ones display correctly:
    # 1. White (completed) - drawn first (lowest priority)
    # 2. Grey (uncompleted) - drawn second (medium priority)
    # 3. Blue (next/current) - drawn last (highest priority)

    # Separate turnpoints by color priority
    white_tps = []
    grey_tps = []
    blue_tps = []

    for idx, tp in enumerate(task.turnpoints):
        center_x, center_y = latlon_to_pixel(
            tp.lat, tp.lon, bounds, track_width, track_height
        )

        # Determine color based on completion status
        if current_waypoint_idx is not None:
            if idx < current_waypoint_idx:
                # Completed turnpoint - white
                white_tps.append((tp, center_x, center_y))
            elif idx == current_waypoint_idx:
                # Next turnpoint - blue
                blue_tps.append((tp, center_x, center_y))
            else:
                # Uncompleted turnpoint - gray
                grey_tps.append((tp, center_x, center_y))
        else:
            # No progress info - draw all in gray
            grey_tps.append((tp, center_x, center_y))

    # Draw in priority order: white, then grey, then blue
    # Helper function to draw a turnpoint
    def draw_tp_circle(tp, center_x, center_y, color):
        # Calculate radius in pixels using the padded bounds
        min_lat, max_lat, min_lon, max_lon = bounds

        # Meters per degree at this latitude
        lat_deg_to_m = 111000  # meters per degree latitude
        lon_deg_to_m = 111000 * np.cos(np.radians(tp.lat))  # meters per degree longitude at this latitude

        # Calculate pixels per degree for both dimensions
        padded_lat_range = max_lat - min_lat
        padded_lon_range = max_lon - min_lon
        pixel_per_lat_deg = track_height / padded_lat_range if padded_lat_range > 0 else 1
        pixel_per_lon_deg = track_width / padded_lon_range if padded_lon_range > 0 else 1

        # Calculate radius in pixels for both directions
        radius_pixels_y = int(tp.radius / lat_deg_to_m * pixel_per_lat_deg)
        radius_pixels_x = int(tp.radius / lon_deg_to_m * pixel_per_lon_deg)

        draw.ellipse(
            [center_x - radius_pixels_x, center_y - radius_pixels_y,
             center_x + radius_pixels_x, center_y + radius_pixels_y],
            outline=color,
            width=2
        )

    # Draw white (completed) first
    for tp, center_x, center_y in white_tps:
        draw_tp_circle(tp, center_x, center_y, (255, 255, 255, 255))

    # Draw grey (uncompleted) second
    for tp, center_x, center_y in grey_tps:
        draw_tp_circle(tp, center_x, center_y, (128, 128, 128, 255))

    # Draw blue (next/current) last (highest priority)
    for tp, center_x, center_y in blue_tps:
        draw_tp_circle(tp, center_x, center_y, (0, 128, 255, 255))


def generate_tracklog_overlay_sequence(igc_log, framerate, output_dir, use_task=False):
    """
    Generate an image sequence showing tracklog progress over time.

    Each frame shows the full tracklog in grey with the flown portion in orange.
    If the igclog has a task (set via build_computed_comp_metrics), turnpoints are drawn:
    - Completed turnpoints: White
    - Next turnpoint: Blue
    - Uncompleted turnpoints: Gray

    Args:
        igc_log: igclog object with flight data (and optional task)
        framerate: Target framerate (frames per second)
        output_dir: Directory to save image sequence

    Returns:
        int: Number of frames generated

    Example:
        >>> log = igc_tools.igclog("flight.igc")
        >>> num_frames = generate_tracklog_overlay_sequence(log, 30, "./frames")
        >>> print(f"Generated {num_frames} frames")
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Get flight data - use comp_dataframe if task exists, otherwise main dataframe
    task = igc_log.task if (use_task and hasattr(igc_log, 'task')) else None
    if task is not None:
        if not hasattr(igc_log, 'comp_dataframe') or igc_log.comp_dataframe is None:
            raise ValueError("Task exists but igclog has no comp_dataframe. Run build_competition_metrics() first.")
        df = igc_log.comp_dataframe
    else:
        df = igc_log.dataframe

    if len(df) == 0:
        raise ValueError("igclog has no data")

    # Calculate total flight duration in seconds
    start_time = df.iloc[0]["time_pandas"]
    end_time = df.iloc[-1]["time_pandas"]
    duration_seconds = (end_time - start_time).total_seconds()

    # Calculate number of frames needed
    num_frames = int(duration_seconds * framerate)

    # Get lat/lon coordinates
    lats = df["lat"].values
    lons = df["lon"].values
    alts = df["gnss_altitude_m"].values
    min_alt = df["gnss_altitude_m"].min()
    max_alt = df["gnss_altitude_m"].max()

    # Calculate padded bounds once for all coordinate transformations
    bounds = calculate_padded_bounds(lats, lons, padding=0.2)

    # Full image dimensions
    image_width = int(1200)
    image_height = int(1.5 * image_width)

    # Track Overlay dimensions
    track_width = image_width
    track_height = track_width

    # Convert all coordinates to pixels using pre-calculated bounds
    pixel_coords = [latlon_to_pixel(lat, lon, bounds, track_height, track_width) for lat, lon in zip(lats, lons)]
    path_colors = [alt_to_color(alt, min_alt, max_alt) for alt in alts]


    # Generate frames
    images = []
    for frame_idx in range(num_frames):
        # Calculate current time for this frame
        current_time = start_time + (frame_idx / framerate) * np.timedelta64(1, 's')

        # Find the index in the dataframe corresponding to this time
        # Binary search would be faster, but simple iteration is fine for clarity
        flown_idx = 0
        for idx, row_time in enumerate(df["time_pandas"]):
            if row_time <= current_time:
                flown_idx = idx
            else:
                break

        # Create image with transparency
        img = Image.new('RGBA', (image_width, image_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Define the bounding box as a sequence of two tuples: [(x0, y0), (x1, y1)]
        track_bounding_box = [(0, 0), (track_width, track_height)]

        # Specify the radius for the rounded corners
        corner_radius = int(image_width / 10)

        draw.rounded_rectangle(
            track_bounding_box,
            radius=corner_radius,
            fill=(0, 0, 0, 40),
            outline="#000000",
            width=3 # Outline width in pixels
        )

        # Get current waypoint index if task provided (df is comp_dataframe in this case)
        if (use_task and (task is not None)):

            current_waypoint_idx = df.iloc[flown_idx]["next_waypoint"]

            # Draw turnpoints (before track so track appears on top)
            draw_turnpoint_cylinders(draw, task, bounds, track_width, track_height, current_waypoint_idx)

        # Draw full tracklog in grey
        if len(pixel_coords) > 1:
            draw.line(pixel_coords, fill=(128, 128, 128, 255), width=future_track_width(image_width))

        # Draw flown portion in orange
        if flown_idx > 0:
            flown_coords = pixel_coords[:flown_idx + 1]
            if len(flown_coords) < 1:
                return
            for coor_idx in range(flown_idx):
                center_x, center_y = pixel_coords[coor_idx]
                width = track_line_width(image_width)
                min_x = int(center_x - (width/2))
                min_y = int(center_y - (width/2))
                max_x = int(center_x + (width/2))
                max_y = int(center_y + (width/2))
                draw.ellipse([(min_x, min_y), (max_x, max_y)], fill=path_colors[coor_idx], outline=None)

            center_x, center_y = pixel_coords[coor_idx]
            width = point_line_width(image_width)
            min_x = int(center_x - (width/2))
            min_y = int(center_y - (width/2))
            max_x = int(center_x + (width/2))
            max_y = int(center_y + (width/2))
            draw.ellipse([(min_x, min_y), (max_x, max_y)], fill=path_colors[coor_idx], outline=2)


        # Setup Text Overlay Font
        font = ImageFont.truetype("fonts/opensans.ttf", size=int(image_width/15)) 
        altitude = df["gnss_altitude_m"][flown_idx]
        climb_rate = df["vertical_speed_ms_20s"][flown_idx]
        speed = df["speed_kmh_20s"][flown_idx]

        alt_y_offset = image_width + (image_width * 0.1)
        
        speed_y_offset = image_width + (image_width * 0.2)

        draw.text((0, alt_y_offset), f"{altitude}m MSL", font=font, fill=top_color)
        
        draw.text((int(image_width/2), alt_y_offset), f"{climb_rate:.1f}m/s", font=font, fill=top_color)
        
        draw.text((0, speed_y_offset), f"{speed:.1f}km/h", font=font, fill=top_color)

        # Draw Altitude

        # Save frame
        frame_filename = os.path.join(output_dir, f"frame_{frame_idx:06d}.png")
        img.save(frame_filename, 'PNG')
        images.append(img)

    images[0].save(
            os.path.join(output_dir, f"path_animation.gif"),
            save_all=True,
            append_images=images[1:],
            duration=10,
            loop=0,
            disposal=2
        )

    return num_frames


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate tracklog overlay image sequence from IGC file'
    )
    parser.add_argument('--in_file', type=str, required=True,
                       help='Input IGC file path')
    parser.add_argument('--in_task', type=str, required=False,
                       help='Input .xctsk file path')
    parser.add_argument('--out_dir', type=str, required=True,
                       help='Output directory for image sequence')
    parser.add_argument('--framerate', type=float, default=30.0,
                       help='Target framerate (default: 30 fps)')

    args = parser.parse_args()

    # Load IGC file
    print(f"Loading IGC file: {args.in_file}")
    log = igc_lib.igclog(args.in_file)
    task = None
    if args.in_task:
        task = xctsk_lib.xctsk(args.in_task)
        log.build_computed_comp_metrics(task)

    # Generate image sequence
    print(f"Generating frames at {args.framerate} fps...")
    num_frames = generate_tracklog_overlay_sequence(
        log,
        args.framerate,
        args.out_dir, 
        use_task=(task is not None)
    )

    print(f"Generated {num_frames} frames in {args.out_dir}")
