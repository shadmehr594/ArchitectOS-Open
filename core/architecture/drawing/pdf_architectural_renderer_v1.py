from __future__ import annotations
from math import cos, radians, sin
from pathlib import Path
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None; get_display = lambda x: x

class PdfArchitecturalRenderer:
    """Native ReportLab renderer. It never reads or converts SVG."""
    def __init__(self):
        fonts=[Path('C:/Windows/Fonts/tahoma.ttf'),Path('C:/Windows/Fonts/arial.ttf')]
        self.font='Helvetica'
        for f in fonts:
            if f.exists(): pdfmetrics.registerFont(TTFont('ArchitectFA',str(f))); self.font='ArchitectFA'; break
        self.s=32; self.ox=120; self.oy=735
    def _p(self,x,y):
        # ReportLab's origin is bottom-left while the canonical architectural
        # scene uses NORTH at increasing Y.  Mirror only at the PDF view
        # boundary so SOUTH/street stays at the sheet bottom and geometry,
        # SVG and semantic source proofs retain their canonical coordinates.
        return self.ox+x*self.s, self.oy-(20.0-y)*self.s
    def _txt(self,t): return get_display(arabic_reshaper.reshape(t)) if arabic_reshaper and any('\u0600'<=c<='\u06ff' for c in t) else t
    def render(self,scene,path):
        c=canvas.Canvas(str(path),pagesize=landscape(A3),pageCompression=1); c.setTitle(f'ArchitectOS Candidate {scene.candidate_id} native vector plan')
        c.setFillColorRGB(.985,.98,.96); c.rect(0,0,*landscape(A3),fill=1,stroke=0)
        for p in scene.primitives: self._item(c,p)
        c.setFillColorRGB(.1,.1,.1); c.setFont(self.font,9); c.drawString(25,20,'NATIVE VECTOR PDF - generated directly from ArchitecturalDrawingScene')
        c.showPage(); c.save()
    def render_many(self, scenes, path):
        c=canvas.Canvas(str(path),pagesize=landscape(A3),pageCompression=1); c.setTitle('ArchitectOS multi-candidate native vector comparison')
        for scene in scenes:
            c.setFillColorRGB(.985,.98,.96); c.rect(0,0,*landscape(A3),fill=1,stroke=0)
            for p in scene.primitives: self._item(c,p)
            c.setFillColorRGB(.1,.1,.1); c.setFont(self.font,9); c.drawString(25,20,f'NATIVE VECTOR COMPARISON - CANDIDATE {scene.candidate_id} - PAGE {scenes.index(scene)+1}/4')
            c.showPage()
        c.save()
    def _style(self,c,st):
        c.setLineWidth(max(.6,st.get('line_width',.03)*self.s)); c.setStrokeColor(st.get('stroke','#222')); c.setFillColor(st.get('fill','#ffffff') if st.get('fill')!='none' else '#ffffff'); c.setDash([6,4] if st.get('dash') else [])
    def _item(self,c,p):
        g=p.geometry; self._style(c,p.style)
        if p.kind=='POLYGON':
            if 'rect' in g:
                r=g['rect']; x,y=self._p(r['x'],r['y']); c.rect(x,y-r['h']*self.s,r['w']*self.s,r['h']*self.s,fill=1 if p.style.get('fill')!='none' else 0,stroke=1); return
            pts=[self._p(*z) for z in g['points']]; path=c.beginPath(); path.moveTo(*pts[0]); [path.lineTo(*z) for z in pts[1:]]; path.close(); c.drawPath(path,fill=1 if p.style.get('fill')!='none' else 0,stroke=1); return
        if p.kind=='HATCH':
            x1,y1,x2,y2=g['rect']; step=max(.08,g.get('spacing',.25)); t=x1-(y2-y1)
            while t<=x2:
                ax=max(x1,t); ay=y1+max(0,x1-t); bx=min(x2,t+(y2-y1)); by=y1+min(y2-y1,x2-t)
                c.line(*self._p(ax,ay),*self._p(bx,by)); t+=step
            return
        if p.kind=='LINE': c.line(*self._p(g['x1'],g['y1']),*self._p(g['x2'],g['y2'])); return
        if p.kind=='POLYLINE':
            pts=[self._p(*z) for z in g['points']]; path=c.beginPath(); path.moveTo(*pts[0]); [path.lineTo(*z) for z in pts[1:]]; c.drawPath(path,fill=0,stroke=1); return
        if p.kind=='ARC':
            x,y=self._p(g['cx'],g['cy']); r=g['r']*self.s; c.arc(x-r,y-r,x+r,y+r,g['start'],g['extent']); return
        if p.kind=='TEXT':
            x,y=self._p(g['x'],g['y']); c.setFillColor('#111111'); c.setFont(self.font,max(7,g.get('size',.25)*self.s)); t=self._txt(g['text']);
            if p.style.get('align')=='center': c.drawCentredString(x,y,t)
            else: c.drawString(x,y,t)
            return
        if p.kind=='DIMENSION':
            x1,y1=self._p(*g['p1']); x2,y2=self._p(*g['p2']); c.line(x1,y1,x2,y2); c.setFont(self.font,8); c.drawCentredString((x1+x2)/2,(y1+y2)/2+3,g['text']); return
        if p.kind=='GROUP': self._symbol(c,g,p.layer)
    def _symbol(self,c,g,layer):
        # Reuse identical geometric semantics as SVG, expressed as native PDF primitives.
        x,y=self._p(g.get('x',0),g.get('y',0)); w=g.get('w',1)*self.s; h=g.get('h',1)*self.s; s=g.get('symbol','')
        if layer=='WINDOWS':
            axis=g['axis']; fixed=g['fixed']; a,b=g['a'],g['b']; t=g['thickness']; config=g.get('configuration','TWO_LEAF_CASEMENT'); c.setFillColor('#faf9f5');
            if axis=='H': xx,yy=self._p(a,fixed); ww=(b-a)*self.s; hh=t*self.s; c.rect(xx,yy-hh/2,ww,hh,fill=1,stroke=0); c.setStrokeColor('#1593b5'); c.rect(xx,yy-hh/2,ww,hh,fill=0,stroke=1); c.line(xx,yy,xx+ww,yy); origin=(xx,yy-hh/2)
            else: xx,yy=self._p(fixed,a); ww=t*self.s; hh=(b-a)*self.s; c.rect(xx-ww/2,yy,ww,hh,fill=1,stroke=0); c.setStrokeColor('#1593b5'); c.rect(xx-ww/2,yy,ww,hh,fill=0,stroke=1); c.line(xx,yy,xx,yy+hh); origin=(xx-ww/2,yy)
            panels={'MULTI_PANEL':3,'FIXED_PLUS_OPERABLE':3,'SLIDING_GLAZED_OPENING':2,'TWO_LEAF_CASEMENT':2}.get(config,1)
            for n in range(1,panels):
                if axis=='H': c.line(origin[0]+ww*n/panels,origin[1],origin[0]+ww*n/panels,origin[1]+hh)
                else: c.line(origin[0],origin[1]+hh*n/panels,origin[0]+ww,origin[1]+hh*n/panels)
            return
        if s=='NORTH_ARROW': c.setFillColor('#111'); path=c.beginPath(); path.moveTo(x+w/2,y+h); path.lineTo(x,y); path.lineTo(x+w,y); path.close(); c.drawPath(path,fill=1); c.drawCentredString(x+w/2,y+h+3,'N'); return
        if s=='PLANTER_TREE': c.setFillColor('#cfe8c9'); c.setStrokeColor('#39734b'); c.circle(x+w/2,y+h/2,min(w,h)/2,fill=1); c.line(x+w*.2,y+h*.5,x+w*.8,y+h*.5); c.line(x+w*.5,y+h*.2,x+w*.5,y+h*.8); return
        if g.get('vector_primitives'):
            colors={'frame':'#f8fafc','pillow':'#dbe4ec','seat':'#e7dfd3','arm':'#c9b9a5','table':'#f5efe5','chair':'#eee5d8','cabinet':'#dfe6e9','appliance':'#e5e7eb','counter':'#e7e5e4','fixture':'#eaf5f8','bowl':'#f7fcfd','drain':'#d9eef2','shaft':'#d1d5db','body':'#dbeafe','glass':'#bfdbfe','wheel':'#334155','canopy':'#cfe8c9','trunk':'#6b4f32','platform':'#ded6c6','steps':'#e8e0d2','planter':'#d7c4a6','shrub':'#a7d39d'}
            c.setStrokeColor('#52616b'); c.setLineWidth(.7)
            for p in g['vector_primitives']:
                c.setFillColor(colors.get(p.get('role'),'#ffffff')); k=p['kind']
                if k=='rect': c.roundRect(x+p['x']*w,y+p['y']*h,p['w']*w,p['h']*h,p.get('rx',0)*min(w,h),fill=1 if p.get('role') in colors else 0,stroke=1)
                elif k=='line': c.line(x+p['x1']*w,y+p['y1']*h,x+p['x2']*w,y+p['y2']*h)
                elif k=='circle': c.circle(x+p['cx']*w,y+p['cy']*h,p['r']*min(w,h),fill=1 if p.get('role') in colors else 0,stroke=1)
                elif k=='ellipse': c.ellipse(x+(p['cx']-p['rx'])*w,y+(p['cy']-p['ry'])*h,x+(p['cx']+p['rx'])*w,y+(p['cy']+p['ry'])*h,fill=1 if p.get('role') in colors else 0,stroke=1)
                elif k=='arc':
                    rr=p['r']*min(w,h); cx=x+p['cx']*w; cy=y+p['cy']*h; c.arc(cx-rr,cy-rr,cx+rr,cy+rr,p['start'],p['extent'])
            return
        c.setFillColor('#ffffff'); c.setStrokeColor('#475569'); c.roundRect(x,y,w,h,min(w,h)*.08,fill=1,stroke=1)
        if s=='PARKED_CAR': c.setFillColor('#dbeafe'); c.roundRect(x,y,w,h,8,fill=1,stroke=1); c.roundRect(x+w*.16,y+h*.2,w*.68,h*.6,5,fill=0,stroke=1)
        elif 'BED' in s: c.setFillColor('#e2e8f0'); c.rect(x+w*.08,y-h*.24,w*.38,h*.18,fill=1,stroke=1); c.rect(x+w*.54,y-h*.24,w*.38,h*.18,fill=1,stroke=1); c.line(x,y-h*.3,x+w,y-h*.3)
        elif 'SOFA' in s or s=='ARMCHAIR': c.setFillColor('#e7dfd3'); c.roundRect(x+w*.08,y-h*.77,w*.84,h*.62,4,fill=1,stroke=1); c.line(x+w*.33,y-h*.15,x+w*.33,y-h*.77); c.line(x+w*.66,y-h*.15,x+w*.66,y-h*.77)
        elif 'DINING' in s: c.ellipse(x+w*.08,y-h*.85,x+w*.92,y-h*.15,fill=0,stroke=1)
        elif s in {'WC_IRANIAN','WC_WESTERN','SINK'}: c.ellipse(x+w*.2,y-h*.8,x+w*.8,y-h*.25,fill=0,stroke=1)
        elif s=='COOKTOP':
            for dx in (.3,.7):
                for dy in (.3,.7): c.circle(x+w*dx,y-h*dy,4,fill=0,stroke=1)
        elif s=='SHOWER': c.line(x,y,x+w,y-h); c.circle(x+w*.5,y-h*.5,3,fill=0,stroke=1)
