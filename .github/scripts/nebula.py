"""The Frame Performance Analyzer backdrop, as SVG.

This is a port of the application's own background - `Visuals/NebulaField.cs` and
`Visuals/DynamicBackdrop.cs` - so the profile card carries the same scene the app draws
behind its windows.

What is faithfully copied, value for value:

* the seeded generator. `NebulaField` builds its field with `new Random(20260914)`, so the
  particles are a fixed sequence rather than a random-looking one. `NetRandom` below is
  the compatibility generator .NET 6+ still uses for a seeded `Random`, and its output was
  checked digit for digit against a C# build of the same loop.
* the draw order in the constructor (depth, angle, spin, heading) and then `Scatter()`
  (x, y), which is what makes the reproduced field the same field.
* the geometry: radius `3 + depth*11`, core scale `0.7 + depth*1.2`, core alpha
  `40 + depth*150`, speed `(5 + depth*22)/60` per frame with the `-speed*0.35` lift, the
  unit triangle `(0,-1) (0.62,0.62) (-0.62,0.62)`, and the sprite's `(1-d)^2` falloff.
* the composition: field colour, particle layer at 60%, the lime-to-sky wash across the
  top 500 px at 15% under an elliptical mask.

What is translated rather than copied, and why:

* WPF wraps a particle when it leaves an edge. SVG cannot wrap, so each particle carries
  the copies its own motion needs and its animation moves exactly one canvas period per
  axis per cycle - the drift then loops with no jump, which is what wrapping looks like.
* particles are bucketed by depth for the sprite and share an animation when their
  quantised direction and duration match, so 500 particles cost ~500 nodes, not ~4000.
* per-particle rotation is dropped. The core is 1-3 px across; at that size its angle is
  not information.
"""

import math

MBIG = 2147483647
MSEED = 161803398


class NetRandom:
    """System.Random(int seed) - the legacy subtractive generator, kept in .NET for seeded use."""

    def __init__(self, seed):
        self.state = [0] * 56
        subtraction = MBIG if seed == -2147483648 else abs(seed)
        mj = MSEED - subtraction
        self.state[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            self.state[ii] = mk
            mk = mj - mk
            if mk < 0:
                mk += MBIG
            mj = self.state[ii]
        for _ in range(4):
            for i in range(1, 56):
                self.state[i] -= self.state[1 + (i + 30) % 55]
                if self.state[i] < 0:
                    self.state[i] += MBIG
        self.i, self.j = 0, 21

    def _sample(self):
        i = self.i + 1 if self.i + 1 < 56 else 1
        j = self.j + 1 if self.j + 1 < 56 else 1
        result = self.state[i] - self.state[j]
        if result == MBIG:
            result -= 1
        if result < 0:
            result += MBIG
        self.state[i] = result
        self.i, self.j = i, j
        return result

    def next_double(self):
        return self._sample() * (1.0 / MBIG)


# The sprite: a unit triangle core over a halo whose falloff is (1-d)^2, sampled at five
# points. Linear would reach zero with a slope, and the eye reads that slope as a disc.
HALO_STOPS = ((0.0, 1.0), (0.25, 0.5625), (0.5, 0.25), (0.75, 0.0625), (1.0, 0.0))
TRIANGLE = "M0 -1L0.62 0.62L-0.62 0.62Z"


def _n(value):
    """Shortest honest number: SVG carries no more precision than the geometry needs."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


def field(width, height, count=250, seed=20260914):
    """The app's field at this surface size, in the app's own draw order."""
    rnd = NetRandom(seed)
    particles = []
    for _ in range(count):
        depth = 0.18 + rnd.next_double() * 0.82
        angle = rnd.next_double() * 360
        spin = (rnd.next_double() - 0.5) * 0.9
        speed = (5 + depth * 22) / 60.0
        heading = rnd.next_double() * math.pi * 2
        particles.append({
            "depth": depth, "angle": angle, "spin": spin,
            "radius": 3 + depth * 11,
            "alpha": (40 + depth * 150) / 255.0,
            "vx": math.cos(heading) * speed * 60.0,          # px per second
            "vy": (math.sin(heading) * speed - speed * 0.35) * 60.0,
        })
    for p in particles:
        p["x"] = rnd.next_double() * width
        p["y"] = rnd.next_double() * height
    return particles


def defs(width, height, color="#76B900", buckets=10, radius_cap=14.0, prefix="nb"):
    """The halo gradient and the depth-bucket sprites the layer refers to."""
    out = ['<radialGradient id="halo">' + "".join(
        f'<stop offset="{offset}" stop-color="{color}" stop-opacity="{alpha}"/>'
        for offset, alpha in HALO_STOPS
    ) + "</radialGradient>"]
    for k in range(buckets):
        depth = 0.18 + ((k + 0.5) / buckets) * 0.82
        out.append(
            f'<g id="{prefix}{k}">'
            f'<circle r="{_n(min(3 + depth * 11, radius_cap))}" fill="url(#halo)"/>'
            f'<path d="{TRIANGLE}" transform="scale({_n(0.7 + depth * 1.2)})" fill="{color}" '
            f'opacity="{(40 + depth * 150) / 255.0:.3f}"/></g>'
        )
    out.append(f'<clipPath id="fieldclip"><rect width="{_n(width)}" height="{_n(height)}" rx="34"/></clipPath>')
    return out


def layer(width, height, count=250, color="#76B900", opacity=0.6, buckets=10, seed=20260914,
          mode="auto"):
    """The drifting field.

    Two motions, and the surface decides which is honest:

    * `wrap` - the app's own behaviour, one period of travel per axis per cycle, with the
      copies that need. Only valid when the surface is viewport-shaped: on a 1440x8120
      card a particle crosses the width eight times per vertical period, and no sane
      number of copies covers that.
    * `drift` - a bounded out-and-back excursion around each particle's home. A scrollable
      document has no edge for a particle to wrap around, so the field drifts and returns
      instead of teleporting. Direction and speed are the app's; only the wrap is dropped.
    """
    particles = field(width, height, count, seed)

    plan = []
    for p in particles:
        vx, vy = p["vx"], p["vy"]
        # MIN, not max: the cycle must be the time to reach the NEAREST edge. Taking the
        # farthest lets an almost-horizontal particle score hundreds of periods per cycle.
        period = min(width / abs(vx) if vx else float("inf"),
                     height / abs(vy) if vy else float("inf"))
        if period in (0.0, float("inf")):
            period = 120.0
        plan.append((int(round(vx * period / width)) if vx else 0,
                     int(round(vy * period / height)) if vy else 0,
                     period))

    if mode == "auto":
        # Wrapping is the app's behaviour on a window. On a card nine screens tall the same
        # motion turns into a horizontal conveyor, so the field drifts and returns instead.
        viewport_shaped = height <= 1.6 * width
        mode = ("wrap" if viewport_shaped and all(abs(n) <= 1 and abs(m) <= 1 for n, m, _ in plan)
                else "drift")

    groups = {}
    if mode == "wrap":
        for p, (n, m, period) in zip(particles, plan):
            if n == 0 and m == 0:                 # a particle that never moves is not a particle
                if abs(p["vy"]) >= abs(p["vx"]):
                    m = 1 if p["vy"] >= 0 else -1
                else:
                    n = 1 if p["vx"] >= 0 else -1
            duration = max(20.0, round(period / 20.0) * 20.0)
            bucket = min(buckets - 1, max(0, int((p["depth"] - 0.18) / 0.82 * buckets)))
            groups.setdefault((n, m, duration), []).append((p, bucket))
    else:
        for p in particles:
            speed = math.hypot(p["vx"], p["vy"]) or 1.0
            heading = math.atan2(p["vy"], p["vx"])
            heading_bin = int(round(heading / (math.pi / 12)))           # 15 degree steps
            speed_bin = max(1, int(round(speed / 4.0)))                  # 4 px/s steps
            duration = min(240.0, max(40.0, round(1200.0 / speed / 20.0) * 20.0))
            bucket = min(buckets - 1, max(0, int((p["depth"] - 0.18) / 0.82 * buckets)))
            key = (heading_bin, speed_bin, duration)
            groups.setdefault(key, []).append((p, bucket))

    out = [f'<g clip-path="url(#fieldclip)" opacity="{opacity}">']
    for key, members in sorted(groups.items()):
        if mode == "wrap":
            n, m, duration = key
            values = f"0 0;{_n(n * width)} {_n(m * height)}"
        else:
            heading_bin, speed_bin, duration = key
            heading = heading_bin * (math.pi / 12)
            reach = (speed_bin * 4.0) * duration / 2.0                   # px each way
            values = f"0 0;{_n(math.cos(heading) * reach)} {_n(math.sin(heading) * reach)};0 0"
        out.append(
            f'<g><animateTransform attributeName="transform" type="translate" '
            f'values="{values}" dur="{_n(duration)}s" repeatCount="indefinite"/>'
        )
        for p, bucket in members:
            if mode == "wrap":
                n, m, _ = key
                # Exactly the copies this particle's motion needs: one per wrap state it visits.
                offsets = {(0, 0)}
                if n:
                    offsets.add((-n * width, 0))
                if m:
                    offsets.add((0, -m * height))
                if n and m:
                    offsets.add((-n * width, -m * height))
            else:
                offsets = {(0, 0)}          # a returning drift never leaves a gap to cover
            for ox, oy in sorted(offsets):
                out.append(f'<use href="#nb{bucket}" x="{p["x"] + ox:.1f}" y="{p["y"] + oy:.1f}"/>')
        out.append("</g>")
    out.append("</g>")
    return "".join(out)


def wash_defs(width, top=500):
    """The lime-to-sky wash the app lays across the top of its window, and its elliptical cut."""
    return (
        '<linearGradient id="wash" x1="0.007" y1="0.585" x2="0.993" y2="0.415">'
        '<stop offset="0.015" stop-color="#BFF230"/><stop offset="1" stop-color="#7CD7FE"/>'
        '</linearGradient>'
        '<radialGradient id="washmask" cx="0.5" cy="0" r="0.75" gradientTransform="scale(1 0.8)">'
        '<stop offset="0" stop-color="#fff"/><stop offset="0.3" stop-color="#fff"/>'
        '<stop offset="0.7" stop-color="#000"/></radialGradient>'
        f'<mask id="washcut"><rect width="{_n(width)}" height="{_n(top)}" fill="url(#washmask)"/></mask>'
    )


def wash_layer(width, top=500, opacity=0.15):
    return (f'<g mask="url(#washcut)"><rect width="{_n(width)}" height="{_n(top)}" '
            f'fill="url(#wash)" opacity="{opacity}"/></g>')
