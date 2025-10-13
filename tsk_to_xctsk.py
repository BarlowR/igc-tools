import json
import argparse
import re

parser = argparse.ArgumentParser(description='Convert task.txt format to .xctsk format')
parser.add_argument('--in_file', type=str, required=True, help='Input task file (e.g., task.txt)')
parser.add_argument('--out_file', type=str, required=False, help='Output .xctsk file (optional)')

def parse_radius(radius_str):
    """Parse radius string like '1000m' or '400m' and return meters as integer"""
    match = re.match(r'(\d+)m?', radius_str)
    if match:
        return int(match.group(1))
    return 400  # default

def parse_altitude(altitude_str):
    """Parse altitude string like '1040m' and return meters as integer"""
    match = re.match(r'(\d+)m?', altitude_str)
    if match:
        return int(match.group(1))
    return 0  # default

def parse_coordinates(coord_str):
    """Parse coordinate string like '39.34065, -122.68528' and return (lat, lon)"""
    parts = [x.strip() for x in coord_str.split(',')]
    if len(parts) == 2:
        return float(parts[0]), float(parts[1])
    return 0.0, 0.0

def determine_turnpoint_type(no_str):
    """Determine turnpoint type from the No. column"""
    no_str = no_str.strip().upper()
    if 'SS' in no_str:
        return 'SSS'
    elif 'ES' in no_str:
        return 'ESS'
    elif 'GOAL' in no_str:
        return 'GOAL'
    return None  # regular turnpoint

def convert_task_to_xctsk(input_file):
    """Convert task.txt format to xctsk format"""
    turnpoints = []

    with open(input_file, 'r') as f:
        lines = f.readlines()

        # Skip header line
        for line in lines[1:]:
            if not line.strip():
                continue

            # Split by tab
            parts = line.strip().split('\t')
            if len(parts) < 8:
                continue

            no, dist, tp_id, radius, open_time, close_time, coordinates, altitude = parts

            # Parse values
            lat, lon = parse_coordinates(coordinates)
            radius_m = parse_radius(radius)
            alt_m = parse_altitude(altitude)
            tp_type = determine_turnpoint_type(no)

            # Build turnpoint object
            turnpoint = {
                "radius": radius_m,
                "waypoint": {
                    "lon": lon,
                    "lat": lat,
                    "altSmoothed": alt_m,
                    "name": tp_id.strip(),
                    "description": tp_id.strip()  # Use same as name if no description available
                }
            }

            # Add type if it's start or goal
            if tp_type:
                turnpoint["type"] = tp_type

            turnpoints.append(turnpoint)

    # Build the xctsk structure
    xctsk = {
        "version": 1,
        "taskType": "CLASSIC",
        "turnpoints": turnpoints,
        "sss": {
            "type": "RACE",
            "direction": "EXIT",
            "timeGates": ["13:00:00Z"]
        },
        "goal": {
            "type": "CYLINDER",
            "deadline": "20:00:00Z"
        },
        "earthModel": "WGS84"
    }

    return xctsk

if __name__ == "__main__":
    args = parser.parse_args()

    in_file = args.in_file
    out_file = args.out_file

    # Make the output file name based on input if none is given
    if not out_file:
        # Remove extension and add .xctsk
        if '.' in in_file:
            out_file = in_file.rsplit('.', 1)[0] + '.xctsk'
        else:
            out_file = in_file + '.xctsk'

    # Ensure output has .xctsk extension
    elif not out_file.endswith('.xctsk'):
        out_file = out_file + '.xctsk'

    # Convert the task
    xctsk_data = convert_task_to_xctsk(in_file)

    # Write to output file
    with open(out_file, 'w') as f:
        json.dump(xctsk_data, f)

    print(f"Converted {in_file} to {out_file}")
    print(f"Created {len(xctsk_data['turnpoints'])} turnpoints")
