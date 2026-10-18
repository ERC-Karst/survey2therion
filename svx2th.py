"""
Created on Fri Jul 12 13:02:02 2024

@author: Tanguy Racine, Celia Trunz

This provides a parser for converting "survex" file structures to therion
"""


import re
from itertools import accumulate
import argparse
import pandas as pd
from os import walk, makedirs, listdir
from os.path import abspath, isfile, isdir, dirname, join, exists, split, normpath, relpath
from helpers import therion_classes as th
from helpers.utils import *
encodings = ['utf-8', 'mac_roman', 'iso-8859-1', 'iso-8859-3', 'iso-8859-15', 'cp1252', 'cp437', 'cp850', 'ansi']

def open_file_with_encodings(file_path, encodings):
    for encoding in encodings:
        try:
            with open(file_path, encoding=encoding) as file:
                return file.read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    raise ValueError(f"Unable to open file {file_path} with provided encodings.")



def traverse_survey_structure(directory: str, rootfile: str, savetofile=True) -> dict:

    #create dictionnary containing all the full paths and address of the svx data folders
    path_to_data_file = []
    alternate_path = {}
    address_dict = process_svx_file(directory, rootfile, path_to_data_file, alternate_path, include_commented=True)
    if savetofile == True:
        df = pd.DataFrame.from_dict(address_dict, orient='index')
        df.to_csv('dict_paths.csv')

    # # Save the alternate_path dictionary to a file
    #     with open(join("./",'all_addresses.csv'), 'w') as file:
    #         for key, value in address_dict.items():
    #             file.write(f"{key};{value}\n")
    #             file.close()

    return address_dict



# def copy_tree_structure(src, dst):
#     for root, dirs, files in walk(src):
#         # Construct the destination path
#         dest_dir = root.replace(src, dst, 1)
#         if not exists(dest_dir):
#             makedirs(dest_dir)
#         for dir in dirs:
#             dest_subdir = join(dest_dir, dir)
#             if not exists(dest_subdir):
#                 makedirs(dest_subdir)



def reformat_includes(file_path):
    lines = [line.strip() for line in open(file_path, 'r', encoding='utf-8')]
    lst = []
    for line in lines:
        if line.endswith(';'):
            line = line.rstrip(line[-1])
        if ".svx" in line:
            line = line.split(".svx", 1)[0]
        if line.lower().startswith('*include'):
            print(line.split()[1].lower().strip(';'))
            lst.append(line.split()[1].lower().strip(';'))
            #in case it was commented in the svx file
        # elif line.lower().startswith(';') and '*include' in line:
            # lst.append(f'# {line.split(' ')[1]}')
    return [f'input {s}.th' for s in lst]

def reformat_begin(file_path):
    lines = [line.strip() for line in open(file_path, 'r', encoding='utf-8')]
    for line in lines:
        if line.endswith(';'):
            line = line.rstrip(line[-1])
        if line.lower().startswith('*begin') and len(line.split())>1:
            survey_name = line.split()[1]
            return f'survey {survey_name.lower()} -title "{survey_name}"'
        else:
            return None

def reformat_equates(file_path,list_all_address):
    lines = [line.strip().strip('   ') for line in open(file_path, 'r', encoding='utf-8')]
    list_strings = ['']
    for line in lines:
        if line.endswith(';'):
            line = line.rstrip(line[-1])
        if line.startswith('    '):
            print(line)
        if line.lower().startswith('*equate'):
            # print(line)
            parts = line.split()
            # lst.append([line.split(' ')[1],line.split(' ')[2]])
            equate_from = reformat_address(parts[1],list_all_address)
            equate_to = reformat_address(parts[2],list_all_address)
            list_strings.append(f'equate {equate_from.lower()} {equate_to.lower()}')

        # elif line.lower().startswith(';') and '*equate' in line:
        #     parts = line.split(' ')
        #     # lst.append([line.split(' ')[1],line.split(' ')[2]])
        #     equate_from = reformat_address(parts[1],list_all_address)
        #     equate_to = reformat_address(parts[2],list_all_address)
        #     list_strings.append(f'# equate {equate_from} {equate_to}')
    return list_strings


def reformat_fixes(file_path,list_all_address):
    lines = [line.strip() for line in open(file_path, 'r', encoding='utf-8')]
    lst = ['']
    for line in lines:
        if line.endswith(';'):
            line = line.rstrip(line[-1])
        if line.lower().startswith('*fix'):
            parts =line.split()
            station_name = reformat_address(parts[1],list_all_address)
            lst.append(f'fix {station_name.lower()} {" ".join(parts[-3:])}')

        # elif line.lower().startswith(';') and '*fix' in line:
        #     parts =line.split(' ')
        #     station_name = reformat_address(parts[1],list_all_address)
        #     lst.append(f'# fix {station_name} {' '.join(parts[-3:])}')


    return lst

def reformat_entrances(file_path,list_all_address):
    lines = [line.strip() for line in open(file_path, 'r', encoding='utf-8')]
    lst = ['']
    for line in lines:
        if line.endswith(';'):
            line = line.rstrip(line[-1])
        if line.lower().startswith('*entrance'):
            parts =line.split()
            station_name = reformat_address(parts[1],list_all_address)
            lst.append(f'station {station_name.lower()} "" entrance')

        # elif line.lower().startswith(';') and '*entrance' in line:
        #     parts =line.split(' ')
        #     station_name = reformat_address(parts[1],list_all_address)
        #     lst.append(f'# station {station_name} "" -entrance')

    return lst

def reformat_comments(file_path):
    lines = [line.strip() for line in open(file_path, 'r', encoding='utf-8')]
    lst = ['']
    for line in lines:
        if line.endswith(';'):
            line = line.rstrip(line[-1])
        if line.lower().startswith(('*declination auto','*cs','*set', ';')):
            lst.append(line) 
            # if any(x in line for x in ['*entrance','*include','*equate','*fix']):
            #     pass
            # else:
            #     lst.append(line) 
    return [f'# {s}' for s in lst]

# def reformat_crs(file_path):
#     lines = [line.strip() for line in open(file_path, 'r', encoding='utf-8')]
#     lst = ['']
#     for line in lines:
#         if line.endswith(';'):
#             line = line.rstrip(line[-1])
#         if line.lower().startswith('*cs'):
#             #make sure to take only the crs of the file and cont *cs out
#             if 'out' not in line.lower():
#                 crs =line.split()[1]
#     return [f'#']
        

def reformat_address(address,list_all_address):
    #address is a string ('aaa.bbb.cc.d')
    address_split = address.strip().split('.') 

    if len(address_split) == 1:
        #for cases where the point is in the same folder as the svx file
        return address    
    else:
        index = None
        for i in range(1,len(address_split),1):
            new_string = '.'.join(address_split[:-i])
            # print(new_string)
            if any(new_string.lower() in s.lower() for s in list_all_address):
                index = i
                # print(index)
                break
        if index == None:
            print('list_all_address',list_all_address)
            print(f'missing address for survey point {address}')
        else:
            # Create the 'beginning' and 'end' strings
            beginning = '.'.join(address_split[-index:])
            end = '.'.join(address_split[:-index][::-1])
        return '@'.join([beginning.lower(),end.lower()])
               
#### BEGIN NINA AWESOMENESS
class NameNotFoundError(Exception):
    pass

def extract_name_from_svx(file_path) -> list:
    # extract name should return a list of names if there are more than one surveys
    # at the same level in a given file. 
    names = None
    try:
        with open(file_path, 'r', encoding='utf-8') as file: #, errors='ignore') as file:
            names = []
            
            for line in file:
                args = command_args(line, "*begin")
                if args:
                    names.append(args[0])
           
    except UnicodeDecodeError as e:
        print(f"Error while reading file {file_path}: {e}")
    #raise NameNotFoundError(f"No line starting with '*begin' found in file {file_path}.")
    return names

def extract_includes_from_svx(file_path, include_commented=False):
    """This scans a survex file and appends included filepaths to a list.

    Parameters
    ----------
    file_path : str
        path to survex file
    include_commented : bool, optional
        whether to include commented out files, by default False

    Returns
    -------
    includes: list[str]
        a list of filepaths to checkout because they are called by this main survex index file.
    """

    includes = []
    with open(file_path, 'r', encoding='utf-8') as file: #, errors='ignore') as file:
        for line in file:
            line = line.lstrip()  # Remove leading whitespace, including tabs
            if line.lower().startswith('*include'):
                include_path = line.split()[1]
                includes.append(include_path.replace('\\', '/'))
            elif include_commented and line.lower().startswith(';*include'):
                include_path = line.split()[1]
                includes.append(include_path.replace('\\', '/'))
    return includes


def process_svx_file(directory, rel_path_to_file, path_to_data_file=None, alternate_path=None, include_commented=False):
    if path_to_data_file is None:
        path_to_data_file = []
    if alternate_path is None:
        alternate_path = {}

    # here split the relpath to the file from directory.

    subdirectory, file = split(rel_path_to_file)
    file_path = join(directory, subdirectory, file).replace('\\', '/')

    names = extract_name_from_svx(file_path)

    if len(names) > 0: 
        alternate_path[normpath(file_path)] = []
        for name in names:
            
            path_to_data_file.append(name)
    #else:
    #    path_to_data_file.append("None")

            # call the extract includes from svx function for this specific filepath.

            includes = extract_includes_from_svx(file_path, include_commented=include_commented)

            # if no includes was found, this was a bottom of hierarchy survex file. 
            if not includes:
                print("there were no includes in this file.")
                alternate_path[normpath(file_path)].append('.'.join(path_to_data_file))

                del path_to_data_file[-1]

            else:
                alternate_path[normpath(file_path)] = '.'.join(path_to_data_file)
                for include in includes:
                    include_path = join(directory, subdirectory, include).replace('\\', '/')
                    if not include_path.lower().endswith('.svx'):
                        include_path_with_ext = include_path + '.svx'
                        if isfile(include_path_with_ext):
                            include_path = include_path_with_ext
                            print(include_path)
                        elif isdir(include_path):
                            process_svx_files(include_path, path_to_data_file=path_to_data_file.copy(), alternate_path=alternate_path)
                            continue
                        else:
                            print(f"Neither file nor directory found for {include_path}")
                            continue

                    dir, fil = split(include_path)
                    # recursively go deeper. 
                    process_svx_file(dir, fil, path_to_data_file=path_to_data_file.copy(), alternate_path=alternate_path)
    elif len(names) == 0:
    # call the extract includes from svx function for this specific filepath.

        includes = extract_includes_from_svx(file_path, include_commented=include_commented)

        # if no includes was found, this was a bottom of hierarchy survex file. 
        if not includes:
            print("there were no includes in this file.")
            alternate_path[normpath(file_path)] = '.'.join(path_to_data_file)
            del path_to_data_file[-1]

        else:
            alternate_path[normpath(file_path)] = '.'.join(path_to_data_file)
            for include in includes:
                include_path = join(directory, subdirectory, include).replace('\\', '/')
                if not include_path.lower().endswith('.svx'):
                    include_path_with_ext = include_path + '.svx'
                    if isfile(include_path_with_ext):
                        include_path = include_path_with_ext
                    elif isdir(include_path):
                        process_svx_files(include_path, path_to_data_file=path_to_data_file.copy(), alternate_path=alternate_path)
                        continue
                    else:
                        print(f"Neither file nor directory found for {include_path}")
                        continue

            dir, fil = split(include_path)
            # recursively go deeper. 
            process_svx_file(dir, fil, path_to_data_file=path_to_data_file.copy(), alternate_path=alternate_path)

    return alternate_path

def process_svx_files(directory, path_to_data_file=None, alternate_path=None):
    if path_to_data_file is None:
        path_to_data_file = []
    if alternate_path is None:
        alternate_path = {}
    for file in listdir(directory):
        if file.lower().endswith('.svx'):
            process_svx_file(directory, file, path_to_data_file=path_to_data_file, alternate_path=alternate_path)
    return alternate_path

#### END NINA AWESOMENESS



def read_raw_data(fp) -> list:
    with open (fp, "r",encoding='utf-8') as file:
        contents = file.readlines()

    file.close()
    return contents

def command_args(line, command):
    """Return the arguments of the given survex command if the line holds this command, or None otherwise"""
    words = line.split(";")[0].split()
    if words and words[0].lower() == command:
        return words[1:]
    return None

def find_comments(data) -> list:
    comments = [elem for elem in data if elem.startswith(";")]
    return comments
 
def is_data_file(data) -> bool:
    isdatafile = False
    for line in data:
        if command_args(line, "*begin") is not None:
            isdatafile = True
    return isdatafile

def find_entrance(data):
    entrances = []

    for line in data:
        args = command_args(line, "*entrance")
        if args:
            entrances.append(" ".join(args))

    return entrances

def find_fixes(data, maxlevel):
    fixes = []
    for line in data:
        args = command_args(line, "*fix")
        if args is None:
            continue

        fullname = args[0]
        coordinates = [elem for elem in args[1:] if elem.lower() != "reference"]
        # survex fixes a station given without coordinates at the origin
        x, y, z = coordinates[:3] if len(coordinates) >= 3 else ("0", "0", "0")

        # separate between station name and survey name. 
        if maxlevel != 0:

            stn = ".".join(fullname.split(".")[maxlevel:])
            srv = ".".join(fullname.split(".")[:maxlevel])
        else: 
            stn = fullname
            srv = None
    
        fixes.append((stn, srv, x, y, z))
        
    return fixes

def find_inputs(data):
    inputs = []
    for line in data:
        args = command_args(line, "*include")
        if args:
            inputs.append(" ".join(args))
    return inputs

def split_station_address(address, survey_names):
    """Split a survex station address into its station name and the survey it belongs to. The survey is None if the address contains none of the given survey names"""
    # survey names use _ instead of dots, so a survey name can span several parts of the address
    parts = address.split(".")
    # we prefer the survey nearest to the station, and the longest name ending there
    for name_end in range(len(parts) - 1, 0, -1):
        for name_start in range(name_end):
            name = "_".join(parts[name_start:name_end]).lower()
            if name in survey_names:
                return ".".join(parts[name_end:]), name
    return address, None

def find_equates(data, maxlevel, hierarchy):
    equates = []

    possible_survey_names = list(hierarchy[maxlevel].keys())

    for line in data:
        equate = command_args(line, "*equate")

        if equate is not None and len(equate) >= 2:
            stn1, srv1 = split_station_address(equate[0], possible_survey_names)
            stn2, srv2 = split_station_address(equate[1], possible_survey_names)
            equates.append(((stn1, srv1),(stn2, srv2)))
    return equates

def find_all_file_surveys(data):
    starts = []
    ends = []
    survey_names = []
    for c, line in enumerate(data):
        # looking for starts and end lines of survex named surveys. anonymous surveys will be ignored and 
        # put into the same centreline.
        
        begin_args = command_args(line, "*begin")
        if begin_args:
            starts.append(c)
            survey_names.append(begin_args[0].replace(".", "_"))

        elif command_args(line, "*end") is not None:
            ends.append(c)

    return starts, ends, survey_names

def parse_survey_hierarchy(starts, ends, names):
    starts = starts.copy()
    ends = ends.copy()
    hierarchy = {}
    lvl = 0

    if len(starts)== 0:
        print("this file has no beginning and no end.")
        hierarchy[lvl] = {"none": (None, None)}

    elif len(starts) == 1:
        print("only one survey level in this file")
        hierarchy[lvl] = {names[0].replace(".", "_").lower(): (starts[0], ends[0])}
    
    else:
        while len(starts) > 1 and starts[1] < ends[0]:

            print("at least one level deeper.")
            hierarchy[lvl] = {names[0].replace(".", "_").lower(): (starts[0], ends[-1])}
            starts.pop(0)
            ends.pop(-1)
            names.pop(0)
            lvl+=1
        
        hierarchy[lvl] = {}

        for start, end, name in zip(starts, ends, names):
            hierarchy[lvl][name.replace(".", "_").lower()] = (start, end)

    return hierarchy

def make_survey_data_list(data):
    
    starts, ends, names = find_all_file_surveys(data)
    starts_ends = parse_survey_hierarchy(starts, ends, names)

    # find the deepest level. 
    max_level = max(starts_ends.keys())
    survey_data_list = []
    
    for start, end in starts_ends[max_level].values():
        # if both start and end indices exist we can plunge deeper.
        if start is not None and end is not None:
            survey_data = [elem for elem in data[start+1:end]]
        else:
            survey_data = data

        survey_data_list.append(survey_data)

    return survey_data_list

def find_survey_date(survey_data):
     dates = []
     for elem in survey_data:
          if elem.lower().strip("\t").strip(" ").startswith("*date"):
               _match = re.findall(r"(?<=date\s).+",elem.lower())[0].split(';')[0]
               dates.append(".".join(_match[2:].split(".")[::-1]))
               
        #   elif elem.startswith("*DATE"):
        #        _match = re.findall(r"(?<=DATE\s).+",elem)[0]
        #        dates.append(".".join(_match[2:].split(".")[::-1]))
     
     if len(dates) == 0:
          dates.append(None)
     return dates

def find_survey_strategy(data):
    possible_strategies = []
    
    for c, line in enumerate(data):
        if "*data" in line.lower(): 
            strategy_switch = [elem for elem in line.lower()[:-1].strip(" ")[5:].split(" ") if elem]
            possible_strategies.append((c, {strategy_switch[0]: " ".join(strategy_switch[1:])}))
        
    return possible_strategies

def last_unit_before(units_switches, quantities, end, default):
    """Return the unit set by the last *units switch for one of the given quantities before the end line, or the default if there is none"""
    units = [next(iter(switch.values())) for line, switch in units_switches if line < end and any(quantity in switch for quantity in quantities)]
    return units[-1] if units else default

def parse_survey_data(survey_data, strategy_switches, units_switches, calibration_switches, start, end, expand_lrud):

    # a file without *begin gives no start and end, and its survey data is the whole file
    first_line = 0 if start is None else start + 1
    if end is None:
        end = len(survey_data)

    newCentreline = th.Centreline()
    date = find_survey_date(survey_data)[0]
    if date is not None:
        newCentreline.add_Date(date)
    else:
        newCentreline.add_Date(None)
    
    normal_strategy_switches = [elem for elem in strategy_switches if "normal" in elem[1].keys()]
    
    if len(normal_strategy_switches) == 0:
        print("using default strategy, no data header found, no LRUD blocks.")
        theStrategy = th.Strategy("from to tape compass clino", orig_format="survex")
    else:
        # find the nearest normal strategy. 
        switch_lines = [elem[0] for elem in normal_strategy_switches]
        # find the last strategy for which the centreline ends. 
        comes_after_index = sum([end > elem for elem in switch_lines]) - 1
        theStrategy = th.Strategy(input_str= normal_strategy_switches[comes_after_index][1]["normal"], orig_format="survex")

    newCentreline.strategy = theStrategy

    lrud_strategy_switches = [elem for elem in strategy_switches if "passage" in elem[1].keys()]

    if len(lrud_strategy_switches) == 0:
        checkLRUDBlock = False
        LRUD_strategy = " "

    else:
        switch_lines = [elem[0] for elem in lrud_strategy_switches]
        # find the last strategy for which the centreline ends. 
        comes_after_index = sum([end > elem for elem in switch_lines]) - 1
        checkLRUDBlock = True
        LRUD_strategy = "data dimensions "+ lrud_strategy_switches[comes_after_index][1]["passage"]
    
    newCentreline.lrud_reader = LRUD_strategy

    # the survex command calibrate declination is of opposite sign to the one understood by therion.
    declinations = {line: -switch["declination"] for line, switch in calibration_switches if "declination" in switch}
    # the last declination set before the survey data applies from its first shot
    earlier_declinations = [declination for line, declination in declinations.items() if line < first_line]

    # check the units switches
    if len(units_switches) == 0:
        newCentreline.units = th.Units(" ", fmt = "survex default")
    else:
        compass_unit = last_unit_before(units_switches, ["compass", "bearing"], end, "degrees")
        clino_unit = last_unit_before(units_switches, ["clino", "gradient"], end, "degrees")
        tape_unit = last_unit_before(units_switches, ["tape", "length"], end, "meters")
        newCentreline.units = th.Units(" ", length= tape_unit, clino=clino_unit, compass=compass_unit, fmt = "survex")

    lrud_datalines = []
    datalines = []
    commented_stations = []

    flags = None
    
    LRUD_start = -1

    if checkLRUDBlock == True:
        for i, line in enumerate(survey_data):
            data_args = command_args(line, "*data")
            if data_args and data_args[0].lower() == "passage":
                LRUD_start = i

    if earlier_declinations:
        datalines.append(th.LineDeclination(earlier_declinations[-1]))

    for k, line in enumerate(survey_data):
        if first_line + k in declinations:
            datalines.append(th.LineDeclination(declinations[first_line + k]))

        # check whether commented. 

        if flag_args := command_args(line.lower(), "*flags"):
            datalines.append(th.LineFlag(" ".join(flag_args)))
        elif line.startswith(";"):
            datalines.append(th.CommentedLine(line.strip(";").strip("\n")))
        elif not (line.strip(" ").strip("\t").startswith(";") or line.strip(" ").strip("\t").startswith("*")):
            # check the flags.
            
            if k < LRUD_start or LRUD_start == -1:
                if len(line.split(";")) ==2:
                    readings, comment = (line.split(";"))
    	            
                    station_from = readings.split()[0]
                    theComment = th.StationWithComment(station_from.lower(), comment.strip("\n").replace('"',''))
                    commented_stations.append(theComment)
                else: 
                    readings = line
                
                if len(readings) > 1:
                    split = [elem for elem in readings.replace("\t", " ").split(" ") if elem][:5]
                 
                    if len(split) == 5:
                        from_stn, to_stn, tape, compass, clino = [elem.strip("\n") for elem in split[:5]]
                        if to_stn == "..":
                            to_stn = "."
                        dataLine = th.NormalDataLine(from_station=from_stn.lower(), to_station= to_stn.lower(), tape=tape, compass= compass, clino=clino)
                        datalines.append(dataLine)
                    
            else:
                if len(line.split(";")) ==2:
                    readings, comment = (line.split(";"))
                else: 
                    readings = line
                
                if len(readings) > 1:
                    split = readings.split()[:5]

                    if len(split) == 5:

                        from_stn, left, right, up, down = split

                        LRUD_dataLine = th.LineLRUD(from_station=from_stn.lower(), 
                                                    left = parse_float(left), 
                                                    right= parse_float(right), 
                                                    up= parse_float(up), 
                                                    down = parse_float(down))
                        lrud_datalines.append(LRUD_dataLine)
        
    for dataline in datalines:
        newCentreline.add_dataline(dataline)
    
    for lrud_dataline in lrud_datalines:
        newCentreline.add_LRUDdataline(lrud_dataline)

    if expand_lrud == True:
        inject_lrud(newCentreline, lrud_datalines, datalines)

    
    for commented_station in commented_stations:
        newCentreline.add_station_line(commented_station)
        
    newCentreline.add_string_repr()
    return newCentreline

def switches_in_scope(switches, data, start):
    """Return the switches that still apply at the start line of a survey. Survex ends a switch at the *end of the block it is set in"""
    def is_in_scope(switch_line):
        # the block of the switch has ended if more blocks end than begin between the switch and the survey
        steps = [1 if command_args(line, "*begin") is not None else -1 if command_args(line, "*end") is not None else 0 for line in data[switch_line + 1:start]]
        return min(accumulate(steps), default=0) >= 0
    return [switch for switch in switches if is_in_scope(switch[0])]

def parse_top_level(hierarchy, data, max_lvl, strategies, units_switches, calibration_switches, crs, expand_lrud):
    toplevelSurveys = []
    
    for elem in hierarchy[0].items():
        toplevelname, start_end = elem
        
        toplevelSurvey = th.Survey(toplevelname.lower(), isTopLevel=True)

        survey_data_list = make_survey_data_list(data)

        equates = find_equates(data, max_lvl, hierarchy)
        entrances = find_entrance(data)
        inputs = find_inputs(data)
        fixes = find_fixes(data, max_lvl)


        for equate in equates:
            theEquate = th.Equate(equate[0][0].lower(), equate[0][1], equate[1][0].lower(), equate[1][1])
            print("adding this equate: ", theEquate)
            toplevelSurvey.add_equate(theEquate)

        for fix in fixes:
            station = fix[0].lower() if fix[1] is None else f"{fix[0].lower()}@{fix[1]}"
            theFix = th.Fix(station, x=float(fix[2]), y=float(fix[3]), z=float(fix[4]), crs=crs)
            toplevelSurvey.add_entrance_fix(theFix)

        names = [elem for elem in hierarchy[max_lvl].keys()]

        if max_lvl == 0:
            start, end = hierarchy[max_lvl][toplevelSurvey.name]
            scope_start = 0 if start is None else start
            centreline = parse_survey_data(survey_data_list[0], 
                                           switches_in_scope(strategies, data, scope_start), 
                                           switches_in_scope(units_switches, data, scope_start), 
                                           switches_in_scope(calibration_switches, data, scope_start), 
                                           start, end, expand_lrud)
            
            toplevelSurvey.add_centrelines([centreline])

        else:
            for name, survey_data in zip(names, survey_data_list):
                start, end = hierarchy[max_lvl][name]
                centreline = parse_survey_data(survey_data, 
                                               switches_in_scope(strategies, data, start), 
                                               switches_in_scope(units_switches, data, start), 
                                               switches_in_scope(calibration_switches, data, start), 
                                               start, end, expand_lrud)

                ChildSurvey = th.Survey(name.lower())
                ChildSurvey.add_centrelines([centreline])
                ChildSurvey.add_string_repr()
            
                toplevelSurvey.add_child(ChildSurvey)
            
        toplevelSurvey.add_string_repr()

        toplevelSurveys.append(toplevelSurvey)
        
    return toplevelSurveys

def find_aliases(data):
    aliases_switches = []

    for c, line in enumerate(data):
        isAliasSwitch = "alias" in line.lower()
        if isAliasSwitch:
            switch_line = [elem for elem in line.lower().strip("\n").strip(" ").strip("\t").strip("*alias").split(" ") if elem]
            if len(switch_line) == 3:
                aliases_switches.append((c,{switch_line[0]: {"from": switch_line[1], "to": switch_line[2]}}))

    return aliases_switches

def find_calibration_switches(data):
    
    calibration_switches = []

    for c, line in enumerate(data):
        switch_line = command_args(line.lower(), "*calibrate")
        if switch_line is not None and len(switch_line) == 2:
            calibration_switches.append((c,{switch_line[0]: float(switch_line[1])}))
    return calibration_switches

def find_units_switches(data):
    units_switches = []
    for c, line in enumerate(data):
        switch_line = command_args(line.lower(), "*units")
        if switch_line is not None:
            if len(switch_line) == 2:
                units_switches.append((c,{switch_line[0]: switch_line[1]}))
            elif len(switch_line)==3:
                units_switches.append((c,{switch_line[0]: switch_line[2]}))
                units_switches.append((c,{switch_line[1]: switch_line[2]}))

    return units_switches


def convert_single_datafile(input: str, output: str, crs: str = "epsg:3857", expand_lrud: bool= False) -> None:
    """Convert a survex data file to a therion file of the same name in the output directory"""
    input_dir = dirname(input)

    input_file = input[len(input_dir)+1:]
    basename = input_file[:-4]

    convert_datafile(input, join(output, f"{basename}.th"), crs, expand_lrud)

def convert_datafile(input: str, output_filename: str, crs: str, expand_lrud: bool) -> None:
    print("Will there be injected LRUD?", expand_lrud)
    print("parsing a single file.")
    DATA = read_raw_data(input)
    
    # need to double check that the single svx file is indeed a data file.
    #IS_DATA_FILE = is_data_file(DATA)
    CALIBRATION_SWITCHES = find_calibration_switches(DATA)
    UNITS_SWITCHES = find_units_switches(DATA)
    OUT = find_all_file_surveys(DATA)
    STRATEGIES = find_survey_strategy(DATA)
    HIERARCHY = parse_survey_hierarchy(*OUT)
    MAX_LVL = max(HIERARCHY.keys())
    # ENTRANCES = find_entrance(DATA)
    # FIXES = find_fixes(DATA, MAX_LVL)
    # INPUTS = find_inputs(DATA)
    # SURVEY_DATA_LIST = make_survey_data_list(DATA)
    # TOP_LEVEL_NAME = list(HIERARCHY[0].keys())[0]
    TOP_LEVEL_SURVEYS = parse_top_level(HIERARCHY, 
                                        DATA, 
                                        MAX_LVL, 
                                        STRATEGIES, 
                                        UNITS_SWITCHES, 
                                        CALIBRATION_SWITCHES, 
                                        crs, 
                                        expand_lrud)

    TOP_LEVEL_STR = """
"""
    for top_level_survey in TOP_LEVEL_SURVEYS:
        TOP_LEVEL_STR += top_level_survey._string_repr


    with open(output_filename, "w", encoding="utf-8") as f:
        f.writelines(TOP_LEVEL_STR)
        f.close()

def convert_files_in_directory(addresses_dict, input_dir, output_dir, crs, expand_lrud):

    list_all_paths = [elem.strip() for elem in addresses_dict.keys()]
    list_all_addresses = []
    
    for elem in addresses_dict.values():
        if type(elem) == str:
            list_all_addresses.append(elem.strip())
        else:
            for item in elem:
                list_all_addresses.append(item.strip())

    for filepath in list_all_paths: #index_file_paths:

        #load and reformat equates
        ############################
        # output paths are lowercase, to match the lowercase file names in the input commands
        new_filepath = join(output_dir, relpath(filepath, input_dir).lower().removesuffix(".svx") + ".th")
        new_directory = dirname(new_filepath)
        if not exists(abspath(new_directory)):
            print("the output directory does not exist yet.")
            makedirs(new_directory)

        print(f"I will attempt to convert file {filepath} to file {new_filepath}")

        with open(filepath, "r", encoding='utf-8') as f:
            content = f.read()
            f.close()

            if "*include" in content.lower(): 
                equates = reformat_equates(filepath,list_all_addresses)

                #load and reformat includes
                ###########################
                includes = reformat_includes(filepath)

                #load and reformat fixes
                ###########################
                fixs = reformat_fixes(filepath,list_all_addresses)

                #load and reformat entrances
                ############################
                entrances = reformat_entrances(filepath,list_all_addresses)

                #load and reformat comments
                ############################
                comments = reformat_comments(filepath)

                #load and reformat survey
                ############################    
                survey = reformat_begin(filepath)

            #format to .th:

                # Combine all parts into a single list

                if survey == None and (len(fixs)== 1 and len(entrances) == 1):
                    all_lines = comments + [''] + includes + [''] + equates + ['']
                elif survey == None:
                    all_lines = comments + [''] + ["centreline"] + fixs + [''] + entrances + [''] + ["endcentreline"] + includes + ['']  + equates + ['']
                elif len(fixs)== 1 and len(entrances) == 1:
                    all_lines = [survey] + comments + ['']  + includes + [''] + equates + [''] + ['endsurvey']
                else:
                    all_lines = [survey] + comments + [''] + ["centreline"]  + fixs + [''] + entrances + [''] + ["endcentreline"] + includes + [''] + equates + [''] + ['endsurvey']

                # Write to a .th file
                # therion_filepath = os.path.join(new_directory,filepath)
                # print(therion_filepath)
                with open(new_filepath, 'w', encoding='utf-8') as file:
                    for line in all_lines:
                        file.write(line + '\n')


            else: # if this is a single data file, use other converter before writing to file. 
                print("this appears to be a single datafile. Ignoring for now.")
                convert_datafile(filepath, new_filepath, crs, expand_lrud)

##### SCRIPT CALLING. ######

if __name__ == "__main__":
    # Read the script arguments and load the Survex archive file. 

    # add the argument parsing.
    parser = argparse.ArgumentParser(description="Convert a Survex file to therion format")

    parser.add_argument(
        "input",
        help='The path to survey file (*.svx) or files repository to work from.\
              This script will traverse the repository and convert every recognised\
              survey formatted file within.',
    )

    parser.add_argument(
        "output",
        help='the path to the output directory.',
    )

    parser.add_argument(
        "--rootfile",
        default= None,
        required= False,
        help='the name of the root survey file if giving the script a directory to traverse',
    )


    parser.add_argument(
        "--crs",
        default= "epsg:3857",
        required= False,
        help='coordinate reference system if known.',
    )

    parser.add_argument(
        "--expand_lrud",
        default= "false",
        required=False,
        help='if true, will calculate LRUD data as splay shots and inject them in the therion file',
    )


    args = parser.parse_args()

    INPUT = abspath(args.input)
    OUTPUT = abspath(args.output)
    ROOTFILE = args.rootfile
    CRS = args.crs
    EXPAND_LRUD = "true" in args.expand_lrud.lower()

    print("Will there be injected LRUDs?", EXPAND_LRUD)

    if isfile(INPUT):
        convert_single_datafile(input=INPUT, output=OUTPUT, crs=CRS, expand_lrud=EXPAND_LRUD)
    elif isdir(INPUT):
        print("ooh boy. gonna need to traverse this whole directory...")
        if ROOTFILE == None:
            print("Aborting. You seem to have given a directory to traverse without specifying a root file. I need a root survey file to work from.")
        else:   
            ALL_ADDRESSES = traverse_survey_structure(directory=INPUT, rootfile=ROOTFILE)

            convert_files_in_directory(ALL_ADDRESSES, INPUT, OUTPUT, CRS, EXPAND_LRUD)
        # generate list of paths to convert.
        # for each file:
        #        test isdatafile or not,
        #        convert accordingly, 
        #        makedir if needed, 
        #        write to file
    else:
        print("oopsie.")



        # THCONFIG = """source {basename}_convert.th

        # export model -o {basename}_convert.3d
        # """

        # with open(OUTPUT_FILENAME + "config", "w", encoding="utf-8") as f:
        #     f.writelines(THCONFIG.format(basename=BASENAME))
        #     f.close()

    
