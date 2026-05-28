# survey2therion
This repository contains Python scripts to translate the main cave formats into a Therion project.


## tr2th : a tool for parsing toporobot files and converting them to therion format

This script reads a toporobot archive file and returns a preprocessed therion directory. 

``` 
usage: tr2th.py [-h] survey_file survey_selector

Convert a Toporobot file to Therion format

positional arguments:
  survey_file      The toporobot archive file (*.TEXT) to work from."
  survey_selector  The basename of the survey for the therion file (may not include special characters)"

options:
  -h, --help       show this help message and exit

```

You can test it by running the following script to generate some sample data

```
python tr2th.py sample_data\orutura_cave.trb Orutura -o ../converted
```

You can then navigate to the level of the output directory and run:

```
therion Orutura.thconfig
```


## vtopo2th : a tool for parsing visualtopo files and converting them to therion format


## svx2th : a tool for parsing survex files and converting them to therion format



## comp2th: a tool for parsing compass .DAT and .MAK files and convert them to a therion project.

This script reads a compass directory structure or a single .DAT file and returns a preprocessed therion directory. 

``` 
usage: comp2th.py [-h] [--index-file INDEX_FILE] [--use-mak USE_MAK] [-survey SURVEY] [-o OUTPUT] [-crs COORDINATE_REFERENCE_SYSTEM] survey_directory

Converts a Compass file to Therion format

positional arguments:
  survey_directory      The compass archive directory containing *.DAT files to work from, or the .DAT file itself"

options:
  -h, --help            show this help message and exit
  --index-file INDEX_FILE
                        The compass index file to work from if using a MAK file.
  -survey SURVEY        The basename of the survey for the therion file (may not include special characters)"
  -o OUTPUT, --output OUTPUT
                        The directory in which to store the output)"
  -crs COORDINATE_REFERENCE_SYSTEM, --coordinate_reference_system COORDINATE_REFERENCE_SYSTEM
                        An epsg code of the form: "epsg:12345"

```



