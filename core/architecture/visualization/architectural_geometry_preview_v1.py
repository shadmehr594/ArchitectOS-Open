"""Tiny dependency-free PNG previews derived only from architecture geometry."""

import struct
import zlib


class ArchitecturalGeometryPreviewV1:
    WIDTH, HEIGHT = 1200, 900

    def plan(self, geometry, path, analysis_candidates=None):
        polygons = []
        site = geometry.get("site_geometry", {})
        self._add(polygons, site.get("parcel_boundary"), (80, 80, 80))
        for floor in geometry.get("floor_geometry", []):
            points = (floor.get("parcel_envelope") or {}).get("points")
            self._add(polygons, points, (30, 90, 180) if floor.get("floor") == "basement" else (120, 120, 120))
        for wall in geometry.get("physical_walls", []):
            if wall.get("floor") == "basement":
                self._add(polygons, [wall.get("start"), wall.get("end")], (0, 0, 0))
        for vertical in geometry.get("vertical_geometry", []):
            if vertical.get("type") == "stair_geometry":
                self._add(polygons, vertical.get("polygon"), (180, 90, 0))
        for candidate in analysis_candidates or []:
            self._add(polygons, candidate.get("driveway_corridor"), (210, 30, 45))
        return self._write(polygons, path)

    def model(self, geometry, path, analysis_candidates=None):
        shapes = []
        for wall in geometry.get("physical_walls", []):
            if wall.get("floor") == "basement":
                z = -2.4
                a, b = wall.get("start"), wall.get("end")
                if a and b:
                    self._add(shapes, [self._iso(a[0], a[1], z), self._iso(b[0], b[1], z)], (0, 0, 0))
                    self._add(shapes, [self._iso(a[0], a[1], z+2.4), self._iso(b[0], b[1], z+2.4)], (100, 100, 100))
        for candidate in analysis_candidates or []:
            line = candidate.get("driveway_centerline")
            if line:
                self._add(shapes, [self._iso(p[0], p[1], 0-2.4*i/max(1,len(line)-1)) for i,p in enumerate(line)], (210,30,45))
        return self._write(shapes, path)

    @staticmethod
    def _iso(x, y, z):
        return [x-y*0.45, (x+y)*0.32-z*2.2]

    @staticmethod
    def _add(store, points, color):
        if isinstance(points, list) and len(points) >= 2 and all(isinstance(p, (list, tuple)) and len(p) >= 2 for p in points):
            store.append(([[float(p[0]), float(p[1])] for p in points], color))

    def _write(self, shapes, path):
        all_points = [p for shape, _ in shapes for p in shape]
        if not all_points:
            raise ValueError("resolved geometry required for preview")
        xs, ys = [p[0] for p in all_points], [p[1] for p in all_points]
        margin = 55
        scale = min((self.WIDTH-2*margin)/max(max(xs)-min(xs), 1e-9),
                    (self.HEIGHT-2*margin)/max(max(ys)-min(ys), 1e-9))
        image = bytearray([255])*(self.WIDTH*self.HEIGHT*3)
        def screen(p):
            return (int(margin+(p[0]-min(xs))*scale),
                    int(self.HEIGHT-margin-(p[1]-min(ys))*scale))
        for points, color in shapes:
            closed = len(points) > 2
            pairs = list(zip(points, points[1:])) + ([(points[-1], points[0])] if closed else [])
            for a, b in pairs:
                self._line(image, screen(a), screen(b), color)
        raw = b"".join(b"\x00"+bytes(image[y*self.WIDTH*3:(y+1)*self.WIDTH*3]) for y in range(self.HEIGHT))
        def chunk(kind, data):
            return struct.pack(">I", len(data))+kind+data+struct.pack(">I", zlib.crc32(kind+data)&0xffffffff)
        png = b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", struct.pack(">IIBBBBB", self.WIDTH,self.HEIGHT,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(raw,9))+chunk(b"IEND",b"")
        with open(path, "wb") as handle:
            handle.write(png)
        return path

    def _line(self, image, a, b, color):
        x0,y0=a; x1,y1=b; dx=abs(x1-x0); sx=1 if x0<x1 else -1; dy=-abs(y1-y0); sy=1 if y0<y1 else -1; err=dx+dy
        while True:
            if 0<=x0<self.WIDTH and 0<=y0<self.HEIGHT:
                index=(y0*self.WIDTH+x0)*3; image[index:index+3]=bytes(color)
            if x0==x1 and y0==y1: break
            e2=2*err
            if e2>=dy: err+=dy; x0+=sx
            if e2<=dx: err+=dx; y0+=sy
