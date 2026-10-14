#!/usr/bin/env python3
"""
Snake — un jeu de serpent complet avec pygame.

Contrôles :
    Flèches / ZQSD / WASD   : se déplacer
    ESPACE / P              : pause
    ENTREE                  : démarrer / rejouer
    ECHAP                   : retour au menu / quitter
    M                       : couper/réactiver le son

Lancement :  python3 snake.py
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from dataclasses import dataclass, field
from typing import Optional

import pygame

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TITLE = "Snake"

CELL = 24                 # taille d'une case en pixels
COLS, ROWS = 28, 22       # dimensions de la grille
HUD_H = 68                # hauteur de la barre d'informations

WIDTH = COLS * CELL
HEIGHT = ROWS * CELL + HUD_H

FPS = 60

# Couleurs (R, G, B)
BG_TOP = (18, 24, 32)
BG_BOTTOM = (12, 16, 22)
GRID_A = (26, 33, 43)
GRID_B = (23, 30, 39)
HUD_BG = (15, 20, 27)

SNAKE_HEAD = (120, 235, 140)
SNAKE_BODY_A = (70, 200, 110)
SNAKE_BODY_B = (58, 178, 98)
SNAKE_OUTLINE = (24, 60, 42)

FOOD_COLOR = (240, 78, 92)
FOOD_SHINE = (255, 190, 190)
GOLD_COLOR = (250, 200, 70)
GOLD_SHINE = (255, 240, 190)

TEXT = (232, 238, 245)
TEXT_DIM = (140, 152, 168)
ACCENT = (120, 235, 140)
DANGER = (240, 90, 100)

# Vitesse : secondes par déplacement, du plus lent au plus rapide
BASE_SPEED = 0.135
MIN_SPEED = 0.055
SPEED_STEP = 0.004      # accélération par pomme mangée

HIGHSCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscore.json")

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

KEYMAP = {
    pygame.K_UP: UP, pygame.K_w: UP, pygame.K_z: UP,
    pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT, pygame.K_q: LEFT,
    pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
}


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def load_highscore() -> int:
    try:
        with open(HIGHSCORE_FILE, "r", encoding="utf-8") as fh:
            return int(json.load(fh).get("highscore", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def save_highscore(score: int) -> None:
    try:
        with open(HIGHSCORE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"highscore": int(score)}, fh)
    except OSError:
        pass  # pas bloquant pour le jeu


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix(c1, c2, t: float):
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


def draw_text(surface, font, text, color, pos, anchor="topleft"):
    img = font.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    surface.blit(img, rect)
    return rect


def rounded_rect(surface, color, rect, radius=8, width=0):
    pygame.draw.rect(surface, color, rect, width, border_radius=radius)


# ---------------------------------------------------------------------------
# Entités
# ---------------------------------------------------------------------------

@dataclass
class Food:
    x: int
    y: int
    golden: bool = False
    born: float = 0.0

    @property
    def pos(self):
        return (self.x, self.y)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple
    size: float


@dataclass
class Game:
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        self.reset()

    # -- cycle de vie -------------------------------------------------------

    def reset(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx - i, cy) for i in range(3)]   # tête en premier
        self.direction = RIGHT
        self.pending: list = []          # file d'entrées pour éviter les demi-tours
        self.score = 0
        self.apples = 0
        self.last_eat_golden = False
        self.alive = True
        self.paused = False
        self.speed = BASE_SPEED
        self.move_timer = 0.0
        self.food = self.spawn_food()
        self.particles: list[Particle] = []
        self.shake = 0.0
        self.flash = 0.0
        self.step_count = 0

    def spawn_food(self) -> Food:
        occupied = set(self.snake)
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in occupied]
        if not free:
            return Food(-1, -1)
        x, y = self.rng.choice(free)
        golden = self.apples >= 4 and self.rng.random() < 0.18
        return Food(x, y, golden=golden, born=pygame.time.get_ticks() / 1000.0)

    # -- entrées ------------------------------------------------------------

    def turn(self, new_dir) -> None:
        """Ajoute une direction à la file ; les entrées sont appliquées à chaque pas."""
        last = self.pending[-1] if self.pending else self.direction
        if new_dir == last:
            return
        if (new_dir[0] == -last[0] and new_dir[1] == -last[1]):
            return  # demi-tour interdit
        if len(self.pending) < 2:
            self.pending.append(new_dir)

    # -- simulation ---------------------------------------------------------

    def update(self, dt: float) -> None:
        self.update_particles(dt)
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 3.0)
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt * 2.5)
        if not self.alive or self.paused:
            return

        self.move_timer += dt
        while self.move_timer >= self.speed:
            self.move_timer -= self.speed
            self.step()
            if not self.alive:
                break

    def step(self) -> None:
        if self.pending:
            self.direction = self.pending.pop(0)

        hx, hy = self.snake[0]
        nx, ny = hx + self.direction[0], hy + self.direction[1]

        # Collision murs
        if not (0 <= nx < COLS and 0 <= ny < ROWS):
            self.die()
            return

        # Collision corps (la queue va bouger, sauf si on grandit)
        growing = (nx, ny) == self.food.pos
        body = self.snake if growing else self.snake[:-1]
        if (nx, ny) in body:
            self.die()
            return

        self.snake.insert(0, (nx, ny))
        self.step_count += 1

        if growing:
            self.eat()
        else:
            self.snake.pop()

    def eat(self) -> None:
        f = self.food
        gain = 5 if f.golden else 1
        self.last_eat_golden = f.golden
        self.apples += 1
        self.score += gain
        self.speed = max(MIN_SPEED, self.speed - SPEED_STEP * (2 if f.golden else 1))
        self.shake = 0.35 if f.golden else 0.18
        self.flash = 0.5 if f.golden else 0.0
        color = GOLD_COLOR if f.golden else FOOD_COLOR
        self.burst(f.x, f.y, color, 26 if f.golden else 14)
        self.food = self.spawn_food()

    def die(self) -> None:
        self.alive = False
        self.shake = 0.6
        self.burst(*self.snake[0], DANGER, 30)

    # -- particules ---------------------------------------------------------

    def burst(self, gx: int, gy: int, color, count: int) -> None:
        cx = gx * CELL + CELL / 2
        cy = gy * CELL + HUD_H + CELL / 2
        for _ in range(count):
            ang = self.rng.uniform(0, math.tau)
            spd = self.rng.uniform(40, 210)
            life = self.rng.uniform(0.25, 0.65)
            self.particles.append(Particle(
                cx, cy,
                math.cos(ang) * spd, math.sin(ang) * spd,
                life, life, color,
                self.rng.uniform(2.0, 4.5),
            ))

    def update_particles(self, dt: float) -> None:
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 420 * dt          # gravité
            p.vx *= 0.98
            alive.append(p)
        self.particles = alive


# ---------------------------------------------------------------------------
# Sons (générés en mémoire : aucune ressource externe requise)
# ---------------------------------------------------------------------------

class Sound:
    def __init__(self):
        self.enabled = True
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self._build()
        except pygame.error:
            self.enabled = False

    def _tone(self, freq: float, dur: float, vol: float = 0.25,
              freq_end: Optional[float] = None, wave: str = "sine"):
        rate = pygame.mixer.get_init()[0]
        n = max(1, int(rate * dur))
        buf = bytearray()
        phase = 0.0
        f_end = freq if freq_end is None else freq_end
        for i in range(n):
            t = i / n
            f = lerp(freq, f_end, t)
            phase += math.tau * f / rate
            if wave == "square":
                s = 1.0 if math.sin(phase) >= 0 else -1.0
            elif wave == "noise":
                s = random.uniform(-1, 1)
            else:
                s = math.sin(phase)
            env = min(1.0, i / (rate * 0.005) + 0.001) * (1.0 - t) ** 1.4
            v = int(max(-32768, min(32767, s * env * vol * 32767)))
            buf += int(v).to_bytes(2, "little", signed=True)
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _build(self):
        self.sounds["eat"] = self._tone(660, 0.09, 0.30, 980)
        self.sounds["gold"] = self._tone(880, 0.18, 0.30, 1500)
        self.sounds["die"] = self._tone(320, 0.45, 0.32, 70, wave="square")
        self.sounds["turn"] = self._tone(1200, 0.025, 0.07)

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            try:
                snd.play()
            except pygame.error:
                pass


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(self, surface: pygame.Surface):
        self.surface = surface
        self.font_big = pygame.font.SysFont("Helvetica,Arial", 64, bold=True)
        self.font_mid = pygame.font.SysFont("Helvetica,Arial", 30, bold=True)
        self.font = pygame.font.SysFont("Helvetica,Arial", 20)
        self.font_small = pygame.font.SysFont("Helvetica,Arial", 16)
        self.font_tiny = pygame.font.SysFont("Helvetica,Arial", 13)
        self.bg = self._build_bg()

    def _build_bg(self) -> pygame.Surface:
        """Damier + dégradé, précalculé une fois."""
        surf = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            t = y / max(1, HEIGHT - 1)
            pygame.draw.line(surf, mix(BG_TOP, BG_BOTTOM, t), (0, y), (WIDTH, y))
        for gy in range(ROWS):
            for gx in range(COLS):
                if (gx + gy) % 2 == 0:
                    rect = pygame.Rect(gx * CELL, HUD_H + gy * CELL, CELL, CELL)
                    pygame.draw.rect(surf, GRID_A, rect)
        return surf

    def draw(self, game: Game, highscore: int, state: str,
             blink: bool, best_this_run: int) -> None:
        offset = (0, 0)
        if game.shake > 0:
            amp = game.shake * 9
            offset = (random.uniform(-amp, amp), random.uniform(-amp, amp))

        self.surface.blit(self.bg, offset)
        self._draw_particles(game, offset)
        self._draw_food(game, offset)
        self._draw_snake(game, offset)
        self._draw_hud(game, highscore)
        if game.flash > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 235, 150, int(60 * game.flash)))
            self.surface.blit(overlay, offset)

        if state == "menu":
            self._draw_menu(blink)
        elif state == "paused":
            self._draw_pause()
        elif state == "gameover":
            self._draw_gameover(game, highscore, best_this_run)

    # -- couches ------------------------------------------------------------

    def _draw_particles(self, game: Game, offset):
        for p in game.particles:
            t = max(0.0, p.life / p.max_life)
            alpha = int(255 * t)
            size = max(1, int(p.size * (0.4 + t)))
            layer = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*p.color, alpha), (size, size), size)
            self.surface.blit(layer, (p.x - size + offset[0], p.y - size + offset[1]))

    def _draw_food(self, game: Game, offset):
        f = game.food
        if f.x < 0:
            return
        pulse = 1.0 + 0.10 * math.sin(pygame.time.get_ticks() / 190.0)
        cx = f.x * CELL + CELL / 2 + offset[0]
        cy = f.y * CELL + HUD_H + CELL / 2 + offset[1]
        r = (CELL * 0.36) * pulse
        color = GOLD_COLOR if f.golden else FOOD_COLOR
        shine = GOLD_SHINE if f.golden else FOOD_SHINE

        if f.golden:
            halo = pygame.Surface((int(r * 6), int(r * 6)), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*color, 55), (r * 3, r * 3), r * 2.7)
            self.surface.blit(halo, (cx - r * 3, cy - r * 3))

        pygame.draw.circle(self.surface, color, (int(cx), int(cy)), int(r))
        pygame.draw.circle(self.surface, shine, (int(cx - r * 0.3), int(cy - r * 0.35)),
                           max(1, int(r * 0.30)))

    def _draw_snake(self, game: Game, offset):
        n = len(game.snake)
        for i, (gx, gy) in enumerate(game.snake):
            t = i / max(1, n - 1)
            base = mix(SNAKE_HEAD, SNAKE_BODY_B, min(1.0, t * 1.15))
            rect = pygame.Rect(gx * CELL + offset[0], gy * CELL + HUD_H + offset[1], CELL, CELL)
            inner = rect.inflate(-3, -3)
            rounded_rect(self.surface, SNAKE_OUTLINE, rect, 7)
            rounded_rect(self.surface, base, inner, 6)

            if i == 0:
                self._draw_eyes(rect, game.direction)

        # langue qui bouge
        if game.alive and game.snake and (pygame.time.get_ticks() // 220) % 3 == 0:
            hx, hy = game.snake[0]
            dx, dy = game.direction
            bx = hx * CELL + CELL / 2 + dx * CELL * 0.62 + offset[0]
            by = hy * CELL + HUD_H + CELL / 2 + dy * CELL * 0.62 + offset[1]
            tipx = bx + dx * 7
            tipy = by + dy * 7
            pygame.draw.line(self.surface, (235, 90, 110), (bx, by), (tipx, tipy), 2)

    def _draw_eyes(self, rect: pygame.Rect, direction):
        dx, dy = direction
        # positions perpendiculaires pour les deux yeux
        px, py = -dy, dx
        cx, cy = rect.centerx, rect.centery
        for s in (-1, 1):
            ex = cx + dx * 4 + px * 4.5 * s
            ey = cy + dy * 4 + py * 4.5 * s
            pygame.draw.circle(self.surface, (250, 252, 255), (int(ex), int(ey)), 4)
            pygame.draw.circle(self.surface, (16, 20, 26),
                               (int(ex + dx * 1.6), int(ey + dy * 1.6)), 2)

    # -- HUD ----------------------------------------------------------------

    def _draw_hud(self, game: Game, highscore: int):
        pygame.draw.rect(self.surface, HUD_BG, (0, 0, WIDTH, HUD_H))
        pygame.draw.line(self.surface, (34, 43, 56), (0, HUD_H - 1), (WIDTH, HUD_H - 1))

        # score
        draw_text(self.surface, self.font_small, "SCORE", TEXT_DIM, (18, 12))
        draw_text(self.surface, self.font_mid, str(game.score), ACCENT, (18, 26))

        # longueur
        draw_text(self.surface, self.font_small, "LONGUEUR", TEXT_DIM, (WIDTH // 2 - 60, 12))
        draw_text(self.surface, self.font_mid, str(len(game.snake)), TEXT, (WIDTH // 2 - 60, 26))

        # record
        best = max(highscore, game.score)
        draw_text(self.surface, self.font_small, "RECORD", TEXT_DIM,
                  (WIDTH - 18, 12), anchor="topright")
        draw_text(self.surface, self.font_mid, str(best), GOLD_COLOR,
                  (WIDTH - 18, 26), anchor="topright")

        # barre de vitesse sous le score
        t = min(1.0, max(0.0, (BASE_SPEED - game.speed) / max(1e-6, BASE_SPEED - MIN_SPEED)))
        bar = pygame.Rect(18, HUD_H - 15, 152, 6)
        rounded_rect(self.surface, (40, 50, 64), bar, 3)
        filled = int(bar.w * t)
        if filled > 0:
            rounded_rect(self.surface, mix(ACCENT, DANGER, t),
                         pygame.Rect(bar.x, bar.y, filled, bar.h), 3)
        draw_text(self.surface, self.font_tiny, "VITESSE", TEXT_DIM,
                  (bar.right + 8, bar.y - 3))

    # -- écrans -------------------------------------------------------------

    def _panel(self, w: int, h: int) -> pygame.Rect:
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (WIDTH // 2, HUD_H + (HEIGHT - HUD_H) // 2)
        shadow = rect.move(0, 6)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((6, 9, 13, 165))
        self.surface.blit(veil, (0, 0))
        rounded_rect(self.surface, (10, 14, 19), shadow, 18)
        rounded_rect(self.surface, (25, 32, 42), rect, 18)
        rounded_rect(self.surface, (58, 72, 92), rect, 18, width=2)
        return rect

    def _draw_menu(self, blink: bool):
        rect = self._panel(440, 340)
        cx = rect.centerx
        y = rect.top + 44
        draw_text(self.surface, self.font_big, "SNAKE", ACCENT, (cx, y), anchor="midtop")
        y += 74
        draw_text(self.surface, self.font_small,
                  "Mangez les pommes, évitez les murs et votre queue.",
                  TEXT_DIM, (cx, y), anchor="midtop")
        y += 34
        draw_text(self.surface, self.font_tiny,
                  "Or = 5 points  •  la vitesse augmente à chaque pomme",
                  GOLD_COLOR, (cx, y), anchor="midtop")
        y += 44
        draw_text(self.surface, self.font_small,
                  "Flèches / ZQSD / WASD  —  se déplacer",
                  TEXT, (cx, y), anchor="midtop")
        y += 26
        draw_text(self.surface, self.font_small,
                  "ESPACE  —  pause        M  —  son        ECHAP  —  quitter",
                  TEXT, (cx, y), anchor="midtop")
        y += 52
        if blink:
            draw_text(self.surface, self.font_mid, "ENTRÉE pour jouer",
                      ACCENT, (cx, y), anchor="midtop")

    def _draw_pause(self):
        rect = self._panel(340, 170)
        draw_text(self.surface, self.font_big, "PAUSE", TEXT, rect.center, anchor="center")
        draw_text(self.surface, self.font_small, "ESPACE ou P pour reprendre",
                  TEXT_DIM, (rect.centerx, rect.centery + 52), anchor="midtop")

    def _draw_gameover(self, game: Game, highscore: int, best_this_run: int):
        rect = self._panel(400, 290)
        cx = rect.centerx
        y = rect.top + 40
        new_record = game.score > highscore and game.score > 0
        title = "NOUVEAU RECORD !" if new_record else "PARTIE TERMINÉE"
        draw_text(self.surface, self.font_mid, title,
                  GOLD_COLOR if new_record else DANGER, (cx, y), anchor="midtop")
        y += 56
        draw_text(self.surface, self.font_big, str(game.score), ACCENT,
                  (cx, y), anchor="midtop")
        y += 78
        draw_text(self.surface, self.font, f"Pommes : {game.apples}", TEXT,
                  (cx, y), anchor="midtop")
        y += 28
        draw_text(self.surface, self.font, f"Longueur : {len(game.snake)}", TEXT,
                  (cx, y), anchor="midtop")
        y += 28
        draw_text(self.surface, self.font, f"Record : {max(highscore, best_this_run)}",
                  GOLD_COLOR, (cx, y), anchor="midtop")
        y += 48
        draw_text(self.surface, self.font_mid, "ENTRÉE pour rejouer", TEXT,
                  (cx, y), anchor="midtop")
        draw_text(self.surface, self.font_tiny, "ECHAP pour quitter",
                  TEXT_DIM, (cx, y + 34), anchor="midtop")


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

def main() -> int:
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    renderer = Renderer(screen)
    sound = Sound()

    highscore = load_highscore()
    best_this_run = 0
    game = Game()
    state = "menu"          # menu | playing | paused | gameover

    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        blink = (pygame.time.get_ticks() // 500) % 2 == 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state in ("playing", "paused"):
                        state = "menu"
                        game.reset()
                    else:
                        running = False

                elif event.key == pygame.K_m:
                    sound.enabled = not sound.enabled

                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if state in ("menu", "gameover"):
                        game.reset()
                        state = "playing"

                elif event.key in (pygame.K_SPACE, pygame.K_p):
                    if state == "playing":
                        state = "paused"
                        game.paused = True
                    elif state == "paused":
                        state = "playing"
                        game.paused = False

                elif state == "playing" and event.key in KEYMAP:
                    game.turn(KEYMAP[event.key])

        prev_score = game.score
        if state == "playing":
            game.update(dt)
            if game.score > prev_score:
                sound.play("gold" if game.last_eat_golden else "eat")
            if not game.alive:
                state = "gameover"
                best_this_run = max(best_this_run, game.score)
                if game.score > highscore:
                    highscore = game.score
                    save_highscore(highscore)
                sound.play("die")
        elif state == "gameover":
            game.update(dt)          # laisse vivre les particules
        # menu / pause : rien à simuler

        renderer.draw(game, highscore, state, blink, best_this_run)
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
