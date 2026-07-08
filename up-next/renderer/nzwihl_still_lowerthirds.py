#!/usr/bin/env python3
"""Batch-render NZWIHL still-frame Up Next overlays (Lower Third + Lower Third with Wings)
for every women's matchup. Transparent 1920x1080 PNGs to drop on the countdown still."""
import os, glob, itertools, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE=os.path.dirname(os.path.abspath(__file__)); REPO=os.path.abspath(os.path.join(HERE,"..",".."))
FONTS=f"{HERE}/fonts"; LOGOS=f"{REPO}/assets/logos"
OUT=os.environ.get("OUT_DIR", os.path.join(os.getcwd(),"out")); os.makedirs(OUT,exist_ok=True)
INTER=f"{FONTS}/Inter[opsz,wght].ttf"; OSWALD=f"{FONTS}/Oswald[wght].ttf"
W,H=1920,1080
GOLD=(247,190,17); GOLD_BR=(255,205,46); WHITE=(255,255,255); INK=(8,8,10)

TEAMS={
 "steel":   dict(token="Steel",        lines=["AUCKLAND","STEEL"],   logo="Auckland-Steel-White.png",
    band_top=(22,36,60),  band_bot=(8,14,26),  accent=(150,166,188), name=(178,192,210)),
 "inferno": dict(token="Inferno",      lines=["CANTERBURY","INFERNO"],logo="Inferno-White.png",
    band_top=(104,8,22),  band_bot=(34,2,8),   accent=(255,179,71),  name=(255,186,92)),
 "thunder_w":dict(token="ThunderWomen",lines=["DUNEDIN","THUNDER"],  logo="thunder-women-white.png",
    band_top=(6,52,36),   band_bot=(3,20,14),  accent=(253,173,25),  name=(253,180,42)),
 "wild":    dict(token="Wild",         lines=["WAKATIPU","WILD"],    logo="Wakatipu-wild-white.png",
    band_top=(250,200,5), band_bot=(208,148,4),accent=(29,48,86),    name=(29,48,86), stroke2=WHITE),
}

def var_font(path,size,weight,opsz=None):
    f=ImageFont.truetype(path,size)
    try:
        vals=[]
        for ax in f.get_variation_axes():
            nm=ax['name']; nm=nm.decode() if isinstance(nm,bytes) else nm
            if nm.lower()=='weight': vals.append(weight)
            elif nm.lower() in ('optical size','opsz'): vals.append(opsz if opsz else ax.get('default',ax['minimum']))
            else: vals.append(ax.get('default',ax['minimum']))
        if vals: f.set_variation_by_axes(vals)
    except Exception: pass
    return f
def font_cap(path,weight,cap_px,opsz=None):
    f=var_font(path,80,weight,opsz); b=f.getbbox("H"); ch=max(1,b[3]-b[1])
    return var_font(path,max(8,int(round(80*cap_px/ch))),weight,opsz)
def tsize(text,font,tr=0):
    w=sum(font.getlength(c)+tr for c in text)
    if text: w-=tr
    a,d=font.getmetrics(); return w,a+d
def sprite(text,font,fill,tr=0,sw=0,sf=(0,0,0,255),pad=10):
    w,h=tsize(text,font,tr); im=Image.new("RGBA",(int(w)+pad*2+sw*2,int(h)+pad*2+sw*2),(0,0,0,0))
    d=ImageDraw.Draw(im); x=pad+sw; y=pad+sw
    fc=fill if len(fill)==4 else fill+(255,); sc=sf if len(sf)==4 else sf+(255,)
    for c in text: d.text((x,y),c,font=font,fill=fc,stroke_width=sw,stroke_fill=sc); x+=font.getlength(c)+tr
    return im
def fit_logo(path,target_h,max_w=99999,thr=40):
    im=Image.open(path).convert("RGBA"); a=np.array(im)[:,:,3]
    ys,xs=np.where(a>thr); x0,y0,x1,y1=xs.min(),ys.min(),xs.max()+1,ys.max()+1
    cw,ch=x1-x0,y1-y0; s=target_h/ch
    if cw*s>max_w: s=max_w/cw
    im2=im.resize((max(1,round(im.width*s)),max(1,round(im.height*s))),Image.LANCZOS)
    a2=np.array(im2)[:,:,3]; ys2,xs2=np.where(a2>thr)
    return im2.crop((xs2.min(),ys2.min(),xs2.max()+1,ys2.max()+1))
def paste_c(base,im,cx,cy,alpha=1.0):
    base.alpha_composite(im,(int(cx-im.width/2),int(cy-im.height/2)))
def trim(im,thr=10):
    """Crop to opaque content bbox so downstream width math reflects what's actually
    visible (sprite() pads its canvas by `pad`, which would otherwise throw off
    edge/gap measurements)."""
    a=np.array(im)[:,:,3]; ys,xs=np.where(a>thr)
    if len(xs)==0: return im
    return im.crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1))

# LOWER STRIP layout (2026-07-08, second pass -- CENTRE-symmetric, matches NZIHL):
# The previous fix anchored logo/name from each frame EDGE (equal 150px margins,
# equal 100px logo->name gaps). That equalises the OUTER margins, but the eye
# reads this graphic from the centre outward -- "UP NEXT" sits at 960 and the two
# name blocks / logos are judged by their distance from it. Because each team's
# logo+name renders at a different width, edge-anchoring pushed wider teams'
# blocks closer to centre than narrower teams' (Steel-v-Inferno: Steel's name
# ~47px farther from UP NEXT than Inferno's) -- visibly lopsided where it matters.
# Now using the SAME treatment as the NZIHL heroes (overlay.py: logos ±665,
# names ±360, both mirrored about 960): every block is CENTRED on a fixed anchor
# mirrored about x=960, so logo centres and name-block centres are exactly
# equidistant from centre for every matchup. Outer edge margins now vary a little
# per team (85-127px) -- that's the correct trade-off; nobody perceives edge
# margins, everyone perceives centre balance. Anchor maths (widest cases):
# widest logo 150px at ±800 -> inner edge 725 from centre; widest name 261px at
# ±555 -> spans 424.5..685.5 from centre; logo->name gap worst case ~40px
# (Inferno, widest logo AND name), typical ~70px; name inner edge clears the
# "UP NEXT"+dashes cluster (~±277) by >=147px. No collision risk.
LOGO_CX_OFF = 800   # centre of each logo sits at 960 -/+ this, BOTH sides
NAME_CX_OFF = 555   # centre of each name block sits at 960 -/+ this, BOTH sides
LOGO_H      = 96    # SAME target logo height both sides
def vgrad_rgba(w,h,top,bot,alpha=0.95):
    t=np.linspace(0,1,h)[:,None]; arr=np.zeros((h,w,4),np.float32)
    for i in range(3): arr[:,:,i]=(top[i]*(1-t)+bot[i]*t)/255.
    arr[:,:,3]=alpha; return Image.fromarray((arr*255).astype(np.uint8),"RGBA")
def name_font(cap): return font_cap(INTER,700,cap,opsz=30)

# ---------------------------------------------------------------- A — LOWER STRIP
def build_a(L,R):
    base=Image.new("RGBA",(W,H),(0,0,0,0)); top,h=924,156; slope=-0.37; seam_cy=top+h/2
    def sx(y): return 960+slope*(y-seam_cy)
    LL=np.array(vgrad_rgba(W,h,L['band_top'],L['band_bot'])); RR=np.array(vgrad_rgba(W,h,R['band_top'],R['band_bot']))
    band=np.zeros((h,W,4),np.uint8)
    for yy in range(h):
        ax=int(sx(top+yy)); band[yy,:ax]=LL[yy,:ax]; band[yy,ax:]=RR[yy,ax:]; band[yy,:,3]=int(0.95*255)
    for yy in range(5):
        ax=int(sx(top+yy)); band[yy,:ax,:3]=L['accent']; band[yy,ax:,:3]=R['accent']; band[yy,:,3]=255
    base.alpha_composite(Image.fromarray(band,"RGBA"),(0,top))
    gl=Image.new("L",(W,H),0); ImageDraw.Draw(gl).line([(sx(top),top),(sx(top+h),top+h)],fill=255,width=6)
    gl=gl.filter(ImageFilter.GaussianBlur(7)); ga=np.array(gl).astype(np.float32)/255.
    go=np.zeros((H,W,4),np.uint8); go[:,:,0],go[:,:,1],go[:,:,2]=GOLD_BR; go[:,:,3]=(ga*150).astype(np.uint8)
    base.alpha_composite(Image.fromarray(go,"RGBA"))
    cy=top+h/2
    # CENTRE-symmetric layout (2026-07-08 second pass): every block CENTRED on a
    # fixed anchor mirrored about x=960, same as the NZIHL heroes. See constants
    # block above for the rationale and clearance maths.
    lL=fit_logo(f"{LOGOS}/{L['logo']}",LOGO_H,max_w=150); lR=fit_logo(f"{LOGOS}/{R['logo']}",LOGO_H,max_w=150)
    nf1=name_font(26); nf2=name_font(34)
    l1=trim(sprite(L['lines'][0],nf1,WHITE,tr=2,sw=3,sf=INK))
    l2=trim(sprite(L['lines'][1],nf2,L['name'],tr=2,sw=3,sf=L.get('stroke2',INK)))
    r1=trim(sprite(R['lines'][0],nf1,WHITE,tr=2,sw=3,sf=INK))
    r2=trim(sprite(R['lines'][1],nf2,R['name'],tr=2,sw=3,sf=R.get('stroke2',INK)))

    logoL_cx = 960 - LOGO_CX_OFF; logoR_cx = 960 + LOGO_CX_OFF
    nameL_cx = 960 - NAME_CX_OFF; nameR_cx = 960 + NAME_CX_OFF

    paste_c(base,lL,logoL_cx,cy); paste_c(base,lR,logoR_cx,cy)
    paste_c(base,l1,nameL_cx,cy-24); paste_c(base,l2,nameL_cx,cy+18)
    paste_c(base,r1,nameR_cx,cy-24); paste_c(base,r2,nameR_cx,cy+18)
    unf=font_cap(OSWALD,600,38); tr=14
    paste_c(base,sprite("UP NEXT",unf,WHITE,tr=tr),960,cy)
    lw,_=tsize("UP NEXT",unf,tr); dl=ImageDraw.Draw(base)
    for sgn in(-1,1):
        xi=960+sgn*(lw/2+34); xo=xi+sgn*78
        dl.line([(xi,cy),(xo,cy)],fill=GOLD+(235,),width=3)
        dd=7; dl.polygon([(xi,cy-dd),(xi+sgn*dd,cy),(xi,cy+dd),(xi-sgn*dd,cy)],fill=GOLD_BR+(255,))
    return base

# ---------------------------------------------------------------- G — HYBRID
def build_g(L,R):
    base=Image.new("RGBA",(W,H),(0,0,0,0))
    pw,skew=315,0; wtop,wbot=430,724; wph=wbot-wtop
    def wing(t,left):
        cv=np.zeros((wph,pw+skew,4),np.uint8); g=np.array(vgrad_rgba(pw+skew,wph,t['band_top'],t['band_bot'],alpha=0.96))
        for yy in range(wph):
            off=int(skew*(yy/wph))
            if left:
                x1=pw+off; cv[yy,:x1]=g[yy,:x1]; cv[yy,:x1,3]=int(0.96*255); cv[yy,max(0,x1-4):x1,:3]=t['accent']; cv[yy,max(0,x1-4):x1,3]=255
            else:
                x0=skew-off; cv[yy,x0:]=g[yy,x0:]; cv[yy,x0:,3]=int(0.96*255); cv[yy,x0:x0+4,:3]=t['accent']; cv[yy,x0:x0+4,3]=255
        return Image.fromarray(cv,"RGBA")
    base.alpha_composite(wing(L,True),(0,wtop)); base.alpha_composite(wing(R,False),(W-(pw+skew),wtop))
    lcx,rcx=160,W-160; wcy=(wtop+wbot)//2; LOGO_H,LOGO_MAXW=250,270
    lL=fit_logo(f"{LOGOS}/{L['logo']}",LOGO_H,max_w=LOGO_MAXW); lR=fit_logo(f"{LOGOS}/{R['logo']}",LOGO_H,max_w=LOGO_MAXW)
    paste_c(base,lL,lcx,wcy); paste_c(base,lR,rcx,wcy)
    top,h=924,156; slope=-0.37; seam_cy=top+h/2
    def sx(y): return 960+slope*(y-seam_cy)
    LL=np.array(vgrad_rgba(W,h,L['band_top'],L['band_bot'])); RR=np.array(vgrad_rgba(W,h,R['band_top'],R['band_bot']))
    band=np.zeros((h,W,4),np.uint8)
    for yy in range(h):
        ax=int(sx(top+yy)); band[yy,:ax]=LL[yy,:ax]; band[yy,ax:]=RR[yy,ax:]; band[yy,:,3]=int(0.95*255)
    for yy in range(5):
        ax=int(sx(top+yy)); band[yy,:ax,:3]=L['accent']; band[yy,ax:,:3]=R['accent']; band[yy,:,3]=255
    base.alpha_composite(Image.fromarray(band,"RGBA"),(0,top))
    gl=Image.new("L",(W,H),0); ImageDraw.Draw(gl).line([(sx(top),top),(sx(top+h),top+h)],fill=255,width=6)
    gl=gl.filter(ImageFilter.GaussianBlur(7)); ga=np.array(gl).astype(np.float32)/255.
    go=np.zeros((H,W,4),np.uint8); go[:,:,0],go[:,:,1],go[:,:,2]=GOLD_BR; go[:,:,3]=(ga*150).astype(np.uint8)
    base.alpha_composite(Image.fromarray(go,"RGBA"))
    cy=top+h/2; nbf1=name_font(26); nbf2=name_font(40)
    def bnm(t,cx):
        paste_c(base,sprite(t['lines'][0],nbf1,WHITE,tr=2,sw=3,sf=INK),cx,cy-24)
        paste_c(base,sprite(t['lines'][1],nbf2,t['name'],tr=2,sw=3,sf=t.get('stroke2',INK)),cx,cy+18)
    bnm(L,360); bnm(R,1560)
    unf=font_cap(OSWALD,600,38); tr=12
    paste_c(base,sprite("COMING UP NEXT",unf,WHITE,tr=tr),960,cy)
    lw,_=tsize("COMING UP NEXT",unf,tr); dl=ImageDraw.Draw(base)
    for sgn in(-1,1):
        xi=960+sgn*(lw/2+30); xo=xi+sgn*62
        dl.line([(xi,cy),(xo,cy)],fill=GOLD+(235,),width=3)
        dd=7; dl.polygon([(xi,cy-dd),(xi+sgn*dd,cy),(xi,cy+dd),(xi-sgn*dd,cy)],fill=GOLD_BR+(255,))
    return base

keys=["steel","inferno","thunder_w","wild"]
n=0
for hk,ak in itertools.permutations(keys,2):
    L,R=TEAMS[hk],TEAMS[ak]; d=f"{OUT}/{L['token']}"; os.makedirs(d,exist_ok=True)
    build_a(L,R).save(f"{d}/NZWIHL_UpNext_{L['token']}_v_{R['token']}_LowerThird.png",compress_level=6)
    build_g(L,R).save(f"{d}/NZWIHL_UpNext_{L['token']}_v_{R['token']}_LowerThirdWithWings.png",compress_level=6)
    n+=2
print(f"rendered {n} overlays into {OUT}")
