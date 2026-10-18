"""
Created on Fri Jul 5 08:54:34 2024

@author: Tanguy Racine, Celia Trunz

This provides a parser for converting "Compass" files to therion
"""

import argparse
from os.path import abspath, split, join, normpath, dirname, isfile
from os import makedirs, listdir
from shutil import copy
from helpers.therion_classes import *
from helpers.utils import *
from def_calc_splay_from_lrud import *

_LINE_TYPES = {"measurement": [0,13, 26, 35, 44, 53, 62, 71, 80, 89, 97],
              "survey_name": [0, 13]}

# from https://survex.com/docs/manual/compass.htm
# Shot flag C is currently ignored.
# Shot flag L is mapped to Survex’s “duplicate” leg flag.
# Shot flag P is mapped to Survex’s “surface” leg flag. The Compass documentation describes shot flag P as “Exclude this shot from plotting”, but the suggested use for it is for surface data, and shots flagged P “[do] not support passage modeling”. Even if it’s actually being used for a different purpose, Survex programs don’t show surface legs by default so the end effect is at least to not plot as intended.
# Shot flag S is mapped to Survex’s “splay” leg flag.

_FLAGS = {"|P": "surface", 
          "|PL": "duplicate",
          "|PLC": "duplicate",
          "|LPC": "duplicate",
          "|PCL": "duplicate",
          "|LPL": "duplicate",
          "|LP": "duplicate",
          "|LC": "duplicate", 
          "|LLL": "duplicate", 
          "|C": "duplicate", 
          "|L": "duplicate", 
          "|X": "duplicate", 
          "|X|": "duplicate",
          "|XL": "duplicate",
          "|LX": "duplicate",
          '|CL': "duplicate", 
          '|XXX': "duplicate",
          "|CLL": "duplicate", 
          "|CLX": "duplicate",
          "|S": "splay",
          "|-": "None", #compass does not seem to read it as splays
          "|???": "splay",
          "|?": "splay", 
          "|*": "duplicate", 
          "|!": "splay", 
          "| ": "None",
          "|": "None",
          "|B": "None",
          "|BL": "duplicate",
          "|\t": "None"}

#_FORMAT_UNITS = 
# #0: Az units, 
# #1: Length units, 
# #2: Length units passage dims, 
# 3: Inclination units
# 4,5,6,7: dimension order
# 8, 9, 10: shot items

# The dat file is already formatted thus, with angles in degrees and lengths in feet.

# default compass header

_INCLINATION_UNITS = {"D": "degrees",
                      "R": "grads",
                      "G": "percent",
                      "M": "minutes"}

_AZIMUTH_UNITS = {"D":"degrees",
                  "R": "grads",
                  "Q": "quads"}

_LENGTH_UNITS = {"M":"metres",
                 "D":"feet",
                 "I":"inches"}

_DIMENSIONS = {"L": "left", 
               "R":"right", 
               "U": "up", 
               "D":"down"}

_SHOT_ITEMS = {"L":"length",
               "A":"compass",
               "D":"clino",
               "a": "backcompass",
               "d": "backclino"}

_PART_TH_FILE_TEMPLATE = """
{subsurveys}
"""

_INDEX_TH_FILE_TEMPLATE = """survey {basename}

{inputs}

{fixes}
endsurvey
"""

_TH_FILE_TEMPLATE = """survey {basename}

{subsurveys}

{fixes}
endsurvey
"""

_TH_CONFIG_FILE_TEMPLATE = """source {basename}_convert.th
export database -o outputs/{basename}.sql
export model -o outputs/{basename}.3d
export model -o outputs/{basename}.lox
export model -o outputs/{basename} -fmt esri
"""

_TH_CONFIG_FILE_TEMPLATE_WITH_CRS = """source {basename}_convert.th
cs {crsout}
export database -o outputs/{basename}.sql
export model -o outputs/{basename}.3d
export model -o outputs/{basename}.lox
export model -o outputs/{basename} -fmt esri
"""

feet_to_metres = lambda x: x * 0.3048

### main parsing functions below


def read_file (filename : str, encoding : str = 'utf-8') -> list :
    """Reads a Compass text file in archive format. 

    Parameters
    ----------
    filename : str
        the name of the file to be converted
    encoding : str, optional
        the encoding, by default 'utf-8'

    Returns
    -------
    list
        a list of strings
    """    

    with open ( filename , "r", encoding=encoding ) as f :
        
        lines = f.readlines()
        
        f.close()
        
    return lines

def parse_data_header( line : str) -> dict :
    """Parses each data header line in the Compass data lines using a given strategy
    This should take into account back shots. 
    Returns dictionary containing the data description
    """
    
    declination = line.split("FORMAT:")[0].strip().removeprefix("DECLINATION:").strip()
    if "FORMAT:" not in line:
        format = "DDDDLRUDLADN"
    else:
        format = line.split("FORMAT:")[1].split("CORRECTIONS")[0].strip(" ").strip("\t")
        
        # if the format is an empty string, assume default format.
        if len(format) <=1:
            format = "DDDDLRUDLADN"
        # print(format[0])
        #format = line.split("FORMAT:")[1].split("CORRECTIONS")[0].strip("\n").strip(" ").strip("\t")
    
    if "CORRECTIONS:" not in line:
        corrections = ""
    else:
        corrections = line.split("CORRECTIONS:")[1].strip("\n").strip(" ").strip("\t").split(" ")
    
    data_header = {"declination": declination,
            "format": format,
            "corrections":corrections}
    
    return data_header

def parse_format( format: str) -> dict :

    az_units = _AZIMUTH_UNITS[format[0]]
    length_units = _LENGTH_UNITS[format[1]]
    inc_units = _INCLINATION_UNITS[format[3]]

    
    dim1 = _DIMENSIONS[format[4]]
    dim2 =_DIMENSIONS[format[5]]
    dim3 = _DIMENSIONS[format[6]]
    dim4 = _DIMENSIONS[format[7]]
    shot_item_1 = _SHOT_ITEMS[format[8]] 

    if "DdAa" in format or "AaDd" in format:
        shot_item_2 = _SHOT_ITEMS[format[9]]
        shot_item_3 = _SHOT_ITEMS[format[10]]
        shot_item_4 = _SHOT_ITEMS[format[11]]
        shot_item_5 = _SHOT_ITEMS[format[12]]

        data_format = {"units length": length_units,
                       "units dimensions": length_units,
                    "units compass": az_units,
                    "units clino": inc_units,
                    "units backcompass": az_units,
                    "units backclino": inc_units,
                    "header_order": ["from","to", shot_item_1, shot_item_2, shot_item_4, shot_item_3, shot_item_5, dim1, dim2, dim3, dim4],
                    "orig_data_header": f"data normal from to {shot_item_1} {shot_item_2} {shot_item_4} {shot_item_3}  {shot_item_5}",
                    "station_dims_header": f"data dimensions station left up down right"
                    }
    else: 
        shot_item_2 = _SHOT_ITEMS[format[9]]
        shot_item_3 = _SHOT_ITEMS[format[10]]
    

    
        data_format = {"units length": length_units,
                       "units dimensions": length_units,
                    "units compass": az_units,
                    "units clino": inc_units,
                    "header_order": ["from","to", shot_item_1, shot_item_2, shot_item_3, dim1, dim2, dim3, dim4],
                    "orig_data_header": f"data normal from to {shot_item_1} {shot_item_2} {shot_item_3}",
                     "station_dims_header": f"data dimensions station left up down right"
                    }

    return data_format


def validate_stn_name(stn: str) -> str:
    return stn.replace("!", "exc").replace("'", "quote").replace("`", "revquote").replace("?", "q").replace("*", "ast").replace("#", "hash").replace("$", "dol").replace("%", "perc").replace("&", "amp").replace("=","eq")

def format_dimension(value: str) -> str:
    """Format a passage dimension in feet. Compass writes missing dimensions as negative values or 999, and we write them as 0"""
    dimension = float(value)
    if dimension < 0 or dimension == 999:
        dimension = 0
    return f"{dimension:.2f}"

def parse_measurement( line: str) -> dict:

    rawparts =[elem.strip(" ") for elem in line.split("#")[0].split(" ") if elem != ""] # split the parts by spaces.

    if len(rawparts) == 9: # there is no comment.
        parts = rawparts

    elif len(rawparts) > 0 and len(rawparts) <= 11: 

        try: 
            test = float(rawparts[9])
            test2 = float(rawparts[10]) # this might be forward / backsight pair without comment.
            parts = rawparts
        except: 
            parts = rawparts[:9] # this is a forward sighting with potential flag and comments.
    else:
        try: 
            test = float(rawparts[9])
            test2 = float(rawparts[10]) # this might be forward / backsight pair with comment.
            parts = rawparts[:11]
        except: 
            parts = rawparts[:9] # this is a forward sighting with potential flag and comments.
        
    if len(parts) > 10:  
        
        
        part10 = parts[10].strip('\n')

        if "#" in line:
            flag = line.split("#")[1]
            comment = line.split("#")[-1] 
        else:
            flag = "None"
            comment = ""

        comment_str = ""
        for elem in comment:
            comment_str+= elem.strip("\n").replace('"', "'")
        

        measurement = {"from": validate_stn_name(parts[0]), 
                   "to": validate_stn_name(parts[1]),
                   "length": parts[2],
                   "compass": parts[3],
                   "clino": parts[4],
                   "left": format_dimension(parts[5]),
                   "up": format_dimension(parts[6]),
                   "down": format_dimension(parts[7]),
                   "right": format_dimension(parts[8]),
                   "backcompass": f"{float(parts[9]):.2f}",
                   "backclino": f"{float(part10):.2f}",
                   "comment":comment_str,
                   "flag": flag,
                   }
        
        
        return measurement
    
    elif len(parts) > 8:  
        
        
        part8 = parts[8].strip('\n')

        if "#" in line:
            flag = line.split("#")[1]
            if "\n" in flag:
                flag = "None"
            comment = line.split("#")[-1] 
            
        else:
  

            flag = "None"
            comment = ""

  
        comment_str = ""
        for elem in comment:
            comment_str+= elem.strip("\n").replace('"', "'")
        

        measurement = {"from": validate_stn_name(parts[0]), 
                   "to": validate_stn_name(parts[1]),
                   "length": parts[2],
                   "compass": parts[3],
                   "clino": parts[4],
                   "left": format_dimension(parts[5]),
                   "up": format_dimension(parts[6]),
                   "down": format_dimension(parts[7]),
                   "right": format_dimension(part8),
                   "comment":comment_str,
                   "flag": flag,
                   }
        
        return measurement
    else :
        print(parts)
        return None
    
def parse_survey_team( line: str )-> dict:

    surveyors = ["["+ surveyor.strip(" ").strip("\n") +"]" for surveyor in line.split(",")]
    return surveyors

def parse_survey_name( line: str ) -> str:
    parse_indices = _LINE_TYPES["survey_name"]
    parts = [str(line[i:j]).strip(" ") for i,j in zip(parse_indices, parse_indices[1:]+[None])]
    
    survey_name = parts[1].strip("\n")
    return survey_name

def parse_survey_date_comment( line: str ) -> str:
    if "COMMENT:" not in line:
        date = line
        comment = ""
    else:
        date, comment = line.split("COMMENT:")

    parts = [elem.strip(" ") for elem in date.split(" ") if elem != ""]
    
    date = {"year": parts[-1].strip("\t").strip("\n"),
            "month": f"{int(parts[-3]):02d}",
            "day": f"{int(parts[-2]):02d}"}

    return date, comment.strip("\n")

def parse_corrections( line : str) -> dict:
    header = parse_data_header(line)

    parts = header["corrections"]
    if len(parts) == 1:
        parts = parts[0].split("\t")

        length_corr = ft2m(float(parts[0].strip("\t")))    
        corrections = {"length corr": length_corr,
                        "compass corr": parts[1].strip("\t"),
                        "clino corr": parts[2].strip("\t")}
    else:
        corrections = None
    return corrections

def ft2m( a ):
    return f"{0.3048 * float(a):.2f}"

def deg2grad( a):
    return f"{float(a) / 360 * 400:.2f}" 

def format_measurement( measurement: dict , data_format: dict ) -> str:

    order = data_format["header_order"] # list of indices

    if data_format["units length"] == "metres":
        measurement["length"] = ft2m(measurement["length"])

    if "backclino" not in measurement.keys() and "backcompass" not in measurement.keys():
        measurement["backclino"] = f"{-float(measurement['clino']):.2f}"
        measurement["backcompass"] = f"{(float(measurement['compass']) - 180) % 360:.2f}"
    else:
        if float(measurement["clino"]) == -999.:
            measurement["clino"] = f"{-float(measurement['backclino']):.2f}"

        if  float(measurement["backclino"]) == -999.:
            measurement["backclino"] = f"{-float(measurement['clino']):.2f}"

        if float(measurement["compass"]) == -999.:
            measurement["compass"] = f"{(float(measurement['backcompass']) - 180) % 360:.2f}"

        if  float(measurement["backcompass"]) == -999.:
            measurement["backcompass"] = f"{(float(measurement['compass']) - 180) % 360:.2f}"

    # convert to grads
    if data_format["units compass"] == "grads":
        measurement["compass"] = deg2grad(measurement["compass"])
        measurement["backcompass"] = deg2grad(measurement["backcompass"])
    
    if data_format["units clino"] == "grads":
        measurement["clino"] = deg2grad(measurement["clino"])
        measurement["backclino"] = deg2grad(measurement["backclino"])

    line = ""
    
    if measurement["flag"] != "None" and _FLAGS[measurement['flag']] != "None":
        line += f"flags {_FLAGS[measurement['flag']]}\n"
    
    if measurement["from"] == measurement["to"]:
        #print("equal stations")
        line+="#"
    # elif "X" in measurement["flag"]:
    #     line+="#"

    for elem in order[:-4]:
        line+= measurement[elem]+"\t"
    line+= "\n"
    if measurement["flag"] != "None"  and _FLAGS[measurement['flag']] != "None":
        line += f"flags not {_FLAGS[measurement['flag']]}\n"
    
    return line

def format_station_dimensions(measurement: dict, data_format: dict) -> str:
    # convert to m
    if data_format["units dimensions"] == "metres":
        for dim in ["length", "left", "right", "up", "down"]:
            measurement[dim] = ft2m(measurement[dim])

    line = f"{measurement['to']} {measurement['left']} {measurement['up']} {measurement['down']} {measurement['right']}"
    line +="\n"
    return line 

def format_comment(measurement: dict)-> str:
 
    comment = measurement["comment"]
    stn_name = measurement["from"]
    flag = measurement["flag"]

    if len(comment) > 3:
              
        if "X" in flag or "P" in flag:
            comment_str = f'#station {stn_name} "{comment}"'
        else:
            comment_str = f'station {stn_name} "{comment}"'
        return comment_str
    else:
        return "None"

def list_all_surveys( data: list ) -> list:
    surveys = []
    survey_titles = []
    survey_dates = []
    survey_teams = []
    declinations = []
    data_formats = []
    corrections = []
    
    for c, line in enumerate(data):
        
        if "SURVEY NAME" in line:
            survey_name = parse_survey_name(line)
            surveys.append(survey_name)
        elif "SURVEY DATE" in line:
            survey_date, comment = parse_survey_date_comment(line)
            survey_dates.append(survey_date)
            survey_titles.append(comment)
        elif "SURVEY TEAM" in line:
           survey_team = parse_survey_team(data[c+1])
           survey_teams.append(survey_team)
        elif "DECLINATION" in line:
           declination = parse_data_header(line)["declination"]
           header = parse_data_header(line)
           data_format = parse_format(header["format"])
           correction = parse_corrections(line)

           declinations.append(declination.strip("\n"))
           data_formats.append(data_format) 
           corrections.append(correction)
        
    return surveys, survey_titles, survey_dates, survey_teams, declinations, data_formats, corrections

def find_series_start_end(data: list) -> list:
    starts, ends = [],[]
    for c, line in enumerate(data):
        if "SURVEY NAME" in line:
            starts.append(c+3)
            ends.append(c-1)
    return starts, ends

def list_all_measurement_series( data: list, data_formats: list) -> list:
    measurement_series = []
    dimension_series = []
    comments_series = []

    starts, ends = find_series_start_end(data)

    for start, end, data_format in zip(starts, ends[1:]+[-1], data_formats):
        series_data = data[start:end]
        formatted_comments = []
        formatted_measurements = []
        formatted_dimensions = []

        for line in series_data:
            try: 
                length = float(line.split()[3]) # try to parse third element.
                measurement = parse_measurement(line)
            except:
                measurement = None
            
            if measurement is not None:
                
                formatted_measurement = format_measurement(measurement, data_format)
                formatted_measurements.append(formatted_measurement)
                formatted_comment = format_comment(measurement)
                formatted_dimension = format_station_dimensions(measurement, data_format)
                formatted_dimensions.append(formatted_dimension)
                if formatted_comment != "None":
                    formatted_comments.append(formatted_comment)




        measurement_series.append(formatted_measurements)
        comments_series.append(formatted_comments)    
        dimension_series.append(formatted_dimensions)
    return measurement_series, dimension_series, comments_series

def format_surveyors_str( surveyors: list)-> str:
    
    srv_list = '## SURVEYORS \n' 
    
    for surveyor in surveyors:
        srv_list += f'#team "{surveyor}"\n'
   
    return srv_list

def format_date_str( date: dict) -> str:
    date_str = f'date  {date["year"]}.{date["month"]}.{date["day"]}'

    return date_str

def format_title_str( survey_title ) -> str:
    survey_title = survey_title.replace('"', "'")
    survey_title_str = f'-title "{survey_title}"'
    return survey_title_str

def format_data_header( data_format: dict, declination: str, correction: dict ) -> str:
    
    if correction is not None:

        data_header_str = f"""declination {declination} degrees

units length {data_format["units length"]}
units compass {data_format["units compass"]}
units clino {data_format["units clino"]}
calibrate length {correction["length corr"]}
calibrate compass {correction["compass corr"]}
calibrate clino {correction["clino corr"]}
{data_format["orig_data_header"]}
"""
        
    elif correction is None:
        data_header_str = f"""declination {declination} degrees

units length {data_format["units length"]}
units compass {data_format["units compass"]}
units clino {data_format["units clino"]}
{data_format["orig_data_header"]}
"""

    return data_header_str


def inject_lrud(shot_series, station_dim_series, data_format):
    
    splay_shot_series = []

    centreline_units = Units("empty")
    centreline_units.length=data_format["units length"]
    if data_format["units clino"] == "grads":
        centreline_units.clino = "grads"
    centreline_units.compass=data_format["units compass"]

    order = data_format["header_order"]
    comp_idx = order.index("compass")
    clino_idx = order.index("clino")
    length_idx = order.index("length")

    # set up a counter to keep track of where to insert the splay lines.
    lrud_counter = 0
    station_counter = 0
    for c, lrudLine in enumerate(station_dim_series):

        from_station, left, up, down, right = lrudLine.split(" ")

        th_lrudLine = LineLRUD(from_station=from_station, 
                               left= float(left), 
                               right= float(right), 
                               up= float(up), 
                               down= float(down))
        
        # direction
        normal_vec = np.zeros(3)

        for k, dataLine in enumerate(shot_series):
            from_station, to_station = dataLine.split()[:2]
            compass = dataLine.split()[comp_idx]
            clino = dataLine.split()[clino_idx]
            length = dataLine.split()[length_idx]

            
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

                elif c== len(station_dim_series)-1:
                    if th_dataLine.to_station == lrud_station:
                        try:
                            compass = float(th_dataLine.compass)
                            normal_vec = spherical2cartesian(compass,float(th_dataLine.clino), centreline_units)
                        except ValueError:
                            pass
                        
                        station_counter = k

                else:

                    if th_dataLine.to_station == lrud_station and k != len(shot_series)-1:

                        dataline1= shot_series[k]
                        from_station, to_station = dataline1.split()[:2]
                        compass = dataline1.split()[comp_idx]
                        clino = dataline1.split()[clino_idx]
                        length = dataline1.split()[length_idx]


                        th_dataLine1 = NormalDataLine(from_station=from_station,
                                         to_station=to_station,
                                         compass=compass, 
                                         clino=clino, 
                                         tape=length)
            


                        # now we know we have found good station. 
                        if shot_series[k+1].split()[0] == lrud_station:
                            dataline2= shot_series[k+1]
                            from_station, to_station = dataline2.split()[:2]
                            compass = dataline2.split()[comp_idx]
                            clino = dataline2.split()[clino_idx]
                            length = dataline2.split()[length_idx]
                            
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
                    
                    str_splayline = " ".join([newsplayline.from_station, newsplayline.to_station, newsplayline.tape, newsplayline.compass, newsplayline.clino, "\n"])
                    splay_shot_series.append(str_splayline)
                    #centreline.add_dataline(newsplayline, lrud_counter+station_counter+j)
                    j+=1
        except AssertionError:
            pass #print("splay calculation failed.. vertical shaft")

        lrud_counter+=j

    return splay_shot_series

def format_centreline_str(shot_series,
                          station_dim_series, 
                          survey, 
                          survey_title, 
                          survey_date, 
                          survey_team, 
                          data_format, 
                          declination, 
                          correction, 
                          comments, 
                          lrud):

    if len(shot_series)>= 1:
        title_str = format_title_str(survey_title)
        surveyors_str = format_surveyors_str(survey_team)
        date_str = format_date_str(survey_date)
        data_header_str = format_data_header(data_format, declination, correction)
        data_dimension_str = "units dimensions " + data_format["units dimensions"] + "\n" + data_format["station_dims_header"]
        
        full_splay_shot_series = ""

        if lrud == True:
            splay_data_header = "data normal from to length compass clino"
            splay_shot_series = inject_lrud(shot_series, station_dim_series, data_format)
            
            for line in splay_shot_series:
                full_splay_shot_series+=line
        else:
           splay_data_header = ""

        full_shot_series = ""

        for line in shot_series:
            full_shot_series+=line

        full_stn_dim_series = ""
        for line in station_dim_series:
            full_stn_dim_series+=line

        full_comments = ""
        for line in comments:
            if "None" not in line:
                full_comments+=line +"\n"
        
        session_str = f"""
centreline {title_str}
{date_str}
{surveyors_str}
{data_header_str}
{full_shot_series}

{splay_data_header}
{full_splay_shot_series}

{data_dimension_str}
{full_stn_dim_series}
{full_comments}
endcentreline"""

    # only if returning empty strings
    else:
        session_str = None

    return session_str

def format_all_centrelines(data, lrud= True):

    surveys, survey_titles, survey_dates, survey_teams, declinations, data_formats, corrections = list_all_surveys(data)
    series, station_dims, comments = list_all_measurement_series(data, data_formats)
    centrelines = ""


    for i in range(len(series)):
        centreline_str = format_centreline_str(series[i], 
                                station_dims[i],
                                surveys[i],
                                survey_titles[i], 
                                survey_dates[i], 
                                " ", 
                                data_formats[i], 
                                declinations[i], 
                                corrections[i],
                                comments[i],
                                lrud=lrud)
        if centreline_str is not None:
            centrelines+= centreline_str 
            centrelines+="\n"
    
    print(f"there are {len(centrelines)} centrelines and {len(series)} series in this file.")
    return centrelines


def parse_surface_fixes(datafile : str) -> list:
    
    with open(datafile, "r") as f:
        data = f.readlines()
        f.close()

    fixes = []
    
    for line in data:
        fix = {}
        if line[0] == " ":
            stn_name = line.split("[")[0]
            
            try:
                unit, x, y, z = line.split("[")[1][:-3].split(",")

                
            except IndexError as e:
                print(e)
                unit, x, y, z = "m", 0., 0., 0.
                pass

            fix["name"] = stn_name.strip("\n").strip(",")
            fix["unit"] = unit
            fix["x"] = x
            fix["y"] = y
            fix["z"] = z
            fixes.append(fix)
    return fixes

def format_fix( fix: dict) -> str:
    # always convert the fix to metric. 
    if fix["unit"] == "f":
        x = feet_to_metres(float(fix['x']))
        y = feet_to_metres(float(fix['y']))
        z = feet_to_metres(float(fix['z']))

        formatted_fix = f"fix {fix['name']} {x:.2f} {y:.2f} {z:.2f}\n"

    elif fix["unit"] == "m":
        x = float(fix['x'])
        y = float(fix['y'])
        z = float(fix['z'])

        formatted_fix = f"fix {fix['name']} {x:.2f} {y:.2f} {z:.2f}\n"
    else:
        print("could not parse the fix units.")
        formatted_fix = f"#fix {fix['name']} 0 0 0 # unparsed because of wrong units?\n"

    return formatted_fix

def format_all_fixes( fixes: list) -> str:
    if len(fixes) > 0:
        all_fixes_str = f"centreline\n"

        for fix in fixes:
            all_fixes_str += format_fix(fix)
        all_fixes_str+= "endcentreline\n"
    else:
        all_fixes_str = ""
    return all_fixes_str

def find_all_inputs(index_file_path: str) -> list:
    with open(index_file_path, "r") as f:
        data = f.readlines()
        
        f.close()
    thedirname = dirname(index_file_path)
    
    input_commands = []
    
    for line in data:
        if "#" in line:
            theInput = line.split(";")[0].split(",")[0][1:]
            input_commands.append(normpath(join(thedirname, theInput)))

    return input_commands

def format_all_inputs(input_commands: str):
    formatted_input_commands = []
    for input_command in input_commands: 
        formatted_input_commands.append('input "{path}"'.format(path="./"+split(input_command)[1][:-4]+"_convert.th"))
    return "\n".join(formatted_input_commands)

def format_standalone_therion_file(basename, formatted_subsurveys, formatted_fixes):
    therion_str = _TH_FILE_TEMPLATE.format(basename= basename, 
                               subsurveys= formatted_subsurveys, 
                               fixes = formatted_fixes)
    return therion_str

def format_therion_file(formatted_subsurveys):
    therion_str = _PART_TH_FILE_TEMPLATE.format( subsurveys= formatted_subsurveys)
    return therion_str

def format_therion_index_file(basename: str, formatted_input_commands: list, formatted_fixes)-> str:
    therion_str = _INDEX_TH_FILE_TEMPLATE.format(basename=basename, inputs=  formatted_input_commands, fixes = formatted_fixes)
    return therion_str

if __name__ == "__main__":
    # Read the script arguments and load the Compass archive file. 

    parser = argparse.ArgumentParser(description="Converts a Compass file to Therion format", epilog='thank you for using the compass2therion script. Please double check your output therion file for any bugs and report them to thehelpdesk@realadress.com')

    parser.add_argument(
        "survey_directory",
        help='The compass archive directory containing *.DAT files to work from."',
    )

    parser.add_argument(
        "--index-file",
        help='The compass index file to work from', default= "None")

    parser.add_argument(
        "--use-mak",
        help='Whether to use the MAK file to fix entrance coordinates."', default = False,
    )

    parser.add_argument(
        "-survey",
        help='The basename of the survey for the therion file (may not include special characters)"',
        )
    
    parser.add_argument("-o", "--output",
        help='The directory in which to store the output)"', default = None
        )
    
    parser.add_argument("-crsin", "--input-crs",
        help='An epsg code of the form: "epsg:12345"', default = "epsg:4326"
        )
    
    parser.add_argument("-crsout", "--output-crs",
        help='An epsg code of the form: "epsg:12345"', default = None
        )
    
    parser.add_argument("-lrud", "--inject_LRUD",
        help='Whether to expand station dimension data into splays', default = "True"
        )


    args = parser.parse_args()

    ENTRY_DIRECTORY = abspath(args.survey_directory)

    if args.index_file != "None":
        # the index file sits next to the survey file, or inside the survey directory
        INDEX_DIRECTORY = dirname(ENTRY_DIRECTORY) if isfile(ENTRY_DIRECTORY) else ENTRY_DIRECTORY
        INDEX_FILE = join(INDEX_DIRECTORY, args.index_file)
    else:
        INDEX_FILE = "None"

    BASENAME = args.survey
    USEMAK = args.use_mak
    OUTPUT_DIRECTORY = args.output
    CRSIN = args.input_crs
    CRSOUT = args.output_crs

    if args.inject_LRUD == "True" or args.inject_LRUD == "true":
        LRUD = True
    else:
        LRUD = False

    print("WE PARSED lrud", LRUD)
    ## SET UP THE EXPORT DIRECTORIES WITH OUTPUTS AND ORIGINAL DATA SUBDIRECTORIESs
    WRITE_PATH =  abspath(OUTPUT_DIRECTORY)
    
    OUTPUTS_FILEPATH = join(WRITE_PATH,  "outputs")
    makedirs(OUTPUTS_FILEPATH, exist_ok=True)

    ORIGS_FILEPATH = join(WRITE_PATH,  "original_data")
    makedirs(ORIGS_FILEPATH, exist_ok=True)
    
    if isfile(ENTRY_DIRECTORY):
        copy(ENTRY_DIRECTORY, ORIGS_FILEPATH)
    else:
        for entry in listdir(ENTRY_DIRECTORY):
            if isfile(join(ENTRY_DIRECTORY, entry)):
                copy(join(ENTRY_DIRECTORY, entry), ORIGS_FILEPATH)


    ## READING IN .
    if INDEX_FILE == "None" and isfile(ENTRY_DIRECTORY):
        DATA = read_file(ENTRY_DIRECTORY, encoding= "utf-8")
        THERION_FILE_STRING = format_standalone_therion_file(BASENAME, format_all_centrelines(DATA, LRUD),"")

        if CRSOUT is not None:
            CONFIG_FILE_STRING = _TH_CONFIG_FILE_TEMPLATE_WITH_CRS.format(basename=BASENAME, crsout=CRSOUT)
        else:
            CONFIG_FILE_STRING = _TH_CONFIG_FILE_TEMPLATE.format(basename=BASENAME)


        OUTPUT_THERION_FILEPATH = join(WRITE_PATH,  f"{BASENAME}_convert.th")
        OUTPUT_CONFIG_FILEPATH = join(WRITE_PATH,  f"{BASENAME}.thconfig")
        
        ## Writing to file
        ENTRY_FILENAME = split(ENTRY_DIRECTORY)[1]

        with open(OUTPUT_THERION_FILEPATH, "w+", encoding="utf-8") as f:
            f.write(THERION_FILE_STRING)
            f.close()
        
        ## Writing to file
        with open(OUTPUT_CONFIG_FILEPATH, "w") as f:
            f.write(CONFIG_FILE_STRING)
            f.close()

        

    elif INDEX_FILE != "None" and isfile(ENTRY_DIRECTORY):
        DATA = read_file(ENTRY_DIRECTORY, encoding= "utf-8")
        FIXES = parse_surface_fixes(INDEX_FILE)
        THERION_FILE_STRING = format_standalone_therion_file(BASENAME, format_all_centrelines(DATA, LRUD), format_all_fixes(FIXES))
        if CRSOUT is not None:
            CONFIG_FILE_STRING = _TH_CONFIG_FILE_TEMPLATE_WITH_CRS.format(basename=BASENAME, crsout=CRSOUT)
        else:
            CONFIG_FILE_STRING = _TH_CONFIG_FILE_TEMPLATE.format(basename=BASENAME)
        
        OUTPUT_THERION_FILEPATH = join(WRITE_PATH,  f"{BASENAME}_convert.th")
        OUTPUT_CONFIG_FILEPATH = join(WRITE_PATH,  f"{BASENAME}.thconfig")
        ## Writing to file

        ## Writing to file
        with open(OUTPUT_CONFIG_FILEPATH, "w+", encoding="utf-8") as f:
            f.write(CONFIG_FILE_STRING)
            f.close()

        ENTRY_FILENAME = split(ENTRY_DIRECTORY)[1]

        with open(OUTPUT_THERION_FILEPATH, "w+", encoding="utf-8") as f:
            f.write(THERION_FILE_STRING)
            f.close()

    else:
        # entry files to be found from the .MAK file. 
        ENTRY_FILES = find_all_inputs(INDEX_FILE)

        for ENTRY_FILE in ENTRY_FILES:
            PARTNAME = split(ENTRY_FILE)[1][:-4]
            print("now reading in file: ", ENTRY_FILE )
            DATA = read_file(ENTRY_FILE, encoding= "utf-8")
            THERION_FILE_STRING = format_therion_file(format_all_centrelines(DATA, LRUD))

            OUTPUT_THERION_FILEPATH = join(WRITE_PATH,  f"{PARTNAME}_convert.th")
            ## Writing to file
            ENTRY_FILENAME = split(ENTRY_FILE)[1]

            with open(OUTPUT_THERION_FILEPATH, "w+", encoding="utf-8") as f:
                f.write(THERION_FILE_STRING)
                f.close()

        if INDEX_FILE != None:
            FIXES = parse_surface_fixes(INDEX_FILE)

            INDEX_FILE_STRING = format_therion_index_file(basename=BASENAME, formatted_input_commands=format_all_inputs(ENTRY_FILES), formatted_fixes= format_all_fixes(FIXES))
            INDEX_FILE_PATH =  join(WRITE_PATH,   f"{BASENAME}_convert.th")

            ## Writing to file the index therion file
            with open(INDEX_FILE_PATH, "w") as f:
                f.write(INDEX_FILE_STRING)
                f.close()
    
            if CRSOUT is not None:
                CONFIG_FILE_STRING = _TH_CONFIG_FILE_TEMPLATE_WITH_CRS.format(basename=BASENAME, crsout=CRSOUT)
            else:
                CONFIG_FILE_STRING = _TH_CONFIG_FILE_TEMPLATE.format(basename=BASENAME)

            OUTPUT_CONFIG_FILEPATH = join(WRITE_PATH,  f"{BASENAME}.thconfig")
            
        
            ## Writing to file the config file
            with open(OUTPUT_CONFIG_FILEPATH, "w") as f:
                f.write(CONFIG_FILE_STRING)
                f.close()

    ## Compiling the therion files immediately. 

    #subprocess.check_output(f"cd {join(WRITE_PATH, BASENAME)} \n therion {BASENAME}.thconfig", shell = True)

