import argparse
import os
import igc_tools

parser = argparse.ArgumentParser()
parser.add_argument('--in_folder', type=str, required=True)
parser.add_argument('--out_folder', type=str, required=False, default="")
parser.add_argument('--use_name', action='store_true', required=False)


def convert_kml(root, filename, use_name, out_folder):
    # Set the folder to save files to. Default to using the root folder
    save_folder = out_folder
    if (save_folder == ""):
        save_folder = root
    
    # Grab the full filepath of the igc file
    filepath = os.path.join(root, filename)

    # Create the IGCLog
    flight_log = igc_tools.IGCLog(filepath)

    # Handle saving the file using the pilot's name as the identifier
    if (use_name):
        if flight_log.pilot_name == None:
            print("No pilot name found in file, using default filename")
        else: 
            prefix = os.path.join(save_folder, flight_log.pilot_name.lower().replace(" ", "_"))
            flight_log.export_tracks(f"{prefix}")
            return
    
    # Handle saving the file using the existing file name otherwise
    out_name = filename[:-4]
    prefix = os.path.join(save_folder, out_name)
    flight_log.export_tracks(f"{prefix}")
                
if __name__ == "__main__":
    args = parser.parse_args()

    in_folder = args.in_folder
    out_folder = args.out_folder
    use_name = args.use_name

    igc_dict = {}
    for root, dirs, files in os.walk(in_folder):
        for filename in files:
            if filename.endswith(".igc"):
                print(f"Converting {root}/{filename}")
                convert_kml(root, filename, use_name, out_folder)
                
