"""Quick sanity checks for bounce geometry (no pygame required)."""

from physics import Rect, Vec2, trace_bounces


def test_left_wall_reflects():
    field = Rect(0, 0, 100, 200)
    pts, hits = trace_bounces(Vec2(50, 180), Vec2(-1, -1), field, max_bounces=3)
    assert pts[0].x == 50
    assert hits[0].kind == "left"
    wall_i = next(i for i, p in enumerate(pts) if abs(p.x) < 1e-6)
    assert wall_i + 1 < len(pts)
    assert pts[wall_i + 1].x > pts[wall_i].x


def test_top_reflects_then_hits_bottom():
    field = Rect(0, 0, 100, 200)
    pts, hits = trace_bounces(Vec2(50, 180), Vec2(0, -1), field, max_bounces=5)
    assert len(pts) >= 3
    assert hits[0].kind == "top"
    assert hits[-1].kind == "bottom"
    assert abs(pts[1].y) < 1e-6
    assert abs(pts[-1].y - 200) < 1e-6


def test_bottom_does_not_bounce():
    field = Rect(0, 0, 100, 200)
    pts, hits = trace_bounces(Vec2(50, 100), Vec2(0.1, 1), field, max_bounces=5)
    assert hits[-1].kind == "bottom"
    assert abs(pts[-1].y - 200) < 1e-6
    assert len(pts) == 2


def test_right_then_top_bounce():
    field = Rect(10, 20, 110, 220)
    pts, hits = trace_bounces(Vec2(60, 200), Vec2(1, -2), field, max_bounces=8, ball_radius=0)
    assert any(h.kind == "right" for h in hits)
    assert any(h.kind == "top" for h in hits)


if __name__ == "__main__":
    test_left_wall_reflects()
    test_top_reflects_then_hits_bottom()
    test_bottom_does_not_bounce()
    test_right_then_top_bounce()
    print("ok")
