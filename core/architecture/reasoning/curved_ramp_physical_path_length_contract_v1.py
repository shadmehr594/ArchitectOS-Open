"""Physical longitudinal path-length gate for curved ramps."""
from math import hypot

from core.architecture.reasoning.curved_ramp_stationed_surface_v1 import CurvedRampStationedSurfaceV1


class CurvedRampPhysicalPathLengthContractV1:
    EPS=1e-7

    def resolve(self,topology,width_transition,start_z=0.0,end_z=-2.4,maximum_grade=.15):
        # XY cross-sections are generated from the authoritative centerline;
        # their Z values are not used for this upstream path-length gate.
        stationed=CurvedRampStationedSurfaceV1().resolve(topology,width_transition)
        left=self._length(stationed['left_edge_xy']);center=self._length(stationed['centerline_xy']);right=self._length(stationed['right_edge_xy'])
        required=abs(end_z-start_z)/maximum_grade;shortest=min(left,center,right);margin=shortest-required
        grades={'left':abs(end_z-start_z)/left,'centerline':abs(end_z-start_z)/center,'right':abs(end_z-start_z)/right}
        valid=margin>=-self.EPS
        return {'contract':'CurvedRampPhysicalPathLengthContractV1','geometry_status':'resolved' if valid else 'insufficient_physical_edge_run',
            'failure_reasons':[] if valid else ['shortest_physical_path_below_required_run'],
            'centerline_length':center,'left_edge_length':left,'right_edge_length':right,
            'shortest_physical_path':shortest,'shortest_path_id':min((left,'left'),(center,'centerline'),(right,'right'))[1],
            'required_minimum_path':required,'path_length_margin':margin,
            'left_average_grade':grades['left'],'centerline_average_grade':grades['centerline'],'right_average_grade':grades['right'],
            'maximum_local_left_grade':stationed['maximum_abs_grade_left_edge'],
            'maximum_local_center_grade':stationed['maximum_abs_grade_centerline'],
            'maximum_local_right_grade':stationed['maximum_abs_grade_right_edge'],
            'level_start_edge':stationed['cross_sections'][0]['level_error']<=self.EPS,
            'level_end_edge':stationed['end_cross_section_level_error']<=self.EPS,
            'required_max_cross_slope':self._required_cross_slope(stationed),
            'cross_slope_compliance':'pending_requirement','stationed_xy_evidence':stationed}

    @staticmethod
    def _length(points):return sum(hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(points,points[1:]))

    @staticmethod
    def _required_cross_slope(stationed):
        values=[]
        for section in stationed['cross_sections']:
            width=section['width'];values.append(abs(section['left'][2]-section['right'][2])/width if width else 0.0)
        return max(values,default=0.0)
