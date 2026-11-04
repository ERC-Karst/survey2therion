import string
import unicodedata

from helpers.therion_classes import Centreline, StationWithComment

# Therion accepts these characters in a station name. The second set is only accepted after the first character
_STATION_FIRST_CHARS = set(string.ascii_letters + string.digits + "_/")
_STATION_OTHER_CHARS = _STATION_FIRST_CHARS | set("-+*.,'")

# Therion reads these names as a station without a name, such as the end of a splay
ANONYMOUS_STATIONS = {"-", "."}

def is_valid_station_name(name: str) -> bool:
    return name[0] in _STATION_FIRST_CHARS and all(ch in _STATION_OTHER_CHARS for ch in name[1:])

def rewrite_station_name(name: str) -> str:
    """Strip the accents from the name, then replace each character Therion rejects with an underscore"""
    letters = "".join(ch for ch in unicodedata.normalize("NFKD", name) if unicodedata.category(ch) != "Mn")
    return "".join(ch if ch in (_STATION_FIRST_CHARS if i == 0 else _STATION_OTHER_CHARS) else "_" for i, ch in enumerate(letters))

def station_renaming(names: list[str]) -> dict[str, str]:
    """Get the new name of each station whose name Therion rejects. Valid names stay unchanged.
    A rewritten name already in use gets a numbered suffix, so two stations never merge.

    Parameters
    ----------
    names : list[str]
        every station name of the project, in the order of the files. Anonymous stations are ignored

    Returns
    -------
    dict
        the new name of each renamed station, keyed by its original name
    """
    names = [name for name in dict.fromkeys(names) if name and name not in ANONYMOUS_STATIONS]
    taken = {name for name in names if is_valid_station_name(name)}
    renaming = {}
    for name in names:
        if name in taken:
            continue
        new_name = rewrite_station_name(name)
        suffix = 2
        while new_name in taken:
            new_name = f"{rewrite_station_name(name)}_{suffix}"
            suffix += 1
        taken.add(new_name)
        renaming[name] = new_name
    return renaming

def stations_of(centreline: Centreline) -> set[str]:
    return {line.from_station for line in centreline.data if hasattr(line, "from_station")} \
        | {line.to_station for line in centreline.data if hasattr(line, "to_station")} \
        | {line.from_station for line in centreline.lrud_data} \
        | {equate.stn1 for equate in centreline.equates} | {equate.stn2 for equate in centreline.equates}

def add_original_names(centrelines: list[Centreline], renaming: dict[str, str]) -> None:
    """Keep the original name of each renamed station as its comment, unless the station has a comment of its own.
    The comment goes in the first of the centrelines using the station, so give the centrelines of one Therion survey"""
    commented = {station.name for centreline in centrelines for station in centreline.commented_stations}
    for original, new_name in renaming.items():
        if new_name in commented:
            continue
        for centreline in centrelines:
            if new_name in stations_of(centreline):
                centreline.add_station_line(StationWithComment(new_name, original))
                break
