
from dataclasses import dataclass
import datetime


@dataclass
class BFix:
    # UTC
    # HHMMSS
    time: datetime=datetime.datetime.now()
    # decmal 
    lat: float=0

    lon: float=0
    fix_validity: str=""
    pressure_altitude: int=0
    gnss_altitude: int=0

    def to_dict(self):
        return {
            "time": self.time,
            "time_iso": self.time.isoformat(),
            "lat": self.lat,
            "lon": self.lon,
            "fix_validity": self.fix_validity,
            "pressure_altitude": self.pressure_altitude,
            "gnss_altitude": self.gnss_altitude,
        }


def injest_igc_file(igc_file: str):
    header_lines = []
    content_lines = []
    footer_lines = []
    with open(igc_file, "r") as igc_file:
        header = True
        contents = False
        footer = False

        for line in igc_file:
            # remove the \n
            line = line [:-1]
            if header:
                if line[0] == "B":
                    content_lines.append(line)
                    header = False
                    contents = True
                header_lines.append(line)
                continue
            if contents:
                if line[0] != "B":
                    if line[0] == "E":
                        continue
                    contents = False
                    footer = True
                    footer_lines.append(line)
                    continue
                content_lines.append(line)
                continue
            if footer: 
                footer_lines.append(line)
    return (header_lines, content_lines, footer_lines)

#B 235531 3440751N 11955269W A 00690 00732 54
#B HHMMSS DDMMmmmN DDDMMmmmE V PPPPP GGGGG
def parse_bfix(line: str):
    fix = BFix()
    assert(line[0] == "B")
    hour = int(line[1:3])
    min = int(line[3:5])
    sec = int(line[5:7])
    fix.time = datetime.time(hour=hour, minute=min, second=sec)

    # pull latitude 
    lat_degrees = int(line[7:9])
    lat_minutes = int(line[9:14])/1000
    north = line[14] == "N"
    fix.lat = (lat_degrees + lat_minutes/60) * (1 if north else -1)

    # pull longitude
    lon_degrees = int(line[15:18])
    lon_minutes = int(line[18:23])/1000

    east = line[23] == "E"
    fix.lon = (lon_degrees + lon_minutes/60) * (1 if east else -1)
    
    fix.fix_validity = line[24]

    # pressure altitude
    fix.pressure_altitude = int(line[25:30])
    # gps altitude
    fix.gnss_altitude = int(line[30:35])
    return fix

def replace_gps_with_baro(line: str):
    # pressure altitude
    pressure_altitude = line[25:30]

    # gps altitude replacement
    new_line = line[:30] + pressure_altitude + line[35:]
    return new_line


def fix_robs_gps_issues(igc_file: str, new_igc_file: str = None):
    if new_igc_file is None:
        new_igc_file = igc_file[:-4] + "_fixed" + igc_file[-4:]
    with open(igc_file, "r") as igc_file_lines, open(new_igc_file, "w+") as new_igc_file_lines:
        for line in igc_file_lines:
            if line[0] == "B":
                new_igc_file_lines.write(replace_gps_with_baro(line))
                continue
            new_igc_file_lines.write(line)
