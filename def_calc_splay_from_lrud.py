import numpy as np

def calc_splay_from_lrud(station_coordinates, normal_vector_dir,lrud, other_normal=None):
    """Transform left-right-up-down caving survey measurements to splays.
    Calculation made by Nina Egli

    This assumes that:
    1. the normal vector corresponds to the main direction of the conduit
    2. the normal vector is pointing in the direction of survey
    3. left and right measurements are always made in the horizontal plan
    4. up and down are made perpendicular to the direction of the conduit and not strait up or down

    Parameters
    ----------
    station_coordinates : list or array
        x,y,z coordinates of the station in meters or feet. example: [x,y,z]
    normal_vector_dir : list or array
        direction of the conduit. x,y,z vector calculated with .... in the direction of the survey.
    lrud : list or array
        left, right, up, down measurements in the same unit of measurements as the coordinates.

    Returns
    -------
    list of array
        left, right, up, down splays list of coordinates of the position measured on the wall

    """
    #unit vector pointing north
    unit_vector_z = np.array([0,0,1])
    #we normalize the normal vector by its norm    
    normal_vector_plan_normalized =  (normal_vector_dir/np.linalg.norm(normal_vector_dir))
    #extract the left right up down scalar values
    left_scalar = lrud[0]
    right_scalar = lrud[1]
    up_scalar = lrud[2]
    down_scalar = lrud[3]

    #calculate the unit vector to the right and down by taking the vectorial product
    unit_vector_right = np.cross(normal_vector_plan_normalized,unit_vector_z) 
    #in case of vertical conduit where the normal is perfectly vertical, we use the normal of the previous or next point  
    if other_normal is not None and np.linalg.norm(unit_vector_right) < 0.01:
        unit_vector_right = (np.cross(other_normal,normal_vector_plan_normalized)*np.sign(normal_vector_plan_normalized[2]))

    assert np.linalg.norm(unit_vector_right) > 0.01, f'unit vector right is null: {unit_vector_right}, station coordinates:{station_coordinates}, normal_vector_plan_normalized:{normal_vector_plan_normalized}, normal_vector_dir:{normal_vector_dir}, other_normal:{other_normal}, lrud:{lrud}'

    unit_vector_right = unit_vector_right / np.linalg.norm(unit_vector_right)

    # assert np.abs(1-np.linalg.norm(unit_vector_right))<0.000001, f'unit vector right normalized is not unit vector, instead{np.linalg.norm(unit_vector_right)}'



    unit_vector_down = np.cross(normal_vector_plan_normalized,unit_vector_right) 
    unit_vector_down = unit_vector_down / np.linalg.norm(unit_vector_down)
    # assert np.abs(1-np.linalg.norm(unit_vector_down))<0.000001, f'unit vector down is not unit vector, instead{np.linalg.norm(unit_vector_down)}'

    #calculate position
    left_vector = station_coordinates - unit_vector_right * left_scalar
    right_vector = station_coordinates + unit_vector_right * right_scalar
    up_vector = station_coordinates - unit_vector_down * up_scalar
    down_vector = station_coordinates + unit_vector_down * down_scalar

    return [left_vector.tolist(), right_vector.tolist(), up_vector.tolist(), down_vector.tolist()]    