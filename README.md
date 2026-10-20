# The Green Sector: ASCII RPG

A full-screen, colorful ASCII space RPG built with Python and Pygame. The player ship is `#`; the sector contains a drifting mother ship (`<O>`), raiders (`<>`), small asteroids (`&`), and larger asteroid clusters. Ships and rocks drift with inertia. Impact bursts use animated ASCII particles.

## Install and run on Windows

From the project root (`i-x20`):

```powershell
python -m pip install -e .
python -m ascii_rpg.main
```

Or, if you are already in `src\ascii_rpg`:

```powershell
python -m pip install pygame
python .\main.py
```

## Controls

- **Arrow keys**: accelerate in that direction
- **B**: hold for gradual retro-thruster braking
- **Space**: fire unlimited lasers
- **M**: fire a missile (maximum carried: 10)
- **P** or **Esc**: pause; Esc resumes from the pause menu
- **F11**: toggle fullscreen

Lasers and missiles can damage raiders and the mother ship. The mother ship fires tracking missiles when nearby and periodically releases repair packs or missile supplies. Destroying it releases both. Asteroid collisions break the rock and damage hull integrity.

The main menu has **Start New Game**, **Load Game**, **Settings**, **Credits**, and **Exit**. The pause menu includes **Resume**, **Save Game**, **Load Game**, **Settings**, and **Exit to Main Menu**. Settings let you toggle fullscreen and impact particles.

Saves are stored in `savegame.json` in the project root.
