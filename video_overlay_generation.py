"""Video overlay generation tools for IGC flight data visualization."""
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np


# Function to convert lat/lon to image coordinates
def latlon_to_pixel(lat, lon, lats, lons, img_width, img_height, x_offset = 0, y_offset = 0):

    # Calculate bounds with padding
    min_lat, max_lat = lats.min(), lats.max()
    min_lon, max_lon = lons.min(), lons.max()

    # Add 10% padding
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon
    padding = 0.1

    min_lat -= lat_range * padding
    max_lat += lat_range * padding
    min_lon -= lon_range * padding
    max_lon += lon_range * padding

    """Convert lat/lon to pixel coordinates."""
    # Normalize to 0-1 range
    x_norm = (lon - min_lon) / (max_lon - min_lon) if (max_lon - min_lon) > 0 else 0.5
    # Flip y because image coordinates start at top
    y_norm = 1 - ((lat - min_lat) / (max_lat - min_lat) if (max_lat - min_lat) > 0 else 0.5)

    # Scale to image dimensions
    x = int(x_norm * img_width)
    y = int(y_norm * img_height)

    # Clamp to image bounds
    x = max(0, min(img_width - 1, x))
    y = max(0, min(img_height - 1, y))

    return (x + x_offset), (y + y_offset)


def generate_tracklog_overlay_sequence(igc_log, framerate, output_dir):
    """
    Generate an image sequence showing tracklog progress over time.

    Each frame shows the full tracklog in grey with the flown portion in orange.
    Images are 600x600px with transparent backgrounds.

    Args:
        igc_log: IGCLog object with flight data
        framerate: Target framerate (frames per second)
        output_dir: Directory to save image sequence

    Returns:
        int: Number of frames generated

    Example:
        >>> log = igc_tools.IGCLog("flight.igc")
        >>> num_frames = generate_tracklog_overlay_sequence(log, 30, "./frames")
        >>> print(f"Generated {num_frames} frames")
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Get flight data
    df = igc_log.dataframe

    if len(df) == 0:
        raise ValueError("IGCLog has no data")

    # Calculate total flight duration in seconds
    start_time = df.iloc[0]["time_pandas"]
    end_time = df.iloc[-1]["time_pandas"]
    duration_seconds = (end_time - start_time).total_seconds()

    # Calculate number of frames needed
    num_frames = int(duration_seconds * framerate)

    # Get lat/lon coordinates
    lats = df["lat"].values
    lons = df["lon"].values

    # Full image dimensions
    image_width = int(600)
    image_height = int(1.5 * image_width)

    
    # Track Overlay dimensions
    track_width = image_width
    track_height = track_width

    
    # Convert all coordinates to pixels
    pixel_coords = [latlon_to_pixel(lat, lon, lats, lons, track_height, track_width) for lat, lon in zip(lats, lons)]

    # Generate frames
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

        # Draw full tracklog in grey
        if len(pixel_coords) > 1:
            draw.line(pixel_coords, fill=(128, 128, 128, 255), width=2)

        # Draw flown portion in orange
        if flown_idx > 0:
            flown_coords = pixel_coords[:flown_idx + 1]
            if len(flown_coords) > 1:
                draw.line(flown_coords, fill=(255, 165, 0, 255), width=3)

        # Setup Text Overlay Font
        font = ImageFont.truetype("Arial Black", size=40) 
        altitude = df["gnss_altitude_m"][flown_idx]
        climb_rate = df["vertical_speed_ms_5s"][flown_idx]
        speed = df["speed_kmh_5s"][flown_idx]

        alt_y_offset = image_width + (image_width * 0.1)
        
        speed_y_offset = image_width + (image_width * 0.2)

        draw.text((0, alt_y_offset), f"{altitude}m MSL", font=font, fill="orange")
        
        draw.text((300, alt_y_offset), f"{climb_rate:.1f}m/s", font=font, fill="orange")
        
        draw.text((0, speed_y_offset), f"{speed:.1f}km/h", font=font, fill="orange")

        # Draw Altitude

        # Save frame
        frame_filename = os.path.join(output_dir, f"frame_{frame_idx:06d}.png")
        img.save(frame_filename, 'PNG')

    return num_frames


if __name__ == "__main__":
    import argparse
    import igc_tools

    parser = argparse.ArgumentParser(
        description='Generate tracklog overlay image sequence from IGC file'
    )
    parser.add_argument('--in_file', type=str, required=True,
                       help='Input IGC file path')
    parser.add_argument('--out_dir', type=str, required=True,
                       help='Output directory for image sequence')
    parser.add_argument('--framerate', type=float, default=30.0,
                       help='Target framerate (default: 30 fps)')

    args = parser.parse_args()

    # Load IGC file
    print(f"Loading IGC file: {args.in_file}")
    log = igc_tools.IGCLog(args.in_file)

    # Generate image sequence
    print(f"Generating frames at {args.framerate} fps...")
    num_frames = generate_tracklog_overlay_sequence(
        log,
        args.framerate,
        args.out_dir
    )

    print(f"Generated {num_frames} frames in {args.out_dir}")
