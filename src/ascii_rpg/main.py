"""Fullscreen ASCII space RPG with menus, physics, combat, and save/load."""
from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import pygame

BG = (5, 8, 18)
PANEL = (9, 17, 34)
WHITE = (219, 233, 250)
DIM = (73, 101, 134)
CYAN = (73, 225, 255)
GREEN = (105, 250, 157)
YELLOW = (255, 218, 105)
RED = (255, 99, 119)
PURPLE = (193, 128, 255)
ORANGE = (255, 157, 83)
SAVE_PATH = Path(__file__).resolve().parents[2] / "savegame.json"


@dataclass
class Ship:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    hull: float = 100.0
    missiles: int = 10
    facing: float = 0.0
    laser_wait: float = 0.0
    missile_wait: float = 0.0
    brake: bool = False


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def vector(angle: float, speed: float) -> tuple[float, float]:
    return math.cos(angle) * speed, math.sin(angle) * speed


class SpaceRPG:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("THE GREEN SECTOR — ASCII RPG")
        self.fullscreen = True
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()
        self.font_size = 25
        self.font = pygame.font.SysFont("consolas", self.font_size, bold=True)
        self.ui = pygame.font.SysFont("consolas", 21, bold=True)
        self.small = pygame.font.SysFont("consolas", 16)
        self.width, self.height = self.screen.get_size()
        self.cell_w = max(15, self.font.size("M")[0])
        self.cell_h = max(22, self.font.get_linesize())
        self.mode = "menu"
        self.return_mode = "menu"
        self.selection = 0
        self.message = ""
        self.message_time = 0.0
        self.particles_on = True
        self.stars = [(random.randrange(self.width), random.randrange(self.height), random.choice((1, 1, 2))) for _ in range(180)]
        self.new_game()
        self.mode = "menu"
        self.selection = 0

    def new_game(self) -> None:
        self.player = Ship()
        self.asteroids: list[dict] = []
        self.enemies: list[dict] = []
        self.shots: list[dict] = []
        self.particles: list[dict] = []
        self.pickups: list[dict] = []
        self.score = 0
        self.elapsed = 0.0
        self.mother = {"x": 27.0, "y": -8.0, "vx": -0.4, "vy": 0.25, "hp": 100.0, "wait": 2.0, "drop": False}
        for _ in range(48):
            self.spawn_asteroid(initial=True)
        for _ in range(4):
            self.spawn_enemy(initial=True)
        self.mode = "game"
        self.selection = 0
        self.notify("Sector entered. Arrows accelerate; B brakes; Space fires lasers; M launches missiles.", 6)

    def spawn_asteroid(self, initial: bool = False) -> None:
        angle = random.random() * math.tau
        radius = random.uniform(14, 52) if initial else random.uniform(32, 55)
        x = self.player.x + math.cos(angle) * radius
        y = self.player.y + math.sin(angle) * radius
        large = random.random() < 0.22
        cells = []
        if large:
            for cy in range(3):
                for cx in range(3):
                    if random.random() < 0.76:
                        cells.append((cx - 1, cy - 1))
            if not cells:
                cells = [(0, 0)]
        else:
            cells = [(0, 0)]
        self.asteroids.append({"x": x, "y": y, "vx": random.uniform(-0.35, 0.35), "vy": random.uniform(-0.35, 0.35), "cells": cells, "hp": 2 if large else 1, "large": large})

    def spawn_enemy(self, initial: bool = False) -> None:
        a = random.random() * math.tau
        d = random.uniform(18, 38) if initial else random.uniform(28, 44)
        self.enemies.append({"x": self.player.x + math.cos(a) * d, "y": self.player.y + math.sin(a) * d, "vx": 0.0, "vy": 0.0, "hp": 3, "wait": random.uniform(0.7, 2.0)})

    def notify(self, text: str, seconds: float = 3.0) -> None:
        self.message, self.message_time = text, seconds

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        flags = pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE
        self.screen = pygame.display.set_mode((0, 0) if self.fullscreen else (1100, 760), flags)
        self.width, self.height = self.screen.get_size()
        self.stars = [(random.randrange(self.width), random.randrange(self.height), random.choice((1, 1, 2))) for _ in range(180)]

    def save(self) -> None:
        data = {
            "player": asdict(self.player), "score": self.score, "elapsed": self.elapsed,
            "mother": self.mother, "asteroids": self.asteroids, "enemies": self.enemies,
            "pickups": self.pickups,
        }
        SAVE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.notify("Game saved.")

    def load(self) -> bool:
        if not SAVE_PATH.exists():
            self.notify("No save game found yet.")
            return False
        try:
            data = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
            self.player = Ship(**data["player"])
            self.score = int(data.get("score", 0))
            self.elapsed = float(data.get("elapsed", 0))
            self.mother = data["mother"]
            self.asteroids = data["asteroids"]
            self.enemies = data["enemies"]
            self.pickups = data.get("pickups", [])
            self.shots, self.particles = [], []
            self.mode, self.selection = "game", 0
            self.notify("Save game loaded.")
            return True
        except (OSError, ValueError, KeyError, TypeError):
            self.notify("Could not read the save game.")
            return False

    def add_particles(self, x: float, y: float, color: tuple[int, int, int], count: int = 12) -> None:
        if not self.particles_on:
            return
        for _ in range(count):
            a = random.random() * math.tau
            speed = random.uniform(1.5, 7.0)
            vx, vy = vector(a, speed)
            self.particles.append({"x": x, "y": y, "vx": vx, "vy": vy, "life": random.uniform(0.22, 0.75), "max": 0.75, "glyph": random.choice(("*", ".", "+", "x")), "color": color})

    def fire(self, missile: bool = False) -> None:
        p = self.player
        if missile:
            if p.missiles <= 0 or p.missile_wait > 0:
                return
            p.missiles -= 1
            p.missile_wait = 0.55
            speed, kind, color = 21.0, "missile", ORANGE
        else:
            if p.laser_wait > 0:
                return
            p.laser_wait = 0.13
            speed, kind, color = 35.0, "laser", GREEN
        dx, dy = vector(p.facing, speed)
        self.shots.append({"x": p.x, "y": p.y, "vx": dx + p.vx, "vy": dy + p.vy, "owner": "player", "kind": kind, "life": 2.2, "color": color})

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper) -> None:
        self.elapsed += dt
        p = self.player
        ax = (float(keys[pygame.K_RIGHT]) - float(keys[pygame.K_LEFT])) * 18.0
        ay = (float(keys[pygame.K_DOWN]) - float(keys[pygame.K_UP])) * 18.0
        if ax or ay:
            p.facing = math.atan2(ay, ax)
            mag = math.hypot(ax, ay)
            ax, ay = ax / mag * 18, ay / mag * 18
        p.vx += ax * dt
        p.vy += ay * dt
        speed = math.hypot(p.vx, p.vy)
        max_speed = 13.0
        if speed > max_speed:
            p.vx, p.vy = p.vx / speed * max_speed, p.vy / speed * max_speed
        # Near-zero drag keeps the ship drifting. Brake applies gradual retro-thrust drag.
        friction = math.exp((-3.6 if p.brake else -0.035) * dt)
        p.vx *= friction
        p.vy *= friction
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.laser_wait = max(0, p.laser_wait - dt)
        p.missile_wait = max(0, p.missile_wait - dt)
        if keys[pygame.K_SPACE]:
            self.fire(False)
        if keys[pygame.K_m]:
            self.fire(True)

        # Mother ship slowly drifts, and fires tracking missiles at close range.
        m = self.mother
        md = distance(p.x, p.y, m["x"], m["y"])
        m["x"] += m["vx"] * dt
        m["y"] += m["vy"] * dt
        m["wait"] -= dt
        if md < 24 and m["wait"] <= 0:
            angle = math.atan2(p.y - m["y"], p.x - m["x"])
            vx, vy = vector(angle, 12)
            self.shots.append({"x": m["x"], "y": m["y"], "vx": vx, "vy": vy, "owner": "mother", "kind": "missile", "life": 4.0, "color": RED})
            m["wait"] = random.uniform(2.2, 3.5)
            self.notify("Mother ship launched a missile!")

        # Smaller raiders pursue the player and fire short laser bursts.
        for e in self.enemies:
            d = distance(p.x, p.y, e["x"], e["y"])
            angle = math.atan2(p.y - e["y"], p.x - e["x"])
            tx, ty = vector(angle, 4.1 if d > 8 else 1.2)
            e["vx"] += (tx - e["vx"]) * min(1, dt * 0.8)
            e["vy"] += (ty - e["vy"]) * min(1, dt * 0.8)
            e["x"] += e["vx"] * dt
            e["y"] += e["vy"] * dt
            e["wait"] -= dt
            if d < 20 and e["wait"] <= 0:
                svx, svy = vector(angle, 17)
                self.shots.append({"x": e["x"], "y": e["y"], "vx": svx, "vy": svy, "owner": "enemy", "kind": "laser", "life": 2.3, "color": PURPLE})
                e["wait"] = random.uniform(1.5, 2.7)

        # Drift small rocks and asteroid clusters.
        for rock in self.asteroids:
            rock["x"] += rock["vx"] * dt
            rock["y"] += rock["vy"] * dt
        for shot in self.shots:
            shot["x"] += shot["vx"] * dt
            shot["y"] += shot["vy"] * dt
            shot["life"] -= dt
            if shot["kind"] == "missile" and shot["owner"] == "mother":
                shot["vx"] += (p.x - shot["x"]) * dt * 0.65
                shot["vy"] += (p.y - shot["y"]) * dt * 0.65

        # Projectile impacts and combat damage.
        for shot in list(self.shots):
            if shot["owner"] == "player":
                for e in list(self.enemies):
                    if distance(shot["x"], shot["y"], e["x"], e["y"]) < 1.5:
                        e["hp"] -= 1 if shot["kind"] == "laser" else 3
                        self.shots.remove(shot)
                        self.add_particles(e["x"], e["y"], GREEN, 8)
                        if e["hp"] <= 0:
                            self.enemies.remove(e)
                            self.score += 100
                            self.add_particles(e["x"], e["y"], ORANGE, 24)
                            if random.random() < 0.22:
                                self.pickups.append({"x": e["x"], "y": e["y"], "kind": random.choice(("hull", "missile"))})
                        break
                if shot in self.shots and distance(shot["x"], shot["y"], m["x"], m["y"]) < 2.5:
                    m["hp"] -= 18 if shot["kind"] == "missile" else 5
                    self.shots.remove(shot)
                    self.add_particles(m["x"], m["y"], YELLOW, 15)
                    if m["hp"] <= 0 and not m["drop"]:
                        m["hp"], m["drop"] = 0, True
                        self.score += 1000
                        self.pickups.extend([{"x": m["x"] + 1, "y": m["y"], "kind": "hull"}, {"x": m["x"] - 1, "y": m["y"], "kind": "missile"}])
                        self.add_particles(m["x"], m["y"], ORANGE, 50)
                        self.notify("Mother ship destroyed! Hull and missile supplies released.", 5)
            elif distance(shot["x"], shot["y"], p.x, p.y) < 1.2:
                p.hull = max(0, p.hull - (12 if shot["kind"] == "missile" else 5))
                self.shots.remove(shot)
                self.add_particles(p.x, p.y, RED, 18)
                self.notify("Direct hit! Hull integrity damaged.")

        # Asteroid contact damages the hull; the rock breaks apart in a burst.
        for rock in list(self.asteroids):
            if any(distance(p.x, p.y, rock["x"] + ox, rock["y"] + oy) < 1.15 for ox, oy in rock["cells"]):
                p.hull = max(0, p.hull - (18 if rock["large"] else 9))
                self.asteroids.remove(rock)
                self.score += 20
                self.add_particles(rock["x"], rock["y"], ORANGE, 30 if rock["large"] else 14)
                self.notify("Asteroid collision! Hull damaged; rock shattered.")
                self.spawn_asteroid()

        for pickup in list(self.pickups):
            if distance(p.x, p.y, pickup["x"], pickup["y"]) < 1.4:
                if pickup["kind"] == "hull":
                    p.hull = min(100, p.hull + 30)
                    self.notify("Hull repair pack collected.")
                else:
                    p.missiles = min(10, p.missiles + 5)
                    self.notify("Missile supply collected (+5, maximum 10).")
                self.pickups.remove(pickup)
                self.add_particles(p.x, p.y, GREEN, 12)

        # A mother ship also periodically releases supplies nearby while alive.
        if not m["drop"] and random.random() < dt * 0.025:
            self.pickups.append({"x": m["x"] + random.uniform(-2, 2), "y": m["y"] + random.uniform(-2, 2), "kind": random.choice(("hull", "missile"))})
        for part in self.particles:
            part["x"] += part["vx"] * dt
            part["y"] += part["vy"] * dt
            part["life"] -= dt
        self.particles = [part for part in self.particles if part["life"] > 0]
        self.shots = [shot for shot in self.shots if shot["life"] > 0]
        self.asteroids = [r for r in self.asteroids if distance(p.x, p.y, r["x"], r["y"]) < 65]
        self.enemies = [e for e in self.enemies if distance(p.x, p.y, e["x"], e["y"]) < 60]
        self.pickups = [item for item in self.pickups if distance(p.x, p.y, item["x"], item["y"]) < 60]
        while len(self.asteroids) < 45:
            self.spawn_asteroid()
        if len(self.enemies) < 4 and random.random() < dt * 0.18:
            self.spawn_enemy()
        if p.hull <= 0:
            self.mode = "gameover"
            self.selection = 0
            self.notify("Your ship was destroyed.")
        self.message_time = max(0, self.message_time - dt)

    def draw_text(self, text: str, x: int, y: int, color: tuple[int, int, int], font: pygame.font.Font | None = None, center: bool = False) -> None:
        surf = (font or self.font).render(text, True, color)
        rect = surf.get_rect()
        rect.center = (x, y) if center else rect.center
        if not center:
            rect.topleft = (x, y)
        self.screen.blit(surf, rect)

    def draw_world(self) -> None:
        p = self.player
        ox, oy = self.width / 2 - p.x * self.cell_w, self.height / 2 - p.y * self.cell_h
        self.screen.fill(BG)
        for sx, sy, size in self.stars:
            pygame.draw.circle(self.screen, (31, 51, 77), (sx, sy), size)

        def pos(x: float, y: float) -> tuple[int, int]:
            return round(ox + x * self.cell_w), round(oy + y * self.cell_h)

        for rock in self.asteroids:
            for dx, dy in rock["cells"]:
                self.draw_text("&", *pos(rock["x"] + dx, rock["y"] + dy), ORANGE)
        if self.mother["hp"] > 0:
            self.draw_text("<O>", *pos(self.mother["x"], self.mother["y"]), PURPLE)
        for e in self.enemies:
            self.draw_text("<>", *pos(e["x"], e["y"]), RED)
        for item in self.pickups:
            glyph, color = ("+", GREEN) if item["kind"] == "hull" else ("m", YELLOW)
            self.draw_text(glyph, *pos(item["x"], item["y"]), color)
        for shot in self.shots:
            glyph = "*" if shot["kind"] == "missile" else ("-" if abs(shot["vx"]) > abs(shot["vy"]) else "|")
            self.draw_text(glyph, *pos(shot["x"], shot["y"]), shot["color"])
        for part in self.particles:
            self.draw_text(part["glyph"], *pos(part["x"], part["y"]), part["color"], self.small)
        # A little exhaust flame appears opposite the current thrust direction.
        keys = pygame.key.get_pressed()
        if any(keys[k] for k in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)):
            fx, fy = vector(p.facing + math.pi, 1.0)
            self.draw_text(".", *pos(p.x + fx, p.y + fy), ORANGE)
        self.draw_text("#", *pos(p.x, p.y), CYAN)

        pygame.draw.rect(self.screen, PANEL, (0, 0, self.width, 57))
        self.draw_text("THE GREEN SECTOR", 24, 13, CYAN, self.ui)
        self.draw_text(f"HULL {int(p.hull):03d}%   MISSILES {p.missiles:02d}/10   SCORE {self.score:06d}", 280, 14, WHITE, self.ui)
        self.draw_text("ARROWS THRUST   B BRAKE   SPACE LASER   M MISSILE   P PAUSE", 24, 63, DIM, self.small)
        if self.message_time > 0:
            pygame.draw.rect(self.screen, (20, 26, 36), (18, self.height - 48, self.width - 36, 32))
            self.draw_text(self.message, 28, self.height - 44, YELLOW, self.small)
        pygame.draw.rect(self.screen, CYAN, (14, 14, max(3, int((self.width - 28) * p.hull / 100)), 3))

    def draw_menu(self, title: str, options: list[str], subtitle: str = "") -> None:
        self.screen.fill(BG)
        for x, y, size in self.stars:
            pygame.draw.circle(self.screen, (31, 51, 77), (x, y), size)
        self.draw_text("#  THE GREEN SECTOR  #", self.width // 2, self.height // 3 - 46, CYAN, self.font, True)
        self.draw_text(title, self.width // 2, self.height // 3 + 12, WHITE, self.ui, True)
        if subtitle:
            self.draw_text(subtitle, self.width // 2, self.height // 3 + 48, DIM, self.small, True)
        start_y = self.height // 2 - 15
        for i, option in enumerate(options):
            color = YELLOW if i == self.selection else DIM
            prefix = "> " if i == self.selection else "  "
            self.draw_text(prefix + option, self.width // 2, start_y + i * 42, color, self.ui, True)
        if self.message_time > 0 and self.message:
            self.draw_text(self.message, self.width // 2, start_y + len(options) * 42 + 24, YELLOW, self.small, True)
        self.draw_text("UP/DOWN SELECT     ENTER CONFIRM     ESC BACK", self.width // 2, self.height - 42, CYAN, self.small, True)

    def menu_options(self) -> list[str]:
        if self.mode == "menu":
            return ["Start New Game", "Load Game", "Settings", "Credits", "Exit"]
        if self.mode == "pause":
            return ["Resume", "Save Game", "Load Game", "Settings", "Exit to Main Menu"]
        if self.mode == "settings":
            return [f"Fullscreen: {'On' if self.fullscreen else 'Off'}", f"Impact particles: {'On' if self.particles_on else 'Off'}", "Back"]
        if self.mode == "credits":
            return ["Back"]
        return ["Start New Game", "Load Game", "Exit"]

    def activate(self) -> bool:
        options = self.menu_options()
        choice = options[self.selection]
        if self.mode == "menu":
            if choice == "Start New Game":
                self.new_game()
            elif choice == "Load Game":
                self.load()
            elif choice == "Settings":
                self.return_mode, self.mode, self.selection = "menu", "settings", 0
            elif choice == "Credits":
                self.mode, self.selection = "credits", 0
            elif choice == "Exit":
                return False
        elif self.mode == "pause":
            if choice == "Resume":
                self.mode = "game"
            elif choice == "Save Game":
                self.save()
            elif choice == "Load Game":
                self.load()
            elif choice == "Settings":
                self.return_mode, self.mode, self.selection = "pause", "settings", 0
            elif choice == "Exit to Main Menu":
                self.mode, self.selection = "menu", 0
        elif self.mode == "settings":
            if choice.startswith("Fullscreen:"):
                self.toggle_fullscreen()
            elif choice.startswith("Impact particles:"):
                self.particles_on = not self.particles_on
            else:
                self.mode, self.selection = self.return_mode, 0
        elif self.mode == "credits":
            self.mode, self.selection = "menu", 0
        elif self.mode == "gameover":
            if choice == "Start New Game":
                self.new_game()
            elif choice == "Load Game":
                self.load()
            else:
                return False
        return True

    def run(self) -> None:
        running = True
        while running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    if self.mode == "game":
                        if event.key in (pygame.K_p, pygame.K_ESCAPE):
                            self.mode, self.selection = "pause", 0
                        elif event.key == pygame.K_b:
                            self.player.brake = True
                        elif event.key == pygame.K_SPACE:
                            self.fire(False)
                        elif event.key == pygame.K_m:
                            self.fire(True)
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.selection = (self.selection - 1) % len(self.menu_options())
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.selection = (self.selection + 1) % len(self.menu_options())
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        running = self.activate()
                    elif event.key == pygame.K_ESCAPE:
                        if self.mode == "pause":
                            self.mode = "game"
                        elif self.mode in ("settings", "credits"):
                            self.mode, self.selection = self.return_mode if self.mode == "settings" else "menu", 0
                        elif self.mode == "gameover":
                            running = False
                elif event.type == pygame.KEYUP and event.key == pygame.K_b:
                    self.player.brake = False
            if self.mode == "game":
                self.update(dt, pygame.key.get_pressed())
                self.draw_world()
            elif self.mode in ("menu", "pause", "settings", "gameover"):
                if self.mode == "pause":
                    self.draw_world()
                    overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 175))
                    self.screen.blit(overlay, (0, 0))
                    self.draw_menu("PAUSED", self.menu_options())
                elif self.mode == "gameover":
                    self.draw_menu("SHIP DESTROYED", self.menu_options())
                else:
                    self.draw_menu(self.mode.upper() if self.mode != "menu" else "A COLORFUL ASCII SPACE RPG", self.menu_options())
            elif self.mode == "credits":
                self.draw_menu("CREDITS", ["Back"], "A small space RPG made with Python and Pygame")
            pygame.display.flip()
        pygame.quit()


def main() -> None:
    SpaceRPG().run()


if __name__ == "__main__":
    main()
