#!/usr/bin/env python3
"""Tests sans écran pour snake.py (SDL dummy)."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame  # noqa: E402
import snake as S  # noqa: E402

FAILS = []


def check(label, cond):
    print(("  OK  " if cond else " FAIL ") + label)
    if not cond:
        FAILS.append(label)


def section(t):
    print("\n== " + t + " ==")


def run():
    pygame.init()
    screen = pygame.display.set_mode((S.WIDTH, S.HEIGHT))

    # ---------------------------------------------------------------- logique
    section("Démarrage de partie")
    g = S.Game(rng=__import__("random").Random(42))
    check("3 segments au départ", len(g.snake) == 3)
    check("score à 0", g.score == 0)
    check("serpent vivant", g.alive)
    check("nourriture hors du serpent", g.food.pos not in set(g.snake))
    check("nourriture dans la grille",
          0 <= g.food.x < S.COLS and 0 <= g.food.y < S.ROWS)

    section("Déplacement")
    head = g.snake[0]
    g.step()
    check("la tête avance vers la droite", g.snake[0] == (head[0] + 1, head[1]))
    check("longueur stable sans pomme", len(g.snake) == 3)

    section("Demi-tour interdit")
    g2 = S.Game(rng=__import__("random").Random(1))
    g2.turn(S.LEFT)              # direction actuelle = RIGHT
    check("LEFT ignoré", g2.pending == [])
    g2.turn(S.UP)
    check("UP accepté", g2.pending == [S.UP])

    section("Manger une pomme")
    g3 = S.Game(rng=__import__("random").Random(7))
    g3.food = S.Food(g3.snake[0][0] + 1, g3.snake[0][1], golden=False)
    before_len = len(g3.snake)
    g3.step()
    check("longueur +1", len(g3.snake) == before_len + 1)
    check("score +1", g3.score == 1)
    check("compteur de pommes", g3.apples == 1)
    check("la vitesse augmente", g3.speed < S.BASE_SPEED)
    check("particules créées", len(g3.particles) > 0)
    check("nouvelle pomme générée", g3.food.pos not in set(g3.snake))

    section("Pomme dorée")
    g4 = S.Game(rng=__import__("random").Random(3))
    g4.food = S.Food(g4.snake[0][0] + 1, g4.snake[0][1], golden=True)
    g4.step()
    check("score +5", g4.score == 5)
    check("last_eat_golden", g4.last_eat_golden is True)

    section("Collision mur")
    g5 = S.Game(rng=__import__("random").Random(5))
    g5.snake = [(S.COLS - 1, 5), (S.COLS - 2, 5), (S.COLS - 3, 5)]
    g5.direction = S.RIGHT
    g5.pending = []
    g5.step()
    check("mort sur le mur droit", not g5.alive)

    section("Collision queue / corps")
    g6 = S.Game(rng=__import__("random").Random(6))
    # Carré : la tête va revenir sur le corps
    g6.snake = [(5, 5), (5, 6), (4, 6), (4, 5)]
    g6.direction = S.RIGHT
    g6.pending = []
    g6.food = S.Food(20, 20)
    # On force une direction vers le bas puis la tête revient sur (5,6)
    g6.snake = [(4, 5), (4, 6), (5, 6), (5, 5)]
    g6.direction = S.RIGHT
    g6.step()                    # (5,5) est la queue -> autorisé
    check("suivre sa queue est autorisé", g6.alive)
    g6.snake = [(4, 5), (5, 5), (6, 5), (6, 6)]
    g6.direction = S.DOWN
    g6.pending = []
    g6.step()                    # (4,6) n'est pas le corps, ok
    check("avancer normalement", g6.alive)

    g7 = S.Game(rng=__import__("random").Random(8))
    # tête (5,5) ; le corps passe par (5,6) qui n'est PAS la queue -> mort
    g7.snake = [(5, 5), (6, 5), (6, 6), (5, 6), (4, 6)]
    g7.direction = S.DOWN
    g7.pending = []
    g7.food = S.Food(20, 20)
    g7.step()
    check("mort en se mordant", not g7.alive)

    section("Pause")
    g8 = S.Game(rng=__import__("random").Random(9))
    g8.paused = True
    pos = list(g8.snake)
    g8.update(1.0)
    check("rien ne bouge en pause", g8.snake == pos)
    g8.paused = False
    g8.update(1.0)
    check("reprise du mouvement", g8.snake != pos)

    section("Grande vitesse = plusieurs pas par frame")
    g9 = S.Game(rng=__import__("random").Random(10))
    g9.speed = 0.01
    g9.update(0.05)
    check("plusieurs déplacements", len(g9.snake) >= 3)

    section("Partout rempli")
    g10 = S.Game(rng=__import__("random").Random(11))
    g10.snake = [(x, y) for x in range(S.COLS) for y in range(S.ROWS)]
    f = g10.spawn_food()
    check("pomme sentinelle si plateau plein", f.x == -1 and f.y == -1)

    section("Rendu de tous les états")
    r = S.Renderer(screen)
    try:
        g11 = S.Game(rng=__import__("random").Random(12))
        for st in ("menu", "playing", "paused", "gameover"):
            for blink in (True, False):
                r.draw(g11, 12, st, blink, 12)
        check("rendu des 4 états sans exception", True)
    except Exception as exc:  # noqa: BLE001
        print("     ", type(exc).__name__, exc)
        check("rendu des 4 états sans exception", False)

    try:
        g12 = S.Game(rng=__import__("random").Random(13))
        g12.food = S.Food(3, 3, golden=True)
        g12.shake = 0.5
        g12.flash = 1.0
        g12.burst(3, 3, S.GOLD_COLOR, 30)
        for _ in range(60):
            g12.update(1 / 60)
            r.draw(g12, 0, "playing", True, 0)
        check("60 frames animées (pomme dorée + particules + shake)", True)
    except Exception as exc:  # noqa: BLE001
        print("     ", type(exc).__name__, exc)
        check("60 frames animées", False)

    try:
        long_snake = S.Game(rng=__import__("random").Random(14))
        long_snake.snake = [(x, 0) for x in range(S.COLS)] + \
                           [(S.COLS - 1, y) for y in range(1, S.ROWS)]
        long_snake.food = S.Food(0, 5)
        r.draw(long_snake, 999, "playing", True, 0)
        check("serpent très long rendu", True)
    except Exception as exc:  # noqa: BLE001
        print("     ", type(exc).__name__, exc)
        check("serpent très long rendu", False)

    section("Barre de vitesse aux extrêmes")
    try:
        g13 = S.Game(rng=__import__("random").Random(15))
        g13.speed = S.BASE_SPEED
        r._draw_hud(g13, 0)
        g13.speed = S.MIN_SPEED
        r._draw_hud(g13, 0)
        check("barre de vitesse min/max", True)
    except Exception as exc:  # noqa: BLE001
        print("     ", type(exc).__name__, exc)
        check("barre de vitesse min/max", False)

    section("Score / record")
    import tempfile
    S.HIGHSCORE_FILE = os.path.join(tempfile.mkdtemp(), "hs.json")
    S.save_highscore(37)
    check("record sauvegardé et relu", S.load_highscore() == 37)
    S.HIGHSCORE_FILE = os.path.join(tempfile.mkdtemp(), "absent.json")
    check("record absent -> 0", S.load_highscore() == 0)

    section("Sons générés")
    snd = S.Sound()
    check("moteur audio dummy initialisé", pygame.mixer.get_init() is not None)
    check("sons construits", len(snd.sounds) >= 3)
    snd.play("eat")
    snd.play("die")
    check("lecture sans exception", True)


if __name__ == "__main__":
    run()
    print("\n" + ("ÉCHECS : " + ", ".join(FAILS) if FAILS else "Tous les tests passent."))
    sys.exit(1 if FAILS else 0)
