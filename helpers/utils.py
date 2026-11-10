import numpy as np
from .therion_classes import NormalDataLine

#### utilities 

def rad2deg(radian):
    return radian * 180/np.pi

def rad2grad(radian):
    return radian *200/np.pi

def deg2rad(degree):
    return degree * np.pi/180

def deg2grad(deg):
    return deg *10/9

def grad2deg(grad):
    return grad * 9/10

def grad2rad(grad):
    return grad * np.pi/200



def spherical2cartesian(compass, clino, units):

    if units.compass== "degrees" or units.compass == "degree":
        compass = deg2rad(compass)
    elif units.compass == "grads":
        compass =grad2rad(compass)
    else: 
        print("azimuth already given in radians? ")
    
    if units.clino== "degrees" or units.clino == "degree":
        clino = deg2rad(clino)
    elif units.clino == "grads":
        clino =grad2rad(clino)
    else: 
        print("compass already given in radians? ")
    

    uv_x = np.sin(compass)*np.cos(clino)
    uv_y = np.cos(compass)*np.cos(clino)
    uv_z = np.sin(clino)

    uv = np.array([uv_x, uv_y, uv_z])
    
    assert np.abs(np.linalg.norm(uv) - 1) < 1.e-5
    
    return uv

def bisector(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Return the unit vector halfway between two unit vectors. Opposite vectors have no bisector, so we return the first one"""
    total = u + v
    if np.linalg.norm(total) < 1.e-5:
        return u
    return total / np.linalg.norm(total)

def cartesian2spherical(u: np.ndarray, units, vert_threshold: float = 70) -> tuple:
    """Returns the angular inclination and angle from north from a vector in cartesian
    coordinates, depending on the current units of a centreline block.

    :param u: the coordinate triplet of the dimension vector
    :type u: np.ndarray
    :param units: an instance of Units object corresponding to the current centreline's units. 
    :type units: Units
    :param vert_threshold: a threshold beyond which up and down splays are assumed to be taken vertically.
    :type vert_threshold: float
    :return: phi, theta in current centreline's units (degrees or radians)
    :rtype: tuple
    """

    l  = np.linalg.norm(u)     # norm of vector u
    if l == 0:
        theta = 0
    else:
        theta = np.arcsin(u[2] / l) # inclination from horizontal
    
    # apply a critical verticality threshold.
    if theta > vert_threshold * np.pi / 180:
        theta = np.pi / 2
    elif theta < -vert_threshold * np.pi / 180:
        theta = -np.pi / 2

    phi = np.pi / 2 - np.arctan2(u[1], u[0]) # angle from north

    if units.compass == "degrees" or units.compass == "degree":
        phi = rad2deg(phi) % 360
    elif units.compass == "grads" or units.compass == "grad":
        phi = rad2grad(phi) % 400
    else:
        print("unknown compass units")


    if units.clino == "degrees" or units.clino == "degree":
        theta = rad2deg(theta)
    elif units.clino == "grads" or units.clino == "grad":
        theta = rad2grad(theta)
    else:
        print("unknown compass units")
    
    return phi, theta

def calc_splay_from_lrud(normal_vector_dir,lrud, other_normal=None):
    """Transform left-right-up-down caving survey measurements to splays.
    Calculation made by Nina Egli

    This assumes that:
    1. the normal vector corresponds to the main direction of the conduit
    2. the normal vector is pointing in the direction of survey
    3. left and right measurements are always made in the horizontal plan
    4. up and down are made perpendicular to the direction of the conduit and not strait up or down

    Parameters
    ----------

    normal_vector_dir : list or array
        direction of the conduit. x,y,z vector calculated with .... in the direction of the survey.
    lrud : list or array
        left, right, up, down measurements in the same unit of measurements as the coordinates.

    Returns
    -------
    list of array
        left, right, up, down splays list of coordinates of the position measured on the wall

    """
    #unit vector pointing up
    unit_vector_z = np.array([0,0,1])

    # a dimension that wasn't measured makes no splay
    left_scalar = lrud.left or 0.0
    right_scalar = lrud.right or 0.0
    up_scalar = lrud.up or 0.0
    down_scalar = lrud.down or 0.0

    #calculate the unit vector to the right and down by taking the vector product
    unit_vector_right = np.cross(normal_vector_dir,unit_vector_z) 
    #in case of vertical conduit where the normal is perfectly vertical, we use the normal of the previous or next point  
    if other_normal is not None and np.linalg.norm(unit_vector_right) < 0.01:
        unit_vector_right = (np.cross(other_normal,normal_vector_dir)*np.sign(normal_vector_dir[2]))

    #assert np.linalg.norm(unit_vector_right) > 0.01, f'unit vector right is null: {unit_vector_right}, station coordinates:{station_coordinates}, normal_vector_plan_normalized:{normal_vector_plan_normalized}, normal_vector_dir:{normal_vector_dir}, other_normal:{other_normal}, lrud:{lrud}'

    unit_vector_right = unit_vector_right / np.linalg.norm(unit_vector_right)

    # assert np.abs(1-np.linalg.norm(unit_vector_right))<0.000001, f'unit vector right normalized is not unit vector, instead{np.linalg.norm(unit_vector_right)}'


    unit_vector_down = np.cross(normal_vector_dir,unit_vector_right) 
    unit_vector_down = unit_vector_down / np.linalg.norm(unit_vector_down)
    # assert np.abs(1-np.linalg.norm(unit_vector_down))<0.000001, f'unit vector down is not unit vector, instead{np.linalg.norm(unit_vector_down)}'

    #calculate position
    print("left scalar:  ",left_scalar,  type(left_scalar))
    left_vector = - unit_vector_right * left_scalar
    right_vector = unit_vector_right * right_scalar
    up_vector = - unit_vector_down * up_scalar
    down_vector = unit_vector_down * down_scalar

    return np.array([left_vector.tolist(), right_vector.tolist(), up_vector.tolist(), down_vector.tolist()])


def inject_lrud(centreline, lrudlines, datalines):
            # set up a counter to keep track of where to insert the splay lines.
            lrud_counter = 0
            station_counter = 1
            for c, lrudLine in enumerate(lrudlines):
                # direction

                normal_vec = np.zeros(3)



                for k, dataLine in enumerate(datalines):
                    lrud_station = lrudLine.from_station
                    
                    if isinstance(dataLine, NormalDataLine):

                        if c == 0:
                            if dataLine.from_station == lrud_station:
                                try:
                                    compass = float(dataLine.compass)
                                    normal_vec = spherical2cartesian(compass,float(dataLine.clino), centreline.units)
                                except ValueError:
                                    pass
                                
                            station_counter = k


                                

                        elif c== len(lrudlines)-1:
                            if dataLine.to_station == lrud_station:
                                try:
                                    compass = float(dataLine.compass)
                                    normal_vec = spherical2cartesian(compass,float(dataLine.clino), centreline.units)
                                except ValueError:
                                    pass
                                
                                station_counter = k

                        else:

                            if dataLine.to_station == lrud_station and k != len(datalines)-1:

                                dataline1= datalines[k]

                                # now we know we have found good station. 
                                if isinstance(datalines[k+1], NormalDataLine):
                                    dataline2= datalines[k+1]
                                    try:
                                        comp1 = float(dataline1.compass)
                                        clino1 = float(dataline1.clino) 
                                    except ValueError:
                                        comp1 = 0
                                        if dataline1.clino.lower() == "up":
                                            clino1 = +90
                                        else:
                                            clino1 = -90

                                    try:
                                        comp2 = float(dataline2.compass)
                                        clino2 = float(dataline2.clino)

                                    except ValueError:
                                        comp2 = 0
                                        if dataline2.clino.lower() == "up":
                                            clino2 = +90
                                        else:
                                            clino2 = -90

                                    # 1. dir 1 to cartesian, dir 2 to cartesian
                                    cartesian_1 = spherical2cartesian(comp1, clino1, centreline.units)
                                    cartesian_2 = spherical2cartesian(comp2, clino2, centreline.units)
                        
                                    normal_vec = bisector(cartesian_1, cartesian_2)

                                    # splay from normal vector and lruds 
                                    station_counter = k+1
                                
                                else:
                                    try:
                                        comp1 = float(dataline1.compass)
                                        clino1 = float(dataline1.clino) 
                                        normal_vec = spherical2cartesian(comp1,clino1, centreline.units)

                                    except ValueError:
                                        pass


                                    station_counter = k+1

                                
                        
                lrud_vectors = calc_splay_from_lrud(normal_vec, lrudLine)

                j = 0
                for dim in lrud_vectors:
                    # transform back to original units. 

                    phi, theta = cartesian2spherical(dim, centreline.units)

                    compass = f"{phi:.1f}"
                    inclination = f"{theta:.1f}"
                    len_dim = f"{np.linalg.norm(dim):.1f}"

                    # injection de ligne bidon. 
                    if float(len_dim) > 0:
                        newsplayline = NormalDataLine(from_station=lrudLine.from_station,
                                                    to_station=".", 
                                                    tape=len_dim,
                                                    compass=compass,
                                                    clino=inclination)
                
                        centreline.add_dataline(newsplayline, lrud_counter+station_counter+j)
                        j+=1
                
                lrud_counter+=j

def parse_float(dim):
    try:
        return float(dim)
    except:
        return 0.