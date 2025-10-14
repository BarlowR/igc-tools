import json
from simplekml import Kml, Color
from polycircles import polycircles
from dataclasses import dataclass
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--in_file', type=str, required=True)
parser.add_argument('--out_file', type=str, required=False)

@dataclass
class xctsk_turnpoint:
    """ Container for the turnpoints in xctsk files"""

    radius: int = 0
    type: str = None
    altSmoothed: int = 0
    description: str = ""
    lat: int = 0
    lon: int = 0
    name: str = ""
    order: int = 0

    def load_from_dict(self, turnpoint_dict, order):
        self.order = order
        self.radius = turnpoint_dict["radius"]
        if ("type" in turnpoint_dict.keys()):
            self.type = turnpoint_dict["type"]
        self.altSmoothed = turnpoint_dict["waypoint"]["altSmoothed"]
        self.description = turnpoint_dict["waypoint"]["description"]
        self.lat = turnpoint_dict["waypoint"]["lat"]
        self.lon = turnpoint_dict["waypoint"]["lon"]
        self.name = turnpoint_dict["waypoint"]["name"]
    
    def generate_name(self):
        name = ""
        if self.type:
            return f"{self.type}, {self.name}"
        else: 
            return f"TP{self.order}, {self.name}"


@dataclass
class xctsk:
    """xctsk Data Type from XContest
    """
    earth_model: str = ""
    goal = {}
    sss = {}
    task_type:str = ""
    turnpoints = []

    def __init__(self, path):
        self.ingest_xctsk(path)

    def ingest_xctsk(self, xctsk_file: str):
        """
        Parse an xctsk. This is fairly easy since xctsk files are just Json files with a different extension.
        """

        with open(xctsk_file, "r") as xctsk_file:
            xc_task = json.load(xctsk_file)

            # Load task metadata
            if "earthModel" in xc_task:
                self.earth_model = xc_task["earthModel"]
            if "goal" in xc_task:
                self.goal = xc_task["goal"]
            if "sss" in xc_task:
                self.sss = xc_task["sss"]
            if "taskType" in xc_task:
                self.task_type = xc_task["taskType"]

            # load the tunpoints into objects
            for index, tp in enumerate(xc_task["turnpoints"]):
                next_turnpoint = xctsk_turnpoint()
                next_turnpoint.load_from_dict(tp, index)
                self.turnpoints.append(next_turnpoint)
    
    def export_to_kml(self, task_name):
        kml_output = Kml()
        last_tp = {"lat": None, "lon": None}
        # iterate over the turnpoints
        for turnpoint in self.turnpoints:
            # Create a polycircle
            polycircle = polycircles.Polycircle(latitude=turnpoint.lat,
                                    longitude=turnpoint.lon,
                                    radius=turnpoint.radius,
                                    number_of_vertices=36)
            # Create a polygon from the circle (google earth doesn't natively support circles)
            polygon = kml_output.newpolygon(name=turnpoint.generate_name(),
                                         outerboundaryis=polycircle.to_kml())

            # Style the circle
            polygon.style.linestyle.width = 2
            polygon.style.linestyle.color = "FFFFFFFF"
            # make the fill empty
            polygon.style.polystyle.color = "00000000"
            
            # Create lines between the centers of the turnpoints
            if last_tp["lat"]:
                last_point = [last_tp["lon"], last_tp["lat"], 0]
                current_point = [turnpoint.lon, turnpoint.lat, 0]
                line = kml_output.newlinestring(coords=[current_point, last_point], altitudemode="relative")
                line.style.linestyle.color = "FFFFFFFF"

            last_tp["lat"] = turnpoint.lat
            last_tp["lon"] = turnpoint.lon
        
        # Save the file
        kml_output.save(f"{task_name}.kml")


if __name__ == "__main__":
    args = parser.parse_args()

    in_file = args.in_file
    out_file = args.out_file

    # Make the output file name the same as the input if none is given
    if not out_file:
        out_file = in_file[:-6]

    # strip the ".kml" if it is passed in the string
    elif out_file[-4:] == ".kml":
        out_file = out_file[:-4]

    task = xctsk(in_file)
    task.export_to_kml(out_file)
