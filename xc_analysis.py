import pandas as pd

def bin_by_thermal_strength(vertical_speed):
    # Split out time spent climbing into discrete bins
    bins = [-100, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 100]
    bin_names = ["<0", "<0.5", "<1", "<1.5", "<2", "<2.5", "<3", "<3.5", "<4", "<4.5", "<5", "<5.5", "<6", ">6"]
    vspeed_binned = pd.cut(vertical_speed, bins)

    # List of counts of seconds spent in each bin
    binned = list(vspeed_binned.groupby(vspeed_binned).size())

    # list of altitude gain for each bin
    altitude = [bin * time for bin, time in zip(bins[1:-1], binned[1:])]

    # list of altitude gain for each bin normalized by total altitude climbed
    altitude = [alt/sum(altitude) for alt in altitude]

    return (bins[1:-1], altitude)

