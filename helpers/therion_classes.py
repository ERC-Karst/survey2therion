"""
Created on May 21 14:02:02 2024

@author: Tanguy Racine, Celia Trunz

This provides a series of classes for representing a classic survey structure as series of python objects
"""


from dataclasses import dataclass, field
import re
import numpy as np
## dataclasses 

@dataclass 
class Date:
    """A class which represents a string formatted date"""
    year : int = None
    month : int = 1
    day : int = 1
    date_string : str = field(init = False)

    def __post_init__(self) -> None:
        if self.year is not None:
            self.date_string = f"{self.year}.{self.month:02d}.{self.day:02d}"
        else:
            self.date_string = None

@dataclass 
class StationWithComment:
    name : str
    comment : str
    command : str = field(init=False)

    def __post_init__(self) -> None:
        self.comment = self.comment.replace('"', "'") # replace double quotes in comments to better work on therion syntax.
        if self.name == "*":
            self.command = f'# station {self.name} "{self.comment}"'
        else:
            self.command = f'station {self.name} "{self.comment}"'

def format_dimension(value: float | None) -> str:
    """Format a passage dimension. Therion reads "-" as a dimension that wasn't measured"""
    return "-" if value is None else f"{value}"

@dataclass
class LineLRUD:
    """The passage dimensions at a station. A dimension is None when it wasn't measured"""
    from_station : str
    left : float | None
    right : float | None
    up : float | None
    down : float | None
    inclination : float = field(init=False)
    azimuth : float = field(init=False)

    def __post_init__(self) -> None:
        self.dims = [self.left, self.right, self.up, self.down]

@dataclass
class Equate:
    stn1 : str
    survey1 : str
    stn2 : str
    survey2 : str
    command : str = field(init=False)

    def __post_init__(self) -> None:
        if not self.survey1 and not self.survey2:
            self.command = f'\n\tequate {self.stn1} {self.stn2}'
        elif not self.survey1:
            self.command = f'\n\tequate {self.stn1} {self.stn2}@{self.survey2}'
        elif not self.survey2:
            self.command = f'\n\tequate {self.stn1}@{self.survey1} {self.stn2}'
        else:
            self.command = f'\n\tequate {self.stn1}@{self.survey1} {self.stn2}@{self.survey2}'


@dataclass
class Input:
    filepath : str
    command : str = field(init=False)

    def __post_init__(self) -> None:
        self.command = f'input "./{self.filepath}"'

@dataclass
class LineFlag:
    flag : str
    command : str = field(init=False)
    
    def __post_init__(self) -> None:
        self.command = f"""\n\tflags {self.flag}"""

@dataclass
class LineDeclination:
    declination : float
    command : str = field(init=False)

    def __post_init__(self) -> None:
        self.command = f"\n\tdeclination {self.declination} degrees"

@dataclass
class CommentedLine:
    line : str
    command : str = field(init=False)
    
    def __post_init__(self) -> None:
        self.command = f"\n\t## {self.line}"


@dataclass
class Fix:
    name : str
    x : float
    y : float 
    z : float
    crs : str

    def __post_init__(self) -> None:
        self.command = f'\t\tcs {self.crs}\n\t\tfix {self.name} {self.x:.0f} {self.y:.0f} {self.z:.0f}'


@dataclass 
class DataLine:
    from_station : str
    to_station : str
    tape : float
    compass : float
    calibration : str = field(init=False) # add optional calibration line prior to the line. 


@dataclass
class NormalDataLine(DataLine):
    clino : float

@dataclass
class DivingDataLine(DataLine):
    to_depth : float
    from_depth : float

@dataclass
class Units:
    input_str : str = None
    fmt: str = "tro"
    length : str = "metre"
    clino : str = "degree"
    compass : str = "degree"
    dimensions : str = "metre"
    #declination : float = None
    command : str = field(init=False)

    def __post_init__(self) -> None:
        if len(self.input_str.split(";")) >=2:
            line, comment = self.input_str.split(";")[:2]
        elif self.input_str == "empty":
            self.fmt = "empty"
        else:
            line = self.input_str
        
        if self.fmt == "tro" or self.fmt == "trox":
            tape, clino, _, compass, declination, _, where_dims = line.split(" ")[:7]
        
        elif self.fmt == "survex default":
            tape = "Deca"
            clino = "Deg"
            compass = "Deg"
            self.dimensions = "metre"
        
        else: 
            tape, clino, compass = None, None, None

        if tape == "Deca":
            self.length = "meters"
        
        if clino == "Degd" or clino == "Deg":
            self.clino = "degrees"
        elif clino == "Gra" or clino == "Grad":
            self.clino = "grads"
        
        if compass == "Degd" or compass == "Deg":
            self.compass = "degrees"
        elif compass == "Gra" or compass == "Grad":
            self.compass = "grads"

        # try:
        #     self.declination = float(declination)
        # except:
        #     print("no valid declination given, using default from therion given date and location.")
    

        # if self.declination is not None:
        #     declination_command = f"declination {self.declination:.4f} degrees\n"
        # else:
        #     declination_command = ""
        
        self.command = f"""units length {self.length}
        units compass {self.compass}
        units clino {self.clino}
        units dimensions {self.dimensions}"""
    
@dataclass
class Strategy:
    input_str : str
    orig_format : str 
    compass : str = "normal"
    clino : str = "normal"
    type : str = "normal"
    command : str = "data normal from to length compass clino"

    def __post_init__(self) -> None:
        if self.orig_format == "tro" or self.orig_format == "trox": 

            if "Dir,Dir,Inv" in self.input_str:
                self.clino = "back"
                self.type = "normal_backclino"

            elif "Inv,Inv,Dir" in self.input_str or "Inv,Dir,Dir" in self.input_str:
                self.compass = "back"
                if "Prof" in self.input_str:
                    print("##################  found some diving data !! ################################")
                    self.type = "diving_backcompass"
                else: 
                    self.type = "normal_backcompass"

            elif "Inv,Inv,Inv" in self.input_str:
                self.compass = "back"
                self.clino = "back"
                self.type = "normal_backcompass_backclino"

            elif ("Dir,Dir,Dir" in self.input_str) and ("Prof") in self.input_str:
                print("##################  found some diving data !! ################################")
                self.type = "diving"
        elif self.orig_format == "survex":
            self.type = "normal survex"
            self.command = "data normal " + self.input_str

    def update_command(self):
        if self.type == 'normal':
            self.data_header = ["data", "normal", "from", "to", "tape", "compass", "clino"]
        elif self.type == "normal_backclino":
            self.data_header = ["data", "normal", "from", "to", "tape", "compass", "backclino"]
        elif self.type == "normal_backcompass":
            self.data_header = ["data", "normal", "from", "to", "tape", "backcompass", "clino"]
        elif self.type == "normal_backcompass_backclino":
            self.data_header = ["data", "normal", "from", "to", "tape", "backcompass", "backclino"]
        elif self.type == "diving":
            self.data_header = ["data", "diving",  "from", "fromdepth","to", "todepth", "tape", "compass"]
        elif self.type == "diving_backcompass":
            self.data_header = ["data", "diving",  "from", "fromdepth","to", "todepth", "tape", "backcompass"]
        
        self.command = "\t".join(self.data_header)

@dataclass
class Centreline:
    explo_date : Date = field(init= False)
    explorers : list[str] = field(init= False, default_factory= list)
    declination : float = None
    fmt: str = "tro"
    strategy : Strategy = field(init= False)
    units : Units = field(init= False)
    declinations: dict = field(init=False, default_factory= dict)
    lrud_reader : str = "data dimensions station left right up down"
    data : list[DataLine] = field(init=False, default_factory= list)
    lrud_data : list[LineLRUD] = field(init=False, default_factory= list)
    equates : list[Equate] = field(init=False, default_factory= list)
    commented_stations : list[StationWithComment] = field(init=False, default_factory=list)
    _string_repr : str = field(init=False, default_factory= str)

        
    def add_explorers(self, explorers : list[str]) -> None:
        self.explorers += explorers

    def add_dataline(self, line: DataLine, index: int = None) -> None:
        if index is not None:
            self.data.insert(index, line)
        else:
            self.data+= [line]

    def add_station_line(self, station : StationWithComment) -> None:
        self.commented_stations.append(station)

    def add_LRUDdataline(self, line: LineLRUD) -> None:
        self.lrud_data+= [line]

    def add_equate(self, equate:  Equate) -> None:
        """Appends every equate command found in the survey file

        Parameters
        ----------
        centrelines : list[Equate]
            A list of instantiated equate objects. 
        """
        self.equates.append(equate)

    def add_Date(self, date: str) -> None:
        if date == None:
            self.date = Date(year=None)
            self.explo_date = Date(year=None)
        
        else:
            # format the date using some logic to guess the format in which it was given.
            if len(date.split("."))== 3:
                DATE = date.split(".")
            elif len(date.split("/"))== 3:
                DATE = date.split("/")
            elif len(date.split("-"))== 3:
                DATE = date.split("-")
            elif len(date)==6:
                DATE = [date[:2], date[2:4], date[4:]]
            else:
                # we can't read this date, so the survey stays undated
                self.add_Date(None)
                return

            DATE = [part.strip() for part in DATE]

            # a 4-digit first part is the year of a YYYY.MM.DD date
            if len(DATE[0]) == 4:
                DATE = DATE[::-1]

            # dates are sometimes given in DDMMYY format.
            if len(DATE[2]) == 4:
                DATE[2] = int(DATE[2])
            elif int(DATE[2]) < 50:
                DATE[2] = 2000+int(DATE[2])
            elif int(DATE[2]) < 100:
                DATE[2] = 1900+int(DATE[2])
            else:
                # allow for none dates to be given, but this means declination should also be given.
                DATE[2] = None

            self.date = Date(year=DATE[2],month=int(DATE[1]),day=int(DATE[0]))
            self.explo_date = Date(year=DATE[2],month=int(DATE[1]),day=int(DATE[0]))

    def parse_strategy(self, input_str: str) -> None:
        self.strategy = Strategy(input_str, self.fmt)
        self.strategy.update_command()

    def parse_units(self, input_str: str) -> None:
        self.units = Units(input_str, fmt=self.fmt)

    
    def add_equate_line(self, equate: Equate):
        self.equates.append(equate)

    def parse_declination(self, input_str: str) -> None:
        if self.fmt == "tro" or self.fmt == "trox":
        # now check whether the date has been given at all.
            self.declinations = {0: input_str.split(" ")[4]}


    def add_string_repr(self) -> None:
        
        explorers = ""
        for explorer in self.explorers:
            explorers += f"explo-team {explorer}\n\t"

        formatted_data : str = ""
        formatted_lrud : str = ""
        formatted_comments : str = ""
        formatted_equates : str = ""


        for c, line in enumerate(self.data):
            if c in list(self.declinations.keys()):
                formatted_data+=f"\n\tdeclination {self.declinations[c]} degrees"
                
            try:
                formatted_data+=f"{line.command}"
                
            except AttributeError:
                
                prefix = ""
                suffix = ""
                if line.from_station == line.to_station:
                    print("shot between to same stations will be ignored and commented out!! ")
                    prefix = "#"
                    suffix = "# shot between two equal stations ignored at conversion."

                if "normal" in self.strategy.type:
                    formatted_data += f"\n\t\t{prefix}{line.from_station}\t{line.to_station}\t{line.tape}\t{line.compass}\t{line.clino}\t{suffix}" # type: ignore
                elif "diving" in self.strategy.type:
                    formatted_data += f"\n\t\t{prefix}{line.from_station}\t{line.from_depth}\t{line.to_station}\t{line.to_depth}\t{line.tape}\t{line.compass}\t{suffix}" # type: ignore
            
        # appending the station dimension data to the centreline string representation     
        for lrud_line in self.lrud_data:
            formatted_lrud += f"""
        {lrud_line.from_station}\t{format_dimension(lrud_line.left)}\t{format_dimension(lrud_line.right)}\t{format_dimension(lrud_line.up)}\t{format_dimension(lrud_line.down)}\t"""

        # appending equates at the end of the centreline block
        for equate_line in self.equates:
            formatted_equates += equate_line.command

        # adding the parsed station comments to the centreline string representation
        for comment in self.commented_stations:
            formatted_comments += f"""
        {comment.command}"""

        # allowing for either dated or undated surveys to be parsed. 
        if self.explo_date.date_string is not None:
            self.date_block = f"""
        explo-date {self.explo_date.date_string}
        date {self.explo_date.date_string}"""
        else: 
            self.date_block = ""

        # formatting the whole centreline string representation in therion format. 
        self._string_repr = f"""
    centreline
        {self.date_block}
        {explorers}
        {self.units.command}
        {self.strategy.command}
        {formatted_data}

        {self.lrud_reader}
        {formatted_lrud}
        {formatted_comments}
    endcentreline

    {formatted_equates}"""
            
        

@dataclass
class Survey:
    name : str
    isTopLevel : bool = False
    entrance_fixes : list[Fix] = field(init= False, default_factory= list)
    centrelines : list[Centreline] = field(init= False, default_factory= list)
    inputs:  list[Input] = field(init= False, default_factory= list)
    equates:  list[Equate] = field(init= False, default_factory= list)
    children:  list = field(init= False, default_factory= list)  
    _string_repr : str = field(init=False, default_factory= str)

    def add_centrelines(self, centrelines:  list[Centreline]) -> None:
        """Appends every centreline found in the survey file

        Parameters
        ----------
        centrelines : list[Centreline]
            A list of populated centreline objects. 
        """
        self.centrelines.append(centrelines[0])

        if len(centrelines) > 0:
            # cycle over additional centrelines. 
            for newcentreline in centrelines[1:]:

                if len(self.centrelines[-1].data) >0:
                    end_station = self.centrelines[-1].data[-1].to_station
                else:
                    end_station = None
                
                if len(newcentreline.data) > 0:
                    start_station = newcentreline.data[0].from_station
                else:
                    start_station = None
                
                if start_station == "*" and end_station !=None:
                    newcentreline.data[0].from_station = end_station
                    newcentreline.add_string_repr()
                    self.centrelines.append(newcentreline)
                else:
                    self.centrelines.append(newcentreline)    

    def add_equate(self, equate:  Equate) -> None:
        """Appends every equate command found in the survey file

        Parameters
        ----------
        centrelines : list[Equate]
            A list of instantiated equate objects. 
        """
        self.equates.append(equate)

    def add_input(self, input:  Input) -> None:
        """Appends every centreline found in the survey file

        Parameters
        ----------
        centrelines : list[Input]
            A list of populated centreline objects. 
        """
        self.inputs += input

    def add_entrance_fix(self, entrance_fix : Fix) -> None:
        """Appends a fixed station found in the survey file. The first one is used as the survey entrance

        Parameters
        ----------
        entrance_fix : Fix
            the fixed station and its coordinates.
        """
        self.entrance_fixes.append(entrance_fix)

    def add_child(self, child) -> None:
        """Appends every centreline found in the survey file

        Parameters
        ----------
        centrelines : list[Centreline]
            A list of populated centreline objects. 
        """
        self.children.append(child)

    def add_string_repr(self) -> None:
        """Parse the children centreline objects to make a string
        representation of the survey in therion format.

        Parameters
        ----------
        self : Survey
            the Survey itself.
        """


        # format the string representation of the survey.
        self._string_repr = f"""

survey {self.name.strip('"')} """
        
        if len(self.entrance_fixes) > 0:
            fix_commands = "\n".join(fix.command for fix in self.entrance_fixes)

            self._string_repr +=f"""-entrance {self.entrance_fixes[0].name}
    
    # entrance fix.
    centreline
{fix_commands}
    endcentreline

"""
            
        if self.inputs is not None:
            for input in self.inputs:
                self._string_repr +=f"""\t{input.command}
"""
        if len(self.equates) > 0:

            for equate in self.equates:
                self._string_repr +=f"\n\t{equate.command}"

        if len(self.centrelines) > 0:
            # concatenate the centrelines    
            centrelines = ""


            for c, centreline in enumerate(self.centrelines):
                centrelines += f"{centreline._string_repr}\n"

            self._string_repr += f"""

{centrelines}"""

            
        if self.isTopLevel and len(self.children) > 0:
            for child in self.children:
                self._string_repr += f"""
{child._string_repr}"""

        self._string_repr +=f"""
endsurvey
"""