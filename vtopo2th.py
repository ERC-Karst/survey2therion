"""
Created on May 21 14:27:01 2024

@author: Tanguy Racine, Celia Trunz

This provides a parser for converting VisualTopo file structures to therion
"""

import argparse
from os.path import abspath, dirname, split, isdir, join

import subprocess

# the behaviour of the class is sort of tested
from helpers.utils import * 
from helpers.therion_classes import * 


### utility functions. 
def joinlist(l : list[str])-> str:
    newstr = ""

    for elem in l:
        newstr += f"{elem} "

    return newstr

def find_entrance_fix(data: list[str], format : str, crs: str) -> Fix:
    """Find the name of the entrance station
    
    Parameters
    ----------
    data : list[str]
        the original raw data
    fmt : str
        the original survey format
    crs : str
        the coordinate reference system for the original survey. 

    Returns
    -------
    Fix
        A Fix object (name, coordinates, command)
    """

    if format == "tro":
        # search the visual topo file for the entrance station
        for c,l in enumerate(data):
            if ('Entree' in l) and (";" not in l):
                entrance_name= re.findall(r"(?<=Entree\s).+",l)[0]

                # the entrance coordinates are always given at the top of the file. 
            elif "Trou" in l and c < 7:
                print(f"bugfixing on line {c}", re.findall(r"(?<=Trou\s).+",l)[0].split(","))
                x, y, z = [float(elem) for elem in re.findall(r"(?<=Trou\s).+",l)[0].split(",")[1:4]]
                    
    else: 
        start, end  = 0,0
        for c,l in enumerate(data):
            # find the start and end indices of cave metadata
            if "<Cavite>" in l:
                start = c
            elif "</Cavite>" in l:
                end = c


        for c, l in enumerate(data):
            if "Coordonnees" in l and c < end:
                split_l = l.split(('"'))
                x, y, z = float(split_l[1]), float(split_l[3]), float(split_l[5])

            if '<Entree>' in l:
                entrance_name = l.strip(" ").strip("\t").strip("<Entree>").split("<")[0]
                print("entrance name: ", entrance_name)
            elif '<Entree ' in l:
                # for newer trox versions. 
                entrance_name = l.split("Station")[1].split('"')[1]
                x = float(l.split("X")[1].split('"')[1])
                y = float(l.split("Y")[1].split('"')[1])
                z = float(l.split("Z")[1].split('"')[1])            
        
    
    admitted_crs = ["epsg:21781", "EPSG:21781", "epsg:27572", "EPSG:27572"]

    if crs in admitted_crs:
        # there may be some weirdly parsed coordinates.
        x*=1000
        y*=1000
    entrance_fix = Fix(name=entrance_name, x=x, y=y, z=z, crs=crs)
    return entrance_fix


def return_centreline_params(data: list[str], fmt: str) -> tuple:
    """Wraps around dedicated metadata parsing functions depending on the surveys
    original format

    Parameters
    ----------
    data : list[str]
        the original raw data
    fmt : str
        the original survey format

    Returns
    -------
    tuple
        a tuple containing a surveyors's group, a date and starting / ending indices in the original survey file
    """
    if fmt == "tro":
        return return_centreline_params_tro(data)
    else: 
        return return_centreline_params_trox(data)
    


def return_centreline_params_trox(data):
    """Parses a centreline's metadata.

    Parameters
    ----------
    data : list[str]
        a list of measurements relating to a centreline

    Returns
    -------
    tuple
        a tuple containing a surveyors's group, a date and starting / ending indices in the original survey file
    """

    start,end = [],[]
    survey_dates = []
    surveyor_groups = []

    for c,l in enumerate(data):
        if ('Param' in l) and ('/Param' not in l):
            if 'Comment' in data[c+1]:
                if len(start) >= 1:
                    end.append(c-1)
                start.append(c+2)
            else:
                if len(start) >= 1:
                    end.append(c-1)
                start.append(c+1)

            reg_explodate = re.findall(r'(?<=Date\=")\d\d\/\d\d\/\d\d\d\d', l)
            # what if no explo date is given?
            if len(reg_explodate) > 0:
                reg_explodate = [elem for elem in reg_explodate[0].split("/")]
            else:
                reg_explodate = ["01", "01", "2001"]
            explodate = "{dd}.{mm}.{yy}".format(yy =reg_explodate[2][2:], mm =reg_explodate[1], dd = reg_explodate[0])

            if len(explodate) == 0:
                survey_dates.append('')
            else:
                survey_dates.append(re.sub(r"/",".",explodate))
            tp = re.findall(r"(?<=Topo réalisée par )[\w+\s]*",l)
            if len(tp) == 0:
                surveyor_groups.append('')
            else:
                surveyor_groups.append(tp[0].split(' '))
        elif 'Configuration' in l:
            end.append(c-1)

    return surveyor_groups,survey_dates,start,end


def return_centreline_params_tro(data: list[str]) -> tuple:
    """Parses a centreline's metadata.

    Parameters
    ----------
    data : list[str]
        a list of measurements relating to a centreline

    Returns
    -------
    tuple
        a tuple containing a surveyors's group, a date and starting / ending indices in the original survey file
    """

    # find the parameters of the file.
    start,end = [],[]
    survey_dates = []
    surveyor_groups = []

    for c,l in enumerate(data):

        if 'Param' in l:
            if len(start) >= 1:
                end.append(c-1)
            start.append(c+1)

            explodate = re.findall(r"\d\d.\d\d.\d\d", l)
            if len(explodate) == 0:
                survey_dates.append('')
            else:
                survey_dates.append(re.sub(r"-",".",explodate[0]))
            tp = re.findall(r"(?<=Topo réalisée par )[\w+\s]*",l)
            if len(tp) == 0:
                surveyor_groups.append('')
            else:
                surveyor_groups.append(tp[0].split(' '))
        elif 'Configuration' in l:
            end.append(c-1)

    return surveyor_groups,survey_dates,start,end

def parseFloat(x: str) -> float:
        try: 
            X = float(x)
            return X
        
        # when the value is starred.
        except ValueError:
            X = 0.
            return X


def parse_CommentedStations(lines : list[str]) -> list[StationWithComment]:
    """Parses station comments

    Parameters
    ----------
    lines : list[str]
        a list of measurements given as strings
    format : str
        the original survey format

    Returns
    -------
    list[StationWithComment]
        a list of commented station objects
    """
    parsed_lines = [[elem for elem in line.split(";") if elem != ""] for line in lines[1:]]
    stations_list = []
    for line in parsed_lines: 
        if len(line) > 1:
            stn_name = [elem for elem in line[0].split(" ") if elem != ""][0]
            comment = line[1]
            station = StationWithComment(stn_name,comment)
            stations_list.append(station)

    return stations_list

def parse_LRUDS(lines: list[str], format : str) -> list[LineLRUD]:
    """Parses station dimensions

    Parameters
    ----------
    lines : list[str]
        a list of measurements given as strings
    format : str
        the original survey format

    Returns
    -------
    list[LineLRUD]
        a list of diving data line objects.
    """
        
    if format == "tro":
        LRUDlines = [[elem for elem in line.split(" ") if elem != ""] for line in lines[:]]


    elif format == "trox":
        print("parsing a trox file")
        LRUDlines = []

        for line in lines:
            arr = None
            l = "0.00"
            r = "0.00"
            u = "0.00"
            d = "0.00"
            
            if "Arr=" in line:
                arr = line.split("Arr=")[1].split('"')[1]

            if "G=" in line:  
                l = line.split("G=")[1].split('"')[1]
            if "D=" in line:  
                r = line.split("D=")[1].split('"')[1]
            if "H=" in line:  
                u = line.split("H=")[1].split('"')[1]
            if "B=" in line:  
                d = line.split("B=")[1].split('"')[1]

            if arr is not None:
                empty_lrud = float(l) + float(r) + float(u) +float(d)
                if empty_lrud > 0:
                    LRUDlines.append([arr, l,r,u,d])
        
    else:
        LRUDlines = [[]]
    
    lrud_lines = []

    for c,line in enumerate(LRUDlines):
        if "*" in line[0] and len(line) >=9:
            LRUDline =LineLRUD(LRUDlines[c][1],parseFloat(line[5]),parseFloat(line[6]),parseFloat(line[7]),parseFloat(line[8])) 
        elif len(line) >=9:
            LRUDline =LineLRUD(line[1],parseFloat(line[5]),parseFloat(line[6]),parseFloat(line[7]),parseFloat(line[8]))
        elif len(line) ==5:
            LRUDline =LineLRUD(line[0],parseFloat(line[1]),parseFloat(line[2]),parseFloat(line[3]),parseFloat(line[4]))

        else:
            print("skipping empty line {}".format(c))
            print(line)
        try:
            lrud_lines.append(LRUDline) # type:ignore
        except:
            print("skipped a line here.")

    return lrud_lines

def parse_normal_data(lines: list[str], format: str ) -> list[NormalDataLine]:
    """Parses normal data

    Parameters
    ----------
    lines : list[str]
        a list of measurements given as strings
    format : str
        the original survey format

    Returns
    -------
    list[NormalDataLine]
        a list of normal data line objects.
    """
    if format == "tro":
        datalines = [[elem for elem in line.split(" ") if elem != ""] for line in lines]

    elif format == "trox":
        print("parsing a trox file")
        datalines: list = []
        datalines.append([elem.split("=")[-1].strip('"') for elem in lines[0].split(" ")[1:] if elem != ""])

        for line in lines[1:]:
            if "Visee Dep=" in line: 
                datalines.append([elem.split("=")[-1].strip('"') for elem in line.split(" ")[1:] if elem != ""])
            else: 
                datalines.append(["*"]+[elem.split("=")[-1].strip('"') for elem in line.split(" ")[1:] if elem != ""])
    else:
        datalines = [[]]
    
    dataLines = []
    equateLines = []


    for c,line in enumerate(datalines):
        print(line)
        if "*" in line[0] and len(line) >=5:
            if "Commentaire" not in " ".join(line):
                dataLine = NormalDataLine(datalines[c-1][1],line[1],float(line[2]),float(line[3]),float(line[4]))
        elif len(line) >=5:
            
            dataLine = NormalDataLine(line[0],line[1],float(line[2]),float(line[3]),float(line[4]))

            if dataLine.tape != 0:  # type:ignore
                dataLines.append(dataLine) # type:ignore
        
            else:
                print(f"found an equate on line {c}")
                theEquate = Equate(dataLine.from_station, "" ,dataLine.to_station, "")
                equateLines.append(theEquate)

        else:
            print("skipping empty line {}".format(c))
        
        

    return dataLines, equateLines

def parse_diving_data(lines: list[str], format: str, station_depth_lookup: dict) -> list[DivingDataLine]:
    """Parses diving data

    Parameters
    ----------
    lines : list[str]
        a list of measurements given as strings
    format : str
        the original survey format

    Returns
    -------
    list[DivingDataLine]
        a list of diving data line objects.
    """

    if format == "tro":
        datalines = [[elem for elem in line.strip("\n").split(" ") if elem != ""] for line in lines]
    elif format == "trox":
        print("parsing a trox file")
        datalines = []
        datalines.append([elem.split("=")[-1].strip('"') for elem in lines[0].split(" ")[1:] if elem != ""])
        datalines = datalines + [["*"]+[elem.split("=")[-1].strip('"') for elem in line.split(" ")[1:] if elem != ""] for line in lines[1:]]
    else:
        print("oops empty")
        datalines = [[]]


    dataLines = []
    equateLines = []

    # this is subtle here. you have to keep track of the depth of previous topographic points. 
    k = 0
    for c,line in enumerate(datalines[:]): # keep and index and ignore the first one.
        
        if len(line) >=9:
            # first test whether the depth lookup is empty. 
            if len(station_depth_lookup) == 0 and k == 0:
                station_depth_lookup[datalines[c][1]] = float(datalines[c][4])
                k+=1
            elif k== 0:
                from_station = line[0]
                station_depth_lookup[datalines[c][1]] = float(datalines[c][4])

                dataLine = DivingDataLine(from_depth= float(station_depth_lookup[from_station]),
                    from_station= from_station,
                    to_depth= float(line[4]),
                    to_station=line[1],
                    tape= float(line[2]),
                    compass =float(line[3]))
                k+=1

                if dataLine.tape != 0:
                    dataLines.append(dataLine)
                else:
                    print(f"found an equate on line {c}")
                    equateLines.append(dataLine)
            
            else:
                if "*" in line[:3] and len(datalines[c-1]) > 9:
                    station_depth_lookup[datalines[c][1]] = float(line[4])
                    
                    dataLine = DivingDataLine(from_depth= float(station_depth_lookup[datalines[c-1][1]]),
                    from_station= datalines[c-1][1],
                    to_depth= float(line[4]),
                    to_station=line[1],
                    tape= float(line[2]),
                    compass =float(line[3]))
                    
                    k+=1
                
                elif len(datalines[c-1])> 9:
                    station_depth_lookup[datalines[c][1]] = float(datalines[c][4])

                    dataLine = DivingDataLine(from_depth= float(station_depth_lookup[line[0]]),
                    from_station= line[0],
                    to_depth= float(line[4]),
                    to_station=line[1],
                    tape= float(line[2]),
                    compass =float(line[3]))

                    k+=1

                if dataLine.tape != 0:
                    dataLines.append(dataLine)
                else:
                    print(f"found an equate on line {c}")
                    equateLines.append(dataLine)
            

    return dataLines, equateLines


def make_centrelines_list(data : list[str], fmt: str, expand_lrud: bool = True ) -> list[Centreline]:
    """The main parser function: 
    -reads the original data file, 
    -finds the different centreline blocks
    - parses the metadata associated with each centreline

    - finds the measurement strategy, units, declination, date
    - parses the measurement data

    centrelines

    Parameters
    ----------
    data : list[str]
        the original data file in readable text.
    format : str
        the original format of the survey file

    Returns
    -------
    list[Centreline]
        a list of centreline objects.
    """
    
    _, survey_dates,starts,ends = return_centreline_params(data, fmt= fmt) # type:ignore

    centrelines : list[Centreline] = []
    station_depth_lookup = {}

    for start,end,date in zip(starts,ends,survey_dates):
        newCentreline = Centreline(fmt=fmt)
        print(date)
        newCentreline.add_Date(date)
        if format == "tro":
            header = data[start-1]
        else:
            if "Comment" in data[start-1]:
                header = ""
                for elem in data[start-2].split(" ")[1:]:
                    header += elem.split("=")[-1].strip('"')+" "
            else:
                header = ""
                for elem in data[start-1].split(" ")[1:]:
                    header += elem.split("=")[-1].strip('"')+" "

        newCentreline.parse_strategy(header)
        newCentreline.parse_units(header)

        station_lines = parse_CommentedStations(data[start:end+1])

        if "normal" in newCentreline.strategy.type:
            lrudLines = parse_LRUDS(data[start:end], format = fmt)
            dataLines, equateLines = parse_normal_data(data[start:end], format= fmt)

        elif "diving" in newCentreline.strategy.type:
            lrudLines = parse_LRUDS(data[start:end], format = fmt)
            dataLines, equateLines = parse_diving_data(data[start:end], format = fmt, station_depth_lookup=station_depth_lookup)
        
        for dataLine in dataLines:
            newCentreline.add_dataline(dataLine)
        
        for lrudLine in lrudLines:
            newCentreline.add_LRUDdataline(lrudLine)

        if expand_lrud == True:
            inject_lrud(newCentreline, lrudLines, dataLines)

        for line in station_lines:
            newCentreline.add_station_line(line)
        
        for equate in equateLines:

            newCentreline.add_equate_line(equate)



        newCentreline.add_string_repr()
        centrelines.append(newCentreline)

    return centrelines



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


##### SCRIPT CALLING. ######

if __name__ == "__main__":
    # Read the script arguments and load the Visual Topo archive file. 



    parser = argparse.ArgumentParser(description="Create a skeleton scrap")

    parser.add_argument(
        "input",
        help='The path to survey file (*.tro) to work from. e.g. "data/107/BahiaBlanca/BahiaBlanca.tro"',
    )

    parser.add_argument(
        "cave_name",
        help='The name of the cave or survey',
    )

    parser.add_argument("-fmt",
        "--format",
        help='the format of the Visual Topo File',
    )

    parser.add_argument("-o",
        "--output",
        help='the path to the output directory',
    )

    parser.add_argument("-crsin",
        "--input-crs",
        default= "epsg:3857",
        required = False,
        help='the epsg:code for the coordinate reference system, e.g. epsg:4326 for lat-long (WGS84 datum)',
    )

    parser.add_argument("-crsout",
        "--output-crs",
        default= None,
        required = False,
        help='the epsg:code for the coordinate reference system, e.g. epsg:4326 for lat-long (WGS84 datum)',
    )

    parser.add_argument("-lrud",
        "--expand_lrud",
        default= "false",
        required=False,
        help='if true, will calculate LRUD data as splay shots and inject them in the therion file',
    )

    args = parser.parse_args()

    ENTRY_FILE = abspath(args.input)
    FORMAT = args.format
    BASENAME = args.cave_name
    WRITE_PATH = abspath(args.output)
    EXIT_FILE = join(WRITE_PATH, f"{BASENAME}_convert.th")
    CRSIN = args.input_crs
    CRSOUT = args.output_crs
    EXPAND_LRUD = "true" in args.expand_lrud.lower()

    # EXIT_FILE = f"{dirname(ENTRY_FILE)}/{CAVE_NAME}.th"

    with open (ENTRY_FILE,'r', encoding='latin-1') as f:
            data = f.readlines()

    # create a named survey
    newSurvey = Survey(name=BASENAME)

    # add the entrance
    newSurvey.add_entrance_fix(find_entrance_fix(data, FORMAT, CRSIN))

    # read the data to centrelines and add to survey
    centrelines = make_centrelines_list(data, fmt= FORMAT, expand_lrud=EXPAND_LRUD)
    newSurvey.add_centrelines(centrelines)

    # make a formatted string
    newSurvey.add_string_repr()

    # create the output directory if it does not already exist.

    if not isdir(WRITE_PATH):
        subprocess.check_output(f'md "{WRITE_PATH}"', shell=True)

    if not isdir(join(WRITE_PATH, "outputs")):
        THERION_OUTPUTS_DIR = join(WRITE_PATH, 'outputs')
        subprocess.check_output(f'md "{THERION_OUTPUTS_DIR}"', shell=True)
    
    with open(EXIT_FILE, 'w+', encoding="utf-8") as f:
        f.write(newSurvey._string_repr)

    if CRSOUT is not None:
        CONFIG_FILE_STRING = _TH_CONFIG_FILE_TEMPLATE_WITH_CRS.format(basename=BASENAME, crsout=CRSOUT)
    else:
        CONFIG_FILE_STRING = _TH_CONFIG_FILE_TEMPLATE.format(basename=BASENAME)

    OUTPUT_CONFIG_FILEPATH = join(WRITE_PATH,  f"{BASENAME}.thconfig")
    

    ## Writing to file the config file
    with open(OUTPUT_CONFIG_FILEPATH, "w") as f:
        f.write(CONFIG_FILE_STRING)
        f.close()
