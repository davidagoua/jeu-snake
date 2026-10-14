#!/usr/bin/env python3
"""Lance la vraie boucle main() avec des touches simulées et sauve des captures."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pygame  # noqa: E402
import snake as S  # noqa: E402

SHOTS = os.path.join(HERE, "captures")
os.makedirs(SHOTS, exist_ok=True)

script = []          # (frame, key)
for f in range(5):
    script.append((f, None))
script.append((6, pygame.K_RETURN))          # démarrer
for f in range(8, 60):                        # jouer un peu
    script.append((f, pygame.K_UP))
script.append((62, pygame.K_SPACE))           # pause
script.append((70, pygame.K_SPACE))           # reprendre
for f in range(75, 130):
    script.append((f, pygame.K_RIGHT))
script.append((132, pygame.K_m))              # couper le son
script.append((140, pygame.K_ESCAPE))         # retour menu
script.append((145, pygame.K_RETURN))         # rejouer
for f in range(150, 200):
    script.append((f, pygame.K_DOWN))
script.append((205, pygame.K_ESCAPE))         # menu
script.append((210, pygame.K_ESCAPE))         # quitter

frame = 0
injected = {}

# Captures demandées à certaines frames
WANT = {4: "01-menu", 40: "02-partie", 65: "03-pause", 200: "04-retour"}


def fake_get():
    global frame
    events = []
    for f, key in script:
        if f == frame and key is not None:
            events.append(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0,
                                             unicode="", scancode=0))
    frame += 1
    if frame > 400:
        events.append(pygame.event.Event(pygame.QUIT))
    return events


pygame.event.get = fake_get

real_flip = pygame.display.flip
shots_taken = []


def fake_flip():
    real_flip()
    name = WANT.get(frame)
    if name:
        surf = pygame.display.get_surface()
        for suffix in ("a", "b"):
            path = os.path.join(SHOTS, f"{name}-{suffix}.png")
            if not os.path.exists(path):
                pygame.image.save(surf, path)
                shots_taken.append(path)
                break


pygame.display.flip = fake_flip

rc = S.main()
print("main() a rendu le code :", rc)
print("captures :", len(shots_taken))
for p in shots_taken:
    print("  ", os.path.relpath(p, HERE), os.path.getsize(p), "octets")
print("frames simulées :", frame)
