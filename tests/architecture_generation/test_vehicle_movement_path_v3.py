from core.architecture.reasoning.vehicle_movement_path_v3 import VehicleMovementPathV3


def test_other_stall_is_an_occupied_obstacle():
    result=VehicleMovementPathV3().resolve([[0,2],[2,2]],[[2,1],[2,3]],[[2,0],[10,0],[10,6],[2,6]],[[2,0],[10,0],[10,6],[2,6]],
        [[[6,0],[8,0],[8,5],[6,5]],[[8,0],[10,0],[10,5],[8,5]]],1.0)
    assert all(item['other_stalls_treated_as_occupied'] for item in result['stall_paths'])
    assert all('clearance_corridor' in item for item in result['stall_paths'])


def test_invalid_corridor_is_not_renderable_as_valid_path():
    result=VehicleMovementPathV3().resolve([[0,2],[2,2]],[[2,1],[2,3]],[[2,0],[4,0],[4,4],[2,4]],[[2,0],[4,0],[4,4],[2,4]],
        [[[8,8],[10,8],[10,13],[8,13]]],3.0)
    assert result['geometry_status']=='generated_not_valid'
    assert result['stall_paths'][0]['center_trajectory']==[]
