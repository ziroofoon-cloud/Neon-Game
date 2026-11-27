import math
import os
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.uix.label import Label
from kivy.uix.widget import Widget

Window.clearcolor = (0.04, 0.04, 0.10, 1)

MAX_LIVES = 5
COLORS = {
    "star": (1.0, 0.9, 0.2),
    "bomb": (1.0, 0.25, 0.35),
    "heart": (0.3, 1.0, 0.5),
    "shield": (0.3, 0.9, 1.0),
    "slow": (0.75, 0.45, 1.0),
}


class Game(Widget):
    def __init__(self, store, **kw):
        super().__init__(**kw)
        self.store = store
        self.best = store.get("best")["v"] if store.exists("best") else 0
        self.mode = "menu"  # menu / play / pause / over
        self.bg = [[random.random(), random.random(), random.uniform(1, 3),
                    random.uniform(0.02, 0.08)] for _ in range(40)]
        self.items = []
        self.parts = []
        self.trail = []
        self.score = 0
        self.lives = 3
        self.combo = 0
        self.level = 1
        self.px = self.target = 0
        self.spawn = 0
        self.shield = 0
        self.slow = 0
        self.shake = 0
        self.t_over = 0
        self.new_best = False

        self.hud = Label(font_size="18sp", halign="left", valign="top")
        self.msg = Label(font_size="26sp", halign="center", valign="middle")
        self.add_widget(self.hud)
        self.add_widget(self.msg)
        Clock.schedule_interval(self.update, 1 / 60.0)

    # ---------- helpers ----------
    @property
    def mult(self):
        return min(5, 1 + self.combo // 5)

    def reset(self):
        self.px = self.target = self.width / 2
        self.items = []
        self.parts = []
        self.trail = []
        self.score = 0
        self.lives = 3
        self.combo = 0
        self.level = 1
        self.spawn = 0.3
        self.shield = 0
        self.slow = 0
        self.shake = 0
        self.new_best = False
        self.mode = "play"

    def touch_x(self, x):
        self.target = min(max(x, 0), self.width)

    def burst(self, x, y, kind, n):
        col = COLORS[kind]
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            sp = self.width * random.uniform(0.15, 0.6)
            self.parts.append([x, y, math.cos(a) * sp, math.sin(a) * sp,
                               random.uniform(0.3, 0.7), col])

    def game_over(self):
        self.mode = "over"
        self.t_over = 0
        if self.score > self.best:
            self.best = self.score
            self.new_best = True
            try:
                self.store.put("best", v=self.best)
            except Exception:
                pass

    # ---------- input ----------
    def on_touch_down(self, touch):
        if self.mode == "menu" or (self.mode == "over" and self.t_over > 0.8):
            self.reset()
        elif self.mode == "pause":
            self.mode = "play"
        if self.mode == "play":
            self.touch_x(touch.x)
        return True

    def on_touch_move(self, touch):
        if self.mode == "play":
            self.touch_x(touch.x)
        return True

    # ---------- logic ----------
    def spawn_item(self):
        w, h = self.width, self.height
        r = random.random()
        if r < 0.48:
            kind = "bomb"
        elif r < 0.88:
            kind = "star"
        elif r < 0.92:
            kind = "heart" if self.lives < MAX_LIVES else "star"
        elif r < 0.96:
            kind = "shield"
        else:
            kind = "slow"
        s = w * random.uniform(0.07, 0.11)
        self.items.append({
            "k": kind, "x": random.uniform(0, w - s), "y": h, "s": s,
            "v": h * random.uniform(0.28, 0.42),
        })

    def collect(self, it):
        k = it["k"]
        cx, cy = it["x"] + it["s"] / 2, it["y"] + it["s"] / 2
        if k == "bomb":
            if self.shield > 0:
                self.shield = 0
                self.burst(cx, cy, "shield", 14)
            else:
                self.lives -= 1
                self.combo = 0
                self.shake = 0.3
                self.burst(cx, cy, "bomb", 24)
                if self.lives <= 0:
                    self.game_over()
        elif k == "star":
            self.combo += 1
            self.score += self.mult
            self.burst(cx, cy, "star", 10)
        elif k == "heart":
            self.lives = min(MAX_LIVES, self.lives + 1)
            self.burst(cx, cy, "heart", 14)
        elif k == "shield":
            self.shield = 6
            self.burst(cx, cy, "shield", 14)
        elif k == "slow":
            self.slow = 5
            self.burst(cx, cy, "slow", 14)

    def step(self, dt, pw, ph, py):
        self.shield = max(0, self.shield - dt)
        self.slow = max(0, self.slow - dt)
        self.level = 1 + self.score // 15
        speed = (1 + (self.level - 1) * 0.1) * (0.5 if self.slow > 0 else 1)

        self.spawn -= dt
        if self.spawn <= 0:
            self.spawn = max(0.2, 0.75 - self.level * 0.04)
            self.spawn_item()

        self.px += (self.target - self.px) * min(1, dt * 14)
        self.trail.append(self.px)
        if len(self.trail) > 8:
            self.trail.pop(0)

        rx = self.px - pw / 2
        for it in self.items[:]:
            it["y"] -= it["v"] * speed * dt
            s = it["s"]
            if it["y"] + s < 0:
                self.items.remove(it)
                continue
            if (rx < it["x"] + s and rx + pw > it["x"] and
                    py < it["y"] + s and py + ph > it["y"]):
                self.items.remove(it)
                self.collect(it)
                if self.mode != "play":
                    break

    def update(self, dt):
        dt = min(dt, 0.05)
        w, h = self.width, self.height
        if w < 10:
            return
        pw = w * 0.16
        ph = pw * 0.55
        py = h * 0.12

        for b in self.bg:
            b[1] -= b[3] * dt
            if b[1] < 0:
                b[1] = 1
                b[0] = random.random()

        for p in self.parts[:]:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
            if p[4] <= 0:
                self.parts.remove(p)

        self.shake = max(0, self.shake - dt)
        if self.mode == "over":
            self.t_over += dt
        elif self.mode == "play":
            self.step(dt, pw, ph, py)

        self.draw(pw, ph, py)

    # ---------- drawing ----------
    def draw(self, pw, ph, py):
        w, h = self.width, self.height
        k = self.shake / 0.3
        ox = random.uniform(-1, 1) * dp(8) * k
        oy = random.uniform(-1, 1) * dp(8) * k

        self.canvas.before.clear()
        with self.canvas.before:
            Color(1, 1, 1, 0.6)
            for x, y, r, _ in self.bg:
                Ellipse(pos=(x * w, y * h), size=(dp(r), dp(r)))

            if self.slow > 0:
                Color(*COLORS["slow"], 0.10)
                Rectangle(pos=(0, 0), size=(w, h))

            for it in self.items:
                x, y, s = it["x"] + ox, it["y"] + oy, it["s"]
                col = COLORS[it["k"]]
                Color(*col, 0.25)
                Ellipse(pos=(x - s * 0.2, y - s * 0.2), size=(s * 1.4, s * 1.4))
                Color(*col, 1)
                if it["k"] == "bomb":
                    Rectangle(pos=(x, y), size=(s, s))
                elif it["k"] == "shield":
                    Line(circle=(x + s / 2, y + s / 2, s / 2), width=dp(2.5))
                else:
                    Ellipse(pos=(x, y), size=(s, s))

            for p in self.parts:
                Color(*p[5], min(1, p[4] / 0.4))
                Ellipse(pos=(p[0] + ox, p[1] + oy), size=(dp(5), dp(5)))

            if self.mode != "menu":
                n = len(self.trail)
                for i, tx in enumerate(self.trail):
                    Color(0.2, 0.9, 1, 0.12 * (i + 1) / max(n, 1))
                    Ellipse(pos=(tx - pw / 2 + ox, py + oy - dp(4) * (n - i) / 2),
                            size=(pw, ph))
                Color(0.2, 0.9, 1, 0.25)
                Ellipse(pos=(self.px - pw * 0.7 + ox, py - ph * 0.5 + oy),
                        size=(pw * 1.4, ph * 2))
                Color(0.2, 0.9, 1, 1)
                Ellipse(pos=(self.px - pw / 2 + ox, py + oy), size=(pw, ph))
                if self.shield > 0:
                    Color(*COLORS["shield"], 0.9)
                    Line(circle=(self.px + ox, py + ph / 2 + oy, pw * 0.75),
                         width=dp(2))

            Color(1, 0.3, 0.4, 1)
            for i in range(max(self.lives, 0)):
                Ellipse(pos=(w - (i + 1) * dp(26) - dp(8), h - dp(40)),
                        size=(dp(18), dp(18)))

        self.hud.size = (w * 0.65, dp(60))
        self.hud.text_size = self.hud.size
        self.hud.pos = (dp(10), h - dp(70))
        status = ""
        if self.shield > 0:
            status += "  SHIELD"
        if self.slow > 0:
            status += "  SLOW"
        self.hud.text = "Score %d   x%d\nBest %d   Lv %d%s" % (
            self.score, self.mult, self.best, self.level, status)

        self.msg.size = (w, h * 0.3)
        self.msg.text_size = self.msg.size
        self.msg.pos = (0, h * 0.4)
        if self.mode == "menu":
            self.msg.text = ("NEON DODGE\n\nCatch stars, dodge red blocks\n"
                             "Green = life, Cyan = shield, Purple = slow\n\n"
                             "Tap to start")
        elif self.mode == "pause":
            self.msg.text = "PAUSED\n\nTap to resume"
        elif self.mode == "over":
            extra = "\nNEW BEST!" if self.new_best else ""
            self.msg.text = "GAME OVER\nScore: %d%s\n\nTap to retry" % (self.score, extra)
        else:
            self.msg.text = ""


class NeonDodgeApp(App):
    def build(self):
        self.title = "Neon Dodge"
        store = JsonStore(os.path.join(self.user_data_dir, "save.json"))
        self.game = Game(store)
        return self.game

    def on_pause(self):
        if self.game.mode == "play":
            self.game.mode = "pause"
        return True

    def on_resume(self):
        pass


if __name__ == "__main__":
    NeonDodgeApp().run()
