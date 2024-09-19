# Tools for IGC & xctsk files
#### Rob Barlow, 2024-06


## .xctsk Files

### Convert to KML
Run the following from the command line:
```
python3 xctsk_tools.py --in_file="<your_xctsk_file>.xctsk"
```
Or:
```
python3 xctsk_tools.py --in_file="<your_xctsk_filepath>.xctsk" --out_file="<your_kml_output_filepath>"
```

![vs](./assets/task.png)


## .igc Files
See igc_review.ipynb for examples

### Load IGC to Pandas Dataframe with key metrics calculated (Speed, Vertical Speed, Glide, Altidude, etc.)

### Export to GPX

### Export KML with color scale for vertical speed

![vs](./assets/vs.png)

### Export KML with color scale for horizontal speed

![speed](./assets/speed.png)

