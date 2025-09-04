# Controls:
#   Look: Arrow Keys    Move: W/A/S/D
#   Fire: SPACE         Scope/Firemode: F
#   Jump: C             Map: Z
#   Cheat (x-ray): X    Swap AK/AWP: V
#   Frag: G             Smoke: T
#   End: Q              Menu: Esc (Enter to select)

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import time, math, random, sys, os

# ---------------- Window / Camera ----------------
win_w, win_h = 1280, 900
aspect = win_w / float(win_h)
FOVY_NORM, FOVY_ZOOM = 95.0, 38.0

zoomed = False
scope_on = False

# ---------------- Player ----------------
Px, Py, Pz = 0.0, -900.0, 0.0
Pangle, Pitch = 90.0, 0.0
Pspeed = 280.0
PLAYER_RADIUS = 20.0
EYE_HEIGHT = 65.0

# jump
Pvz = 0.0
JUMP_V0 = 420.0
GRAVITY_PLAYER = -980.0
GROUND_EPS = 0.01

# input state (no key-up callback; emulate release by timeout)
key_W = key_S = key_A = key_D = False
fire_hold = False
_key_last_time = {"w":0.0,"a":0.0,"s":0.0,"d":0.0,"space":0.0}
_key_hold_window = 0.15

# overlays
map_overlay = False
crosshair_on = True  # AK default

# time / session
play_time = 0.0
session_over = False
session_reason = "Quit"
menu_active = False
menu_choice = 0

# ---------------- World ----------------
grid_l, WALL_H = 1400, 170.0
MAZE = [
    (-grid_l,0,40,grid_l,WALL_H), (grid_l,0,40,grid_l,WALL_H),
    (0,-grid_l,grid_l,40,WALL_H), (0,grid_l,grid_l,40,WALL_H),
    (0,0,420,40,WALL_H), (0,420,300,40,WALL_H), (0,-420,300,40,WALL_H),
    (-600,0,40,420,WALL_H), (600,0,40,420,WALL_H),
    (-280,620,260,40,WALL_H), (280,-620,260,40,WALL_H),
    (-800,300,40,260,WALL_H), (800,-300,40,260,WALL_H),
    (-220,-240,140,40,WALL_H), (220,240,140,40,WALL_H),
]
CRATES = [
    (-150,60,60,60,120), (180,-120,70,50,120), (420,260,65,65,120),
    (-420,-260,65,65,120), (0,620,90,50,120), (0,-620,90,50,120),
    (820,60,80,80,120), (-820,-60,80,80,120), (520,520,80,70,120),
    (-520,-520,80,70,120), (260,880,70,60,120), (-260,-880,70,60,120)
]
def all_obstacles():
    for o in MAZE:  yield o
    for o in CRATES: yield o

# ---------------- Enemies ----------------
NUM_ENEMIES = 5
enemies = []   # dicts: {x,y,z,hp,next_shot}
HEAD_R = 14.0
BODY_W, BODY_H, BODY_D = 28.0, 50.0, 18.0
LEG_H = 20.0
ENEMY_RADIUS = 22.0
ENEMY_SPEED = 145.0

E_BULLETS = []
E_B_SPD   = 800.0
player_hp = 100
hs_for_heal = 0

# ---------------- Player bullets ----------------
bullets = []
AWP_SPEED, AWP_CD, B_LIFE, B_SIZE = 1600.0, 1.2, 1.25, 8.0
_last_shot = -1e9

# AK weapon
AK_SPEED = 1400.0
AK_CD_SINGLE = 0.14
AK_CD_AUTO   = 0.10
AK_BURST_SPACING = 0.07
weapon = "AK"            # "AK" or "AWP"
ak_mode = "single"       # "single" | "burst" | "auto"
ak_next_fire = 0.0
ak_burst_left = 0

# ---------------- Grenades / Smoke ----------------
GRAVITY = -900.0
grenades  = []
explosions= []  # visual rings (polyline)

SMOKES = []
SMOKE_EMIT_TIME   = 6.0
SMOKE_PUFF_LIFE   = 7.0
SMOKE_PUFF_SIZE   = 26.0
SMOKE_BURST_RATE  = 8
SMOKE_RADIUS_VIS  = 280.0

class Puff:
    __slots__=("x","y","z","vx","vy","vz","born")
    def __init__(self,x,y,z):
        self.x,self.y,self.z = x,y,z
        ang = random.uniform(0, 2*math.pi)
        self.vx = math.cos(ang)*30.0
        self.vy = math.sin(ang)*30.0
        self.vz = 120.0 + random.uniform(0,60)
        self.born = time.time()

FRAG_FUSE, FRAG_RADIUS = 2.0, 150.0

# ---------------- Stats / Feed ----------------
headshots = bodykills = grenade_kills = shots_fired = missed_shots = wallbang_kills = 0

# ---------------- Cheats ----------------
xray = False

# ---------------- Helpers ----------------
def clamp(v,lo,hi): return lo if v<lo else hi if v>hi else v
def circle_aabb(px,py,pr,cx,cy,sx,sy):
    dx=max(abs(px-cx)-sx,0.0); dy=max(abs(py-cy)-sy,0.0)
    return (dx*dx+dy*dy)<=pr*pr
def blocked(nx,ny):
    if abs(nx)>grid_l-PLAYER_RADIUS or abs(ny)>grid_l-PLAYER_RADIUS: return True
    for (cx,cy,sx,sy,h) in all_obstacles():
        if circle_aabb(nx,ny,PLAYER_RADIUS,cx,cy,sx,sy): return True
    return False
def enemy_blocked(nx,ny):
    if abs(nx)>grid_l-ENEMY_RADIUS or abs(ny)>grid_l-ENEMY_RADIUS: return True
    for (cx,cy,sx,sy,h) in all_obstacles():
        if circle_aabb(nx,ny,ENEMY_RADIUS,cx,cy,sx,sy): return True
    return False
def point_in_obstacle(px,py):
    for (cx,cy,sx,sy,h) in all_obstacles():
        if (cx-sx)<=px<=(cx+sx) and (cy-sy)<=py<=(cy+sy): return True
    return False
def right_vec_from_yaw(yaw):
    y=math.radians(yaw); return -math.sin(y), math.cos(y)
def norm2(x,y):
    d=math.hypot(x,y); return (x/d,y/d) if d else (0.0,0.0)

def has_line_of_sight(px,py, ex,ey, step=18.0):
    dx,dy=ex-px,ey-py; dist=math.hypot(dx,dy)
    if dist==0: return True
    ux,uy=dx/dist,dy/dist; t=0.0
    while t<=dist:
        x=px+ux*t; y=py+uy*t
        if point_in_obstacle(x,y): return False
        for s in SMOKES:
            for p in s["puffs"]:
                if (x-p.x)**2 + (y-p.y)**2 <= (SMOKE_RADIUS_VIS*0.45)**2:
                    return False
        t+=step
    return True

# ---- painter helpers (still template-safe)
def view_forward():
    y = math.radians(Pangle); p = math.radians(Pitch)
    return (math.cos(y)*math.cos(p), math.sin(y)*math.cos(p), math.sin(p))

def depth_to_cam(x, y, z):
    fx, fy, fz = view_forward()
    return (x - Px)*fx + (y - Py)*fy + (z - (Pz + EYE_HEIGHT))*fz

def box_nearest_depth(cx, cy, sx, sy, h):
    fx, fy, fz = view_forward()
    ez = Pz + EYE_HEIGHT
    mins = 1e9
    for dx in (-sx, sx):
        for dy in (-sy, sy):
            for dz in (0.0, h):
                d = (cx+dx - Px)*fx + (cy+dy - Py)*fy + (dz - ez)*fz
                if d < mins: mins = d
    return mins

def enemy_nearest_depth(e):
    dz = [e["z"], e["z"] + LEG_H + BODY_H + HEAD_R*2]
    return min(depth_to_cam(e["x"], e["y"], z) for z in dz)

def draw_box_single(cx, cy, sx, sy, h, color):
    glColor3f(*color)
    glPushMatrix(); glTranslatef(cx, cy, h*0.5); glScalef(sx*2, sy*2, h); glutSolidCube(1.0); glPopMatrix()

# ---------------- Camera ----------------
def setupCamera():
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(FOVY_ZOOM if (zoomed and weapon=="AWP") else FOVY_NORM, aspect, 0.1, 5000.0)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    ex,ey,ez=Px,Py,Pz+EYE_HEIGHT
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    gluLookAt(ex,ey,ez, ex+fx,ey+fy,ez+fz, 0,0,1)

# ---------------- Viewmodels ----------------
def draw_awp():
    if scope_on or menu_active or map_overlay: return
    ex,ey,ez=Px,Py,Pz+EYE_HEIGHT
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    rx,ry=right_vec_from_yaw(Pangle)
    side,drop,forward=14.0,10.0,22.0
    bx=ex+rx*side+fx*forward; by=ey+ry*side+fy*forward; bz=ez-drop+fz*2.0
    glPushMatrix(); glTranslatef(bx,by,bz); glRotatef(Pangle,0,0,1); glRotatef(-Pitch,0,1,0)
    glColor3f(0.18,0.18,0.18); glPushMatrix(); glScalef(40,10,10); glutSolidCube(1.0); glPopMatrix()
    glColor3f(0.28,0.28,0.28); glPushMatrix(); glTranslatef(22,0,0); glRotatef(90,0,1,0)
    gluCylinder(gluNewQuadric(),2.8,2.6,70,12,1); glPopMatrix()
    glColor3f(0.12,0.12,0.12); glPushMatrix(); glTranslatef(5,0,6); glRotatef(90,0,1,0)
    gluCylinder(gluNewQuadric(),3.5,3.2,20,12,1); glPopMatrix()
    glPopMatrix()

def draw_ak():
    if menu_active or map_overlay: return
    ex,ey,ez=Px,Py,Pz+EYE_HEIGHT
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    rx,ry=right_vec_from_yaw(Pangle)
    side,drop,forward=14.0,10.0,20.0
    bx=ex+rx*side+fx*forward; by=ey+ry*side+fy*forward; bz=ez-drop+fz*2.0
    glPushMatrix(); glTranslatef(bx,by,bz); glRotatef(Pangle,0,0,1); glRotatef(-Pitch,0,1,0)
    # ORANGE BODY (receiver/handguard/mag block)
    glColor3f(0.95,0.55,0.12); glPushMatrix(); glScalef(34,10,12); glutSolidCube(1.0); glPopMatrix()
    # black top cover attachment
    glColor3f(0.10,0.10,0.10); glPushMatrix(); glTranslatef(0,0,5); glScalef(24,6,4); glutSolidCube(1.0); glPopMatrix()
    # black pistol grip
    glColor3f(0.10,0.10,0.10); glPushMatrix(); glTranslatef(-10,-0, -6); glScalef(6,4,8); glutSolidCube(1.0); glPopMatrix()
    # gray barrel/muzzle
    glColor3f(0.65,0.65,0.65); glPushMatrix(); glTranslatef(16,0,2); glRotatef(90,0,1,0)
    gluCylinder(gluNewQuadric(),2.2,2.0,34,10,1); glPopMatrix()
    glPopMatrix()

def draw_weapon():
    if weapon=="AK": draw_ak()
    else: draw_awp()

def muzzle_world_pos():
    ex,ey,ez=Px,Py,Pz+EYE_HEIGHT
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    rx,ry=right_vec_from_yaw(Pangle)
    side,drop,forward = (14.0,10.0,22.0) if weapon=="AWP" else (14.0,10.0,18.0)
    return (ex+rx*side+fx*(forward+60), ey+ry*side+fy*(forward+60), ez-drop+fz*60)

# ---------------- Enemies ----------------
def draw_enemy(e, color=(0.0,0.6,0.0)):
    if map_overlay: return
    glPushMatrix(); glTranslatef(e["x"],e["y"],e["z"])
    glColor3f(color[0]*0.8,color[1]*0.8,color[2]*0.8)
    for s in (-BODY_W*0.25,BODY_W*0.25):
        glPushMatrix(); glTranslatef(s,0,LEG_H*0.5); glScalef(BODY_W*0.4,BODY_D*0.6,LEG_H); glutSolidCube(1.0); glPopMatrix()
    glColor3f(*color)
    glPushMatrix(); glTranslatef(0,0,LEG_H+BODY_H*0.5); glScalef(BODY_W,BODY_D,BODY_H); glutSolidCube(1.0); glPopMatrix()
    glColor3f(0,0,0); glPushMatrix(); glTranslatef(0,0,LEG_H+BODY_H+HEAD_R); gluSphere(gluNewQuadric(),HEAD_R,12,12); glPopMatrix()
    glColor3f(0.3,0.3,0.3); glPushMatrix(); glTranslatef(BODY_W*0.45,0,LEG_H+BODY_H*0.7); glRotatef(90,0,1,0)
    gluCylinder(gluNewQuadric(),3,2.5,25,12,1); glPopMatrix()
    glPopMatrix()

def spawn_enemy():
    while True:
        x=random.randint(-grid_l+100,grid_l-100); y=random.randint(-grid_l+100,grid_l-100)
        if not point_in_obstacle(x,y): return {"x":float(x),"y":float(y),"z":0.0,"hp":2,"next_shot":time.time()+9999}

def reset_enemies():
    global enemies; enemies=[spawn_enemy() for _ in range(NUM_ENEMIES)]

def update_enemies(dt):
    # enemies dodge player and strongly avoid boundaries
    prx,pry=right_vec_from_yaw(Pangle)
    for e in enemies:
        toE_x,toE_y=e["x"]-Px,e["y"]-Py
        s = 1.0 if (prx*toE_x + pry*toE_y) < 0.0 else -1.0
        awayx,awayy=norm2(toE_x,toE_y)
        sidex,sidey=prx*s,pry*s

        # edge avoidance force (push back when near borders)
        marginX = grid_l - abs(e["x"])
        marginY = grid_l - abs(e["y"])
        pushx = 0.0
        pushy = 0.0
        if marginX < 220:
            pushx = -math.copysign((220 - marginX)/220.0, e["x"])
        if marginY < 220:
            pushy = -math.copysign((220 - marginY)/220.0, e["y"])

        desx,desy=awayx*0.65+sidex*0.35 + pushx*1.2, awayy*0.65+sidey*0.35 + pushy*1.2
        dlen=math.hypot(desx,desy)
        if dlen>0: desx,desy=desx/dlen,desy/dlen

        base=ENEMY_SPEED; yaw=math.degrees(math.atan2(desy,desx))
        best=None
        for off in (0,+30,-30,+60,-60,+90,-90,+150,-150,+180):
            a=math.radians(yaw+off); dirx,diry=math.cos(a),math.sin(a)
            step=base*dt; nx,ny=e["x"]+dirx*step, e["y"]+diry*step
            if enemy_blocked(nx,ny): continue
            margin = min(grid_l-abs(nx), grid_l-abs(ny))
            score=margin + random.random()*0.3  # prefer safer-from-edge spots
            if (best is None) or (score>best[0]): best=(score,nx,ny)
        if best:
            e["x"],e["y"]=best[1],best[2]

        # hard clamp just in case
        e["x"]=clamp(e["x"], -grid_l+ENEMY_RADIUS, grid_l-ENEMY_RADIUS)
        e["y"]=clamp(e["y"], -grid_l+ENEMY_RADIUS, grid_l-ENEMY_RADIUS)

# enemy fire (starts at 10 kills)
def enemy_try_fire(now):
    total_kills=headshots+bodykills+grenade_kills
    if total_kills < 10 or map_overlay:
        return
    head_z = Pz + EYE_HEIGHT
    for e in enemies:
        if e["next_shot"] > now + 3.0:
            e["next_shot"] = now + random.uniform(0.4, 1.2)
        if now < e["next_shot"]: continue
        if not has_line_of_sight(e["x"],e["y"], Px,Py):
            e["next_shot"] = now + 0.6; continue
        tx,ty,tz = Px,Py,(head_z if random.random()<0.5 else Pz+BODY_H*0.6)
        dx,dy = tx-e["x"], ty-e["y"]; dist=max(1e-6, math.hypot(dx,dy))
        ux,uy = dx/dist, dy/dist
        rx,ry = -uy, ux
        origin_x = e["x"] + ux*18.0 + rx*6.0
        origin_y = e["y"] + uy*18.0 + ry*6.0
        origin_z = e["z"] + LEG_H + BODY_H*0.7
        dz = tz - origin_z; dist3 = math.sqrt((tx-origin_x)**2+(ty-origin_y)**2+dz*dz)
        vx,vy,vz = (tx-origin_x)/dist3, (ty-origin_y)/dist3, dz/dist3
        spread = 0.03
        vx += random.uniform(-spread,spread); vy += random.uniform(-spread,spread); vz += random.uniform(-spread,spread)
        d = math.sqrt(vx*vx+vy*vy+vz*vz); vx,vy,vz = vx/d,vy/d,vz/d
        E_BULLETS.append({"x":origin_x,"y":origin_y,"z":origin_z,
                          "vx":vx*E_B_SPD,"vy":vy*E_B_SPD,"vz":vz*E_B_SPD})
        e["next_shot"] = now + random.uniform(1.4, 2.6)

def step_enemy_bullets(dt):
    global player_hp
    alive=[]
    for b in E_BULLETS:
        nx=b["x"]+b["vx"]*dt; ny=b["y"]+b["vy"]*dt; nz=b["z"]+b["vz"]*dt
        if abs(nx)>grid_l or abs(ny)>grid_l or point_in_obstacle(nx,ny):
            continue
        # smoke blocks
        blocked_by_smoke=False
        for s in SMOKES:
            for p in s["puffs"]:
                if (nx-p.x)**2+(ny-p.y)**2 <= (SMOKE_RADIUS_VIS*0.55)**2:
                    blocked_by_smoke=True; break
            if blocked_by_smoke: break
        if blocked_by_smoke: continue
        headx,heady,headz = Px,Py,Pz+EYE_HEIGHT
        if (nx-headx)**2+(ny-heady)**2 <= (12.0**2) and abs(nz-headz)<=12.0:
            player_hp -= 25; print("[HIT BY ENEMY] HEAD -25  HP:", player_hp)
        elif (nx-Px)**2+(ny-Py)**2 <= (PLAYER_RADIUS**2) and Pz <= nz <= Pz+EYE_HEIGHT:
            player_hp -= 10; print("[HIT BY ENEMY] BODY -10  HP:", player_hp)
        else:
            b["x"],b["y"],b["z"]=nx,ny,nz; alive.append(b); continue
        if player_hp <= 0 and not session_over:
            end_session("Killed by Enemies")
    E_BULLETS[:] = alive

# ---------------- Logging ----------------
def log_shot(label): print(f"[SHOT] {label}")
def log_kill(label): print(f"[KILL] {label}")

# ---------------- Player bullets & firing ----------------
def player_fire_common(now, speed):
    global shots_fired
    shots_fired += 1
    mx,my,mz=muzzle_world_pos()
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    bullets.append({"x":mx,"y":my,"z":mz,"vx":fx*speed,"vy":fy*speed,"vz":fz*speed,"born":now,"hit":False})

def fire_awp(now):
    global _last_shot
    if now-_last_shot<AWP_CD: return
    _last_shot=now
    log_shot("AWP")
    player_fire_common(now, AWP_SPEED)

def apply_ak_recoil():
    global Pitch, Pangle
    Pitch = clamp(Pitch - 0.9, -60, 60)
    Pangle = (Pangle + random.uniform(-0.6,0.6)) % 360

def fire_ak(now):
    global ak_next_fire, ak_burst_left
    if ak_mode=="single":
        if now<ak_next_fire: return
        ak_next_fire = now + AK_CD_SINGLE
        log_shot("AK single")
        player_fire_common(now, AK_SPEED); apply_ak_recoil()
    elif ak_mode=="burst":
        if now<ak_next_fire: return
        ak_next_fire = now + AK_CD_SINGLE*1.5
        ak_burst_left = 2
        log_shot("AK burst (1/3)")
        player_fire_common(now, AK_SPEED); apply_ak_recoil()
    elif ak_mode=="auto":
        if now<ak_next_fire: return
        ak_next_fire = now + AK_CD_AUTO
        log_shot("AK auto")
        player_fire_common(now, AK_SPEED); apply_ak_recoil()

def step_ak_burst(now):
    global ak_burst_left, ak_next_fire
    if ak_burst_left>0 and now>=ak_next_fire-AK_CD_SINGLE*1.5 + AK_BURST_SPACING*(3-ak_burst_left):
        log_shot(f"AK burst ({3-ak_burst_left+1}/3)")
        player_fire_common(now, AK_SPEED); apply_ak_recoil()
        ak_burst_left -= 1

def step_bullets(dt,now):
    global enemies, headshots, bodykills, missed_shots, wallbang_kills, player_hp, hs_for_heal
    alive=[]
    for b in bullets:
        nx=b["x"]+b["vx"]*dt; ny=b["y"]+b["vy"]*dt; nz=b["z"]+b["vz"]*dt
        expired = (now-b["born"])>B_LIFE or abs(nx)>grid_l or abs(ny)>grid_l
        if expired and not b["hit"]:
            missed_shots+=1
            continue
        elif expired:
            continue
        hit=False
        for e in list(enemies):
            hx,hy,hz=e["x"],e["y"],e["z"]+LEG_H+BODY_H+HEAD_R
            wb = (not has_line_of_sight(Px,Py,e["x"],e["y"]))
            if (nx-hx)**2+(ny-hy)**2<=HEAD_R**2 and abs(nz-hz)<=HEAD_R:
                e["hp"]=0; headshots+=1; hs_for_heal+=1; hit=True; b["hit"]=True
                if player_hp<100 and hs_for_heal>=2:
                    player_hp = min(100, player_hp+10); hs_for_heal-=2
                if wb: wallbang_kills+=1
                log_kill("WALLBANG HEADSHOT" if wb else "HEADSHOT")
            elif (nx-e["x"])**2+(ny-e["y"])**2<=ENEMY_RADIUS**2 and e["z"]<=nz<=e["z"]+LEG_H+BODY_H:
                e["hp"]-=1; hit=True
                if e["hp"]<=0:
                    bodykills+=1
                    if wb: wallbang_kills+=1
                    log_kill("WALLBANG BODY" if wb else "BODY")
            if e["hp"]<=0:
                enemies.remove(e); enemies.append(spawn_enemy())
        if hit: continue
        b["x"],b["y"],b["z"]=nx,ny,nz; alive.append(b)
    bullets[:]=alive

# ---------------- Grenades / Smoke (opaque puffs; no blending) ----------------
def throw_grenade(type_):
    mx,my,mz=muzzle_world_pos()
    fx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
    fz=math.sin(math.radians(Pitch))
    speed=700.0 if type_=="frag" else 600.0
    grenades.append({"x":mx,"y":my,"z":mz,"vx":fx*speed,"vy":fy*speed,"vz":fz*speed+200.0,
                     "born":time.time(),"bounces":0,"type":type_,"exploded":False})

def _process_frag_explosion(x,y,z, now):
    global enemies, grenade_kills
    for e in list(enemies):
        dx,dy = e["x"]-x, e["y"]-y
        if dx*dx + dy*dy <= FRAG_RADIUS*FRAG_RADIUS:
            enemies.remove(e); enemies.append(spawn_enemy())
            grenade_kills += 1
            log_kill("GRENADE")

def step_grenades(dt,now):
    alive=[]
    for g in grenades:
        if g["exploded"]: continue
        nx,ny,nz=g["x"]+g["vx"]*dt, g["y"]+g["vy"]*dt, g["z"]+g["vz"]*dt
        g["vz"]+=GRAVITY*dt
        if abs(nx)>grid_l: g["vx"]*=-0.6; nx=clamp(nx,-grid_l,grid_l)
        if abs(ny)>grid_l: g["vy"]*=-0.6; ny=clamp(ny,-grid_l,grid_l)
        if nz<=0.0: nz=0.0; g["vz"]*=-0.35; g["vx"]*=0.85; g["vy"]*=0.85; g["bounces"]+=1
        if point_in_obstacle(nx,ny): g["vx"]*=-0.5; g["vy"]*=-0.5
        g["x"],g["y"],g["z"]=nx,ny,nz
        if (now-g["born"]>= (2.0 if g["type"]=="frag" else 1.2)) or g["bounces"]>=3:
            if g["type"]=="frag":
                explosions.append({"x":nx,"y":ny,"z":nz,"start":now})
                if (Px-nx)**2+(Py-ny)**2 <= FRAG_RADIUS**2:
                    end_session("Grenade Suicide")
                _process_frag_explosion(nx,ny,nz, now)
            else:
                SMOKES.append({"x":nx,"y":ny,"z":nz,"vx":g["vx"]*0.2,"vy":g["vy"]*0.2,"vz":max(0.0,g["vz"]*0.2),
                               "emit_end":now+SMOKE_EMIT_TIME,"puffs":[], "dead":False})
            g["exploded"]=True
        else:
            alive.append(g)
    grenades[:] = alive

def step_smokes(dt, now):
    alive_emitters=[]
    for s in SMOKES:
        if not s["dead"]:
            s["vz"] += GRAVITY*dt
            s["x"]  += s["vx"]*dt
            s["y"]  += s["vy"]*dt
            s["z"]  += s["vz"]*dt
            if s["z"] <= 0.0:
                s["z"]=0.0; s["vz"]*=-0.25; s["vx"]*=0.8; s["vy"]*=0.8
                if abs(s["vz"])<20.0: s["vz"]=0.0
            if point_in_obstacle(s["x"],s["y"]):
                s["vx"]*=-0.5; s["vy"]*=-0.5

        # Emit puffs while active
        if now <= s["emit_end"]:
            for _ in range(SMOKE_BURST_RATE):
                s["puffs"].append(Puff(s["x"]+random.uniform(-14,14),
                                       s["y"]+random.uniform(-14,14),
                                       s["z"]+10))

        # Update puffs
        alive=[]
        for p in s["puffs"]:
            age = now - p.born
            if age > SMOKE_PUFF_LIFE: 
                continue
            p.x += p.vx*dt*0.45; p.y += p.vy*dt*0.45; p.z += p.vz*dt*0.45
            p.vx *= 0.985; p.vy *= 0.985; p.vz *= 0.985
            if p.z > 220.0: p.vz *= 0.6
            alive.append(p)
        s["puffs"] = alive

        if now > s["emit_end"] and not s["puffs"]:
            s["dead"]=True
        if not s["dead"]:
            alive_emitters.append(s)
    SMOKES[:] = alive_emitters

def draw_grenades_and_smoke(now):
    if not menu_active and not map_overlay:
        for g in grenades:
            glPushMatrix(); glTranslatef(g["x"],g["y"],g["z"])
            glColor3f(0.3,0.3,0.3) if g["type"]=="frag" else glColor3f(0.6,0.6,0.6)
            glutSolidCube(16.0); glPopMatrix()
        # explosion ring (polyline with GL_LINES)
        new_ex=[]
        for e in explosions:
            t = now - e["start"]
            if t <= 0.6:
                r=40+t*240; glPushMatrix(); glTranslatef(e["x"],e["y"],e["z"]+10)
                glColor3f(0.95,0.55,0.10)
                glBegin(GL_LINES)
                lastx = None; lasty = None
                for i in range(37):
                    ang = 2*math.pi*i/36.0
                    x = r*math.cos(ang); y = r*math.sin(ang)
                    if lastx is not None:
                        glVertex3f(lastx, lasty, 0); glVertex3f(x, y, 0)
                    lastx, lasty = x, y
                glEnd()
                glPopMatrix()
                new_ex.append(e)
        explosions[:] = new_ex
    # smoke last (opaque puffs)
    for s in SMOKES:
        for p in s["puffs"]:
            glColor3f(0.82,0.82,0.82)
            glPushMatrix(); glTranslatef(p.x,p.y,p.z); gluSphere(gluNewQuadric(), SMOKE_PUFF_SIZE, 12, 10); glPopMatrix()

# ---------------- HUD / Menus / Map ----------------
def draw_floor():
    step=120
    for x in range(-grid_l,grid_l,step):
        for y in range(-grid_l,grid_l,step):
            glColor3f(0.18,0.18,0.22) if ((x//step+y//step)&1)==0 else glColor3f(0.14,0.14,0.17)
            glBegin(GL_QUADS); glVertex3f(x,y,0); glVertex3f(x+step,y,0); glVertex3f(x+step,y+step,0); glVertex3f(x,y+step,0); glEnd()

def draw_text(x,y,s,font=GLUT_BITMAP_HELVETICA_18):
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(1,1,1); glRasterPos2f(x,y)
    for ch in s: glutBitmapCharacter(font, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

def format_time(secs):
    m=int(secs//60); s=int(secs%60); return f"{m:02d}:{s:02d}"

def draw_health_bar():
    if menu_active or map_overlay: return
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(0.25,0.25,0.25); glBegin(GL_QUADS)
    glVertex3f(12,28,0); glVertex3f(212,28,0); glVertex3f(212,48,0); glVertex3f(12,48,0); glEnd()
    w = 2*player_hp
    glColor3f(0.15,0.8,0.2) if player_hp>35 else glColor3f(0.9,0.2,0.1)
    glBegin(GL_QUADS); glVertex3f(12,28,0); glVertex3f(12+w,28,0); glVertex3f(12+w,48,0); glVertex3f(12,48,0); glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    

def draw_crosshair():
    if not crosshair_on or (weapon=="AWP" and scope_on) or menu_active or map_overlay: return
    cx,cy=win_w//2, win_h//2
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(1,1,1); glBegin(GL_LINES)
    glVertex3f(cx-10,cy,0); glVertex3f(cx-2,cy,0); glVertex3f(cx+2,cy,0); glVertex3f(cx+10,cy,0)
    glVertex3f(cx,cy-10,0); glVertex3f(cx,cy-2,0); glVertex3f(cx,cy+2,0); glVertex3f(cx,cy+10,0)
    glEnd(); glPointSize(4); glBegin(GL_POINTS); glVertex3f(cx,cy,0); glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

def draw_scope_overlay():
    if weapon!="AWP" or not scope_on or menu_active or map_overlay: return
    cx,cy=win_w//2,win_h//2; r=int(min(win_w,win_h)*0.42)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(0,0,0)
    # mask outside circle
    glBegin(GL_QUADS); glVertex3f(0,0,0); glVertex3f(cx-r,0,0); glVertex3f(cx-r,win_h,0); glVertex3f(0,win_h,0); glEnd()
    glBegin(GL_QUADS); glVertex3f(cx+r,0,0); glVertex3f(win_w,0,0); glVertex3f(win_w,win_h,0); glVertex3f(cx+r,win_h,0); glEnd()
    glBegin(GL_QUADS); glVertex3f(cx-r,cy+r,0); glVertex3f(cx+r,cy+r,0); glVertex3f(cx+r,win_h,0); glVertex3f(cx-r,win_h,0); glEnd()
    glBegin(GL_QUADS); glVertex3f(cx-r,0,0); glVertex3f(cx+r,0,0); glVertex3f(cx+r,cy-r,0); glVertex3f(cx-r,cy-r,0); glEnd()
    # circular frame (GL_LINES polyline)
    glColor3f(0,0,0); glBegin(GL_LINES)
    lastx = None; lasty = None
    for i in range(121):
        t=2*math.pi*i/120.0
        x = cx + r*math.cos(t); y = cy + r*math.sin(t)
        if lastx is not None:
            glVertex3f(lastx, lasty, 0); glVertex3f(x, y, 0)
        lastx, lasty = x, y
    glEnd()
    glBegin(GL_LINES); glVertex3f(cx-r,cy,0); glVertex3f(cx+r,cy,0); glEnd()
    glBegin(GL_LINES); glVertex3f(cx,cy-r,0); glVertex3f(cx,cy+r,0); glEnd()
    glColor3f(1,0,0); glPointSize(5); glBegin(GL_POINTS); glVertex3f(cx,cy,0); glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

def draw_full_map_overlay():
    road=(0.76,0.64,0.48); walls=(0.28,0.30,0.34); border=(0.10,0.10,0.10)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(-grid_l, grid_l, -grid_l, grid_l)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(*road); glBegin(GL_QUADS)
    glVertex3f(-grid_l,-grid_l, 0); glVertex3f(grid_l,-grid_l, 0); glVertex3f(grid_l,grid_l, 0); glVertex3f(-grid_l,grid_l, 0); glEnd()
    glColor3f(*walls)
    for (cx,cy,sx,sy,h) in MAZE+CRATES:
        glBegin(GL_QUADS); glVertex3f(cx-sx, cy-sy, 0); glVertex3f(cx+sx, cy-sy, 0); glVertex3f(cx+sx, cy+sy, 0); glVertex3f(cx-sx, cy+sy, 0); glEnd()
    glColor3f(*border); glBegin(GL_LINES)
    glVertex3f(-grid_l,-grid_l, 0); glVertex3f(grid_l,-grid_l, 0)
    glVertex3f(grid_l,-grid_l, 0); glVertex3f(grid_l,grid_l, 0)
    glVertex3f(grid_l,grid_l, 0); glVertex3f(-grid_l,grid_l, 0)
    glVertex3f(-grid_l,grid_l, 0); glVertex3f(-grid_l,-grid_l, 0)
    glEnd()
    glPointSize(10.0); glColor3f(1.0,0.15,0.15); glBegin(GL_POINTS); glVertex3f(Px,Py, 0); glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

def draw_hud():
    if menu_active or map_overlay: return
    wep = f"{weapon} ({ak_mode})" if weapon=="AK" else "AWP"
    draw_text(10, win_h-20, f"{wep} | Kills:{headshots+bodykills+grenade_kills} (H:{headshots} B:{bodykills} N:{grenade_kills})  WB:{wallbang_kills}  Time:{format_time(play_time)}")
    draw_text(10, win_h-40, f"Shots:{shots_fired}  Missed:{missed_shots}")
    draw_text(10, 10, "Arrows:Look  WASD:Move  SPACE:Fire  F:Scope/Mode  C:Jump  Z:Map  X:Xray  V:Swap  G/T:Frag/Smoke  Q:End  Esc:Menu")

# ---------------- Display / Loop ----------------
prev_time=None
def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    setupCamera()
    draw_floor()

    items = []
    maze_col  = (0.40, 0.42, 0.48)
    crate_col = (0.32, 0.34, 0.40)

    # boxes (nearest corner depth for robust painter sort)
    for (cx, cy, sx, sy, h) in MAZE:
        items.append(("box", (cx, cy, sx, sy, h, maze_col),
                      box_nearest_depth(cx, cy, sx, sy, h)))
    for (cx, cy, sx, sy, h) in CRATES:
        items.append(("box", (cx, cy, sx, sy, h, crate_col),
                      box_nearest_depth(cx, cy, sx, sy, h)))

    # enemies & bullets
    for e in enemies:
        items.append(("enemy", e, enemy_nearest_depth(e)))
    for b in bullets:
        items.append(("pbullet", b, depth_to_cam(b["x"], b["y"], b["z"])))
    for eb in E_BULLETS:
        items.append(("ebullet", eb, depth_to_cam(eb["x"], eb["y"], eb["z"])))

    # far -> near
    items.sort(key=lambda t: t[2], reverse=True)

    for kind, obj, _ in items:
        if kind == "box":
            cx, cy, sx, sy, h, col = obj
            draw_box_single(cx, cy, sx, sy, h, col)
        elif kind == "enemy":
            draw_enemy(obj, (0.0, 0.6, 0.0))
        elif kind == "pbullet":
            glColor3f(0.95, 0.85, 0.10)
            glPushMatrix(); glTranslatef(obj["x"], obj["y"], obj["z"])
            glutSolidCube(B_SIZE); glPopMatrix()
        elif kind == "ebullet":
            glColor3f(1.0, 0.25, 0.25)
            glPushMatrix(); glTranslatef(obj["x"], obj["y"], obj["z"])
            glutSolidCube(8.0); glPopMatrix()

    if xray and not menu_active and not map_overlay:
        for e in enemies:
            draw_enemy(e, (1.0, 0.2, 0.7))

    now = time.time()
    draw_grenades_and_smoke(now)
    draw_weapon()
    draw_scope_overlay()
    draw_crosshair()
    draw_health_bar()
    draw_hud()
    if map_overlay: draw_full_map_overlay()
    if menu_active: draw_menu()
    glutSwapBuffers()

def reshape(w,h):
    global win_w,win_h,aspect
    if h==0: h=1
    win_w,win_h=w,h; aspect=w/float(h); glViewport(0,0,w,h)

def idle():
    global prev_time, Px, Py, Pz, Pvz, play_time, ak_burst_left, key_W, key_A, key_S, key_D, fire_hold
    now=time.time()
    if prev_time is None: prev_time=now
    dt=now-prev_time; prev_time=now
    if not menu_active and not session_over and not map_overlay:
        play_time += dt

    if menu_active:
        glutPostRedisplay(); return

    # jump physics
    Pvz += GRAVITY_PLAYER*dt; Pz += Pvz*dt
    if Pz <= GROUND_EPS:
        Pz=0.0
        if Pvz<0: Pvz=0.0

    # emulate key release timeout
    if (now - _key_last_time["w"]) > _key_hold_window: key_W = False
    if (now - _key_last_time["a"]) > _key_hold_window: key_A = False
    if (now - _key_last_time["s"]) > _key_hold_window: key_S = False
    if (now - _key_last_time["d"]) > _key_hold_window: key_D = False
    if (now - _key_last_time["space"]) > _key_hold_window: fire_hold = False

    if not session_over and not map_overlay:
        fwdx=math.cos(math.radians(Pangle))*math.cos(math.radians(Pitch))
        fwdy=math.sin(math.radians(Pangle))*math.cos(math.radians(Pitch))
        step=Pspeed*dt
        if key_W:
            nx,ny=Px+fwdx*step, Py+fwdy*step
            if not blocked(nx,ny): Px,Py=nx,ny
        if key_S:
            nx,ny=Px-fwdx*step, Py-fwdy*step
            if not blocked(nx,ny): Px,Py=nx,ny
        rx,ry = right_vec_from_yaw(Pangle)
        if key_D:
            nx,ny=Px-rx*step, Py-ry*step
            if not blocked(nx,ny): Px,Py=nx,ny
        if key_A:
            nx,ny=Px+rx*step, Py+ry*step
            if not blocked(nx,ny): Px,Py=nx,ny

        update_enemies(dt)
        step_bullets(dt,now)
        step_enemy_bullets(dt)

        if weapon=="AK":
            if fire_hold: fire_ak(now)
            if ak_mode=="burst" and ak_burst_left>0:
                step_ak_burst(now)

    step_grenades(dt,now); step_smokes(dt,now); enemy_try_fire(now)
    glutPostRedisplay()

# ---------------- Input ----------------
def keyboardListener(k,x,y):
    global key_W,key_S,key_A,key_D, xray, zoomed, map_overlay, menu_active, menu_choice, crosshair_on, Pvz, weapon, ak_mode, scope_on, fire_hold
    now = time.time()
    if k in (b'w',b'W'):
        key_W=True; _key_last_time["w"]=now
    elif k in (b's',b'S'):
        key_S=True; _key_last_time["s"]=now
    elif k in (b'a',b'A'):
        key_A=True; _key_last_time["a"]=now
    elif k in (b'd',b'D'):
        key_D=True; _key_last_time["d"]=now

    elif k in (b'c',b'C'):  # Jump
        if Pz <= GROUND_EPS and Pvz == 0.0: Pvz = JUMP_V0

    elif k in (b'x',b'X'):  # Cheat
        xray = not xray

    elif k in (b'z',b'Z'):  # Map overlay
        map_overlay = not map_overlay

    elif k in (b'v',b'V'):  # Swap weapon
        weapon = "AWP" if weapon=="AK" else "AK"
        scope_on=False; zoomed=False
        crosshair_on = (weapon=="AK")
        print("[WEAPON]", weapon)

    elif k in (b'f',b'F'):  # Scope/Firemode
        if weapon=="AK":
            ak_mode = {"single":"burst","burst":"auto","auto":"single"}[ak_mode]
            print("[AK MODE]", ak_mode)
        else:
            scope_on = not scope_on
            zoomed = scope_on

    elif k in (b' ',):      # Fire (Space)
        _key_last_time["space"]=now
        if weapon=="AWP":
            fire_awp(now)
        else:
            fire_hold = True

    elif k in (b'g',b'G'):
        throw_grenade("frag")
    elif k in (b't',b'T'):
        throw_grenade("smoke")

    elif k in (b'q',b'Q'):
        end_session("Quit")

    elif k in (b'\x1b',):  # Esc
        menu_active = not menu_active; menu_choice = 0

    elif k in (b'\r', b'\n'):
        if menu_active:
            label = (["Restart","Exit"] if session_over else ["Continue","End Session","Restart","Exit"])[menu_choice]
            menu_activate(label)

def specialKeyListener(key, x, y):
    global Pangle, Pitch, menu_choice
    if menu_active:
        items = ["Restart","Exit"] if session_over else ["Continue","End Session","Restart","Exit"]
        if key==GLUT_KEY_UP:
            menu_choice=(menu_choice-1)%len(items)
        elif key==GLUT_KEY_DOWN:
            menu_choice=(menu_choice+1)%len(items)
        return
    # Arrow keys act as mouse-look
    if key==GLUT_KEY_LEFT:   Pangle=(Pangle+3.0) % 360
    elif key==GLUT_KEY_RIGHT: Pangle=(Pangle-3.0) % 360
    elif key==GLUT_KEY_UP:    Pitch =clamp(Pitch+2.0, -60.0, 60.0)
    elif key==GLUT_KEY_DOWN:  Pitch =clamp(Pitch-2.0, -60.0, 60.0)

def mouseListener(button, state, x, y):
    pass

# ---------------- Menus / End / Exit ----------------
def quit_game():
    print("[SESSION] Exit")
    try: sys.exit(0)
    except SystemExit: pass
    os._exit(0)

def current_menu_items(): return ["Restart","Exit"] if session_over else ["Continue","End Session","Restart","Exit"]

def draw_menu():
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,win_w,0,win_h)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    title = "== TRAINING SESSION END ==" if session_over else "== GAME PAUSED =="
    draw_text(win_w//2-160, win_h-90, title)
    items=current_menu_items()
    for i,item in enumerate(items):
        prefix="> " if i==menu_choice else "  "; y=win_h-160-44*i
        draw_text(win_w//2-80, y, prefix+item)
    if session_over:
        draw_text(win_w//2-220, win_h//2,   f"Kills:{headshots+bodykills+grenade_kills} (H:{headshots} B:{bodykills} N:{grenade_kills})  WB:{wallbang_kills}")
        draw_text(win_w//2-220, win_h//2-30,f"Shots:{shots_fired}  Miss:{missed_shots}  Time:{format_time(play_time)}")
        draw_text(win_w//2-220, win_h//2-60,f"Reason: {session_reason}")
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

def menu_activate(label):
    global menu_active, headshots, bodykills, shots_fired, missed_shots, wallbang_kills, grenade_kills
    global Px,Py,Pz,Pangle,Pitch, bullets, grenades, explosions, SMOKES
    global zoomed, scope_on, xray, session_over, player_hp, E_BULLETS, Pvz, map_overlay, play_time
    global weapon, ak_mode, hs_for_heal, fire_hold
    if label=="Continue" and not session_over:
        menu_active=False
    elif label=="End Session" and not session_over:
        end_session("Ended from Menu")
    elif label=="Restart":
        headshots=bodykills=shots_fired=missed_shots=wallbang_kills=grenade_kills=0; hs_for_heal=0
        bullets.clear(); grenades.clear(); explosions.clear(); SMOKES.clear(); E_BULLETS.clear()
        reset_enemies()
        Px,Py,Pz,Pangle,Pitch,Pvz = 0.0,-900.0,0.0,90.0,0.0,0.0
        zoomed=scope_on=xray=False
        session_over=False; menu_active=False; map_overlay=False
        player_hp=100; play_time=0.0
        weapon="AK"; ak_mode="single"; fire_hold=False
        print("[SESSION] Restarted"); 
        crosshair_on=True
    elif label=="Exit":
        quit_game()

def end_session(reason):
    global session_over, menu_active, session_reason, map_overlay
    if session_over: return
    session_over=True; menu_active=True; map_overlay=False
    session_reason = reason
    print("Training Session End")
    print(f"Reason: {session_reason}")
    print(f"Time: {format_time(play_time)} | "
          f"Kills:{headshots+bodykills+grenade_kills} (H:{headshots} B:{bodykills} N:{grenade_kills}) | "
          f"Shots:{shots_fired} Miss:{missed_shots} | WB:{wallbang_kills}")

# ---------------- Main ----------------
def main():
    random.seed(21); reset_enemies()
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(win_w,win_h); glutInitWindowPosition(60,40)
    glutCreateWindow(b"Shooting-Arena by Ohi")
    glutDisplayFunc(display); glutReshapeFunc(reshape); glutIdleFunc(idle)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener); glutMouseFunc(mouseListener)
    glutMainLoop()

if __name__=="__main__":
    main()
