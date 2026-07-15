"""Wall bounce trajectory for Nikke-style brick-breaker aiming."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float

    def normalized(self) -> Vec2:
        length = (self.x * self.x + self.y * self.y) ** 0.5
        if length <= 1e-9:
            return Vec2(0.0, -1.0)
        return Vec2(self.x / length, self.y / length)


@dataclass(frozen=True)
class Hit:
    pos: Vec2
    kind: str  # "left" | "right" | "top" | "bottom" | "extend"


def trace_bounces(
    origin: Vec2,
    direction: Vec2,
    field: Rect,
    max_bounces: int = 8,
    ball_radius: float = 0.0,
) -> tuple[list[Vec2], list[Hit]]:
    """Cast a ray reflecting off left, right, and top walls.

    Bottom stops the ray (no bounce).
    Returns (polyline points including start, hit records for points[1:]).
    """
    left = field.left + ball_radius
    right = field.right - ball_radius
    top = field.top + ball_radius
    bottom = field.bottom - ball_radius

    if right <= left or bottom <= top:
        return [origin], []

    pos = Vec2(origin.x, origin.y)
    pos = Vec2(min(max(pos.x, left), right), min(max(pos.y, top), bottom))
    dir_ = direction.normalized()

    if abs(dir_.x) < 1e-9 and abs(dir_.y) < 1e-9:
        dir_ = Vec2(0.0, -1.0)

    points: list[Vec2] = [pos]
    hits: list[Hit] = []
    bounces = 0

    while bounces <= max_bounces:
        if abs(dir_.y) < 1e-12 and abs(dir_.x) < 1e-12:
            break

        candidates: list[tuple[float, Vec2, str]] = []

        if dir_.x < -1e-12:
            t = (left - pos.x) / dir_.x
            if t > 1e-9:
                y = pos.y + t * dir_.y
                if top - 1e-6 <= y <= bottom + 1e-6:
                    candidates.append((t, Vec2(left, y), "left"))

        if dir_.x > 1e-12:
            t = (right - pos.x) / dir_.x
            if t > 1e-9:
                y = pos.y + t * dir_.y
                if top - 1e-6 <= y <= bottom + 1e-6:
                    candidates.append((t, Vec2(right, y), "right"))

        if dir_.y < -1e-12:
            t = (top - pos.y) / dir_.y
            if t > 1e-9:
                x = pos.x + t * dir_.x
                if left - 1e-6 <= x <= right + 1e-6:
                    candidates.append((t, Vec2(x, top), "top"))

        if dir_.y > 1e-12:
            t = (bottom - pos.y) / dir_.y
            if t > 1e-9:
                x = pos.x + t * dir_.x
                if left - 1e-6 <= x <= right + 1e-6:
                    candidates.append((t, Vec2(x, bottom), "bottom"))

        if not candidates:
            ext = Vec2(pos.x + dir_.x * 40, pos.y + dir_.y * 40)
            points.append(ext)
            hits.append(Hit(ext, "extend"))
            break

        candidates.sort(key=lambda c: c[0])
        _, hit, kind = candidates[0]
        points.append(hit)
        hits.append(Hit(hit, kind))
        pos = hit

        if kind == "bottom":
            break

        if kind in ("left", "right"):
            dir_ = Vec2(-dir_.x, dir_.y)
        else:
            dir_ = Vec2(dir_.x, -dir_.y)

        pos = Vec2(pos.x + dir_.x * 1e-3, pos.y + dir_.y * 1e-3)
        bounces += 1

    return points, hits
