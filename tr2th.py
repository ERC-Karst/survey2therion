"""
Created on April 12 11:54:32 2024

@author: Tanguy Racine, Celia Trunz

This provides a parser for converting Toporobot file structures to therion
"""

import datetime
import argparse
from os.path import abspath, split, join, isfile
from os import makedirs
from shutil import copy
from math import sqrt
import numpy as np

from helpers.utils import *
from helpers.therion_classes import *
from def_calc_splay_from_lrud import *


# A schema to split Toporobot lines. Toporobot works with a series of keys keys which are explained below.
_LINETYPES = {  -6: ("cave_name", [0, 7, 13, 17, 21, 24, 25, 78]),
                -5: ("entrance_fix", [0, 7, 13, 17, 21, 24, 36, 48, 60, 66, 72]),
                -4: ("session_date", [0, 7, 13, 17, 21, 24, 32, 50, 64]),
                -2: ("explo_date", [0, 7, 13, 17, 21, 24, 33, 49, 63]),
                -3: ("unused", []),
                -1: ("instrument_code", [0, 7, 13, 17, 21, 24, 32, 40, 48, 56, 64, 72, 80]),
                0: ("measurement", [0, 6, 12, 16, 20, 24, 80]),
                1:("comment", [0, 7, 13, 17, 21, 24, 80])
                }

# A schema for the conversion of measurement unit codes to actual units. 
_UNIT_CODES = { 
                350: "degrees inverse",
                359: "degrees nadir", # direct nadiral,
                360: "degrees", #direct, horizontal
                361: "degrees zenith", #direct, zénithal
                380: "dh",
                389: "grads inverse",
                390: "grads inverse",
                370: "percentage",
                399: "grads nadir",
                400: "grads",
                401: "grads zenith",
                800: "direct"
                # 800:"TLM 330, Directe Horizontal" 
                }

_COMMENTS_STRING = """
centreline
# comments for the above survey
{comments}
endcentreline
"""
_TH_SUBSURVEY_TEMPLATE = """
survey {survey_name} -title "{survey_title}"
centreline 
{centreline}
endcentreline
endsurvey
"""

_TH_FILE_TEMPLATE = """survey {basename}
centreline
cs {crs}
{fixes} 
{equates}
endcentreline
{subsurveys}

{comments}
endsurvey
"""

_TH_FILE_TEMPLATE_NO_CRS = """survey {basename}
centreline
{fixes} 
{equates}
endcentreline
{subsurveys}

{comments}
endsurvey
"""
_TH_CONFIG_FILE_TEMPLATE = """source {basename}_convert.th
export database -o outputs/{basename}.sql
export model -o outputs/{basename}.3d
export model -o outputs/{basename} -fmt esri
"""

_TH_CONFIG_FILE_TEMPLATE_WITH_CRS = """source {basename}_convert.th
cs {crsout}
export database -o outputs/{basename}.sql
export model -o outputs/{basename}.3d
export model -o outputs/{basename} -fmt esri
"""


_FLAGS_PARSER = {0: "None",
                -100: "duplicate",
                 -101: "duplicate",
                 100: "None",
                 10: "None", #vertical
                 80: "None",
                 45: "None",
                 -50: "surface"}

_LOCAL_SERIES_FLAGS = {"None": 0,
               "duplicate": 1,
               "surface": 2,
               "artifical": 3}

def read_file (filename : str, encoding : str = 'utf-8') -> list :
    """Reads a TopoRobot text file in archive format. 
    Returns a list of strings

    Parameters
    ----------
    filename : str
        the filename
    encoding : str, optional
        file encoding, by default 'utf-8'

    Returns
    -------
    list
        a list of strings, corresponding to every line  not beginning with # or \n
    """    

    with open ( filename , "r" , encoding = encoding ) as f :
        lines = f.readlines()
        
        f.close()
        #double quotes in suvey name create issues. this replace it
        lines = [line.replace('"',"'") for line in lines]

        # strip non-toporobot-style comments beginning with # 
        no_comment = [line for line in lines if ("#" not in line) and (line != "\n")]
    return no_comment

def parse_from_indices( line : str, key : int, verbose = False) -> tuple :
    """Parses each line in the TopoRobot data lines using a given strategy
    Returns a tuple with a list of look up keys, and list of data entry.

    Parameters
    ----------
    line : str
        the line in the parsed toporobot data file
    key : int
        an integer key which corresponds to the line type defined by toporobot. 

        _LINETYPES = {  -6: ("cave_name", [0, 7, 13, 17, 21, 24, 26, 78]),
                -5: ("entrance_fix", [0, 7, 13, 17, 21, 24, 36, 48, 60, 66, 72]),
                -4: ("session_date", [0, 7, 13, 17, 21, 24, 32, 50, 64]),
                -2: ("explo_date", [0, 7, 13, 17, 21, 24, 33, 49, 63]),
                -3: ("unused", []),
                -1: ("instrument_code", [0, 7, 13, 17, 21, 24, 32, 40, 48, 56, 64, 72, 80]),
                0: ("measurement", [0, 7, 13, 17, 21, 24, 80]),
                1:("comment", [0, 7, 13, 17, 21, 24, 80])
                }

    Returns
    -------
    tuple
        a tuple containing two lists. The first element is a list of look up keys.
        the second contains data to be interpreted.
    """

    line_type = _LINETYPES[key][0]
    parse_indices = _LINETYPES[key][1] 
    parsed_line = [str(line[i:j]).strip(" ") for i,j in zip(parse_indices, parse_indices[1:]+[None])]
    
    try:
        if verbose == True:
            print("parsing linetype: ", line_type)
        
        # first five elements are lookup keys, last five are data
        keys, data_entry = parsed_line[:5], parsed_line[5:-1]

        return ( keys, data_entry )
    
    except IndexError:
        print("Empty line")
        pass

def parse_keys ( data : list ) -> list :
    
    """Parses each line in the TopoRobot data lines, using the strategy given by key
    to the _LINETYPE dictionary.

    Parameters :
        data : a list of strings, separated by whitespace

    Returns:
    a list in the form : List[Tuple(List[keys], List[data entries])]"""


    keys = [line[:6].strip(" ") for line in data]
    entries = [line for line in data]
    parsed_data = []
    comments = []

    for key, entry in zip(keys, entries):
        if "(" in key:
            # catch comments
            parsed_line = parse_from_indices(entry, 1)
            comments.append(parsed_line)
        elif key == "\n":
            print("invalid key, skipping")
        else:
            parsed_line = parse_from_indices(entry, min(int(key), 0))
            if len(parsed_line[0])>0:
                parsed_data.append(parsed_line)

    return parsed_data, comments

def identify_series_keys( parsed_data : list ) -> list :
    """Extract the set of unique keys associated with survey sessions.
    Returns a list of unique values. Since TopoRobot surveys are numbered
    consecutively we just need to find the maximum key value.

    Parameters
    ----------
    parsed_data : list
        a list of strings parsed according to their line type

    Returns
    -------
    list
        a list of unique integers corresponding to the individual toporobot series. 
    """    

    # series are numbered in ascending order, we only return positive integer keys
    all_keys = [int(entry[0][0]) for entry in parsed_data if int(entry[0][0]) > 0]

    series_keys = list(set(all_keys))

    return series_keys

def parse_series_measurements( parsed_data: list, series_key : int, equates: list,instrument_codes: list, inst_key_col: int = 2) -> dict:
    """A function to parse a single series of measurements
    Returns non-interleaved data and the title of the survey. 

    Parameters
    ----------
    parsed_data : list
        A list of strings parsed according to their line type.
    series_key : int
        The individual toporobot series key.

    Returns
    -------
    dict 
        For n measurement lines in the toporobot series, we return a dictionary containing
        
        - "shot_data" : the nested list of n-1 survey measurements
        - "station_data" : the nested list of n station dimensions
        - "survey_name" : the survey name
    """    


    shot_data = [] 
    station_data = []
    # we store them separately because therion does not allow mixing interleaved and non
    # interleaved data

    survey_name = ""


    # cycle through parsed_data
    for entry in parsed_data:
        s_key = int(entry[0][0])
        # check that the series key matches the first key of the dataline
        
        if s_key == series_key and int(entry[0][0]) >= 0 and int(entry[0][1])>=0:
            stn = entry[0][1]
            length, compass, clino, left, right, up, down = entry[1][0].split()[:7]
            explo_key = entry[0][4]

            inst_key = entry[0][inst_key_col]

            if float(length) == 0 and float(stn) != 0:
                equates.append(((s_key, shot_data[-1][0]), (s_key, stn), 1))
                shot_data.append([stn, 0., compass, clino, explo_key, inst_key])

            else:
      
                if str(inst_key) == "0":
                    shot_data.append([stn, length, compass, clino, explo_key, inst_key])

                elif instrument_codes[str(inst_key)]["clino"]["unit"] == "direct":
                    # do some pythagoras for the horizontal length to the hypothenuse. 
                    vert = float(clino)
                    horiz = float(length)
                    true_length = sqrt(vert**2 +horiz**2)
                    shot_data.append([stn, f"{true_length:.2f}", compass, clino, explo_key, inst_key])

                else:
                    # check for some quirky data
                    shot_data.append([stn, length, compass, clino, explo_key, inst_key])
            
            station_data.append([stn, left, right, up, down, inst_key])
        
        elif int(entry[0][0]) == series_key and int(entry[0][1]) == -2:
            # also get the survey name
            survey_name = entry[1]
    
    # add the from station from the previous line. 
    interleaved_shot_data = [[shot1[0]] + shot2 for shot1, shot2 in zip(shot_data[:-1], shot_data[1:]) if shot2[1]!=0.]
    
    parsed_series_measurements = {"shot_data": interleaved_shot_data, 
                                   "station_data": station_data, 
                                   "survey_name": survey_name }
    return parsed_series_measurements

def parse_station_comments(comments : list) -> dict :
    """A function to parse all the data and extract station specific comments. 
"""    
    parsed_comments = {}
    
    for entry in comments:
        survey = int(entry[0][0].strip("(").strip(" "))
        if  survey >= 1:
            comment = entry[1][0]
            station = int(entry[0][1].strip(" "))
  
            parsed_comments[f"{station}@{survey}"] = comment.strip("\n")
    return parsed_comments

def parse_instrument_code_comments(comments : list, instrument_codes: dict) -> dict :
    """A function to parse all the data and extract station specific comments. 
"""    
    parsed_instrument_code_comments = {}
    possible_keys = instrument_codes.keys()

    for pos_key in possible_keys:
        parsed_instrument_code_comments[pos_key] = " "
        for entry in comments:
            key = int(entry[0][0].strip("(").strip(" "))
            instr_code = entry[0][1].strip(" ")
            if  key == -1:
                comment = entry[1][0]
                parsed_instrument_code_comments[instr_code] = comment.strip("\n")
                
    return parsed_instrument_code_comments


def parse_all_series(parsed_data : list, series_keys : list, equates : list, instrument_codes : list, inst_key_col: int = 2) -> dict:
    """Loop over all unique keys of a survey series and 
    return a dictionary of parsed measurements

    Parameters
    ----------
    parsed_data : list
        A list of strings parsed according to their line type.
    series_keys : list
        A list of unique series identifiers.

    Returns
    -------
    dict
        A dictionary view of the parsed series measurements.
    """    
    
    series = {}

    for i in range(0, max(series_keys)+1):
        parsed_series_measurements = parse_series_measurements(parsed_data, i, equates, instrument_codes, inst_key_col)
        series[i] = parsed_series_measurements
    return series

def find_tie_points(parsed_data : list, survey_keys : list) -> dict :
    """A function to find both tie points of a survey (start and end)
    Returns a dictionary whose keys are the survey key and values are the start
    and end point as tuples (survey, station)

    Parameters
    ----------
    parsed_data : list
        A list of strings parsed according to their line type.
    keys : list
        unique integer ids to identify the 

    Returns
    -------
    dict
        A dictionary containing for each entry a nested tuple with the different tie points
        containing series keys and stations keys.
    """    


    tie_points = {}

    # loop over entries
    for entry in parsed_data:

        # if 1st key is a subsurvey and second key indicates the tie points: 
        if int(entry[0][0]) in survey_keys and int(entry[0][1]) == -1:
            
            # get the entry and split the line
            equate_line = entry[1][0].split() 

            start_key = (equate_line[0], equate_line[1])
            end_key = (equate_line[2], equate_line[3])
            # append to the dictionary of survey tie points
            tie_points[int(entry[0][0])] = (start_key, end_key)
        else:
            pass
          
    return tie_points


def find_entrances( parsed_data : list ) -> list:
    """Loops over the parsed data and identified entrance points and comments

    Parameters
    ----------
    parsed_data : list
         A list of strings parsed according to their line type.

    Returns
    -------
    list
        a list of equated stations.
    """
    entrances = []

    for keys, entries in parsed_data:
        if int(keys[0]) == -6:
            entrances.append((keys[1], entries[1].strip("\n")))
    return entrances
    

def find_equates( parsed_data : list , tie_points : dict, instrument_codes: dict, inst_key_col: int = 2) -> list:
    """Loops over the parsed data and identified tie points and looks for unique session keys in measurement shots

    Parameters
    ----------
    parsed_data : list
         A list of strings parsed according to their line type.
    tie_points : dict
        a dictionary of nested tuples containing station and series keys as unique identifiers.

    Returns
    -------
    list
        a list of equated stations.
    """

    """"""
    
    equates = []

    for key, value in tie_points.items():

        # parse_all_series collects the equates of zero-length shots, so we drop them here
        parsed_series_measurements = parse_series_measurements(parsed_data, key, [], instrument_codes, inst_key_col)
        if len(parsed_series_measurements["shot_data"])>0:
            start_tie = value[0]
            start_station = (str(key), parsed_series_measurements["shot_data"][0][0])
            end_tie = value[1]
            end_station = (str(key), parsed_series_measurements["shot_data"][-1][1])

            if start_tie != start_station:
                equates.append((start_tie, start_station, 0))
            
            if end_tie != end_station:
                equates.append((end_tie, end_station, 0))
    return equates

def find_session_metadata(parsed_data : list) -> dict:
    """ Loops over the parsed data and populates one dictionary with metadata
    Sessions, each with their unique key contain a date and surveyor. 
    In each measurement line, the fifth key is a lookup key to see who surveyed it and when.

    Parameters
    ----------
    parsed_data : list
         A list of strings parsed according to their line type.

    Returns
    -------
    dict
        A dictionary containing metadata for each exploration key
        - "date": the string formatted survey date
        - "team": the list of surveyors. 
    """

    session_metadata = {}

    for entry in parsed_data:
        if entry[0][0] == "-2":
            str_year = entry[1][0][6:]
            str_month = entry[1][0][3:5]
            try:
                # check whether date is given in DDMMYYYY format first. 
                if ("/" not in entry[1][0] and "." not in entry[1][0]) and len(entry[1][0]) == 8:
                    date = datetime.datetime.strptime(entry[1][0], "%d%m%Y").strftime("%Y.%m.%d")
                
                elif not entry[1][0][0:5]=='00/00':
                    date = datetime.datetime.strptime(entry[1][0], "%d/%m/%y").strftime("%Y.%m.%d")
                elif entry[1][0][0:5]=='00/00':               
                    if int(str_year) <= 50:
                        date = f'20{str_year}'
                    else :
                        date = f'19{str_year}'
                else:
                    if int(str_year) <= 50:
                        date = f'20{str_year}.{str_month}'
                    else :
                        date = f'19{str_year}.{str_month}'
            except ValueError:
   
                print("there was an invalid date here.")
                date = " "
            team = entry[1][1:3]
            session_metadata[entry[0][1]] = {"date": date, 
                                             "team": team}
            
    return session_metadata

def find_instrument_codes(parsed_data: list) -> dict:
    """ Loops over the parsed data and populates one dictionary with entries
    for instrument codes, each with their own key.

    Parameters
    ----------
    parsed_data : list
         A list of strings parsed according to their line type.

    Returns
    -------
    dict
        A dictionary containing the entry for each instrument code
    """

    instrument_codes = {}

    for entry in parsed_data:
        
        if entry[0][0] == "-1":
            instrument_codes[entry[0][1]] = entry[1]

    return instrument_codes

def parse_instrument_codes(instrument_codes: dict) -> dict:
    """
    Loop over the unique instrument codes in the file and convert the
    toporobot codes for readable units."""

    d = {}
    for code, description in instrument_codes.items():
        
        # nadiral or zenithal measurements are only valid for clino units.
        compass_code = float(description[0])
        if compass_code % 10 != 0:
            print("possibly invalid compass code", compass_code)
            compass_code = np.round(compass_code,-1)
            print("new compass code: ", compass_code)
        d[code] = {"compass": {"unit": _UNIT_CODES[compass_code], "precision": description[3]},
                   "clino": {"unit": _UNIT_CODES[float(description[1])],"precision":description[4]},
                "length": {"unit": "metres", "precision": description[2]},
                "flag" : description[-1]}
    return d

def find_fixes(parsed_data: list) -> list:
    """
    Loop over the parsed data to find the fixed stations
    """
    fixes = []
    for entry in parsed_data:
        
        if entry[0][0] == "-5":
            fixes.append([entry[0][1]] + entry[1])
        
    return fixes



def flag_surface_inst_codes(instrument_codes, instrument_comments, user_flags, basedir: str, basename: str):
    insts_to_be_flagged = []
    insts_flags = {}
    insts_to_be_flagged = []

    # check first whether the file actually exists and extract the series to be flagged.
    if isfile(join(basedir, f"{basename}_insts_flags.txt")):  
        print("there exist already some instrument codes which have been flagged as surface.")
        with open(join(basedir, f"{basename}_insts_flags.txt"), "r", encoding='utf-8') as f:
            data = f.readlines()
            f.close()
        insts_to_be_flagged += [int(elem.strip("\n").split("\t")[0]) for elem in data]
    

    for key, value in instrument_comments.items():
        print(key, value)

    
    # if no flag is written, then:
    if user_flags != "":
        try:
            insts_to_be_flagged +=  [int(elem) for elem in user_flags.split(",")]
            print("adding this code to be flagged as surface:", insts_to_be_flagged)
        except ValueError:
            print("you need to write a a list of integers separated by commas. e.g., '-instr_flags=[1,14,20]'\n") 

    # check whether the series is flagged as surface
    for key in instrument_codes:
        if int(key) in insts_to_be_flagged:
            instrument_codes[key][-1] = "-50.00"

    with open(join(basedir, f"{basename}_insts_flags.txt"), "w", encoding='utf-8') as f:
        for key, value in instrument_codes.items():
            flag = value[-1]
            if flag == "-50.00":
                f.write(f"{key}\t2\n")
        f.close()
    
    user_flags = ""
    return instrument_codes
    
def flag_surface_series(user_flags, series: dict, basedir: str, basename: str)-> dict:
    ### takes in a series, assumes that there is a file containing a list of series indices to be flagged. 
    ### writes a file which contains the indices of the series to be flagged. 
    
    series_flags = {}
    series_to_be_flagged = []
    print(join(basedir, f"{basename}_series_flags.txt"))
    # check first whether the file actually exists and extract the series to be flagged.
    if isfile(join(basedir, f"{basename}_series_flags.txt")):  
        print("there exist already some series which have been flagged as surface.")
        with open(join(basedir, f"{basename}_series_flags.txt"), "r", encoding='utf-8') as f:
            data = f.readlines()
            f.close()
        series_to_be_flagged += [int(elem.strip("\n").split("\t")[0]) for elem in data]
    

    for key, value in series.items():
        # ignore empty survey names
        if value["survey_name"] != "":
            print(key, value["survey_name"][0].strip("\n"))

    
    # if no flag is written, then:
    if user_flags != "":
        try:
            series_to_be_flagged +=  [int(elem) for elem in user_flags.split(",")]
        except ValueError:
            print("you need to write a list of integers separated by commas. e.g., '-series_flags=[1,14,20]'\n") 

    # check whether the series is flagged as surface
    for key in series.keys():
        if key in series_to_be_flagged:
            series_flags[key] = "surface"
        else:
            series_flags[key] = "None"

    with open(join(basedir, f"{basename}_series_flags.txt"), "w") as f:
        for key, flag in series_flags.items():
            if flag != "None":
                f.write(f"{key}\t{_LOCAL_SERIES_FLAGS[flag]}\n")
        f.close()

    return series_flags

### END OF OF THE PARSER

### BEGIN FORMATTING

# Formatting  functions below 
def format_surveyors_str(session_metadata, key):
    try:
        srv1, srv2 = session_metadata[key]["team"]
        if "/" not in srv1 and "/" not in srv2:
            srv_list = f'team "[{srv1}]"\nteam "[{srv2}]"'
        else:
            srv_list = f'#team "[{srv1}]"\n#team "[{srv2}]"'
    except KeyError:
        print("survey metadata key seems to be wrong.")
        srv_list = ""

    return srv_list

def format_fixes_str(fixes : list) -> list:
    fixes_str= []

    for fix in fixes:
        fixes_str.append(f"fix {fix[5]}@{fix[4]}\t{fix[1]}\t{fix[2]}\t{fix[3]}\n")
    
    return fixes_str

def is_written_equate(equate) -> bool:
    """Returns true if the equate joins two series, or two stations of one series through a zero-length shot"""
    return equate[1][0] != equate[0][0] or equate[2] == 1

def format_equates_str(equates: list, keys) -> list:
    
    equates_str = []
    for equate in equates:
        # don't allow for equates with non-existent surveys. 
        if int(equate[1][0]) not in keys and int(equate[0][0]) not in keys:
            equates_str.append(f"equate {equate[0][1]}_{equate[0][0]} {equate[1][1]}_{equate[1][0]}\n")
        elif int(equate[0][0]) not in keys:
            equates_str.append(f"equate {equate[0][1]}_{equate[0][0]} {equate[1][1]}@{equate[1][0]}\n")
        elif int(equate[1][0]) not in keys:
            equates_str.append(f"equate {equate[0][1]}@{equate[0][0]} {equate[1][1]}_{equate[1][0]}\n")
        else:
            equates_str.append(f"equate {equate[0][1]}@{equate[0][0]} {equate[1][1]}@{equate[1][0]}\n")

    return equates_str

def format_date_str(session_metadata, key):
    try:
        date = session_metadata[key]["date"]
        thisyear = datetime.datetime.today().strftime('%Y')
        
        # check whether the date should begin with 19 rather than 20.
        print(date)

        try:

            if int(date[:4]) > int(thisyear):
                date = "19" + date[2:]
                print("futuristic date changed to: ", date)
            
            date_str = f"date {date}"

        except ValueError:
            date_str = ""

       
    except KeyError:
        print("session metadata key not found. ")
        date_str = ""

    return date_str

def format_data_header(parsed_instrument_codes, key):
    
    d = parsed_instrument_codes
    print(f"using instrument key {key}")
    flag = None

    if key not in d.keys():
        print("this will fail. attempting to call a non-existing instrument key on this survey...")
        key = str(min([int(elem) for elem in d.keys()]))
    
    if d[key]["clino"]["unit"] == "dh":
        if d[key]["compass"]["unit"] == "degrees inverse":
           data_header_str = f"""## Dive line, inverse sightings
units compass degrees
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} degrees
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data diving from to length backcompass depthchange """
           
        elif d[key]["compass"]["unit"] == "grads inverse":
           data_header_str = f"""## Dive line, inverse sightings
units compass grads
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} grads
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data diving from to length backcompass depthchange """
           
        else:
            data_header_str = f"""## Dive line
units compass {d[key]["compass"]["unit"]}
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} {d[key]["compass"]["unit"]}
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data diving from to length compass depthchange """
    
    elif d[key]["clino"]["unit"] == "direct":
        
       data_header_str = f"""## Dive line
units compass {d[key]["compass"]["unit"]}
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} {d[key]["compass"]["unit"]}
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data diving from to length compass depthchange """
    
    else:
    
        if d[key]["compass"]["unit"] == "degrees inverse" and d[key]["clino"]["unit"] == "degrees inverse":
        
            data_header_str= f"""## Inverse sightings
units compass degrees
units clino degrees
units length {d[key]["length"]["unit"]} 
calibrate clino 0
sd compass {d[key]["compass"]["precision"]} degrees
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length backcompass backclino """
        
        elif d[key]["compass"]["unit"] == "degrees inverse" and d[key]["clino"]["unit"] == "degrees nadir":
        
            data_header_str= f"""## Inverse sightings
units compass degrees
units clino degrees
units length {d[key]["length"]["unit"]} 
calibrate clino 90 -1
sd compass {d[key]["compass"]["precision"]} degrees
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length backcompass clino """
        
        elif d[key]["compass"]["unit"] == "degrees inverse":
        
            data_header_str= f"""## Inverse sightings
units compass degrees
units clino degrees
units length {d[key]["length"]["unit"]} 
calibrate clino 0
sd compass {d[key]["compass"]["precision"]} degrees
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length backcompass clino """
    
        elif d[key]["clino"]["unit"] == "degrees inverse":
        
            data_header_str= f"""## Inverse sightings
units compass degrees
units clino degrees
units length {d[key]["length"]["unit"]} 
calibrate clino 0
sd compass {d[key]["compass"]["precision"]} degrees
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length compass backclino """
        
        elif d[key]["compass"]["unit"] == "grads inverse" and d[key]["clino"]["unit"] == "grads inverse":
        
            data_header_str= f"""## Inverse sightings
units compass grads
units clino grads
units length {d[key]["length"]["unit"]} 
calibrate clino 0
sd compass {d[key]["compass"]["precision"]} grads
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length backcompass backclino """
        
        elif d[key]["compass"]["unit"] == "grads inverse" and d[key]["clino"]["unit"] == "grads nadir":
        
            data_header_str= f"""## Inverse sightings
units compass grads
units clino grads
units length {d[key]["length"]["unit"]} 
calibrate clino 100 -1
sd compass {d[key]["compass"]["precision"]} grads
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length backcompass clino """

        elif d[key]["compass"]["unit"] == "grads inverse":
            data_header_str= f"""## Inverse sightings
units compass grads
units clino grads
units length {d[key]["length"]["unit"]} 
calibrate clino 0
sd compass {d[key]["compass"]["precision"]} grads
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length backcompass clino """
        
        elif d[key]["clino"]["unit"] == "grads inverse":
            data_header_str= f"""## Inverse sightings
units compass grads
units clino grads
units length {d[key]["length"]["unit"]} 
calibrate clino 0
sd compass {d[key]["compass"]["precision"]} grads
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length compass backclino """
    
        elif "grads zenith" in d[key]["clino"]["unit"]:
            unit_comp = d[key]["compass"]["unit"].split("nadir")[0].split("zenith")[0]

            data_header_str=  f"""## zenithal clino measurements
units compass {unit_comp}
units clino grads
calibrate clino 100 -1
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} {unit_comp}
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length compass clino """
    
        elif "degrees zenith" in d[key]["clino"]["unit"]:
            data_header_str= f"""## zenithal clino measurements
units compass {d[key]["compass"]["unit"]}
units clino degrees
calibrate clino 90 -1
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} {d[key]["compass"]["unit"]}
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length compass clino """
        
        elif "grads nadir" in d[key]["clino"]["unit"]:
            data_header_str=  f"""## nadiral grad clino measurements
units compass {d[key]["compass"]["unit"]}
units clino grads
calibrate clino 100 
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} {d[key]["compass"]["unit"]}
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length compass clino """
        
                
        elif "degrees nadir" in d[key]["clino"]["unit"]:
            data_header_str= f"""## nadiral degree clino measurements
units compass {d[key]["compass"]["unit"]}
units clino degrees
calibrate clino 90
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} {d[key]["compass"]["unit"]}
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length compass clino """
   
        else:
            unit_comp = d[key]["compass"]["unit"].split("nadir")[0].split("zenith")[0]
            data_header_str = f"""
units compass {unit_comp}
units clino {d[key]["clino"]["unit"]}
calibrate clino 0
units length {d[key]["length"]["unit"]} 
sd compass {d[key]["compass"]["precision"]} {unit_comp}
sd length {d[key]["length"]["precision"]} {d[key]["length"]["unit"]}
data normal from to length compass clino """
    
    flag_key = float(d[key]["flag"].strip(" "))
    
    return data_header_str, _FLAGS_PARSER[flag_key]


def format_comments(parsed_comments):

    comments = " "
    for key, value in parsed_comments.items():
        if key[:2] != "-1":
            if '"' in value:
                print("invalid comment")
                formatted_comment = f'#station {key} "{value}" ## invalid comment\n'
            else:
                formatted_comment = f'station {key} "{value}"\n'
            comments += formatted_comment
    return _COMMENTS_STRING.format(comments=comments)


def to_degrees_direction(compass: float, clino: float, units: dict) -> tuple:
    """Convert toporobot compass and clino readings to an azimuth and an inclination from the horizontal, both in degrees"""
    compass_unit = units["compass"]["unit"]
    clino_unit = units["clino"]["unit"]

    if "grads" in compass_unit:
        compass = grad2deg(compass)
    if "inverse" in compass_unit:
        # a backsight reading points from the to station back to the from station
        compass = (compass + 180) % 360

    if clino_unit == "percentage":
        clino = rad2deg(np.arctan(clino / 100))
    elif "grads" in clino_unit:
        clino = grad2deg(clino)

    if "zenith" in clino_unit:
        clino = 90 - clino
    elif "nadir" in clino_unit:
        clino = clino - 90
    elif "inverse" in clino_unit:
        clino = -clino

    return compass, clino

def inject_lrud(shot_data, station_data, parsed_instrument_codes):
    
    splay_shot_data = []

    # instrument key 0 has no instrument code, and we write its shots in grads
    key_0_units = {"compass": {"unit": "grads"}, "clino": {"unit": "grads"}}

    # we compute the splays from the true direction of each shot, so they are written in degrees whatever the instrument
    true_shot_data = []
    for from_station, to_station, length, compass, clino, explo_key, ik in shot_data:
        try:
            compass, clino = to_degrees_direction(float(compass), float(clino), parsed_instrument_codes.get(str(ik), key_0_units))
        except ValueError:
            pass
        true_shot_data.append([from_station, to_station, length, compass, clino, explo_key, ik])
    shot_data = true_shot_data

    centreline_units = Units("empty")
    centreline_units.compass = "degrees"
    centreline_units.clino = "degrees"

    # set up a counter to keep track of where to insert the splay lines.
    lrud_counter = 0

    for c, lrudLine in enumerate(station_data):
        from_station, left, right, up, down, ik = lrudLine
        th_lrudLine = LineLRUD(from_station=from_station, left= float(left), right= float(right), up= float(up), down= float(down))
        
        # direction
        normal_vec = np.zeros(3)

        for k, dataLine in enumerate(shot_data):
            from_station, to_station, length, compass, clino, _, _ = dataLine

            th_dataLine = NormalDataLine(from_station=from_station,
                                         to_station=to_station,
                                         compass=compass, 
                                         clino=clino, 
                                         tape=length)
            
            lrud_station = th_lrudLine.from_station
            
            if isinstance(th_dataLine, NormalDataLine):

                if c == 0:
                    if th_dataLine.from_station == lrud_station:
                        try:
                            compass = float(th_dataLine.compass)
                            normal_vec = spherical2cartesian(compass,float(th_dataLine.clino), centreline_units)
                        except ValueError:
                            pass
                        
                    station_counter = k    

                elif c== len(station_data)-1:
                    if th_dataLine.to_station == lrud_station:
                        try:
                            compass = float(th_dataLine.compass)
                            normal_vec = spherical2cartesian(compass,float(th_dataLine.clino), centreline_units)
                        except ValueError:
                            pass
                        
                        station_counter = k

                else:

                    if th_dataLine.to_station == lrud_station and k != len(shot_data)-1:

                        dataLine1= shot_data[k]
                        from_station, to_station, length, compass, clino, _, _ = dataLine1

                        th_dataLine1 = NormalDataLine(from_station=from_station,
                                         to_station=to_station,
                                         compass=compass, 
                                         clino=clino, 
                                         tape=length)
            


                        # now we know we have found good station. 
                        if shot_data[k+1][0] == lrud_station:
                            dataLine2= shot_data[k+1]
                            from_station, to_station, length, compass, clino, _, _ = dataLine2

                            th_dataLine2 = NormalDataLine(from_station=from_station,
                                         to_station=to_station,
                                         compass=compass, 
                                         clino=clino, 
                                         tape=length)
                            
                            
                            try:
                                comp1 = float(th_dataLine1.compass)
                                clino1 = float(th_dataLine1.clino) 
                            
                            except ValueError:
                                comp1 = 0
                                if th_dataLine1.clino.lower() == "up":
                                    clino1 = +90
                                else:
                                    clino1 = -90

                            try:
                                comp2 = float(th_dataLine2.compass)
                                clino2 = float(th_dataLine2.clino)

                            except ValueError:
                                comp2 = 0
                                if th_dataLine2.clino.lower() == "up":
                                    clino2 = +90
                                else:
                                    clino2 = -90

                            # 1. dir 1 to cartesian, dir 2 to cartesian
                            cartesian_1 = spherical2cartesian(comp1, clino1, centreline_units)
                            cartesian_2 = spherical2cartesian(comp2, clino2, centreline_units)
                
                            normal_vec = bisector(cartesian_1, cartesian_2)

                            # splay from normal vector and lruds 
                            station_counter = k+1
                        
                        else:
                            try:
                                comp1 = float(th_dataLine1.compass)
                                clino1 = float(th_dataLine1.clino) 
                                normal_vec = spherical2cartesian(comp1,clino1, centreline_units)

                            except ValueError:
                                pass


                            station_counter = k+1

        j = 0
        try:              
            lrud_vectors = calc_splay_from_lrud(np.zeros(3), normal_vec, th_lrudLine.dims)

            for dim in lrud_vectors:
                # transform back to original units. 

                phi, theta = cartesian2spherical(dim, centreline_units)

                compass = f"{phi:.1f}"
                inclination = f"{theta:.1f}"
                len_dim = f"{np.linalg.norm(dim):.1f}"

                # injection de ligne bidon. 
                if float(len_dim) > 0:
                    newsplayline = NormalDataLine(from_station=th_lrudLine.from_station,
                                                to_station="-", 
                                                tape=len_dim,
                                                compass=compass,
                                                clino=inclination)
                    
                    splay_shot_data.append([newsplayline.from_station, newsplayline.to_station, newsplayline.tape, newsplayline.compass, newsplayline.clino, ik])
                    #centreline.add_dataline(newsplayline, lrud_counter+station_counter+j)
                    j+=1
        except AssertionError:
            print("splay calculation failed.. vertical shaft")

        lrud_counter+=j

    return splay_shot_data

def format_centreline_str(series, series_key, parsed_instcodes, session_metadata, instcodes, parsed_inst_code_comments,series_flags, lrud):
    shot_data = series[series_key]["shot_data"]
    station_data = series[series_key]["station_data"]

    # the splay data should also remain with its instrument keys. 


    series_flag = series_flags[series_key]
    # check whether datalines all have the same instrument key. 
    inst_keys = [elem[-1] for elem in shot_data]

    if lrud == True:
        splay_shot_data = inject_lrud(shot_data, station_data, parsed_instcodes)
    else: 
        splay_shot_data = []
    # special case for tie points definition in surveys with zero shot data. 
    if len(shot_data) == 0: 
        print(station_data)
        session_str = ""
        
        topocomment = f"""\n## This is a tie point survey"""
        
        session_str += f"""
{topocomment}
station {station_data[0][0]} ""
station {station_data[1][0]} ""

equate {station_data[0][0]} {station_data[1][0]}
"""
        
    elif len(shot_data)>= 1:
        session_key = shot_data[0][-2]


        surveyors_str = format_surveyors_str(session_metadata, session_key)
        date_str = format_date_str(session_metadata, session_key)
        data_entry_str = "" 
       
        for inst_key in sorted(set(inst_keys), key=int):
            print(f"now working on survey {series_key}")
            data_header, flag = format_data_header(parsed_instcodes, inst_key)
            if inst_key == 12:
                print("on instrument key 12:", data_header)

            # instrument key 0 has no instrument code, so we read the codes of the smallest other key
            codes_key = inst_key
            if inst_key == "0":
                topocomment = f"""\n## Probably a GhTopo instrument key 0
## Toporobot instrument code comment: fixed point or entrance."""
                codes_key = str(min([int(elem) for elem in set(inst_keys)-{inst_key}]))
                data_header = """
units compass clino grads
units length metres
data normal from to length compass clino"""
            
            else:    
                topocomment = f"""\n## Toporobot instrument key {inst_key}
## Toporobot instrument code comment: {parsed_inst_code_comments[inst_key]}"""
            
            # initialise the shot and dimension entries strings.
            shot_entries = ""
            splay_entries = ""
            lrud_entries = ""

            # subsample the stations from which we want the dimensions. 
            for line in station_data:
                _from, left, right, up, down, ik = line
                if ik == inst_key:
                    lrud_entries += f"{_from}\t{str(abs(float(left)))}\t{str(abs(float(right)))}\t{str(abs(float(up)))}\t{str(abs(float(down)))}\n"
            
            # subsample the stations from which we want the dimensions. 
            for line in splay_shot_data:
                _from, to, length, compass, clino, ik = line
                if ik == inst_key:
                    splay_entries += f"{_from}\t{to}\t{length}\t{compass}\t{clino}\n"

            print(splay_entries)

            for c, line in enumerate(shot_data):
                _from, to, length, compass, clino, _, ik = line

                # add possibility to have back compass or backclino readings as well as nadiral angles for inclinations.
                clino_code = float(instcodes[codes_key][1])
                
                if clino_code == 399:
                    clino = float(clino) 
                elif clino_code == 359:
                    clino = float(clino)
                if ik == inst_key:

                    if _from != to and c != len(shot_entries)-1:
        
                        shot_entries += f"{_from}\t{to}\t{length}\t{compass}\t{clino}\n"
                        
                    elif c == len(shot_data)-1:
                        shot_entries += f"{_from}\t{to}\t{length}\t{compass}\t{clino}\n"
                    
                
            if flag != "None":
                data_entry_str += f"""
{topocomment}
{data_header}
flags {flag}
{shot_entries}
flags not {flag}

units compass clino degrees
calibrate clino 0 ## removing any previous nadiral / zenithal calibrations.
data normal from to length compass clino
{splay_entries}

data dimensions station left right up down
{lrud_entries}"""
                
             ### here, we check what the flag shoud be. 
            elif series_flag != "None":
                print("this series should be a surface series", flag, series_flag)
                flag = series_flag
                data_entry_str += f"""
{topocomment}
{data_header}
flags {flag}
{shot_entries}
flags not {flag}

units compass clino degrees
calibrate clino 0 ## removing any previous nadiral / zenithal calibrations.
data normal from to length compass clino
{splay_entries}

data dimensions station left right up down
{lrud_entries}"""
                   
            else:
                data_entry_str += f"""
{topocomment}
{data_header}
{shot_entries}

units compass clino degrees
calibrate clino 0 ## removing any previous nadiral / zenithal calibrations.
data normal from to length compass clino
{splay_entries}

data dimensions station left right up down
{lrud_entries}"""
            

        session_str = f"""
{date_str}
{surveyors_str}
{data_entry_str}
"""

    # only if returning empty strings
    else:
        session_str = None

    return session_str



def to_therion_string(series_key, series, parsed_instrument_codes, session_metadata, instrument_codes, parsed_inst_code_comments, series_flags, lrud):
    centreline = format_centreline_str(series, series_key, parsed_instrument_codes, session_metadata, instrument_codes, parsed_inst_code_comments, series_flags, lrud)

    try: 
        survey_name = series[series_key]["survey_name"][0].strip("\n")
        
        return _TH_SUBSURVEY_TEMPLATE.format(survey_name=series_key, 
                                 survey_title=survey_name, 
                                 centreline = centreline)
    except IndexError:
        survey_name = "unnamed"
        if centreline != None:
        
            return _TH_SUBSURVEY_TEMPLATE.format(survey_name=series_key, 
                                 survey_title=survey_name, 
                                 centreline = centreline)
        else:
            return "\n"


def format_full_therion_file(basename, parsed_data, keys, series, equates, comments,crs, lrud, *args):
    subsurveys ="" 
    for key in keys:
        
        subsurveys += to_therion_string(key, series, *args, lrud=lrud)



    fixes = find_fixes(parsed_data)
    # equates_str lines up with equates, so the fixes below can rewrite the matching equate line
    equates = [equate for equate in equates if is_written_equate(equate)]
    equates_str = format_equates_str(equates, keys)


    # sanitisation of equates using survey keys. Assuming that any remaining non-surveys are
    # entrance fixes.


    entrances = find_entrances(parsed_data)
    fixes_str = format_fixes_str(fixes)
    
    for c, fix in enumerate(fixes):
        
        # sanitisation using fixes and equates.
        if int(fix[-2]) not in keys:
            print("attempting to create a new survey on this fix, ", fix[-2])
            old_fix = fixes_str[c]
            new_fix = old_fix.replace(f"{fix[-1]}@{fix[-2]}", f"{fix[-1]}_{fix[-2]}")
            print(new_fix)
            fixes_str[c] = new_fix

            for entrance in entrances:
                if entrance[0] == fix[0]:
                    print("this appears to be a new entrance, ", entrance[1])
                    entrance_as_str = f'station {fix[-1]}_{fix[-2]} "{entrance[1]}" entrance\n'
                    fixes_str[c] += entrance_as_str

            print("checking this fix", fix[-2])

            for k, equate in enumerate(equates):
                if int(equate[0][0]) == int(fix[-2]):

                    old_equate = equates_str[k]
                    new_equate = old_equate.replace(f"{equate[0][1]}@{equate[0][0]}", f"{equate[0][1]}_{equate[0][0]}")
                    equates_str[k] = new_equate
                    
                elif int(equate[1][0]) == int(fix[-2]):

                    old_equate = equates_str[k]
                    new_equate = old_equate.replace(f"{equate[1][1]}@{equate[1][0]}", f"{equate[1][1]}_{equate[1][0]}")
                    equates_str[k] = new_equate
                    
        
    comments_str = format_comments(comments)

    if crs == "None":
        return _TH_FILE_TEMPLATE_NO_CRS.format(basename= basename,  
                                    fixes="".join(fixes_str), 
                                    equates="".join(equates_str), 
                                    subsurveys=subsurveys, 
                                    comments = comments_str)
    
    else:
        return _TH_FILE_TEMPLATE.format(basename= basename, 
                                    crs = crs, 
                                    fixes="".join(fixes_str), 
                                    equates="".join(equates_str), 
                                    subsurveys=subsurveys, 
                                    comments = comments_str)

def format_config_file(basename, crsout):
    if crsout == "None":
        return _TH_CONFIG_FILE_TEMPLATE.format(basename = basename)
    else:
        return _TH_CONFIG_FILE_TEMPLATE_WITH_CRS.format(basename = basename,crsout= crsout)

if __name__ == "__main__":
    # Read the script arguments and load the Toporobot archive file. 

    parser = argparse.ArgumentParser(description="Converts a Toporobot file to Therion format", epilog='thank you for using the tr2th script. Please double check your output therion file for any bugs and report them to thehelpdesk@realadress.com')

    parser.add_argument(
        "survey_file",
        help='The toporobot archive file (*.txt) to work from."',
    )

    parser.add_argument(
        "survey_selector",
        help='The basename of the survey for the therion file (may not include special characters)"',
        )
    
    parser.add_argument("-o", "--output",
        help='The file in which to store the output)"', default=None
        )
    
    parser.add_argument("-crsin", "--input_coordinate_reference_system",
        help='An epsg code of the form: "epsg:12345"', default="None"
        )
    
    parser.add_argument("-crsout", "--output_coordinate_reference_system",
        help='An epsg code of the form: "epsg:12345"', default="None"
        )

    parser.add_argument("-e", "--encoding",
        help='The encoding for the file to be read', default="utf-8"
        )
    
    parser.add_argument("-ikc", "--inst_key_col",
        help='Where to find the instrument key', default="2"
        )

    parser.add_argument("-ifl", "--instrument_flags",
            help='A list of user defined instrument flags in the form: "[1,3,20]"', default=""
            )

    parser.add_argument("-sfl", "--series_flags",
            help='A list of user defined surface series flags "[1,3,20]"', default=""
            )
    
    parser.add_argument("-lrud", "--inject_LRUD",
        help='Whether to expand station dimension data into splays', default = "True"
        )

    args = parser.parse_args()

    ENTRY_FILE = abspath(args.survey_file)
    BASENAME = args.survey_selector
    OUTPUT_DIRECTORY = args.output
    CRSIN = args.input_coordinate_reference_system
    CRSOUT = args.output_coordinate_reference_system

    ENCODING = args.encoding
    INST_KEY_COL = int(args.inst_key_col)
    USER_INST_FLAGS =args.instrument_flags.strip("[").strip("]")
    USER_SERIES_FLAGS = args.series_flags.strip("[").strip("]")
    if args.inject_LRUD == "True" or args.inject_LRUD == "true":
        LRUD = True
    else:
        LRUD = False

    print(f"Using encoding {ENCODING} to read the file")
    print(f"You have selected series: {USER_SERIES_FLAGS}")


    ## SET UP THE EXPORT DIRECTORY
    WRITE_PATH =  abspath(OUTPUT_DIRECTORY)
    OUTPUTS_FILEPATH = join(WRITE_PATH, "outputs")
    makedirs(OUTPUTS_FILEPATH, exist_ok=True)
    
    copy(ENTRY_FILE, WRITE_PATH)


    ## READING IN .
    DATA = read_file(ENTRY_FILE, ENCODING)
    PARSED, COMMENTS = parse_keys(DATA)
    find_entrances(PARSED)
    PARSED_COMMENTS = parse_station_comments(COMMENTS)
    SERIES_KEYS = identify_series_keys(PARSED)
    INST_CODES = find_instrument_codes(PARSED)
    PARSED_INST_CODES = parse_instrument_codes(INST_CODES)
    TIES = find_tie_points(PARSED, SERIES_KEYS)
    EQUATES = find_equates(PARSED, TIES, PARSED_INST_CODES, inst_key_col=INST_KEY_COL)
    SERIES = parse_all_series(PARSED, SERIES_KEYS, EQUATES, PARSED_INST_CODES, inst_key_col=INST_KEY_COL)
    SESSION_METADATA = find_session_metadata(PARSED)
    PARSED_INST_CODE_COMMENTS = parse_instrument_code_comments(COMMENTS, INST_CODES)
    INST_CODES = flag_surface_inst_codes(INST_CODES, PARSED_INST_CODE_COMMENTS,USER_INST_FLAGS, OUTPUT_DIRECTORY, BASENAME)
    SERIES_FLAGS = flag_surface_series(USER_SERIES_FLAGS, SERIES, OUTPUT_DIRECTORY, BASENAME)

    #for key, value in PARSED_INST_CODE_COMMENTS.items():
    #    print(key, value)

    ## check whether any of the above instrument codes correspond to a series of surface measurements.
    ## user prompt for list of series to be flagges as surface. 

    # function_to_

    ## Formatting

    THERION_FILE_STRING = format_full_therion_file(BASENAME, 
                                                   PARSED, 
                                                   SERIES_KEYS, 
                                                   SERIES,
                                                   EQUATES, 
                                                   PARSED_COMMENTS,
                                                   CRSIN,
                                                   LRUD,
                                                   PARSED_INST_CODES, 
                                                   SESSION_METADATA,
                                                   INST_CODES,
                                                   PARSED_INST_CODE_COMMENTS,
                                                   SERIES_FLAGS
                                                   )

    CONFIG_FILE_STRING = format_config_file(BASENAME, CRSOUT)

    

    ## Writing to file
    ENTRY_FILENAME = split(ENTRY_FILE)[1]

    with open(join(WRITE_PATH, f"{BASENAME}_convert.th"), "w", encoding=ENCODING) as f:
        f.write(THERION_FILE_STRING)
        f.close()
    ## Writing to file
    with open(join(WRITE_PATH, f"{BASENAME}.thconfig"), "w") as f:
        f.write(CONFIG_FILE_STRING)
        f.close()

# add check for non negative stations in comments. 