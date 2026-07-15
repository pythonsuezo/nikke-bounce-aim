"""Transparent Windows overlay: aim preview with wall reflections for Nikke mini-game."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pygame

from physics import Rect, Vec2, trace_bounces

try:
    import win32api
    import win32con
    import win32gui
except ImportError:
    win32api = win32con = win32gui = None  # type: ignore

def app_dir() -> Path:
    """Folder next to the exe (frozen) or this script (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = app_dir() / "config.json"
LINE_COLOR = (60, 255, 140)
LINE_OUTLINE = (0, 40, 20)
BALL_FILL = (255, 255, 255)
BALL_EDGE = (40, 120, 255)
BALL_GHOST = (180, 255, 220)
BOUNCE_COLOR = (255, 230, 60)
GUIDE_COLOR = (255, 255, 255)
HINT_COLOR = (230, 230, 230)
CROSSHAIR = (0, 255, 200)
HUD_BG = (20, 20, 20)
CHROMA = (255, 0, 255)

# Virtual-key codes for global hotkeys (work even while NIKKE is focused).
VK_ESCAPE = 0x1B
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_OEM_PLUS = 0xBB
VK_OEM_MINUS = 0xBD
VK_ADD = 0x6B
VK_SUBTRACT = 0x6D
VK_OEM_4 = 0xDB  # [
VK_OEM_6 = 0xDD  # ]
VK_OEM_COMMA = 0xBC  # ,
VK_OEM_PERIOD = 0xBE  # .
VK_9 = 0x39
VK_0 = 0x30
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def apply_layered(hwnd: int, clickthrough: bool, opacity: float = 1.0) -> None:
    """Topmost + color-key + optional overall alpha (trajectory/HUD see-through)."""
    if win32gui is None or not hwnd:
        return

    style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST
    style &= ~getattr(win32con, "WS_EX_TOOLWINDOW", 0x00000080)
    if clickthrough:
        style |= win32con.WS_EX_TRANSPARENT
    else:
        style &= ~win32con.WS_EX_TRANSPARENT
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

    colorref = win32api.RGB(*CHROMA)
    # 255 = opaque overlay ink; lower = game shows through the trajectory.
    alpha = max(30, min(255, int(round(opacity * 255))))
    flags = win32con.LWA_COLORKEY | win32con.LWA_ALPHA
    win32gui.SetLayeredWindowAttributes(hwnd, colorref, alpha, flags)
    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_TOPMOST,
        0,
        0,
        0,
        0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
    )


def force_show(hwnd: int) -> None:
    if win32gui is None or not hwnd:
        return
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def screen_size() -> tuple[int, int]:
    if win32api is not None:
        return win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
    info = pygame.display.Info()
    return info.current_w, info.current_h


def key_just_pressed(vk: int) -> bool:
    """True once when key goes down — works system-wide (no app focus needed)."""
    if win32api is None:
        return False
    return bool(win32api.GetAsyncKeyState(vk) & 0x0001)


def key_held(vk: int) -> bool:
    if win32api is None:
        return False
    return bool(win32api.GetAsyncKeyState(vk) & 0x8000)


def cursor_pos() -> tuple[int, int]:
    """Screen cursor position. Use this instead of pygame.mouse.get_pos().

    With WS_EX_TRANSPARENT click-through, pygame often only gets sparse mouse
    updates — so the aim marker appears to lag unless you move very slowly.
    """
    if win32api is not None:
        return win32api.GetCursorPos()
    return pygame.mouse.get_pos()


def draw_ball(
    target: pygame.Surface,
    center: tuple[int, int],
    radius: float,
    *,
    fill: tuple[int, int, int] = BALL_FILL,
    edge: tuple[int, int, int] = BALL_EDGE,
) -> None:
    """Draw a ball at true collision radius so size is visually comparable to the game."""
    r = max(2, int(round(radius)))
    cx, cy = center
    pygame.draw.circle(target, edge, (cx, cy), r + 2)
    pygame.draw.circle(target, fill, (cx, cy), r)
    pygame.draw.circle(target, edge, (cx, cy), r, max(2, r // 6))
    pygame.draw.line(target, edge, (cx - r // 2, cy), (cx + r // 2, cy), 1)
    pygame.draw.line(target, edge, (cx, cy - r // 2), (cx, cy + r // 2), 1)


def draw_bounce_number(
    target: pygame.Surface,
    font: pygame.font.Font,
    number: int,
    center: tuple[int, int],
    wall: str,
    ball_radius: float,
) -> None:
    """Large bounce index; left wall → left of hit, right wall → right of hit."""
    text = str(number)
    # Yellow fill + thick dark outline for readability on water/blocks.
    glow = font.render(text, True, (0, 0, 0))
    core = font.render(text, True, (255, 240, 80))
    cx, cy = center
    gap = max(10, int(ball_radius) + 8)
    tw, th = core.get_width(), core.get_height()

    if wall == "left":
        # Outside / to the left of the left wall hit
        tx = cx - gap - tw
        ty = cy - th // 2
    elif wall == "right":
        tx = cx + gap
        ty = cy - th // 2
    elif wall == "top":
        tx = cx - tw // 2
        ty = cy - gap - th
    else:
        tx = cx + gap
        ty = cy - th // 2

    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)):
        target.blit(glow, (tx + ox, ty + oy))
    target.blit(core, (tx, ty))

def draw_ball_size_preview(
    target: pygame.Surface,
    font: pygame.font.Font,
    radius: float,
    topleft: tuple[int, int],
) -> int:
    """HUD panel with a real-size ball sample + [ ] hint. Returns next y."""
    x, y = topleft
    r = max(2, int(round(radius)))
    pad = 8
    text = font.render(f"ボール半径 {radius:.0f}px   [ 小さく  ] 大きく", True, HINT_COLOR)
    box_w = max(text.get_width() + pad * 2 + r * 2 + 16, r * 2 + 40)
    box_h = max(text.get_height(), r * 2) + pad * 2
    pygame.draw.rect(target, HUD_BG, pygame.Rect(x, y, box_w, box_h))
    pygame.draw.rect(target, (80, 80, 80), pygame.Rect(x, y, box_w, box_h), 1)
    ball_cx = x + pad + r
    ball_cy = y + box_h // 2
    draw_ball(target, (ball_cx, ball_cy), radius)
    target.blit(text, (ball_cx + r + 12, y + (box_h - text.get_height()) // 2))
    return y + box_h + 4


def path_line_widths(ball_radius: float) -> tuple[int, int]:
    """Trajectory thickness ≈ ball diameter so the line reads as the ball's path."""
    core = max(4, int(round(ball_radius * 2 * 0.55)))
    outline = max(core + 4, int(round(ball_radius * 2 * 0.85)))
    return core, outline


def sample_path_points(points: list[Vec2], spacing: float) -> list[tuple[int, int]]:
    """Place ghost balls along the polyline at roughly `spacing` pixels."""
    if len(points) < 2 or spacing <= 1:
        return [(int(p.x), int(p.y)) for p in points]

    out: list[tuple[int, int]] = [(int(points[0].x), int(points[0].y))]
    carry = 0.0
    for a, b in zip(points, points[1:]):
        dx = b.x - a.x
        dy = b.y - a.y
        seg_len = (dx * dx + dy * dy) ** 0.5
        if seg_len < 1e-6:
            continue
        dist = spacing - carry
        while dist <= seg_len:
            t = dist / seg_len
            out.append((int(a.x + dx * t), int(a.y + dy * t)))
            dist += spacing
        carry = seg_len - (dist - spacing)
    end = (int(points[-1].x), int(points[-1].y))
    if out[-1] != end:
        out.append(end)
    return out


def draw_text_plate(
    target: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    xy: tuple[int, int],
) -> int:
    x, y = xy
    text_surf = font.render(text, True, HINT_COLOR)
    pad = 5
    w = text_surf.get_width() + pad * 2
    h = text_surf.get_height() + pad * 2
    pygame.draw.rect(target, HUD_BG, pygame.Rect(x, y, w, h))
    pygame.draw.rect(target, (80, 80, 80), pygame.Rect(x, y, w, h), 1)
    target.blit(text_surf, (x + pad, y + pad))
    return y + h + 4


class OverlayApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Nikke Bounce Aim")

        self.screen_w, self.screen_h = screen_size()
        self.screen = pygame.display.set_mode(
            (self.screen_w, self.screen_h),
            pygame.NOFRAME,
        )
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("meiryo", 18)
        self.font_sm = pygame.font.SysFont("meiryo", 14)
        self.font_bounce = pygame.font.SysFont("meiryo", 36, bold=True)

        hwnd = pygame.display.get_wm_info().get("window")
        self.hwnd = int(hwnd) if hwnd else 0

        cfg = load_config()
        self.field: Rect | None = None
        self.origin: Vec2 | None = None
        if "field" in cfg and "origin" in cfg:
            f = cfg["field"]
            o = cfg["origin"]
            self.field = Rect(f["left"], f["top"], f["right"], f["bottom"])
            self.origin = Vec2(o["x"], o["y"])

        self.max_bounces = int(cfg.get("max_bounces", 10))
        self.ball_radius = float(cfg.get("ball_radius", 6.0))
        # 1.0 = くっきり, lower = ゲームが透けて見える
        self.trail_opacity = float(cfg.get("trail_opacity", 0.55))
        self.trail_opacity = max(0.15, min(1.0, self.trail_opacity))
        # 簡略: 線だけ（ボール飾りなし）
        self.simple_trail = bool(cfg.get("simple_trail", False))
        self.visible = True
        self.calibrating = self.field is None
        self.calib_step = 0
        self.calib_points: list[tuple[int, int]] = []
        self.interactive = self.calibrating
        self.running = True
        self._style_frames = 0
        self._origin_dirty = False
        self._origin_save_cooldown = 0

        if self.calibrating:
            self.message = (
                "起動OK。このまま ① プレイ領域の左上をクリック "
                "（タスクバーに「Nikke Bounce Aim」あり）"
            )
            self._enter_calibration()
        else:
            self.message = "起動OK。, . で軌跡の濃さ / F4 簡略表示 / Esc 終了"
            self._apply_style()

        force_show(self.hwnd)
        # Flush any key-down leftovers from launching.
        for vk in (
            VK_ESCAPE,
            VK_F1,
            VK_F2,
            VK_F3,
            VK_OEM_PLUS,
            VK_OEM_MINUS,
            VK_ADD,
            VK_SUBTRACT,
            VK_OEM_4,
            VK_OEM_6,
            VK_OEM_COMMA,
            VK_OEM_PERIOD,
            VK_9,
            VK_0,
        ):
            key_just_pressed(vk)

    def _overlay_opacity(self) -> float:
        # Keep calibration HUD readable.
        if self.calibrating or self.interactive:
            return 1.0
        return self.trail_opacity

    def _apply_style(self) -> None:
        apply_layered(
            self.hwnd,
            clickthrough=not self.interactive,
            opacity=self._overlay_opacity(),
        )

    def _persist_visuals(self) -> None:
        cfg = load_config()
        cfg["trail_opacity"] = self.trail_opacity
        cfg["simple_trail"] = self.simple_trail
        cfg["ball_radius"] = self.ball_radius
        save_config(cfg)

    def _enter_calibration(self) -> None:
        self.calibrating = True
        self.calib_step = 0
        self.calib_points = []
        self.interactive = True
        self._apply_style()
        force_show(self.hwnd)
        self.message = "① プレイ領域の左上（白い左枠の上端付近）をクリック"

    def _finish_calibration(self, origin_xy: tuple[int, int]) -> None:
        (x0, y0), (x1, y1) = self.calib_points
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        inset = 2.0
        self.field = Rect(left + inset, top + inset, right - inset, bottom - inset)
        self.origin = Vec2(float(origin_xy[0]), float(origin_xy[1]))
        self.calibrating = False
        self.interactive = False
        self._apply_style()
        save_config(
            {
                "field": {
                    "left": self.field.left,
                    "top": self.field.top,
                    "right": self.field.right,
                    "bottom": self.field.bottom,
                },
                "origin": {"x": self.origin.x, "y": self.origin.y},
                "max_bounces": self.max_bounces,
                "ball_radius": self.ball_radius,
                "trail_opacity": self.trail_opacity,
                "simple_trail": self.simple_trail,
            }
        )
        self.message = "完了。上下=↑↓微調整 / 横=←→ or Alt+マウス追従"

    def _save_origin(self) -> None:
        if self.origin is None:
            return
        cfg = load_config()
        cfg["origin"] = {"x": self.origin.x, "y": self.origin.y}
        save_config(cfg)
        self._origin_dirty = False

    def _clamp_origin(self, x: float, y: float) -> Vec2:
        assert self.field is not None
        r = self.ball_radius
        return Vec2(
            min(max(x, self.field.left + r), self.field.right - r),
            min(max(y, self.field.top + r), self.field.bottom - r),
        )

    def _nudge_origin(self, dx: float, dy: float) -> None:
        if self.origin is None or self.field is None or self.calibrating:
            return
        self.origin = self._clamp_origin(self.origin.x + dx, self.origin.y + dy)
        self._save_origin()
        self.message = (
            f"発射点 X={self.origin.x:.0f} Y={self.origin.y:.0f}  "
            f"（↑↓高さ / ←→横 / Alt押しながらマウスで横追従）"
        )

    def _poll_origin_controls(self) -> None:
        """Horizontal follow + fine Y/X nudges after initial origin is set."""
        if self.calibrating or self.origin is None or self.field is None:
            return

        # Alt: lock Y, slide X with mouse (character only moves horizontally).
        if key_held(VK_MENU):
            mx, _my = cursor_pos()
            new_o = self._clamp_origin(float(mx), self.origin.y)
            if abs(new_o.x - self.origin.x) >= 0.5:
                self.origin = new_o
                self._origin_dirty = True
                self.message = (
                    f"横追従中 X={self.origin.x:.0f}（Y={self.origin.y:.0f}固定）  "
                    f"Altを離すと確定"
                )
            self._origin_save_cooldown += 1
            if self._origin_dirty and self._origin_save_cooldown >= 30:
                self._save_origin()
                self._origin_save_cooldown = 0
        elif self._origin_dirty:
            self._save_origin()
            self._origin_save_cooldown = 0
            self.message = (
                f"発射点 X={self.origin.x:.0f} Y={self.origin.y:.0f}  "
                f"（↑↓で高さ微調整）"
            )

        step = 5 if key_held(VK_SHIFT) else 1
        if key_just_pressed(VK_UP):
            self._nudge_origin(0, -step)
        if key_just_pressed(VK_DOWN):
            self._nudge_origin(0, step)
        if key_just_pressed(VK_LEFT):
            self._nudge_origin(-step, 0)
        if key_just_pressed(VK_RIGHT):
            self._nudge_origin(step, 0)

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.calibrating and self.interactive:
                    # Prefer live cursor pos (event.pos can be stale with layered windows).
                    self._on_calib_click(cursor_pos())

        # Global hotkeys: no need to Alt+Tab / focus this app.
        self._poll_global_hotkeys()
        self._poll_origin_controls()

    def _poll_global_hotkeys(self) -> None:
        if key_just_pressed(VK_F1):
            self._on_key(pygame.K_F1)
        if key_just_pressed(VK_F2):
            self._on_key(pygame.K_F2)
        if key_just_pressed(VK_F3):
            self._on_key(pygame.K_F3)
        if key_just_pressed(VK_ESCAPE):
            self._on_key(pygame.K_ESCAPE)
        if key_just_pressed(VK_OEM_PLUS) or key_just_pressed(VK_ADD):
            self._on_key(pygame.K_PLUS)
        if key_just_pressed(VK_OEM_MINUS) or key_just_pressed(VK_SUBTRACT):
            self._on_key(pygame.K_MINUS)
        if key_just_pressed(VK_OEM_4):
            self._on_key(pygame.K_LEFTBRACKET)
        if key_just_pressed(VK_OEM_6):
            self._on_key(pygame.K_RIGHTBRACKET)
        if key_just_pressed(VK_OEM_COMMA) or key_just_pressed(VK_9):
            self._on_key(pygame.K_COMMA)
        if key_just_pressed(VK_OEM_PERIOD) or key_just_pressed(VK_0):
            self._on_key(pygame.K_PERIOD)
        # F4 = simple trail toggle (VK 0x73)
        if key_just_pressed(0x73):
            self._on_key(pygame.K_F4)

    def _on_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            if self.calibrating:
                if self.field and self.origin:
                    self.calibrating = False
                    self.interactive = False
                    self._apply_style()
                    self.message = "キャリブレーションをキャンセルしました"
                else:
                    self.running = False
            else:
                self.running = False
        elif key == pygame.K_F1:
            self._enter_calibration()
        elif key == pygame.K_F2:
            self.calibrating = True
            self.calib_step = 2
            self.calib_points = []
            self.interactive = True
            self._apply_style()
            force_show(self.hwnd)
            self.message = "発射点をクリック（高さの基準）。以後は↑↓で微調整"
        elif key == pygame.K_F3:
            self.visible = not self.visible
            self.message = "表示 ON" if self.visible else "表示 OFF"
        elif key == pygame.K_F4:
            self.simple_trail = not self.simple_trail
            self._persist_visuals()
            self.message = (
                "簡略表示 ON（線のみ）" if self.simple_trail else "簡略表示 OFF（ボール付き）"
            )
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.max_bounces = min(30, self.max_bounces + 1)
            self.message = f"反射回数: {self.max_bounces}"
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.max_bounces = max(1, self.max_bounces - 1)
            self.message = f"反射回数: {self.max_bounces}"
        elif key == pygame.K_LEFTBRACKET:
            self.ball_radius = max(2.0, self.ball_radius - 1)
            self._persist_visuals()
            self.message = f"ボール半径: {self.ball_radius:.0f}px"
        elif key == pygame.K_RIGHTBRACKET:
            self.ball_radius = min(60.0, self.ball_radius + 1)
            self._persist_visuals()
            self.message = f"ボール半径: {self.ball_radius:.0f}px"
        elif key == pygame.K_COMMA:
            self.trail_opacity = max(0.15, round(self.trail_opacity - 0.05, 2))
            self._persist_visuals()
            self._apply_style()
            self.message = f"軌跡の濃さ: {int(self.trail_opacity * 100)}%  （, 薄い  . 濃い）"
        elif key == pygame.K_PERIOD:
            self.trail_opacity = min(1.0, round(self.trail_opacity + 0.05, 2))
            self._persist_visuals()
            self._apply_style()
            self.message = f"軌跡の濃さ: {int(self.trail_opacity * 100)}%  （, 薄い  . 濃い）"

    def _save_radius(self) -> None:
        self._persist_visuals()

    def _on_calib_click(self, pos: tuple[int, int]) -> None:
        if self.calib_step == 0:
            self.calib_points = [pos]
            self.calib_step = 1
            self.message = "② プレイ領域の右下をクリック"
        elif self.calib_step == 1:
            self.calib_points.append(pos)
            self.calib_step = 2
            self.message = "③ 発射点をクリック（高さの基準。横は後で動かせる）"
        elif self.calib_step == 2:
            if len(self.calib_points) < 2 and self.field is not None:
                self.origin = Vec2(float(pos[0]), float(pos[1]))
                self.calibrating = False
                self.interactive = False
                self._apply_style()
                cfg = load_config()
                cfg["origin"] = {"x": self.origin.x, "y": self.origin.y}
                save_config(cfg)
                self.message = (
                    f"発射点更新 X={self.origin.x:.0f} Y={self.origin.y:.0f}  "
                    f"以後↑↓微調整 / Alt+マウスで横移動"
                )
            else:
                self._finish_calibration(pos)

    def draw(self) -> None:
        self.screen.fill(CHROMA)

        if self.calibrating:
            self._draw_calibration()
        elif self.visible and self.field and self.origin:
            self._draw_trajectory()
            self._draw_field_guide()

        self._draw_hud()
        pygame.display.flip()

        self._style_frames += 1
        if self._style_frames <= 5 or self._style_frames % 120 == 0:
            self._apply_style()

    def _draw_calibration(self) -> None:
        mx, my = cursor_pos()
        pygame.draw.line(self.screen, CROSSHAIR, (mx - 22, my), (mx + 22, my), 1)
        pygame.draw.line(self.screen, CROSSHAIR, (mx, my - 22), (mx, my + 22), 1)
        pygame.draw.circle(self.screen, CROSSHAIR, (mx, my), 12, 2)

        if self.calib_step == 0:
            pygame.draw.circle(self.screen, GUIDE_COLOR, (mx, my), 4)
        elif self.calib_step == 1 and self.calib_points:
            x0, y0 = self.calib_points[0]
            left, right = sorted((x0, mx))
            top, bottom = sorted((y0, my))
            pygame.draw.rect(
                self.screen, GUIDE_COLOR, pygame.Rect(left, top, right - left, bottom - top), 2
            )
            pygame.draw.circle(self.screen, BOUNCE_COLOR, (x0, y0), 5)
        elif self.calib_step == 2:
            if self.field:
                pygame.draw.rect(
                    self.screen,
                    GUIDE_COLOR,
                    pygame.Rect(
                        int(self.field.left),
                        int(self.field.top),
                        int(self.field.width),
                        int(self.field.height),
                    ),
                    2,
                )
            elif len(self.calib_points) >= 2:
                (x0, y0), (x1, y1) = self.calib_points
                left, right = sorted((x0, x1))
                top, bottom = sorted((y0, y1))
                pygame.draw.rect(
                    self.screen, GUIDE_COLOR, pygame.Rect(left, top, right - left, bottom - top), 2
                )
            pygame.draw.circle(self.screen, BOUNCE_COLOR, (mx, my), 12, 2)

    def _draw_field_guide(self) -> None:
        assert self.field is not None
        rect = pygame.Rect(
            int(self.field.left),
            int(self.field.top),
            int(self.field.width),
            int(self.field.height),
        )
        pygame.draw.rect(self.screen, (40, 40, 40), rect, 3)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)

    def _draw_trajectory(self) -> None:
        assert self.field is not None and self.origin is not None
        mx, my = cursor_pos()
        direction = Vec2(mx - self.origin.x, my - self.origin.y)
        if direction.y > 0:
            direction = Vec2(direction.x, -abs(direction.y) if abs(direction.y) > 1 else -1)

        points, hits = trace_bounces(
            self.origin,
            direction,
            self.field,
            max_bounces=self.max_bounces,
            ball_radius=self.ball_radius,
        )
        if len(points) < 2:
            return

        coords = [(int(p.x), int(p.y)) for p in points]
        core_w, outline_w = path_line_widths(self.ball_radius)
        if self.simple_trail or self.trail_opacity < 0.45:
            outline_w = max(3, outline_w // 2)
            core_w = max(2, core_w // 2)

        pygame.draw.lines(self.screen, LINE_OUTLINE, False, coords, outline_w)
        pygame.draw.lines(self.screen, LINE_COLOR, False, coords, core_w)

        show_balls = (not self.simple_trail) and self.trail_opacity >= 0.4
        ox, oy = int(self.origin.x), int(self.origin.y)

        # Reflective hits only (left / right / top) get bounce numbers.
        bounce_hits = [h for h in hits if h.kind in ("left", "right", "top")]

        if show_balls:
            spacing = max(28.0, self.ball_radius * 3.5)
            for gx, gy in sample_path_points(points, spacing)[1:-1]:
                r = max(2, int(round(self.ball_radius)))
                pygame.draw.circle(self.screen, BALL_EDGE, (gx, gy), r, 2)

            for h in bounce_hits:
                draw_ball(
                    self.screen,
                    (int(h.pos.x), int(h.pos.y)),
                    self.ball_radius,
                    fill=BALL_GHOST,
                    edge=BOUNCE_COLOR,
                )
            draw_ball(self.screen, (ox, oy), self.ball_radius)
        else:
            pygame.draw.circle(self.screen, GUIDE_COLOR, (ox, oy), 5, 2)
            for h in bounce_hits:
                pygame.draw.circle(
                    self.screen, BOUNCE_COLOR, (int(h.pos.x), int(h.pos.y)), 5
                )

        for i, h in enumerate(bounce_hits, start=1):
            draw_bounce_number(
                self.screen,
                self.font_bounce,
                i,
                (int(h.pos.x), int(h.pos.y)),
                h.kind,
                self.ball_radius,
            )

        pygame.draw.line(self.screen, (160, 160, 255), (ox, oy), (mx, my), 2)

    def _draw_hud(self) -> None:
        lines = [
            self.message,
            "F1 領域 / ↑↓ 発射点の高さ / Alt+マウス 横移動 / , . 濃さ / Esc 終了",
        ]
        if self.calibrating:
            lines.append("※いまは領域合わせ中 → 画面をクリック")
        elif self.field and self.origin:
            mode = "簡略" if self.simple_trail else "詳細"
            lines.append(
                f"発射点 X={self.origin.x:.0f} Y={self.origin.y:.0f}  "
                f"濃さ {int(self.trail_opacity * 100)}%  {mode}"
            )

        y = 8
        for text in lines:
            y = draw_text_plate(self.screen, self.font, text, (8, y))

        if not self.calibrating and not self.simple_trail and self.trail_opacity >= 0.4:
            y = draw_ball_size_preview(self.screen, self.font, self.ball_radius, (8, y))

    def run(self) -> None:
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(60)
        pygame.quit()


def main() -> int:
    if sys.platform != "win32":
        print("このオーバーレイは Windows 向けです。")
        return 1
    # Match cursor coords to pixel coords on scaled displays.
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    print("Nikke Bounce Aim 起動")
    print("  - アクティブにする必要はありません")
    print("  - タスクバーに「Nikke Bounce Aim」が出ます")
    print("  - F1=領域合わせ / F3=表示切替 / Esc=終了（ゲーム操作中でも可）")
    OverlayApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
