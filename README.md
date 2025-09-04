
# 🎯 Shooting Arena

A Python + OpenGL training ground FPS-style game built with **PyOpenGL** and **GLUT**.  
This project simulates a small practice arena where you can move, shoot, throw grenades/smokes, and fight against AI enemies.

---

## 🚀 Features
- **Player movement**: WASD for walking, jumping with C, and camera control with arrow keys.  
- **Weapons**:  
  - **AK-47** (single, burst, auto modes)  
  - **AWP** (scoped sniper rifle with zoom toggle)  
- **Grenades**:  
  - Frag grenades (damage in radius, can kill multiple enemies).  
  - Smoke grenades (line-of-sight blocking with puff particles).  
- **Enemies**:  
  - AI-controlled with dodging and boundary avoidance.  
  - Can fire back after player reaches 10 kills.  
- **Game HUD**:  
  - Health bar with dynamic color.  
  - Crosshair & scope overlay.  
  - Kill stats, wallbangs, headshots, and time.  
- **Cheats**:  
  - X-ray vision (see enemies through walls).  
- **Menu System**:  
  - Pause, continue, restart, or exit.  
  - End session stats (kills, shots, accuracy, time).  

---

## 🎮 Controls
```
Look: Arrow Keys        Move: W / A / S / D
Fire: SPACE             Scope / Firemode: F
Jump: C                 Map Overlay: Z
Cheat (x-ray): X        Swap AK/AWP: V
Frag Grenade: G         Smoke Grenade: T
End Session: Q          Menu: Esc  (Enter to select)
```

---

## 🛠 Requirements
- Python 3.x  
- [PyOpenGL](https://pypi.org/project/PyOpenGL/)  
- [PyOpenGL_accelerate](https://pypi.org/project/PyOpenGL-accelerate/) (optional but recommended)  
- GLUT (via `freeglut` or system OpenGL libraries)

Install dependencies with:
```bash
pip install PyOpenGL PyOpenGL_accelerate
```

---

## ▶️ How to Run
```bash
python Shooting-Arena.py
```

A window titled **"Shooting-Arena by Ohi"** will open.  
Fight enemies, practice aim, and survive as long as possible.

---

## 📊 Gameplay Notes
- **Headshots**: Instant kill, every 2 headshots restore +10 HP (if below 100).  
- **Body shots**: Reduce enemy HP, kill after multiple hits.  
- **Grenades**: Explode after ~2 seconds or 3 bounces.  
- **Smoke**: Blocks vision and bullets passing through its radius.  
- **Enemy AI**: Enemies dodge, avoid arena edges, and fire back after player kills 10+ enemies.  

---

## 📝 Credits
Developed by **Ohi**  
Built for practice and experimentation with **Python OpenGL**.
