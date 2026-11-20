from __future__ import annotations
import html, math
from .architectural_scene_v1 import ArchitecturalDrawingScene

class SvgArchitecturalRenderer:
    def __init__(self, px_per_m=32): self.s=px_per_m; self.ox=120; self.oy=915
    def _p(self,x,y): return self.ox+x*self.s, self.oy-y*self.s
    def render(self, scene: ArchitecturalDrawingScene, path):
        q=['<svg xmlns="http://www.w3.org/2000/svg" width="1191" height="842" viewBox="0 0 1191 842">',
           '<rect width="100%" height="100%" fill="#faf9f5"/>','<g transform="translate(0,-180)">']
        for p in scene.primitives: q += self._item(p)
        q += ['</g>','<text x="35" y="810" font-family="DejaVu Sans" font-size="11">DIRECT SHARED SCENE / VECTOR SVG DEBUG OUTPUT</text>','</svg>']
        path.write_text(''.join(q),encoding='utf-8')
    def _item(self,p):
        g=p.geometry; st=p.style; sw=max(1,st.get('line_width',.03)*self.s); stroke=st.get('stroke','#222'); fill=st.get('fill','none'); dash=' stroke-dasharray="8 5"' if st.get('dash') else ''
        if p.kind=='POLYGON':
            pts=g.get('points');
            if 'rect' in g:
                r=g['rect']; x,y=self._p(r['x'],r['y']+r['h']); return [f'<rect x="{x}" y="{y}" width="{r["w"]*self.s}" height="{r["h"]*self.s}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>']
            return [f'<polygon points="{" ".join(f"{self._p(*z)[0]},{self._p(*z)[1]}" for z in pts)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>']
        if p.kind=='HATCH':
            x1,y1,x2,y2=g['rect']; step=max(.08,g.get('spacing',.25)); out=[]; t=x1-(y2-y1)
            while t<=x2:
                ax=max(x1,t); ay=y1+max(0,x1-t); bx=min(x2,t+(y2-y1)); by=y1+min(y2-y1,x2-t)
                p1=self._p(ax,ay); p2=self._p(bx,by); out.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="{stroke}" stroke-width="{sw}"/>'); t+=step
            return out
        if p.kind in {'LINE','POLYLINE'}:
            pts=[[g['x1'],g['y1']],[g['x2'],g['y2']]] if p.kind=='LINE' else g['points']; tag='line' if p.kind=='LINE' else 'polyline'; a=' '.join(f'{self._p(*z)[0]},{self._p(*z)[1]}' for z in pts)
            return [f'<{tag} points="{a}" fill="none" stroke="{stroke}" stroke-width="{sw}"{dash}/>' if tag=='polyline' else f'<line x1="{self._p(*pts[0])[0]}" y1="{self._p(*pts[0])[1]}" x2="{self._p(*pts[1])[0]}" y2="{self._p(*pts[1])[1]}" stroke="{stroke}" stroke-width="{sw}"{dash}/>']
        if p.kind=='ARC':
            cx,cy=self._p(g['cx'],g['cy']); r=g['r']*self.s; a=math.radians(g['start']); b=math.radians(g['start']+g['extent']); x1=cx+r*math.cos(a); y1=cy-r*math.sin(a); x2=cx+r*math.cos(b); y2=cy-r*math.sin(b)
            return [f'<path d="M{x1},{y1} A{r},{r} 0 0 0 {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>']
        if p.kind=='TEXT':
            x,y=self._p(g['x'],g['y']); anchor='middle' if st.get('align')=='center' else 'start'; return [f'<text x="{x}" y="{y}" font-family="DejaVu Sans" font-size="{g.get("size",.25)*self.s}" text-anchor="{anchor}" direction="rtl">{html.escape(g["text"])}</text>']
        if p.kind=='DIMENSION':
            x1,y1=self._p(*g['p1']); x2,y2=self._p(*g['p2']); return [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#555"/><text x="{(x1+x2)/2}" y="{(y1+y2)/2-5}" text-anchor="middle" font-size="11">{g["text"]}</text>']
        if p.kind=='GROUP': return self._symbol(g,p.layer)
        return []
    def _symbol(self,g,layer):
        s=g.get('symbol'); x,y=self._p(g.get('x',0),g.get('y',0)+g.get('h',0)); w=g.get('w',1)*self.s; h=g.get('h',1)*self.s
        if s=='NORTH_ARROW': return [f'<path d="M{x+w/2},{y} L{x},{y+h} L{x+w/2},{y+h*.72} L{x+w},{y+h} Z" fill="#111"/><text x="{x+w/2}" y="{y-5}" text-anchor="middle">N</text>']
        if s=='PLANTER_TREE': return [f'<circle cx="{x+w/2}" cy="{y+h/2}" r="{min(w,h)/2}" fill="#cfe8c9" stroke="#39734b"/><path d="M{x+w*.2},{y+h*.5} L{x+w*.8},{y+h*.5} M{x+w*.5},{y+h*.2} L{x+w*.5},{y+h*.8}" stroke="#39734b"/>']
        if s=='PARKED_CAR': return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#dbeafe" stroke="#1d4ed8"/><rect x="{x+w*.16}" y="{y+h*.2}" width="{w*.68}" height="{h*.6}" rx="8" fill="none" stroke="#1d4ed8"/>']
        if layer=='WINDOWS':
            axis=g['axis']; fixed=g['fixed']; a,b=g['a'],g['b']; t=g['thickness']; config=g.get('configuration','TWO_LEAF_CASEMENT')
            if axis=='H': xx,yy=self._p(a,fixed+t/2); ww=(b-a)*self.s; hh=t*self.s
            else: xx,yy=self._p(fixed-t/2,b); ww=t*self.s; hh=(b-a)*self.s
            out=[f'<rect x="{xx}" y="{yy}" width="{ww}" height="{hh}" fill="#faf9f5"/>',f'<rect x="{xx}" y="{yy}" width="{ww}" height="{hh}" fill="none" stroke="#1593b5" stroke-width="2"/>',f'<line x1="{xx+(ww/2 if axis=="V" else 0)}" y1="{yy+(0 if axis=="V" else hh/2)}" x2="{xx+(ww/2 if axis=="V" else ww)}" y2="{yy+(hh if axis=="V" else hh/2)}" stroke="#1593b5"/>']
            panels={'MULTI_PANEL':3,'FIXED_PLUS_OPERABLE':3,'SLIDING_GLAZED_OPENING':2,'TWO_LEAF_CASEMENT':2}.get(config,1)
            for n in range(1,panels):
                if axis=='H': out.append(f'<line x1="{xx+ww*n/panels}" y1="{yy}" x2="{xx+ww*n/panels}" y2="{yy+hh}" stroke="#1593b5"/>')
                else: out.append(f'<line x1="{xx}" y1="{yy+hh*n/panels}" x2="{xx+ww}" y2="{yy+hh*n/panels}" stroke="#1593b5"/>')
            return out
        if g.get('vector_primitives'):
            colors={'frame':'#475569','pillow':'#dbe4ec','seat':'#e7dfd3','arm':'#786b5b','table':'#f5efe5','chair':'#eee5d8','cabinet':'#dfe6e9','appliance':'#e5e7eb','counter':'#e7e5e4','fixture':'#eaf5f8','bowl':'#f7fcfd','drain':'#d9eef2','shaft':'#d1d5db','body':'#dbeafe','glass':'#bfdbfe','wheel':'#334155','canopy':'#cfe8c9','trunk':'#6b4f32','platform':'#ded6c6','steps':'#e8e0d2','rug':'none','planter':'#d7c4a6','shrub':'#a7d39d'}
            out=[]
            for p in g['vector_primitives']:
                role=p.get('role','detail'); fill=colors.get(role,'none'); stroke='#52616b'; k=p['kind']
                if k=='rect': out.append(f'<rect x="{x+p["x"]*w}" y="{y+p["y"]*h}" width="{p["w"]*w}" height="{p["h"]*h}" rx="{p.get("rx",0)*min(w,h)}" fill="{fill}" stroke="{stroke}" stroke-width="1.1"/>')
                elif k=='line': out.append(f'<line x1="{x+p["x1"]*w}" y1="{y+p["y1"]*h}" x2="{x+p["x2"]*w}" y2="{y+p["y2"]*h}" stroke="{stroke}" stroke-width="1.1"/>')
                elif k=='circle': out.append(f'<circle cx="{x+p["cx"]*w}" cy="{y+p["cy"]*h}" r="{p["r"]*min(w,h)}" fill="{fill}" stroke="{stroke}"/>')
                elif k=='ellipse': out.append(f'<ellipse cx="{x+p["cx"]*w}" cy="{y+p["cy"]*h}" rx="{p["rx"]*w}" ry="{p["ry"]*h}" fill="{fill}" stroke="{stroke}"/>')
                elif k=='arc': out.append(f'<circle cx="{x+p["cx"]*w}" cy="{y+p["cy"]*h}" r="{p["r"]*min(w,h)}" fill="none" stroke="{stroke}"/>')
            return out
        base=[f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{min(w,h)*.08}" fill="#fff" stroke="#475569" stroke-width="1.4"/>']
        if 'BED' in s: base += [f'<rect x="{x+w*.08}" y="{y+h*.06}" width="{w*.38}" height="{h*.18}" fill="#e2e8f0" stroke="#64748b"/>',f'<rect x="{x+w*.54}" y="{y+h*.06}" width="{w*.38}" height="{h*.18}" fill="#e2e8f0" stroke="#64748b"/>',f'<line x1="{x}" y1="{y+h*.3}" x2="{x+w}" y2="{y+h*.3}" stroke="#64748b"/>']
        elif 'SOFA' in s or s=='ARMCHAIR': base += [f'<rect x="{x+w*.08}" y="{y+h*.15}" width="{w*.84}" height="{h*.62}" rx="6" fill="#e7dfd3" stroke="#786b5b"/>',f'<line x1="{x+w*.33}" y1="{y+h*.15}" x2="{x+w*.33}" y2="{y+h*.77}" stroke="#786b5b"/><line x1="{x+w*.66}" y1="{y+h*.15}" x2="{x+w*.66}" y2="{y+h*.77}" stroke="#786b5b"/>']
        elif 'DINING' in s: base += [f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w*.42}" ry="{h*.35}" fill="#f5efe5" stroke="#6b5b45"/>']
        elif s in {'WC_IRANIAN','WC_WESTERN'}: base += [f'<ellipse cx="{x+w/2}" cy="{y+h*.58}" rx="{w*.28}" ry="{h*.27}" fill="none" stroke="#475569"/>']
        elif s=='SINK': base += [f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w*.28}" ry="{h*.25}" fill="none" stroke="#1593b5"/><circle cx="{x+w*.72}" cy="{y+h*.25}" r="2"/>']
        elif s=='COOKTOP': base += [f'<circle cx="{x+w*.3}" cy="{y+h*.3}" r="5" fill="none"/><circle cx="{x+w*.7}" cy="{y+h*.3}" r="5" fill="none"/><circle cx="{x+w*.3}" cy="{y+h*.7}" r="5" fill="none"/><circle cx="{x+w*.7}" cy="{y+h*.7}" r="5" fill="none"/>']
        elif s=='SHOWER': base += [f'<line x1="{x}" y1="{y}" x2="{x+w}" y2="{y+h}" stroke="#1593b5"/><circle cx="{x+w*.5}" cy="{y+h*.5}" r="3"/>']
        return base
