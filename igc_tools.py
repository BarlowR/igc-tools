
from dataclasses import dataclass
import datetime


@dataclass
class BFix:
    """ BFix IGC Data Type
    See https://xp-soaring.github.io/igc_file_format/igc_format_2008.html#link_4.1
    """

    time: datetime=datetime.datetime.now()
    lat: float=0
    lon: float=0
    fix_validity: str=""
    pressure_altitude_m: int=0
    gnss_altitude_m: int=0

    def to_dict(self):
        return {
            "time": self.time,
            "time_iso": self.time.isoformat(),
            "lat": self.lat,
            "lon": self.lon,
            "fix_validity": self.fix_validity,
            "pressure_altitude_m": self.pressure_altitude_m,
            "gnss_altitude_m": self.gnss_altitude_m,
        }


def injest_igc_file(igc_file: str):
    """ Parse a IGC file into header lines, fix lines and footer lines 
    TODO: this could be much better
    """
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


def parse_bfix(line: str):
    """ Parse a b fix line to a BFix object
        See https://xp-soaring.github.io/igc_file_format/igc_format_2008.html#link_4.1
        Spec:    B HHMMSS DDMMmmmN DDDMMmmmE V PPPPP GGGGG CK
        Example: B 235531 3440751N 11955269W A 00690 00732 54
    """

    fix = BFix()
    assert(line[0] == "B")

    # parse time to datetime
    hour = int(line[1:3])
    min = int(line[3:5])
    sec = int(line[5:7])
    fix.time = datetime.time(hour=hour, minute=min, second=sec)

    # pull latitude 
    lat_degrees = int(line[7:9])
    lat_minutes = int(line[9:14])/1000
    north = line[14] == "N"
    fix.lat = (lat_degrees + lat_minutes/60) 
    fix.lat *= (1 if north else -1)

    # pull longitude
    lon_degrees = int(line[15:18])
    lon_minutes = int(line[18:23])/1000

    east = (line[23] == "E")
    fix.lon = (lon_degrees + lon_minutes/60) 
    fix.lon *= (1 if east else -1)
    fix.fix_validity = line[24]

    # pressure altitude
    fix.pressure_altitude_m = int(line[25:30])
    # gps altitude
    fix.gnss_altitude_m = int(line[30:35])
    return fix

def replace_gps_with_baro(line: str):
    # pressure altitude
    pressure_altitude_m = line[25:30]

    # gps altitude replacement
    new_line = line[:30] + pressure_altitude_m + line[35:]
    return new_line
