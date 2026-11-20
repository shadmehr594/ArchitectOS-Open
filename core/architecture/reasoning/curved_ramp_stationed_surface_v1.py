"""Build a curved ramp mesh from common centerline stations.

The centerline station and vertical profile are authoritative.  Both edge
vertices of a cross-section receive the same Z; edge grades are measured
afterwards on their different physical path lengths.
"""
from math import hypot


class CurvedRampStationedSurfaceV1:
    EPS=1e-9

    def resolve(self,topology,width_transition,tolerance=1e-7):
        profile=topology["z_profile"]; samples=profile["vertices"]
        s1=topology["stationing"]["S1"];s2=topology["stationing"]["S2"];s3=topology["stationing"]["S3"]
        entry=float(width_transition["entry_width"]);curve=float(width_transition["curve_width"])
        terminal=float(width_transition["terminal_leg_width"]["end"])
        cross=[]
        for index,(x,y,station,z) in enumerate(samples):
            tangent=self._tangent(topology,samples,index,station,s1,s2)
            normal=[-tangent[1],tangent[0]];width=self._width(station,s1,s2,s3,entry,curve,terminal)
            left=[x+normal[0]*width/2,y+normal[1]*width/2,z]
            right=[x-normal[0]*width/2,y-normal[1]*width/2,z]
            cross.append({"station":station,"center":[x,y,z],"tangent":tangent,"normal":normal,
                "width":width,"left":left,"right":right,"level_error":abs(left[2]-right[2])})
        center_grades=self._grades([item["center"] for item in cross])
        left_grades=self._grades([item["left"] for item in cross])
        right_grades=self._grades([item["right"] for item in cross])
        max_slope=float(profile["maximum_local_slope"])
        segment_lengths={"left":self._lengths([item["left"] for item in cross]),
            "centerline":self._lengths([item["center"] for item in cross]),
            "right":self._lengths([item["right"] for item in cross])}
        # A shared-station dz must satisfy every physical edge.  Consequently
        # the shortest edge interval governs the maximum admissible dz for
        # that cross-section pair.
        max_drop_by_segment=[max_slope*min(a,b,c) for a,b,c in zip(
            segment_lengths["left"],segment_lengths["centerline"],segment_lengths["right"])]
        maximum_redistributable_drop=sum(max_drop_by_segment)
        required_drop=profile["start_z"]-profile["target_end_z"]
        redistribution_possible=maximum_redistributable_drop+self.EPS>=required_drop
        faces=[];vertices=[]
        for item in cross:vertices.extend([item["left"],item["right"]])
        for i in range(len(cross)-1):faces.append([2*i,2*i+1,2*i+3,2*i+2])
        tin=self._at_station(cross,s1);tout=self._at_station(cross,s2);end=cross[-1]
        failures=[]
        if max(map(abs,left_grades),default=0)>max_slope+tolerance:failures.append("left_edge_local_grade_exceeds_maximum")
        if max(map(abs,center_grades),default=0)>max_slope+tolerance:failures.append("centerline_local_grade_exceeds_maximum")
        if max(map(abs,right_grades),default=0)>max_slope+tolerance:failures.append("right_edge_local_grade_exceeds_maximum")
        if end["level_error"]>tolerance:failures.append("curved_ramp_end_cross_section_not_level")
        if abs(end["center"][2]-profile["target_end_z"])>tolerance:failures.append("curved_ramp_end_elevation_mismatch")
        if any(item["level_error"]>tolerance for item in cross):failures.append("curved_ramp_surface_twisted")
        return {"contract":"CurvedRampStationedSurfaceV1","geometry_status":"resolved" if not failures else "not_feasible",
            "failure_reasons":failures,"station_authority":"centerline","crossfall":0.0,
            "centerline_stations":[item["station"] for item in cross],
            "centerline_xy":[item["center"][:2] for item in cross],"centerline_z":[item["center"][2] for item in cross],
            "left_edge_xy":[item["left"][:2] for item in cross],"left_edge_z":[item["left"][2] for item in cross],
            "right_edge_xy":[item["right"][:2] for item in cross],"right_edge_z":[item["right"][2] for item in cross],
            "cross_sections":cross,"local_grade_centerline":center_grades,"local_grade_left_edge":left_grades,
            "local_grade_right_edge":right_grades,"maximum_abs_grade_centerline":max(map(abs,center_grades),default=0),
            "maximum_abs_grade_left_edge":max(map(abs,left_grades),default=0),
            "maximum_abs_grade_right_edge":max(map(abs,right_grades),default=0),
            "segment_horizontal_lengths":segment_lengths,"maximum_drop_by_shared_station_segment":max_drop_by_segment,
            "required_vertical_drop":required_drop,"maximum_redistributable_vertical_drop":maximum_redistributable_drop,
            "vertical_drop_shortfall":max(0.0,required_drop-maximum_redistributable_drop),
            "grade_redistribution_status":"possible_for_fixed_geometry" if redistribution_possible else "insufficient_fixed_geometry_length",
            "minimum_additional_governing_edge_length_at_15_percent":max(0.0,required_drop-maximum_redistributable_drop)/max_slope,
            "tangent_in_cross_section":tin,"tangent_out_cross_section":tout,"end_cross_section":end,
            "end_left_z":end["left"][2],"end_center_z":end["center"][2],"end_right_z":end["right"][2],
            "end_cross_section_level_error":end["level_error"],"surface_twist_status":"untwisted" if not any(item["level_error"]>tolerance for item in cross) else "twisted",
            "surface_3d":{"vertices":vertices,"faces":faces,"cross_section_vertex_order":"left_right_by_centerline_station"}}

    def _tangent(self,t,samples,index,station,s1,s2):
        if station<=s1+self.EPS:return list(t["leg_1_heading"])
        if station>=s2-self.EPS:return list(t["leg_2_heading"])
        before=samples[max(0,index-1)];after=samples[min(len(samples)-1,index+1)]
        return self._unit([after[0]-before[0],after[1]-before[1]])

    @staticmethod
    def _width(station,s1,s2,s3,entry,curve,terminal):
        if station<=s1:return entry+(curve-entry)*(station/s1 if s1 else 1)
        if station<=s2:return curve
        return curve+(terminal-curve)*((station-s2)/(s3-s2) if s3>s2 else 1)

    @staticmethod
    def _grades(points):
        result=[]
        for a,b in zip(points,points[1:]):
            distance=hypot(b[0]-a[0],b[1]-a[1]);result.append((a[2]-b[2])/distance if distance>1e-12 else 0.0)
        return result

    @staticmethod
    def _lengths(points):
        return [hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(points,points[1:])]

    @staticmethod
    def _at_station(cross,station):return min(cross,key=lambda item:abs(item["station"]-station))

    @staticmethod
    def _unit(v):
        n=hypot(v[0],v[1]);return [v[0]/n,v[1]/n]
