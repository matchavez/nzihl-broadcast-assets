#!/usr/bin/env python3
"""
NZIHL / NZWIHL "UP NEXT" broadcast overlay — TEMPLATE.
Transparent 1920x1080. Top band: centred UP NEXT. Bottom band: two teams split by a
diagonal seam that EXACTLY matches the slant of the "I" in the centred league mark.

Configure a matchup with environment variables:
    LEAGUE = nzihl | nzwihl            (centre mark + seam; default nzihl)
    LEFT   = <team key>                (left team;  default red_devils)
    RIGHT  = <team key>                (right team; default admirals)   [OPP= still works]

Team keys: red_devils admirals thunder stampede swarm mako   (NZIHL)
           steel inferno thunder_w wild                       (NZWIHL)

Modes:
    python overlay.py still            -> hero PNG (transparent 1920x1080)
    python overlay.py bottombar        -> bottom bar only: full-1080 frame + tight crop
    python overlay.py intro|loop ...   -> animation frames (see render_range)

Example:
    LEAGUE=nzwihl LEFT=steel RIGHT=inferno python overlay.py still
"""
import os, sys, math, argparse, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------- paths
# Auto-detect the current sandbox session mount so this doesn't break between runs.
_ROOTS = sorted(glob.glob("/sessions/*/mnt/NZIHL and NZWIHL Broadcast Assets"))
BASE  = _ROOTS[0] if _ROOTS else "/sessions/_/mnt/NZIHL and NZWIHL Broadcast Assets"
_SESS = BASE.split("/mnt/")[0]
FONTS = f"{_SESS}/mnt/outputs/fonts"
OUT   = f"{_SESS}/mnt/outputs/regen"
LOGOS = f"{BASE}/Style Guide/Team Logos"
LEAGUE_LOGOS = f"{BASE}/Style Guide/League & Cup Logos"
ANTON  = f"{FONTS}/Anton-Regular.ttf"
OSWALD = f"{FONTS}/Oswald[wght].ttf"
INTER  = f"{FONTS}/Inter[opsz,wght].ttf"

# Team-name font. SF Pro is Apple-proprietary; Inter is the near-identical free match.
NAME_FONT, NAME_WEIGHT, NAME_OPSZ, NAME_CAP = INTER, 700, 30, 39

# ================================================================ REGISTRY
# Each team: token (filename), name lines, logo file, render height, band gradient
# (top/bottom rgb), accent (top rule), name (line-2 colour). Line 1 is always white.
TEAMS = {
 # ---- NZIHL (men) ----
 "red_devils": dict(token="RedDevils", lines=["CANTERBURY","RED DEVILS"], logo="Red Devils 2000x2000r.png", h=178, logo_h=165,
    band_top=(48,7,7),    band_bot=(13,4,4),   accent=(220,0,0),     name=(240,38,38)),
 "admirals":   dict(token="Admirals", lines=["PURE NZ","ADMIRALS"], logo="Pure-NZ-Admirals-2000x2000.png", h=196,
    band_top=(10,27,62),  band_bot=(5,12,30),  accent=(247,190,17),  name=(255,205,46)),
 "thunder":    dict(token="Thunder", lines=["DUNEDIN","THUNDER"], logo="Dunedin_Thunder.png", h=182, logo_h=165,
    band_top=(6,52,36),   band_bot=(3,20,14),  accent=(253,173,25),  name=(253,180,42)),
 "stampede":   dict(token="Stampede", lines=["SKYCITY","STAMPEDE"], logo="Skycity Stampede 2000x2000.png", h=182,
    band_top=(250,206,22), band_bot=(214,150,4), accent=(12,27,58),  name=(12,27,58), stroke2=(255,255,255)),
 "swarm":      dict(token="Swarm", lines=["BOTANY","SWARM"], logo="Botany Swarm 2000x2000.png", h=186,
    band_top=(74,28,44),  band_bot=(28,10,16), accent=(247,175,40),  name=(247,186,64)),
 "mako":       dict(token="Mako", lines=["AUCKLAND","MAKO"], logo="Auckland Mako 2000x2000.png", h=188,
    band_top=(46,49,55),  band_bot=(16,17,21), accent=(190,200,210), name=(202,212,222)),
 # ---- NZWIHL (women) — white logos on colour bands ----
 "steel":      dict(token="Steel", lines=["AUCKLAND","STEEL"], logo="Auckland-Steel-White.png", h=178, logo_h=160,
    band_top=(22,36,60),  band_bot=(8,14,26),  accent=(150,166,188), name=(178,192,210)),
 "inferno":    dict(token="Inferno", lines=["CANTERBURY","INFERNO"], logo="Inferno-White.png", h=178,
    band_top=(104,8,22),  band_bot=(34,2,8),   accent=(255,179,71),  name=(255,186,92)),
 "thunder_w":  dict(token="ThunderWomen", lines=["DUNEDIN","THUNDER"], logo="thunder-women-white.png", h=182, logo_h=164, logo_dy=-5,
    band_top=(6,52,36),   band_bot=(3,20,14),  accent=(253,173,25),  name=(253,180,42)),
 "wild":       dict(token="Wild", lines=["WAKATIPU","WILD"], logo="Wakatipu-wild-white.png", h=182,
    band_top=(250,200,5), band_bot=(208,148,4), accent=(29,48,86), name=(29,48,86), stroke2=(255,255,255)),
}

# Each league: centre mark + the geometry of its italic letters (measured from the logo).
#   ow,oh   = original logo px size       slope = letter dx/dy (italic slant)
#   i_x,i_y = "I" centroid in original px (used to PLACE the logo)
#   h       = render height of the centre mark
#   ix,iy   = where the I should sit in the 1920x1080 frame
#   seam_ox = original-x column the colour seam runs through (NZIHL: through the I;
#             NZWIHL: in the gap between the W and the I)
LEAGUES = {
 "nzihl":  dict(name="NZIHL",  logo="NZIHL-White-2000.png",        ow=2000, oh=1143, h=116,
    i_x=1093.6, i_y=489.0,  slope=-0.3671, ix=969.5, iy=945.6, seam_ox=1093.6, glow=(255,205,46)),
 "nzwihl": dict(name="NZWIHL", logo="NZWIHL-Logo-White-1000px.png", ow=1000, oh=255,  h=74,
    i_x=661.1,  i_y=127.5,  slope=-0.3685, ix=960.0, iy=946.0, seam_ox=620.0,  glow=(255,205,46),
    match_mark=True, mark_scale=1.10),
}

LEAGUE_KEY = os.environ.get("LEAGUE","nzihl").lower()
LG   = LEAGUES[LEAGUE_KEY]
LEFT  = TEAMS[os.environ.get("LEFT","red_devils").lower()]
RIGHT = TEAMS[os.environ.get("RIGHT", os.environ.get("OPP","admirals")).lower()]

# ---------------------------------------------------------------- look
W, H = 1920, 1080
FPS, INTRO_S, LOOP_S = 30, 5.0, 10.0
RED=(220,0,0); GOLD=(247,190,17); GOLD_BR=(255,205,46); NAVY=(8,29,72); WHITE=(255,255,255); INK=(8,8,10)
TOP_LABEL = "UP NEXT"
TOP_H   = 152
BOT_TOP = 840
BOT_H   = H - BOT_TOP

# Centre league-mark MATCH TARGET = the men's NZIHL wordmark exactly as it renders
# now (big letters only, subtitle excluded): width 196 px, opaque centre (960.0, 945.47).
# Any league with 'match_mark' is scaled+placed to land its wordmark in this same box,
# so NZIHL and NZWIHL marks share identical width and centre. NZIHL itself does NOT set
# the flag, so its placement is untouched.
MARK_W, MARK_CX, MARK_CY = 196.0, 960.0, 945.47

# Team-logo sizing: scale EVERY team logo to the same opaque content height so they read
# at a consistent size (then crop-to-content + centre on the anchor). A logo that would
# exceed MAX_LOGO_W at that height is reined in by width instead, so wide marks (Inferno,
# Admirals, Swarm) don't dominate. Tune TARGET_LOGO_H to grow/shrink all logos at once.
TARGET_LOGO_H, MAX_LOGO_W = 150, 190

# ---------------------------------------------------------------- easing
def clamp(x,a=0.0,b=1.0): return max(a,min(b,x))
def ease_out_cubic(x): x=clamp(x); return 1-(1-x)**3
def ease_out_back(x,s=1.70158): x=clamp(x); x-=1.0; return 1+(s+1)*x**3+s*x*x
def seg(t,a,b): return (1.0 if t>=b else 0.0) if b<=a else clamp((t-a)/(b-a))

# ---------------------------------------------------------------- fonts / text
def load_var(path,size,weight):
    f=ImageFont.truetype(path,size)
    try:
        vals=[]
        for ax in f.get_variation_axes():
            nm=ax['name']; nm=nm.decode() if isinstance(nm,bytes) else nm
            vals.append(weight if nm.lower()=='weight' else ax.get('default',ax['minimum']))
        f.set_variation_by_axes(vals)
    except Exception: pass
    return f
def text_size(text,font,tracking=0):
    w=sum(font.getlength(ch)+tracking for ch in text)
    if text: w-=tracking
    asc,desc=font.getmetrics(); return w,asc+desc
def make_text_sprite(text,font,fill,tracking=0,stroke_w=0,stroke_fill=(0,0,0,255),pad=8):
    w,h=text_size(text,font,tracking)
    W_=int(w)+pad*2+stroke_w*2; H_=int(h)+pad*2+stroke_w*2
    img=Image.new("RGBA",(W_,H_),(0,0,0,0)); d=ImageDraw.Draw(img)
    x=pad+stroke_w; y=pad+stroke_w
    fc=fill if len(fill)==4 else fill+(255,); sc=stroke_fill if len(stroke_fill)==4 else stroke_fill+(255,)
    for ch in text:
        d.text((x,y),ch,font=font,fill=fc,stroke_width=stroke_w,stroke_fill=sc); x+=font.getlength(ch)+tracking
    return img
def make_glow(sprite,color,blur=12,gain=1.6):
    a=np.array(sprite)[:,:,3].astype(np.float32)/255.0; pad=int(blur*3); h,w=a.shape
    c=np.zeros((h+pad*2,w+pad*2),np.float32); c[pad:pad+h,pad:pad+w]=a
    g=np.clip(np.array(Image.fromarray((c*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))).astype(np.float32)/255.0*gain,0,1)
    out=np.zeros((g.shape[0],g.shape[1],4),np.uint8)
    out[:,:,0]=color[0]; out[:,:,1]=color[1]; out[:,:,2]=color[2]; out[:,:,3]=(g*255).astype(np.uint8)
    return Image.fromarray(out,"RGBA")

# ---------------------------------------------------------------- compositing
def to_arr(img): return np.asarray(img,dtype=np.float32)/255.0
def new_canvas(): return np.zeros((H,W,4),np.float32)
def over(dst,src,x,y,alpha=1.0):
    sh,sw=src.shape[:2]; x=int(round(x)); y=int(round(y))
    x0=max(0,x); y0=max(0,y); x1=min(W,x+sw); y1=min(H,y+sh)
    if x0>=x1 or y0>=y1: return
    s=src[y0-y:y1-y, x0-x:x1-x]; d=dst[y0:y1,x0:x1]; sa=s[:,:,3:4]*alpha
    d[:,:,:3]=s[:,:,:3]*sa+d[:,:,:3]*(1-sa); d[:,:,3:4]=sa+d[:,:,3:4]*(1-sa)
def _scaled(img,scale):
    return img if abs(scale-1.0)<1e-3 else img.resize((max(1,int(img.width*scale)),max(1,int(img.height*scale))),Image.LANCZOS)
def over_anchor(dst,img,x,y,anchor='cc',scale=1.0,alpha=1.0):
    img=_scaled(img,scale); w,h=img.width,img.height
    ax = x-w/2 if anchor[0]=='c' else (x if anchor[0]=='l' else x-w)
    over(dst,to_arr(img),ax,y-h/2,alpha)

def vgrad(w,h,top,bot):
    t=np.linspace(0,1,h)[:,None]; arr=np.zeros((h,w,3),np.float32)
    for i in range(3): arr[:,:,i]=(top[i]*(1-t)+bot[i]*t)/255.0
    return arr
def fit_logo(path,target_h):
    im=Image.open(path).convert("RGBA"); s=target_h/im.height
    return im.resize((max(1,int(im.width*s)),target_h),Image.LANCZOS)
def fit_logo_uniform(path,target_h=None,max_w=None,logo_dx=0,logo_dy=0,thr=40):
    """Size a team logo by its OPAQUE content (not its canvas) so every team reads at
    the same visual size: scale so content height == target_h (per-team logo_h or the
    global TARGET_LOGO_H), but if that makes the content wider than MAX_LOGO_W, scale by
    width instead (reins in wide marks like Inferno). Returned sprite is cropped to
    content, so its centre == content centre and over_anchor('cc') lands the midpoint on
    the anchor. logo_dx/logo_dy (render px) re-centre on a focal point (e.g. a logo whose
    real visual centre isn't its bbox centre) by asymmetric transparent padding."""
    target_h = TARGET_LOGO_H if target_h is None else target_h
    max_w    = MAX_LOGO_W if max_w is None else max_w
    im=Image.open(path).convert("RGBA"); a=np.array(im)[:,:,3]
    ys,xs=np.where(a>thr); x0,y0,x1,y1=xs.min(),ys.min(),xs.max()+1,ys.max()+1
    cw,ch=x1-x0,y1-y0
    s=target_h/ch
    if cw*s>max_w: s=max_w/cw                      # width cap for disproportionately wide logos
    im2=im.resize((max(1,round(im.width*s)),max(1,round(im.height*s))),Image.LANCZOS)
    a2=np.array(im2)[:,:,3]; ys2,xs2=np.where(a2>thr)
    sp=im2.crop((xs2.min(),ys2.min(),xs2.max()+1,ys2.max()+1))
    if logo_dx or logo_dy:                          # bake a shift: pad one side by 2*shift
        pl=int(round(2*logo_dx)) if logo_dx>0 else 0; pr=int(round(-2*logo_dx)) if logo_dx<0 else 0
        pt=int(round(2*logo_dy)) if logo_dy>0 else 0; pb=int(round(-2*logo_dy)) if logo_dy<0 else 0
        cv=Image.new("RGBA",(sp.width+pl+pr,sp.height+pt+pb),(0,0,0,0)); cv.alpha_composite(sp,(pl,pt)); sp=cv
    return sp

# ================================================================ build (once)
print(f"building [{LG['name']}] {LEFT['token']} v {RIGHT['token']} ...", file=sys.stderr)
f_upnext = load_var(OSWALD,72,600)
def _load_sized(path,weight,opsz,cap_px):
    def mk(sz):
        f=ImageFont.truetype(path,sz)
        try:
            vals=[]
            for ax in f.get_variation_axes():
                nm=ax['name']; nm=nm.decode() if isinstance(nm,bytes) else nm
                if nm.lower()=='weight': vals.append(weight)
                elif nm.lower() in ('optical size','opsz'): vals.append(opsz)
                else: vals.append(ax.get('default',ax['minimum']))
            if vals: f.set_variation_by_axes(vals)
        except Exception: pass
        return f
    f=mk(80); b=f.getbbox("H"); ch=max(1,b[3]-b[1]); return mk(max(8,int(round(80*cap_px/ch))))
f_name = _load_sized(NAME_FONT,NAME_WEIGHT,NAME_OPSZ,NAME_CAP)

left_logo  = fit_logo_uniform(f"{LOGOS}/{LEFT['logo']}",  target_h=LEFT.get('logo_h'),  logo_dx=LEFT.get('logo_dx',0),  logo_dy=LEFT.get('logo_dy',0))
right_logo = fit_logo_uniform(f"{LOGOS}/{RIGHT['logo']}", target_h=RIGHT.get('logo_h'), logo_dx=RIGHT.get('logo_dx',0), logo_dy=RIGHT.get('logo_dy',0))
# Centre mark. NZIHL: original height-based fit (locked). match_mark leagues (NZWIHL):
# float-scale so the wordmark's opaque width == MARK_W (the men's wordmark width).
if LG.get('match_mark'):
    _lf = Image.open(f"{LEAGUE_LOGOS}/{LG['logo']}").convert("RGBA")
    _bb = _lf.getbbox(); _cw = _bb[2]-_bb[0]
    _sc = MARK_W * LG.get('mark_scale', 1.0) / _cw   # mark_scale lets a league run bigger/smaller than the men's mark
    cen_logo = _lf.resize((max(1,round(_lf.width*_sc)), max(1,round(_lf.height*_sc))), Image.LANCZOS)
else:
    cen_logo = fit_logo(f"{LEAGUE_LOGOS}/{LG['logo']}", LG['h'])

# layout
UPNEXT_CX, UPNEXT_CY = W//2, TOP_H//2-4
LEFT_CX,  LOGO_CY = 295, 956        # logos equidistant from centre (±665)
RIGHT_CX          = 1625
NAMEL_CX, NAMER_CX = 600, 1320      # centred two-line name blocks (±360)
NAME_Y1, NAME_Y2 = 933, 983

# centre mark placement
_S   = LG['h']/LG['oh']
if LG.get('match_mark'):
    # place so the wordmark's opaque centre lands EXACTLY at (MARK_CX, MARK_CY) —
    # i.e. identical centre + width to the men's NZIHL wordmark.
    _b2 = cen_logo.getbbox(); _ccx=(_b2[0]+_b2[2])/2; _ccy=(_b2[1]+_b2[3])/2
    MID_CX = MARK_CX - (_ccx - cen_logo.width/2)
    MID_CY = MARK_CY - (_ccy - cen_logo.height/2)
else:
    MID_CX = LG['ix'] - (LG['i_x']-LG['ow']/2)*_S          # place logo so its "I" sits at (ix,iy)
    MID_CY = LG['iy'] - (LG['i_y']-LG['oh']/2)*_S
SEAM_SLOPE = LG['slope']
# Seam anchored to the FRAME centre: it passes through (960, 960) — the vertical
# midpoint of the bottom bar — independent of the league-mark/logo placement.
SEAM_CENTER_Y = (BOT_TOP + H) / 2.0                    # = 960
def seam_x(y): return 960.0 + SEAM_SLOPE*(y - SEAM_CENTER_Y)

def build_top_base():
    body=vgrad(W,TOP_H,(14,14,16),(8,8,10))
    base=np.concatenate([body,np.full((TOP_H,W,1),0.90,np.float32)],axis=2)
    lh=4; xs=np.linspace(0,1,W)
    def l3(c1,c2,tt): return [c1[i]*(1-tt)+c2[i]*tt for i in range(3)]
    line=np.zeros((lh,W,4),np.float32)
    for x in range(W):
        tt=xs[x]; c=l3(RED,GOLD,tt*2) if tt<0.5 else l3(GOLD,NAVY,(tt-0.5)*2)
        line[:,x,0]=c[0]/255; line[:,x,1]=c[1]/255; line[:,x,2]=c[2]/255; line[:,x,3]=1.0
    base[TOP_H-lh:TOP_H]=line
    img=Image.fromarray((np.clip(base,0,1)*255).astype(np.uint8),"RGBA")
    d=ImageDraw.Draw(img); y=UPNEXT_CY
    lw,_=text_size(TOP_LABEL,f_upnext,tracking=12); half=lw/2; gap=46; rule=150
    for sgn in (-1,1):
        xin=W//2+sgn*(half+gap); xout=xin+sgn*rule
        d.line([(xin,y),(xout,y)],fill=GOLD+(230,),width=3)
        dd=6; d.polygon([(xin,y-dd),(xin+dd,y),(xin,y+dd),(xin-dd,y)],fill=GOLD_BR+(255,))
    return img
top_base=build_top_base()

def build_bottom_half(side):
    T = LEFT if side=='L' else RIGHT
    img=np.zeros((H,W,4),np.float32)
    body=vgrad(W,BOT_H,T['band_top'],T['band_bot']); accent=T['accent']
    band=np.zeros((BOT_H,W,4),np.float32); band[:,:,:3]=body
    for yy in range(BOT_H):
        ax=int(seam_x(BOT_TOP+yy))
        if side=='L': band[yy,:ax,3]=0.93
        else:         band[yy,ax:,3]=0.93
    for yy in range(5):
        ax=int(seam_x(BOT_TOP+yy))
        if side=='L': band[yy,:ax,:3]=np.array(accent)/255; band[yy,:ax,3]=1.0
        else:         band[yy,ax:,:3]=np.array(accent)/255; band[yy,ax:,3]=1.0
    img[BOT_TOP:BOT_TOP+BOT_H]=band
    return Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8),"RGBA")
bot_L=build_bottom_half('L'); bot_R=build_bottom_half('R')

def build_seam_glow():
    img=Image.new("L",(W,H),0); d=ImageDraw.Draw(img)
    d.line([(seam_x(BOT_TOP),BOT_TOP),(seam_x(H-1),H-1)],fill=255,width=6)
    img=img.filter(ImageFilter.GaussianBlur(8)); g=np.array(img).astype(np.float32)/255.0
    gc=LG['glow']; out=np.zeros((H,W,4),np.uint8)
    out[:,:,0]=gc[0]; out[:,:,1]=gc[1]; out[:,:,2]=gc[2]; out[:,:,3]=(g*255).astype(np.uint8)
    return Image.fromarray(out,"RGBA")
seam_glow=build_seam_glow()

sp_upnext   = make_text_sprite(TOP_LABEL,f_upnext,WHITE,tracking=12)
sp_upnext_g = make_glow(sp_upnext,(240,38,38),blur=16,gain=1.9)
sp_L1=make_text_sprite(LEFT['lines'][0], f_name,LEFT.get('name1',WHITE),  tracking=2,stroke_w=3,stroke_fill=LEFT.get('stroke',INK))
sp_L2=make_text_sprite(LEFT['lines'][1], f_name,LEFT['name'], tracking=2,stroke_w=3,stroke_fill=LEFT.get('stroke2',LEFT.get('stroke',INK)))
sp_R1=make_text_sprite(RIGHT['lines'][0],f_name,RIGHT.get('name1',WHITE), tracking=2,stroke_w=3,stroke_fill=RIGHT.get('stroke',INK))
sp_R2=make_text_sprite(RIGHT['lines'][1],f_name,RIGHT['name'],tracking=2,stroke_w=3,stroke_fill=RIGHT.get('stroke2',RIGHT.get('stroke',INK)))
cen_glow=make_glow(cen_logo,WHITE,blur=18,gain=1.3)

TOP_BASE_A=to_arr(top_base); BOT_L_A=to_arr(bot_L); BOT_R_A=to_arr(bot_R); SEAM_A=to_arr(seam_glow)
cov=np.zeros((H,W),np.float32)
cov[0:TOP_H]=np.maximum(cov[0:TOP_H],TOP_BASE_A[:TOP_H,:,3])
cov=np.maximum(cov,BOT_L_A[:,:,3]); cov=np.maximum(cov,BOT_R_A[:,:,3])

def apply_shimmer(dst,phase):
    xc=-350+(W+700)*phase; half=260.0; cols=np.arange(W,dtype=np.float32)
    prof=np.clip(1-((cols-xc)/half)**2,0,1)**1.5
    a=(cov*prof[None,:]*0.26).astype(np.float32)[:,:,None]
    dst[:,:,:3]=a+dst[:,:,:3]*(1-a); dst[:,:,3:4]=a+dst[:,:,3:4]*(1-a)

# ================================================================ composition
def compose_intro(t):
    dst=new_canvas()
    top_y=-TOP_H*(1-ease_out_cubic(seg(t,0.0,0.65))); over(dst,TOP_BASE_A,0,top_y,1.0)
    tp=seg(t,0.55,1.1)
    if tp>0:
        s=0.85+0.15*ease_out_back(tp)
        over_anchor(dst,sp_upnext_g,UPNEXT_CX,UPNEXT_CY+top_y,'cc',alpha=0.65*tp)
        over_anchor(dst,sp_upnext,UPNEXT_CX,UPNEXT_CY+top_y,'cc',scale=s,alpha=tp)
    dxL=-(W*0.55)*(1-ease_out_cubic(seg(t,0.30,1.0))); dxR=(W*0.55)*(1-ease_out_cubic(seg(t,0.38,1.05)))
    over(dst,BOT_L_A,dxL,0,1.0); over(dst,BOT_R_A,dxR,0,1.0)
    gL=dxL*(1-ease_out_cubic(seg(t,0.5,1.05))); gR=dxR*(1-ease_out_cubic(seg(t,0.55,1.1)))
    lp=seg(t,0.85,1.45); rp=seg(t,0.93,1.5)
    if lp>0: over_anchor(dst,left_logo, LEFT_CX+gL, LOGO_CY,'cc',scale=0.6+0.4*ease_out_back(lp),alpha=clamp(lp*1.4))
    if rp>0: over_anchor(dst,right_logo,RIGHT_CX+gR,LOGO_CY,'cc',scale=0.6+0.4*ease_out_back(rp),alpha=clamp(rp*1.4))
    nl=seg(t,1.1,1.7); nr=seg(t,1.17,1.77)
    if nl>0:
        over_anchor(dst,sp_L1,NAMEL_CX+gL,NAME_Y1,'cc',alpha=nl); over_anchor(dst,sp_L2,NAMEL_CX+gL,NAME_Y2,'cc',alpha=nl)
    if nr>0:
        over_anchor(dst,sp_R1,NAMER_CX+gR,NAME_Y1,'cc',alpha=nr); over_anchor(dst,sp_R2,NAMER_CX+gR,NAME_Y2,'cc',alpha=nr)
    sg=seg(t,1.0,2.2)
    if sg>0: over(dst,SEAM_A,0,0,alpha=0.20*sg)
    mp=seg(t,1.35,1.9)
    if mp>0:
        sc=1.5-0.5*ease_out_cubic(mp)
        over_anchor(dst,cen_glow,MID_CX,MID_CY,'cc',scale=sc,alpha=0.5*mp)
        over_anchor(dst,cen_logo,MID_CX,MID_CY,'cc',scale=sc,alpha=clamp(mp*1.5))
    return dst

def compose_loop(tl):
    dst=new_canvas()
    over(dst,TOP_BASE_A,0,0,1.0); over(dst,BOT_L_A,0,0,1.0); over(dst,BOT_R_A,0,0,1.0)
    over(dst,SEAM_A,0,0,alpha=0.20+0.12*math.sin(2*math.pi*tl/2.5))
    over_anchor(dst,sp_upnext_g,UPNEXT_CX,UPNEXT_CY,'cc',alpha=0.45+0.40*(0.5+0.5*math.sin(2*math.pi*tl/2.5)))
    over_anchor(dst,sp_upnext,UPNEXT_CX,UPNEXT_CY,'cc',alpha=1.0)
    floL=3.5*math.sin(2*math.pi*tl/5.0); floR=3.5*math.sin(2*math.pi*tl/5.0+math.pi)
    over_anchor(dst,left_logo, LEFT_CX, LOGO_CY+floL,'cc',alpha=1.0)
    over_anchor(dst,right_logo,RIGHT_CX,LOGO_CY+floR,'cc',alpha=1.0)
    over_anchor(dst,sp_L1,NAMEL_CX,NAME_Y1,'cc',alpha=1.0); over_anchor(dst,sp_L2,NAMEL_CX,NAME_Y2,'cc',alpha=1.0)
    over_anchor(dst,sp_R1,NAMER_CX,NAME_Y1,'cc',alpha=1.0); over_anchor(dst,sp_R2,NAMER_CX,NAME_Y2,'cc',alpha=1.0)
    over_anchor(dst,cen_glow,MID_CX,MID_CY,'cc',alpha=0.30+0.25*(0.5+0.5*math.sin(2*math.pi*tl/2.5)))
    over_anchor(dst,cen_logo,MID_CX,MID_CY,'cc',scale=1.0+0.015*math.sin(2*math.pi*tl/2.5),alpha=1.0)
    apply_shimmer(dst,(tl%5.0)/5.0)
    return dst

def save_png(dst,path): Image.fromarray((np.clip(dst,0,1)*255).astype(np.uint8),"RGBA").save(path,compress_level=6)

# ================================================================ CLI
def _stub(): return f"{LG['name']}_UpNext_{LEFT['token']}_v_{RIGHT['token']}"
def render_range(kind,start,end,outdir):
    os.makedirs(outdir,exist_ok=True)
    for i in range(start,end):
        t=i/FPS; save_png(compose_intro(t) if kind=="intro" else compose_loop(t), f"{outdir}/f_{i:05d}.png")
    print(f"{kind}: {start}..{end}",file=sys.stderr)
def still():
    p=f"{OUT}/{_stub()}_HERO.png"; save_png(compose_loop(0.0),p); print("still:",p,file=sys.stderr)
def bottombar():
    dst=compose_loop(0.0); dst[0:BOT_TOP,:,:]=0.0
    img=Image.fromarray((np.clip(dst,0,1)*255).astype(np.uint8),"RGBA")
    f1=f"{OUT}/{_stub()}_BottomBar_1080frame.png"; img.save(f1)
    bbox=img.getbbox(); crop=img.crop((0,bbox[1],W,H)); f2=f"{OUT}/{_stub()}_BottomBar.png"; crop.save(f2)
    print("bottombar:",f1,"|",f2,file=sys.stderr)
if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=["intro","loop","still","bottombar"])
    ap.add_argument("--start",type=int,default=0); ap.add_argument("--end",type=int,default=0)
    ap.add_argument("--outdir",default=f"{OUT}/frames"); a=ap.parse_args()
    if a.mode=="still": still()
    elif a.mode=="bottombar": bottombar()
    else: render_range(a.mode,a.start,a.end,a.outdir)
