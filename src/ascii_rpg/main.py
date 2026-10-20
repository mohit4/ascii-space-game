"""Fullscreen ASCII space RPG with menus, physics, combat, and save/load."""
from __future__ import annotations

import json
import math
import random
from array import array
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
SAMPLE_RATE = 22050


class AudioEngine:
    """Generate small retro synth sounds at runtime; no audio assets required."""

    def __init__(self) -> None:
        self.ready = pygame.mixer.get_init() is not None
        self.music_on = True
        self.effects_on = True
        self.scene = ""
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music: dict[str, pygame.mixer.Sound] = {}
        if not self.ready:
            return
        try:
            pygame.mixer.set_num_channels(16)
            self.sounds = {name: self._effect(name) for name in ("menu", "laser", "missile", "enemy", "impact", "explosion", "pickup", "brake", "thrust", "alarm")}
            self.music = {"menu": self._music(88, True), "space": self._music(112, False)}
            self.music_channel = pygame.mixer.Channel(0)
            self.music_channel.set_volume(0.35)
        except (pygame.error, MemoryError):
            self.ready = False

    def _sound_from_samples(self, values: array) -> pygame.mixer.Sound:
        return pygame.mixer.Sound(buffer=values.tobytes())

    def _effect(self, name: str) -> pygame.mixer.Sound:
        duration = {"laser": .15, "missile": .42, "enemy": .12, "impact": .48, "explosion": .8, "pickup": .34, "brake": .2, "thrust": .22, "alarm": .34}.get(name, .09)
        count = int(SAMPLE_RATE * duration)
        samples = array("h")
        noise = random.Random(27)
        for i in range(count):
            t = i / SAMPLE_RATE
            progress = t / duration
            if name == "laser":
                freq = 1250 - 800 * progress
                value = math.sin(math.tau * freq * t) * math.exp(-t * 17)
            elif name == "missile":
                freq = 190 + 500 * progress
                value = (2 * ((freq * t) % 1) - 1) * math.sin(math.pi * progress) * .45
            elif name == "enemy":
                value = math.sin(math.tau * (520 - 260 * progress) * t) * math.exp(-t * 23)
            elif name in ("impact", "explosion"):
                decay = math.exp(-t * (5 if name == "explosion" else 12))
                value = (noise.random() * 1.3 - .65) * decay + math.sin(math.tau * (105 - 55 * progress) * t) * decay * .6
            elif name == "pickup":
                note = int(t * 18) % 3
                freq = (660, 830, 990)[note]
                value = math.sin(math.tau * freq * t) * math.exp(-progress * 2.7)
            elif name == "brake":
                value = math.sin(math.tau * (180 - 90 * progress) * t) * math.exp(-t * 7)
            elif name == "thrust":
                value = (noise.random() * 1.1 - .55) * math.exp(-t * 10) + math.sin(math.tau * (110 + 40 * progress) * t) * math.exp(-t * 5)
            elif name == "alarm":
                freq = 920 if int(t * 9) % 2 == 0 else 660
                value = math.sin(math.tau * freq * t) * (0.6 + 0.4 * math.sin(math.tau * 22 * t))
            else:
                value = math.sin(math.tau * (640 + 300 * progress) * t) * math.exp(-t * 20)
            samples.append(int(max(-1, min(1, value * .45)) * 32767))
        return self._sound_from_samples(samples)

    def _music(self, bpm: int, ambient: bool) -> pygame.mixer.Sound:
        beat = 60 / bpm
        duration = beat * 16  # Four bars, looped by the music channel.
        total = int(SAMPLE_RATE * duration)
        samples = array("h")
        roots = (110.0, 130.81, 146.83, 98.0)
        arp = (12, 19, 24, 19, 15, 19, 24, 19)
        melody = (24, 31, 36, 31, 27, 31, 36, 43, 36, 31, 27, 31, 24, 31, 36, 31)
        for i in range(total):
            t = i / SAMPLE_RATE
            bar = int(t / (beat * 4)) % 4
            root = roots[bar]
            beat_phase = (t % beat) / beat
            arp_idx = int(t / (beat / 2)) % len(arp)
            chord_root = root * (0.5 if ambient else 1)
            pad = sum(math.sin(math.tau * chord_root * ratio * t) for ratio in (1, 1.25, 1.5)) / 3
            bass_phase = (root * 0.5 * t) % 1
            bass = (1 if bass_phase < .5 else -1) * math.exp(-beat_phase * 2.8)
            arp_freq = root * 2 ** (arp[arp_idx] / 12)
            pluck_phase = (arp_freq * t) % 1
            pluck = (1 if pluck_phase < .35 else -1) * math.exp(-((t % (beat / 2)) * (8 if ambient else 13)))
            melody_idx = int(t / (beat / 2)) % len(melody)
            melody_freq = root * 2 ** (melody[melody_idx] / 12)
            melody_envelope = math.exp(-((t % (beat / 2)) * 6))
            lead = math.sin(math.tau * melody_freq * t) * melody_envelope
            if ambient:
                value = pad * .48 + bass * .16 + pluck * .06 + lead * .035
            else:
                value = pad * .22 + bass * .18 + pluck * .11 + lead * .10
                if beat_phase < .12:
                    value += .18 * math.exp(-beat_phase * 28) * math.sin(math.tau * (55 - 18 * beat_phase) * t)
            edge_fade = min(1.0, t / .025, (duration - t) / .025)
            value *= edge_fade
            samples.append(int(max(-1, min(1, value * .62)) * 32767))
        return self._sound_from_samples(samples)

    def play(self, name: str) -> None:
        if self.ready and self.effects_on and name in self.sounds:
            self.sounds[name].play()

    def set_scene(self, scene: str) -> None:
        if not self.ready or scene == self.scene:
            return
        self.scene = scene
        self.music_channel.stop()
        if self.music_on:
            self.music_channel.play(self.music[scene], loops=-1, fade_ms=450)

    def toggle_music(self) -> None:
        self.music_on = not self.music_on
        if self.ready:
            if self.music_on:
                self.music_channel.play(self.music[self.scene or "menu"], loops=-1, fade_ms=350)
            else:
                self.music_channel.fadeout(350)

    def toggle_effects(self) -> None:
        self.effects_on = not self.effects_on


@dataclass
class Ship:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    hull: float = 100.0
    missiles: int = 10
    facing: float = -math.pi / 2
    laser_wait: float = 0.0
    missile_wait: float = 0.0
    brake: bool = False
    regen_wait: float = 0.0
    regen_tick: float = 0.0
    shield: float = 0.0
    utonium: int = 0


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def vector(angle: float, speed: float) -> tuple[float, float]:
    return math.cos(angle) * speed, math.sin(angle) * speed


class SpaceRPG:
    def __init__(self) -> None:
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Deep Space — ASCII RPG")
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
        self.asteroid_pitch = max(18, round(self.cell_h * 0.78))
        self.mode = "menu"
        self.return_mode = "menu"
        self.selection = 0
        self.message = ""
        self.message_time = 0.0
        self.particles_on = True
        self.audio = AudioEngine()
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
        self.shake_time = 0.0
        self.shake_strength = 0.0
        self.alarm_wait = 0.0
        self.gameover_timer = 0.0
        self.mother_respawn = random.uniform(22.0, 34.0)
        self.mother = {"x": 27.0, "y": -8.0, "vx": -0.4, "vy": 0.25, "hp": 100.0, "wait": 2.0, "drop": False}
        self.spawn_mother(initial=True)
        for _ in range(48):
            self.spawn_asteroid(initial=True)
        for _ in range(4):
            self.spawn_enemy(initial=True)
        self.mode = "game"
        self.selection = 0
        self.notify("Left/right rotate; Up thrusts; Down slows; hold Tab for gradual braking. Space fires, Shift launches.", 6)

    def spawn_asteroid(self, initial: bool = False) -> bool:
        large = random.random() < 0.22
        cells: list[tuple[float, float]] = []
        if large:
            # Begin with a connected cross, then add symmetric corner pairs.
            cells = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
            for pair in (((-1, -1), (1, 1)), ((-1, 1), (1, -1))):
                if random.random() < 0.72:
                    cells.extend(pair)
        else:
            # Compact 2x2 clusters, centered so the whole group spins in place.
            cells = random.choice([
                [(-0.5, 0), (0.5, 0)],
                [(-0.5, -0.5), (0.5, -0.5), (0, 0.5)],
                [(-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5), (0.5, 0.5)],
            ])
        rock = {"x": 0.0, "y": 0.0, "vx": random.uniform(-0.35, 0.35), "vy": random.uniform(-0.35, 0.35), "cells": cells, "hp": 2 if large else 1, "large": large, "angle": random.random() * math.tau, "spin": random.choice((-1, 1)) * random.uniform(0.35, 1.6)}
        placed = False
        for _ in range(180):
            spawn_angle = random.random() * math.tau
            spawn_radius = random.uniform(16, 54) if initial else random.uniform(34, 58)
            rock["x"] = self.player.x + math.cos(spawn_angle) * spawn_radius
            rock["y"] = self.player.y + math.sin(spawn_angle) * spawn_radius
            radius = self.asteroid_radius(rock)
            clear = all(distance(rock["x"], rock["y"], other["x"], other["y"]) >= radius + self.asteroid_radius(other) + 0.25 for other in self.asteroids)
            clear = clear and distance(rock["x"], rock["y"], self.player.x, self.player.y) >= radius + 1.7
            if self.mother.get("hp", 0) > 0:
                clear = clear and distance(rock["x"], rock["y"], self.mother["x"], self.mother["y"]) >= radius + 3.0
            clear = clear and all(distance(rock["x"], rock["y"], ship["x"], ship["y"]) >= radius + self.ship_radius(ship) + 0.35 for ship in self.enemies)
            clear = clear and all(distance(rock["x"], rock["y"], item["x"], item["y"]) >= radius + self.pickup_radius(item) + 0.35 for item in self.pickups)
            if clear:
                placed = True
                break
        if placed:
            self.asteroids.append(rock)
        return placed

    def asteroid_cells(self, rock: dict) -> list[tuple[float, float]]:
        angle = rock.get("angle", 0.0)
        cosine, sine = math.cos(angle), math.sin(angle)
        px_scale, py_scale = self.asteroid_pitch / self.cell_w, self.asteroid_pitch / self.cell_h
        return [
            (rock["x"] + (dx * px_scale * cosine - dy * py_scale * sine),
             rock["y"] + (dx * px_scale * sine + dy * py_scale * cosine))
            for dx, dy in rock["cells"]
        ]

    def asteroid_radius(self, rock: dict) -> float:
        px_scale, py_scale = self.asteroid_pitch / self.cell_w, self.asteroid_pitch / self.cell_h
        cell_radius = max(math.hypot(dx * px_scale, dy * py_scale) for dx, dy in rock["cells"])
        return cell_radius + max(px_scale, py_scale) * 0.65

    def bounce_asteroids(self) -> None:
        """Resolve asteroid-cluster overlaps as elastic, non-destructive collisions."""
        for index, first in enumerate(self.asteroids):
            for second in self.asteroids[index + 1:]:
                dx, dy = second["x"] - first["x"], second["y"] - first["y"]
                separation = math.hypot(dx, dy)
                min_separation = self.asteroid_radius(first) + self.asteroid_radius(second)
                if separation >= min_separation:
                    continue
                if separation < 1e-6:
                    angle = random.random() * math.tau
                    nx, ny = math.cos(angle), math.sin(angle)
                    separation = 1e-6
                else:
                    nx, ny = dx / separation, dy / separation
                correction = (min_separation - separation) * 0.5 + 0.01
                first["x"] -= nx * correction
                first["y"] -= ny * correction
                second["x"] += nx * correction
                second["y"] += ny * correction
                relative_speed = (second["vx"] - first["vx"]) * nx + (second["vy"] - first["vy"]) * ny
                if relative_speed < 0:
                    impulse = -(1.0 + 0.82) * relative_speed * 0.5
                    first["vx"] -= impulse * nx
                    first["vy"] -= impulse * ny
                    second["vx"] += impulse * nx
                    second["vy"] += impulse * ny

    def ship_radius(self, ship: dict) -> float:
        return 1.7 if ship is self.mother else 1.05

    @staticmethod
    def pickup_radius(pickup: dict) -> float:
        return 2.15 if pickup["kind"] == "missile" else 1.65

    @staticmethod
    def resolve_circles(first: dict, second: dict, first_radius: float, second_radius: float,
                        second_fixed: bool = False, restitution: float = 0.72) -> bool:
        """Separate overlapping circular bodies and bounce their velocities apart."""
        dx, dy = second["x"] - first["x"], second["y"] - first["y"]
        separation = math.hypot(dx, dy)
        minimum = first_radius + second_radius
        if separation >= minimum:
            return False
        if separation < 1e-6:
            angle = random.random() * math.tau
            nx, ny = math.cos(angle), math.sin(angle)
            separation = 1e-6
        else:
            nx, ny = dx / separation, dy / separation
        overlap = minimum - separation + 0.01
        if second_fixed:
            first["x"] -= nx * overlap
            first["y"] -= ny * overlap
        else:
            first["x"] -= nx * overlap * 0.5
            first["y"] -= ny * overlap * 0.5
            second["x"] += nx * overlap * 0.5
            second["y"] += ny * overlap * 0.5
        first.setdefault("vx", 0.0)
        first.setdefault("vy", 0.0)
        second.setdefault("vx", 0.0)
        second.setdefault("vy", 0.0)
        relative_speed = (first["vx"] - second["vx"]) * nx + (first["vy"] - second["vy"]) * ny
        if relative_speed > 0:
            impulse = (1.0 + restitution) * relative_speed
            if second_fixed:
                first["vx"] -= impulse * nx
                first["vy"] -= impulse * ny
            else:
                first["vx"] -= impulse * nx * 0.5
                first["vy"] -= impulse * ny * 0.5
                second["vx"] += impulse * nx * 0.5
                second["vy"] += impulse * ny * 0.5
        return True

    def asteroid_avoidance(self, x: float, y: float, clearance: float) -> tuple[float, float]:
        steer_x = steer_y = 0.0
        for rock in self.asteroids:
            dx, dy = x - rock["x"], y - rock["y"]
            d = math.hypot(dx, dy)
            safe_distance = self.asteroid_radius(rock) + clearance + 6.0
            if 1e-6 < d < safe_distance:
                strength = 7.0 * (safe_distance - d) / safe_distance
                steer_x += dx / d * strength
                steer_y += dy / d * strength
        return steer_x, steer_y

    def resolve_solid_collisions(self) -> None:
        """Keep ships outside asteroid fields and separate ships from each other."""
        ships = ([self.mother] if self.mother.get("hp", 0) > 0 else []) + self.enemies
        for _ in range(2):
            for ship in ships:
                for rock in self.asteroids:
                    self.resolve_circles(ship, rock, self.ship_radius(ship), self.asteroid_radius(rock), second_fixed=True, restitution=0.6)
            for i, first in enumerate(ships):
                for second in ships[i + 1:]:
                    self.resolve_circles(first, second, self.ship_radius(first), self.ship_radius(second), restitution=0.5)

    def bounce_pickups(self) -> None:
        """Bounce packs off rocks, living ships, and one another; leave player collection clear."""
        ships = ([self.mother] if self.mother.get("hp", 0) > 0 else []) + self.enemies
        for _ in range(2):
            for item in self.pickups:
                radius = self.pickup_radius(item)
                for rock in self.asteroids:
                    self.resolve_circles(item, rock, radius, self.asteroid_radius(rock), second_fixed=True)
                for ship in ships:
                    self.resolve_circles(item, ship, radius, self.ship_radius(ship), second_fixed=True)
            for i, first in enumerate(self.pickups):
                for second in self.pickups[i + 1:]:
                    self.resolve_circles(first, second, self.pickup_radius(first), self.pickup_radius(second))

    def draw_asteroid(self, rock: dict, screen_pos) -> None:
        cells = rock["cells"]
        min_x = min(cell[0] for cell in cells)
        max_x = max(cell[0] for cell in cells)
        min_y = min(cell[1] for cell in cells)
        max_y = max(cell[1] for cell in cells)
        pitch = self.asteroid_pitch
        columns = max(1, round(max_x - min_x + 1))
        rows = max(1, round(max_y - min_y + 1))
        sprite = pygame.Surface((columns * pitch, rows * pitch), pygame.SRCALPHA)
        glyph = pygame.transform.smoothscale(self.font.render("#", True, ORANGE), (pitch, pitch))
        for dx, dy in cells:
            px = round((dx - min_x) * pitch)
            py = round((dy - min_y) * pitch)
            sprite.blit(glyph, (px, py))
        sprite = pygame.transform.rotate(sprite, -math.degrees(rock.get("angle", 0.0)))
        center = screen_pos(rock["x"], rock["y"])
        rect = sprite.get_rect(center=(center[0] + self.cell_w // 2, center[1] + self.cell_h // 2))
        self.screen.blit(sprite, rect)

    def damage_player(self, amount: float, shieldable: bool = True) -> None:
        if shieldable and self.player.shield > 0:
            return
        self.player.hull = max(0.0, self.player.hull - amount)
        self.player.regen_wait = 3.0
        self.player.regen_tick = 0.0

    def shake(self, strength: float = 8.0, seconds: float = 0.28) -> None:
        self.shake_strength = max(self.shake_strength, strength)
        self.shake_time = max(self.shake_time, seconds)

    def spawn_enemy(self, initial: bool = False) -> None:
        for _ in range(120):
            a = random.random() * math.tau
            d = random.uniform(18, 38) if initial else random.uniform(28, 44)
            enemy = {"x": self.player.x + math.cos(a) * d, "y": self.player.y + math.sin(a) * d,
                     "vx": 0.0, "vy": 0.0, "hp": 3, "wait": random.uniform(0.7, 2.0)}
            radius = self.ship_radius(enemy)
            clear = all(distance(enemy["x"], enemy["y"], rock["x"], rock["y"]) >= radius + self.asteroid_radius(rock) + 0.5 for rock in self.asteroids)
            clear = clear and distance(enemy["x"], enemy["y"], self.player.x, self.player.y) >= radius + 1.8
            if self.mother.get("hp", 0) > 0:
                clear = clear and distance(enemy["x"], enemy["y"], self.mother["x"], self.mother["y"]) >= radius + self.ship_radius(self.mother) + 0.5
            clear = clear and all(distance(enemy["x"], enemy["y"], other["x"], other["y"]) >= radius + self.ship_radius(other) + 0.35 for other in self.enemies)
            clear = clear and all(distance(enemy["x"], enemy["y"], item["x"], item["y"]) >= radius + self.pickup_radius(item) + 0.35 for item in self.pickups)
            if clear:
                self.enemies.append(enemy)
                return

    def spawn_mother(self, initial: bool = False) -> None:
        if not initial:
            placed = False
            for _ in range(180):
                angle = random.random() * math.tau
                radius = random.uniform(34, 46)
                x, y = self.player.x + math.cos(angle) * radius, self.player.y + math.sin(angle) * radius
                clear = all(distance(x, y, rock["x"], rock["y"]) >= self.asteroid_radius(rock) + 11.0 for rock in self.asteroids)
                clear = clear and all(distance(x, y, enemy["x"], enemy["y"]) >= self.ship_radius(enemy) + 9.0 for enemy in self.enemies)
                clear = clear and all(distance(x, y, item["x"], item["y"]) >= self.pickup_radius(item) + 8.0 for item in self.pickups)
                if distance(x, y, self.player.x, self.player.y) >= 22.0 and clear:
                    self.mother = {"x": x, "y": y, "vx": random.uniform(-0.45, 0.45), "vy": random.uniform(-0.45, 0.45),
                                   "hp": 100.0, "wait": 1.5, "drop": False}
                    placed = True
                    break
            if not placed:
                return
        for index in range(5):
            angle = math.tau * index / 5 + random.uniform(-0.18, 0.18)
            radius = random.uniform(3.2, 5.0)
            self.enemies.append({"x": self.mother["x"] + math.cos(angle) * radius,
                                 "y": self.mother["y"] + math.sin(angle) * radius,
                                 "vx": self.mother["vx"], "vy": self.mother["vy"],
                                 "hp": 3, "wait": random.uniform(0.7, 2.0), "minion": True,
                                 "escort_angle": angle, "escort_radius": radius})

    def spawn_pickup(self, x: float, y: float, kind: str) -> None:
        self.pickups.append({"x": x, "y": y, "vx": random.uniform(-0.8, 0.8),
                             "vy": random.uniform(-0.8, 0.8), "kind": kind, "phase": random.random() * math.tau})

    def asteroid_drop(self, rock: dict) -> None:
        if random.random() < (0.22 if rock["large"] else 0.08):
            self.spawn_pickup(rock["x"], rock["y"], "utonium")

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
            for rock in self.asteroids:
                cells = rock.get("cells", [(0, 0)])
                center_x = (min(cell[0] for cell in cells) + max(cell[0] for cell in cells)) / 2
                center_y = (min(cell[1] for cell in cells) + max(cell[1] for cell in cells)) / 2
                rock["cells"] = [(x - center_x, y - center_y) for x, y in cells]
                rock.setdefault("angle", random.random() * math.tau)
                rock.setdefault("spin", random.choice((-1, 1)) * random.uniform(0.35, 1.6))
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
            self.audio.play("missile")
            p.missiles -= 1
            p.missile_wait = 0.55
            speed, kind, color = 21.0, "missile", ORANGE
        else:
            if p.laser_wait > 0:
                return
            self.audio.play("laser")
            p.laser_wait = 0.13
            speed, kind, color = 35.0, "laser", GREEN
        dx, dy = vector(p.facing, speed)
        shot = {"x": p.x, "y": p.y, "vx": dx, "vy": dy, "owner": "player", "kind": kind, "life": 5.0 if missile else 2.2, "color": color}
        if missile:
            # Missiles acquire hostile ships only; rocks remain unaffected by lock-on.
            targets = list(self.enemies)
            if self.mother.get("hp", 0) > 0:
                targets.append(self.mother)
            target = min(targets, key=lambda item: distance(p.x, p.y, item["x"], item["y"]), default=None)
            shot["target"] = target
            shot["homing"] = target is not None and random.random() < 0.90
        self.shots.append(shot)

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper) -> None:
        self.elapsed += dt
        p = self.player
        turning = float(keys[pygame.K_RIGHT]) - float(keys[pygame.K_LEFT])
        p.facing += turning * 3.2 * dt
        thrust = float(keys[pygame.K_UP])
        ax, ay = vector(p.facing, 18.0 * thrust)
        p.vx += ax * dt
        p.vy += ay * dt
        speed = math.hypot(p.vx, p.vy)
        max_speed = 13.0
        if speed > max_speed:
            p.vx, p.vy = p.vx / speed * max_speed, p.vy / speed * max_speed
        # In space the ship coasts; Tab applies gradual retro-thruster braking.
        if p.brake:
            drag = 5.5
        elif keys[pygame.K_DOWN]:
            drag = 1.8
        else:
            drag = 0.035
        friction = math.exp(-drag * dt)
        p.vx *= friction
        p.vy *= friction
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.laser_wait = max(0, p.laser_wait - dt)
        p.missile_wait = max(0, p.missile_wait - dt)
        if keys[pygame.K_SPACE]:
            self.fire(False)
        if p.regen_wait > 0:
            p.regen_wait = max(0.0, p.regen_wait - dt)
        elif p.hull < 100:
            p.regen_tick += dt
            if p.regen_tick >= 1.0:
                p.hull = min(100.0, p.hull + 1.0)
                p.regen_tick -= 1.0
        else:
            p.regen_tick = 0.0
        p.shield = max(0.0, p.shield - dt)
        self.shake_time = max(0.0, self.shake_time - dt)
        self.shake_strength *= math.exp(-7.0 * dt)
        self.alarm_wait = max(0.0, self.alarm_wait - dt)
        if p.hull < 20 and self.alarm_wait <= 0:
            self.audio.play("alarm")
            self.alarm_wait = 1.15

        # Mother ship slowly drifts, and fires tracking missiles at close range.
        m = self.mother
        md = distance(p.x, p.y, m["x"], m["y"])
        if m["hp"] > 0:
            avoid_x, avoid_y = self.asteroid_avoidance(m["x"], m["y"], self.ship_radius(m))
            m["vx"] += avoid_x * dt
            m["vy"] += avoid_y * dt
            mother_speed = math.hypot(m["vx"], m["vy"])
            if mother_speed > 2.4:
                m["vx"], m["vy"] = m["vx"] / mother_speed * 2.4, m["vy"] / mother_speed * 2.4
        m["x"] += m["vx"] * dt
        m["y"] += m["vy"] * dt
        m["wait"] -= dt
        if m["hp"] > 0 and md < 24 and m["wait"] <= 0:
            angle = math.atan2(p.y - m["y"], p.x - m["x"])
            vx, vy = vector(angle, 12)
            self.shots.append({"x": m["x"], "y": m["y"], "vx": vx, "vy": vy, "owner": "mother", "kind": "missile", "life": 4.0, "color": RED})
            m["wait"] = random.uniform(2.2, 3.5)
            self.audio.play("missile")
            self.notify("Mother ship launched a missile!")
        if m["drop"]:
            self.mother_respawn -= dt
            if self.mother_respawn <= 0:
                self.spawn_mother()
                self.mother_respawn = random.uniform(28.0, 42.0)

        # Smaller raiders pursue the player and fire short laser bursts.
        for e in self.enemies:
            d = distance(p.x, p.y, e["x"], e["y"])
            angle = math.atan2(p.y - e["y"], p.x - e["x"])
            if e.get("minion") and m["hp"] > 0:
                escort_angle = e["escort_angle"] + self.elapsed * 0.10
                tx = m["x"] + math.cos(escort_angle) * e["escort_radius"]
                ty = m["y"] + math.sin(escort_angle) * e["escort_radius"]
                desired_vx = m["vx"] + (tx - e["x"]) * 0.75
                desired_vy = m["vy"] + (ty - e["y"]) * 0.75
                avoid_x, avoid_y = self.asteroid_avoidance(e["x"], e["y"], self.ship_radius(e))
                desired_vx += avoid_x
                desired_vy += avoid_y
                e["vx"] += (desired_vx - e["vx"]) * min(1, dt * 1.6)
                e["vy"] += (desired_vy - e["vy"]) * min(1, dt * 1.6)
            else:
                tx, ty = vector(angle, 4.1 if d > 8 else 1.2)
                avoid_x, avoid_y = self.asteroid_avoidance(e["x"], e["y"], self.ship_radius(e))
                tx += avoid_x
                ty += avoid_y
                e["vx"] += (tx - e["vx"]) * min(1, dt * 0.8)
                e["vy"] += (ty - e["vy"]) * min(1, dt * 0.8)
            e["x"] += e["vx"] * dt
            e["y"] += e["vy"] * dt
            e["wait"] -= dt
            if d < 20 and e["wait"] <= 0:
                svx, svy = vector(angle, 17)
                self.shots.append({"x": e["x"], "y": e["y"], "vx": svx, "vy": svy, "owner": "enemy", "kind": "laser", "life": 2.3, "color": PURPLE})
                self.audio.play("enemy")
                e["wait"] = random.uniform(1.5, 2.7)

        # Drift small rocks and asteroid clusters.
        for rock in self.asteroids:
            rock["x"] += rock["vx"] * dt
            rock["y"] += rock["vy"] * dt
            rock["angle"] = (rock.get("angle", 0.0) + rock.get("spin", 0.0) * dt) % math.tau
        self.bounce_asteroids()
        self.resolve_solid_collisions()
        for shot in self.shots:
            if shot["kind"] == "missile" and shot.get("homing"):
                target = shot.get("target")
                valid = (target is self.mother and self.mother.get("hp", 0) > 0) or any(target is enemy for enemy in self.enemies)
                if valid:
                    desired = math.atan2(target["y"] - shot["y"], target["x"] - shot["x"])
                    current = math.atan2(shot["vy"], shot["vx"])
                    delta = math.atan2(math.sin(desired - current), math.cos(desired - current))
                    current += max(-6.5 * dt, min(6.5 * dt, delta))
                    missile_speed = math.hypot(shot["vx"], shot["vy"]) or 21.0
                    shot["vx"], shot["vy"] = vector(current, missile_speed)
                else:
                    shot["homing"] = False
            shot["x"] += shot["vx"] * dt
            shot["y"] += shot["vy"] * dt
            shot["life"] -= dt

        # Projectile impacts and combat damage.
        for shot in list(self.shots):
            if shot["owner"] == "player":
                for e in list(self.enemies):
                    if distance(shot["x"], shot["y"], e["x"], e["y"]) < 1.5:
                        e["hp"] -= 1 if shot["kind"] == "laser" else 3
                        self.shots.remove(shot)
                        self.audio.play("impact")
                        self.add_particles(e["x"], e["y"], GREEN, 8)
                        if e["hp"] <= 0:
                            self.enemies.remove(e)
                            self.score += 100
                            self.audio.play("explosion")
                            self.add_particles(e["x"], e["y"], ORANGE, 24)
                            if random.random() < 0.32:
                                self.spawn_pickup(e["x"], e["y"], random.choice(("hull", "missile", "shield")))
                        break
                if shot in self.shots and distance(shot["x"], shot["y"], m["x"], m["y"]) < 2.5:
                    m["hp"] -= 18 if shot["kind"] == "missile" else 5
                    self.shots.remove(shot)
                    self.audio.play("impact")
                    self.add_particles(m["x"], m["y"], YELLOW, 15)
                    if m["hp"] <= 0 and not m["drop"]:
                        m["hp"], m["drop"] = 0, True
                        self.score += 1000
                        self.spawn_pickup(m["x"] + 1, m["y"], "hull")
                        self.spawn_pickup(m["x"] - 1, m["y"], "missile")
                        self.spawn_pickup(m["x"], m["y"] + 1, "shield")
                        self.add_particles(m["x"], m["y"], ORANGE, 50)
                        self.audio.play("explosion")
                        self.notify("Mother ship destroyed! Hull and missile supplies released.", 5)
                if shot in self.shots:
                    for rock in list(self.asteroids):
                        if any(distance(shot["x"], shot["y"], rx, ry) < 0.8 for rx, ry in self.asteroid_cells(rock)):
                            rock["hp"] -= 3 if shot["kind"] == "missile" else 1
                            self.shots.remove(shot)
                            self.audio.play("impact")
                            self.shake(4.5, 0.18)
                            self.add_particles(shot["x"], shot["y"], YELLOW if shot["kind"] == "missile" else GREEN, 12)
                            if rock["hp"] <= 0:
                                self.asteroids.remove(rock)
                                self.score += 50 if rock["large"] else 20
                                self.audio.play("explosion")
                                self.shake(7 if rock["large"] else 4.5, 0.25)
                                self.add_particles(rock["x"], rock["y"], ORANGE, 32 if rock["large"] else 18)
                                self.asteroid_drop(rock)
                            break
            elif distance(shot["x"], shot["y"], p.x, p.y) < 1.2:
                self.damage_player(12 if shot["kind"] == "missile" else 5, shieldable=True)
                self.shots.remove(shot)
                self.audio.play("impact")
                self.shake(5.5, 0.23)
                self.add_particles(p.x, p.y, RED, 18)
                self.notify("Direct hit! Hull integrity damaged.")

        # Asteroid contact damages the hull; large rocks also kick the ship backward.
        for rock in list(self.asteroids):
            if any(distance(p.x, p.y, rx, ry) < 1.15 for rx, ry in self.asteroid_cells(rock)):
                self.damage_player(18 if rock["large"] else 9, shieldable=False)
                self.shake(10 if rock["large"] else 6, 0.32)
                if rock["large"]:
                    speed = math.hypot(p.vx, p.vy)
                    if speed > 0.2:
                        p.vx, p.vy = -p.vx * 0.72, -p.vy * 0.72
                    else:
                        p.vx, p.vy = vector(p.facing + math.pi, 3.5)
                self.asteroids.remove(rock)
                self.score += 20
                self.audio.play("explosion")
                self.add_particles(rock["x"], rock["y"], ORANGE, 30 if rock["large"] else 14)
                self.asteroid_drop(rock)
                self.notify("Asteroid collision! Hull damaged; rock shattered.")
                self.spawn_asteroid()

        # Packs drift freely until the ship comes close, then magnetic pull draws
        # them in. Collection remains possible only by the player's ship.
        for pickup in self.pickups:
            pickup.setdefault("vx", 0.0)
            pickup.setdefault("vy", 0.0)
            pickup.setdefault("phase", 0.0)
            pickup["phase"] = (pickup["phase"] + dt * 5.0) % math.tau
            dx, dy = p.x - pickup["x"], p.y - pickup["y"]
            d = math.hypot(dx, dy)
            if 1e-6 < d < 10.0:
                pull = 22.0 * (1.0 - d / 12.0)
                pickup["vx"] += dx / d * pull * dt
                pickup["vy"] += dy / d * pull * dt
            drag = math.exp(-0.8 * dt)
            pickup["vx"] *= drag
            pickup["vy"] *= drag
            pickup["x"] += pickup["vx"] * dt
            pickup["y"] += pickup["vy"] * dt
        self.bounce_pickups()
        for pickup in list(self.pickups):
            if distance(p.x, p.y, pickup["x"], pickup["y"]) < self.pickup_radius(pickup) + 0.6:
                if pickup["kind"] == "hull":
                    p.hull = min(100, p.hull + 30)
                    self.notify("Hull repair pack collected.")
                elif pickup["kind"] == "missile":
                    p.missiles = min(10, p.missiles + 5)
                    self.notify("Missile supply collected (+5, maximum 10).")
                elif pickup["kind"] == "shield":
                    p.shield = 100.0
                    self.notify("Shield activated at 100%.")
                else:
                    p.utonium += 1
                    self.score += 25
                    self.notify(f"Utonium collected. Cargo: {p.utonium}.")
                self.audio.play("pickup")
                self.pickups.remove(pickup)
                self.add_particles(p.x, p.y, GREEN, 12)

        # A mother ship also periodically releases supplies nearby while alive.
        if not m["drop"] and random.random() < dt * 0.025:
            self.spawn_pickup(m["x"] + random.uniform(-2, 2), m["y"] + random.uniform(-2, 2), random.choice(("hull", "missile", "shield")))
        self.bounce_pickups()
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
            if not self.spawn_asteroid():
                break
        if len(self.enemies) < 4 and random.random() < dt * 0.18:
            self.spawn_enemy()
        if p.hull <= 0:
            self.mode = "gameover"
            self.selection = 0
            self.gameover_timer = 4.2
            self.add_particles(p.x, p.y, ORANGE, 70)
            self.add_particles(p.x, p.y, RED, 35)
            self.audio.play("explosion")
            self.shake(13, 0.65)
            self.notify("Hull failure. Ship lost.", 3.5)
        self.message_time = max(0, self.message_time - dt)

    def draw_text(self, text: str, x: int, y: int, color: tuple[int, int, int], font: pygame.font.Font | None = None, center: bool = False) -> None:
        surf = (font or self.font).render(text, True, color)
        rect = surf.get_rect()
        rect.center = (x, y) if center else rect.center
        if not center:
            rect.topleft = (x, y)
        self.screen.blit(surf, rect)

    def draw_world(self, show_player: bool = True) -> None:
        p = self.player
        shake_x = random.uniform(-self.shake_strength, self.shake_strength) if self.shake_time > 0 else 0
        shake_y = random.uniform(-self.shake_strength, self.shake_strength) if self.shake_time > 0 else 0
        ox, oy = self.width / 2 - p.x * self.cell_w + shake_x, self.height / 2 - p.y * self.cell_h + shake_y
        self.screen.fill(BG)
        for sx, sy, size in self.stars:
            pygame.draw.circle(self.screen, (31, 51, 77), (sx, sy), size)

        def pos(x: float, y: float) -> tuple[int, int]:
            return round(ox + x * self.cell_w), round(oy + y * self.cell_h)

        def center_pos(x: float, y: float) -> tuple[int, int]:
            px, py = pos(x, y)
            return px + self.cell_w // 2, py + self.cell_h // 2

        for rock in self.asteroids:
            self.draw_asteroid(rock, pos)
        if self.mother["hp"] > 0:
            self.draw_text("<O>", *center_pos(self.mother["x"], self.mother["y"]), PURPLE, center=True)
        for e in self.enemies:
            self.draw_text("<>", *center_pos(e["x"], e["y"]), RED, center=True)
        for item in self.pickups:
            glyph, base_color = {
                "hull": ("[+]", GREEN),
                "missile": ("[!!]", YELLOW),
                "shield": ("[%]", CYAN),
                "utonium": ("[U]", PURPLE),
            }.get(item["kind"], ("[+]", GREEN))
            brightness = 1.0 if math.sin(item.get("phase", 0.0)) >= 0 else 0.35
            color = tuple(round(channel * brightness) for channel in base_color)
            self.draw_text(glyph, *center_pos(item["x"], item["y"]), color, center=True)
        for shot in self.shots:
            if shot["kind"] == "missile":
                glyph = "*"
            elif abs(shot["vx"]) > abs(shot["vy"]) * 2:
                glyph = "-"
            elif abs(shot["vy"]) > abs(shot["vx"]) * 2:
                glyph = "|"
            else:
                glyph = "/" if shot["vx"] * shot["vy"] < 0 else "\\"
            self.draw_text(glyph, *pos(shot["x"], shot["y"]), shot["color"])
        for part in self.particles:
            self.draw_text(part["glyph"], *pos(part["x"], part["y"]), part["color"], self.small)
        # A little exhaust flame appears opposite the current thrust direction.
        keys = pygame.key.get_pressed()
        if show_player and keys[pygame.K_UP]:
            fx, fy = vector(p.facing + math.pi, 1.0)
            self.draw_text(".", *pos(p.x + fx, p.y + fy), ORANGE)
        if show_player:
            ship_surface = self.font.render("A", True, CYAN)
            ship_surface = pygame.transform.rotate(ship_surface, -math.degrees(p.facing) - 90)
            center = pos(p.x, p.y)
            if p.shield > 0:
                pygame.draw.circle(self.screen, CYAN, (center[0] + self.cell_w // 2, center[1] + self.cell_h // 2), 22, 2)
            self.screen.blit(ship_surface, ship_surface.get_rect(center=(center[0] + self.cell_w // 2, center[1] + self.cell_h // 2)))

        pygame.draw.rect(self.screen, PANEL, (0, 0, self.width, 57))
        self.draw_text("DEEP SPACE", 24, 13, CYAN, self.ui)
        self.draw_text(f"HULL {int(p.hull):03d}%   SHIELD {int(p.shield):03d}%   MISSILES {p.missiles:02d}/10   UTONIUM {p.utonium:02d}   SCORE {self.score:06d}", 280, 14, WHITE, self.ui)
        self.draw_text("LEFT/RIGHT TURN   UP THRUST   DOWN SLOW   HOLD TAB BRAKE   SPACE LASER   SHIFT HOMING MISSILE   P PAUSE", 24, 63, DIM, self.small)
        self.draw_text("[+] HULL   [!!] MISSILES   [%] SHIELD   [U] UTONIUM   Packs are magnetic when you get close.", 24, 84, DIM, self.small)
        if self.message_time > 0:
            pygame.draw.rect(self.screen, (20, 26, 36), (18, self.height - 48, self.width - 36, 32))
            self.draw_text(self.message, 28, self.height - 44, YELLOW, self.small)
        pygame.draw.rect(self.screen, (26, 55, 75), (14, 49, self.width - 28, 3))
        pygame.draw.rect(self.screen, CYAN, (14, 49, max(3, int((self.width - 28) * p.hull / 100)), 3))
        if p.hull < 20:
            jitter = random.randint(-3, 3)
            pulse = 150 + int(90 * abs(math.sin(self.elapsed * 12)))
            red = (pulse, 20, 34)
            pygame.draw.rect(self.screen, red, (jitter, jitter, self.width - 2 * jitter, self.height - 2 * jitter), 6)

    def draw_menu(self, title: str, options: list[str], subtitle: str = "") -> None:
        self.screen.fill(BG)
        for x, y, size in self.stars:
            pygame.draw.circle(self.screen, (31, 51, 77), (x, y), size)
        self.draw_text("#  DEEP SPACE  #", self.width // 2, self.height // 3 - 46, CYAN, self.font, True)
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
            return [
                f"Fullscreen: {'On' if self.fullscreen else 'Off'}",
                f"Impact particles: {'On' if self.particles_on else 'Off'}",
                f"Music: {'On' if self.audio.music_on else 'Off'}",
                f"Sound effects: {'On' if self.audio.effects_on else 'Off'}",
                "Back",
            ]
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
            elif choice.startswith("Music:"):
                self.audio.toggle_music()
            elif choice.startswith("Sound effects:"):
                self.audio.toggle_effects()
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
                    if self.mode == "gameover":
                        if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                            self.gameover_timer = 0.0
                        continue
                    if event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    if self.mode == "game":
                        if event.key in (pygame.K_p, pygame.K_ESCAPE):
                            self.mode, self.selection = "pause", 0
                        elif event.key == pygame.K_TAB:
                            self.player.brake = True
                            self.audio.play("brake")
                        elif event.key == pygame.K_SPACE:
                            self.fire(False)
                        elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                            self.fire(True)
                        elif event.key == pygame.K_UP:
                            self.audio.play("thrust")
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.selection = (self.selection - 1) % len(self.menu_options())
                        self.audio.play("menu")
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.selection = (self.selection + 1) % len(self.menu_options())
                        self.audio.play("menu")
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.audio.play("menu")
                        running = self.activate()
                    elif event.key == pygame.K_ESCAPE:
                        if self.mode == "pause":
                            self.mode = "game"
                        elif self.mode in ("settings", "credits"):
                            self.mode, self.selection = self.return_mode if self.mode == "settings" else "menu", 0
                        elif self.mode == "gameover":
                            running = False
                elif event.type == pygame.KEYUP and event.key == pygame.K_TAB:
                    self.player.brake = False
            music_scene = "space" if self.mode in ("game", "pause") else "menu"
            self.audio.set_scene(music_scene)
            if self.mode == "gameover":
                self.gameover_timer -= dt
                self.shake_time = max(0.0, self.shake_time - dt)
                self.shake_strength *= math.exp(-7.0 * dt)
                for part in self.particles:
                    part["x"] += part["vx"] * dt
                    part["y"] += part["vy"] * dt
                    part["life"] -= dt
                self.particles = [part for part in self.particles if part["life"] > 0]
                self.draw_world(show_player=False)
                if self.gameover_timer <= 2.7:
                    banner = pygame.Surface((560, 146), pygame.SRCALPHA)
                    banner.fill((4, 8, 18, 205))
                    self.screen.blit(banner, banner.get_rect(center=(self.width // 2, self.height // 2)))
                    self.draw_text("GAME OVER", self.width // 2, self.height // 2 - 17, RED, self.font, True)
                    if self.gameover_timer <= 2.0:
                        self.draw_text("Returning to main menu...", self.width // 2, self.height // 2 + 28, WHITE, self.small, True)
                if self.gameover_timer <= 0:
                    self.mode, self.selection = "menu", 0
            elif self.mode == "game":
                self.update(dt, pygame.key.get_pressed())
                self.draw_world(show_player=self.mode == "game")
            elif self.mode in ("menu", "pause", "settings"):
                if self.mode == "pause":
                    self.draw_world()
                    overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 175))
                    self.screen.blit(overlay, (0, 0))
                    self.draw_menu("PAUSED", self.menu_options())
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
