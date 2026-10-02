"""
Screen-specific components: the breathing guide, the essay
coach's badge, and the Graze stage.

Merged from: breathing, coach, graze.
"""
from __future__ import annotations

import reflex as rx


# ====================================================================
# breathing
# ====================================================================

PATTERNS = [
    {
        "key": "box",
        "name": "Box breathing",
        "phases": [4, 4, 4, 4],
        "figure": "box",
        "blurb": "Equal counts on all four sides. Used by people who need to steady "
                 "themselves fast — good right before you open a hard essay prompt.",
    },
    {
        "key": "478",
        "name": "4-7-8",
        "phases": [4, 7, 8, 0],
        "figure": "expand",
        "blurb": "Long hold, longer exhale. Slows you down more than box breathing, "
                 "so it suits winding down at the end of a session.",
    },
    {
        "key": "468",
        "name": "4-6-8",
        "phases": [4, 6, 8, 0],
        "figure": "fill",
        "blurb": "Gentler than 4-7-8 with the same long exhale. A good starting "
                 "point if holding for seven counts feels like too much.",
    },
]

DURATIONS = [1, 2, 3, 5, 10]  # minutes, student picks one

PHASE_LABELS = ["Breathe in", "Hold", "Breathe out", "Hold"]

# --------------------------------------------------------------------------
# Theme figures. All draw into a 200x200 viewBox.
#
#   back   painted behind the animated element
#   shape  the animated element — scaled ("expand") or clipped ("fill")
#   front  painted on top (cup rim, rocket window, outline strokes)
#   level  for "fill": [y_empty, y_full] in viewBox units for the liquid top
# --------------------------------------------------------------------------

def _lotus():
    petals = "".join(
        f'<ellipse cx="100" cy="66" rx="15" ry="36" fill="#B9A6EA" opacity=".85" '
        f'transform="rotate({a} 100 100)"/>' for a in range(0, 360, 45))
    inner = "".join(
        f'<ellipse cx="100" cy="80" rx="10" ry="24" fill="#8FD9BC" opacity=".9" '
        f'transform="rotate({a} 100 100)"/>' for a in range(22, 360, 45))
    return petals + inner + '<circle cx="100" cy="100" r="13" fill="#FBEEC1"/>'


def _star():
    import math
    pts = []
    for i in range(10):
        r = 78 if i % 2 == 0 else 34
        a = math.radians(-90 + i * 36)
        pts.append(f"{100 + math.cos(a) * r:.1f},{100 + math.sin(a) * r:.1f}")
    return (f'<polygon points="{" ".join(pts)}" fill="#F5C518" stroke="#101728" '
            f'stroke-width="5" stroke-linejoin="round"/>'
            f'<circle cx="100" cy="100" r="16" fill="#D0212B"/>')


FIGURES = {
"serenity": {
    "expand": {"back": '<circle cx="100" cy="100" r="86" fill="#7C6BC4" opacity=".08"/>',
               "shape": _lotus(), "front": ""},
    "fill":   {"back": '<circle cx="100" cy="112" r="78" fill="#3D8FC4" opacity=".07"/>',
               "clip": "M100 26 C132 70 154 100 154 126 a54 54 0 0 1 -108 0 C46 100 68 70 100 26 Z",
               "liquid": "#5FB0E0",
               "front": '<path d="M100 26 C132 70 154 100 154 126 a54 54 0 0 1 -108 0 '
                        'C46 100 68 70 100 26 Z" fill="none" stroke="#3D8FC4" stroke-width="5"/>'
                        '<ellipse cx="78" cy="140" rx="9" ry="13" fill="#fff" opacity=".45" '
                        'transform="rotate(-20 78 140)"/>',
               "level": [186, 30]},
},
"superhero": {
    "expand": {"back": '<circle cx="100" cy="100" r="88" fill="#1750C4" opacity=".10"/>',
               "shape": _star(), "front": ""},
    "fill":   {"back": '<circle cx="100" cy="104" r="84" fill="#D0212B" opacity=".08"/>',
               "clip": "M100 22 L166 48 V108 C166 150 134 176 100 188 C66 176 34 150 34 108 V48 Z",
               "liquid": "#D0212B",
               "front": '<path d="M100 22 L166 48 V108 C166 150 134 176 100 188 '
                        'C66 176 34 150 34 108 V48 Z" fill="none" stroke="#101728" stroke-width="6" '
                        'stroke-linejoin="round"/>'
                        '<path d="M100 62 L112 96 L148 96 L119 117 L130 152 L100 131 L70 152 '
                        'L81 117 L52 96 L88 96 Z" fill="#F5C518" opacity=".9"/>',
               "level": [192, 24]},
},
"cafe": {
    "expand": {"back": '<circle cx="100" cy="100" r="86" fill="#7A4E2D" opacity=".08"/>',
               "shape": '<ellipse cx="100" cy="100" rx="76" ry="52" fill="#6B4227" '
                        'transform="rotate(-28 100 100)"/>'
                        '<path d="M46 118 Q100 82 154 82 Q100 118 46 118" fill="#F3EADC" '
                        'opacity=".75" transform="rotate(-28 100 100)"/>',
               "front": ""},
    # the example Nick gave: coffee filling the cup on the inhale, draining on the exhale
    "fill":   {"back": '<ellipse cx="100" cy="182" rx="72" ry="12" fill="#B9A88C" opacity=".35"/>'
                       '<path d="M148 74 a30 30 0 0 1 0 60" fill="none" stroke="#C9A87C" '
                       'stroke-width="12" stroke-linecap="round"/>',
               "clip": "M46 54 h104 l-11 106 a24 24 0 0 1 -24 22 h-34 a24 24 0 0 1 -24 -22 Z",
               "liquid": "#6B4227",
               "front": '<path d="M46 54 h104 l-11 106 a24 24 0 0 1 -24 22 h-34 '
                        'a24 24 0 0 1 -24 -22 Z" fill="none" stroke="#7A4E2D" stroke-width="6" '
                        'stroke-linejoin="round"/>'
                        '<rect x="40" y="44" width="116" height="14" rx="7" fill="#FFFCF7" '
                        'stroke="#7A4E2D" stroke-width="5"/>',
               "level": [180, 62]},
},
"astronomy": {
    "expand": {"back": '<circle cx="100" cy="100" r="88" fill="#7DAEFF" opacity=".10"/>',
               "shape": '<circle cx="100" cy="100" r="52" fill="#F2C14E"/>'
                        '<path d="M100 74 q28 6 48 2" stroke="#B8853A" stroke-width="6" '
                        'fill="none" opacity=".5" stroke-linecap="round"/>'
                        '<path d="M64 116 q36 12 72 -2" stroke="#B8853A" stroke-width="7" '
                        'fill="none" opacity=".45" stroke-linecap="round"/>'
                        '<ellipse cx="100" cy="100" rx="86" ry="22" fill="none" stroke="#F0DCA8" '
                        'stroke-width="7" opacity=".85" transform="rotate(-18 100 100)"/>',
               "front": ""},
    "fill":   {"back": '<circle cx="100" cy="100" r="88" fill="#7DAEFF" opacity=".08"/>'
                       '<circle cx="46" cy="42" r="2.5" fill="#fff" opacity=".8"/>'
                       '<circle cx="160" cy="56" r="2" fill="#fff" opacity=".7"/>'
                       '<circle cx="150" cy="150" r="2.2" fill="#fff" opacity=".6"/>',
               "clip": "M100 16 C132 52 138 96 138 128 v34 h-76 v-34 C62 96 68 52 100 16 Z",
               "liquid": "#7DAEFF",
               "front": '<path d="M100 16 C132 52 138 96 138 128 v34 h-76 v-34 '
                        'C62 96 68 52 100 16 Z" fill="none" stroke="#EAF0FF" stroke-width="5" '
                        'stroke-linejoin="round"/>'
                        '<path d="M62 140 L36 176 L62 166 Z" fill="#FF6B8A"/>'
                        '<path d="M138 140 L164 176 L138 166 Z" fill="#FF6B8A"/>'
                        '<circle cx="100" cy="84" r="16" fill="none" stroke="#EAF0FF" stroke-width="5"/>',
               "level": [166, 22]},
},
"terminal": {
    "expand": {"back": '<circle cx="100" cy="100" r="88" fill="#24C46A" opacity=".07"/>',
               "shape": '<polygon points="100,26 164,63 164,137 100,174 36,137 36,63" '
                        'fill="none" stroke="#24C46A" stroke-width="6" stroke-linejoin="round"/>'
                        '<polygon points="100,58 136,79 136,121 100,142 64,121 64,79" '
                        'fill="#24C46A" opacity=".2"/>'
                        '<circle cx="100" cy="100" r="14" fill="#2E90FF"/>',
               "front": ""},
    "fill":   {"back": '<circle cx="100" cy="100" r="88" fill="#2E90FF" opacity=".06"/>',
               "clip": "M42 52 h116 a10 10 0 0 1 10 10 v76 a10 10 0 0 1 -10 10 h-116 "
                       "a10 10 0 0 1 -10 -10 v-76 a10 10 0 0 1 10 -10 Z",
               "liquid": "#24C46A",
               "front": '<rect x="32" y="52" width="136" height="96" rx="10" fill="none" '
                        'stroke="#24C46A" stroke-width="5"/>'
                        '<rect x="168" y="84" width="12" height="32" rx="4" fill="#24C46A"/>'
                        '<text x="100" y="106" font-family="ui-monospace,monospace" font-size="19" '
                        'fill="#04070A" font-weight="700" text-anchor="middle" '
                        'opacity=".55">breathe</text>',
               "level": [150, 50]},
},
}


def as_js_data() -> dict:
    return {"patterns": PATTERNS, "durations": DURATIONS,
            "phaseLabels": PHASE_LABELS, "figures": FIGURES}


def cycle_seconds(pattern_key: str) -> int:
    p = next(p for p in PATTERNS if p["key"] == pattern_key)
    return sum(p["phases"])


if __name__ == "__main__":
    for p in PATTERNS:
        print(f"{p['name']:16s} {p['phases']}  {cycle_seconds(p['key'])}s/cycle  figure={p['figure']}")
    missing = [(t, k) for t, f in FIGURES.items() for k in ("expand", "fill") if k not in f]
    print("missing figures:", missing or "none")


# ====================================================================
# coach
# ====================================================================

MOOD_BADGE = {
    "idle": "",
    "writing": "✏️",
    "thinking": "💭",
    "cheer": "🎉",
    "proud": "🌟",
    "worried": "😬",
    "sleepy": "💤",
}


def coach_figure(svg, mood) -> rx.Component:
    """The character, wrapped so CSS can move it by mood.

    `svg` is the rendered avatar markup (AuthState.avatar_svg) and `mood` is a
    Var, so this re-renders whenever either changes.
    """
    return rx.box(
        rx.box(rx.html(svg), class_name="coach-av"),
        rx.box(class_name="coach-shadow"),
        # Sparkles for the celebratory moods. Empty elements the CSS animates;
        # cheaper and smoother than drawing particles in JavaScript.
        rx.box(
            rx.el.i(), rx.el.i(), rx.el.i(), rx.el.i(), rx.el.i(),
            class_name="coach-spark",
        ),
        rx.box(class_name="coach-badge"),
        class_name="coach-figure",
        custom_attrs={"data-mood": mood},
    )


def mood_badge_css() -> str:
    """The badge glyph per mood, emitted as CSS content rules.

    Generated from the table above rather than written twice, so adding a mood
    means adding one line here and nothing anywhere else.
    """
    out = []
    for mood, glyph in MOOD_BADGE.items():
        if not glyph:
            # `animation:none` matters as much as the opacity: the badge's
            # entrance animation ends on opacity 1, and an animation's final
            # frame beats a plain declaration. Without this the "idle" mood
            # shows an empty white disc instead of nothing at all.
            out.append(f'.coach-figure[data-mood="{mood}"] .coach-badge'
                       f'{{animation:none;opacity:0;transform:scale(.6);'
                       f'pointer-events:none}}')
        else:
            out.append(f'.coach-figure[data-mood="{mood}"] .coach-badge'
                       f'::after{{content:"{glyph}"}}')
    return "\n".join(out)


if __name__ == "__main__":
    print(mood_badge_css())


# ====================================================================
# graze
# ====================================================================

LENGTHS = [15, 20]

# The four kinds of thing that drift at you. `sides` is the polygon drawn for
# it; `speed` and `pts` are the balance.
KINDS = {
    "drifter": {"r": 11, "speed": 86, "pts": 20, "tone": "danger"},
    "chaser": {"r": 10, "speed": 58, "pts": 35, "tone": "accent2"},
    "weaver": {"r": 10, "speed": 116, "pts": 45, "tone": "success"},
    "hulk": {"r": 26, "speed": 34, "pts": 80, "tone": "warn"},
}

# Per theme: the polygon each kind is drawn as, and what the world calls them.
# A triangle in Terminal and a circle in Serenity are the same object doing the
# same job; only the costume changes.
THEMES = {
    "serenity": {
        "name": "Stillwater",
        "sides": {"drifter": 0, "chaser": 6, "weaver": 5, "hulk": 0},
        "words": {"drifter": "ripple", "chaser": "current",
                  "weaver": "eddy", "hulk": "swell"},
        "blurb": "Petals and ripples drifting on still water.",
    },
    "superhero": {
        "name": "Skyline",
        "sides": {"drifter": 3, "chaser": 4, "weaver": 5, "hulk": 6},
        "words": {"drifter": "shard", "chaser": "drone",
                  "weaver": "streak", "hulk": "wrecker"},
        "blurb": "Debris over the city. Fly close, charge up, clear the block.",
    },
    "cafe": {
        "name": "Roastery",
        "sides": {"drifter": 0, "chaser": 4, "weaver": 6, "hulk": 0},
        "words": {"drifter": "bean", "chaser": "grind",
                  "weaver": "steam", "hulk": "roast"},
        "blurb": "Beans and steam in the warm dark.",
    },
    "astronomy": {
        "name": "Deep Field",
        "sides": {"drifter": 3, "chaser": 4, "weaver": 5, "hulk": 6},
        "words": {"drifter": "fragment", "chaser": "probe",
                  "weaver": "comet", "hulk": "planetoid"},
        "blurb": "Threading the belt with nothing but your own nerve.",
    },
    "terminal": {
        "name": "Daemon",
        "sides": {"drifter": 4, "chaser": 4, "weaver": 3, "hulk": 6},
        "words": {"drifter": "packet", "chaser": "probe",
                  "weaver": "worm", "hulk": "kernel"},
        "blurb": "Processes closing in. Graze to gain privileges.",
    },
}

# Upgrades offered between waves. Deliberately all additive — nothing here
# takes anything away, and nothing is a trap choice, because a wrong pick that
# ruins a session is stress the screen is supposed to remove.
UPGRADES = [
    {"id": "whisk", "n": "Wider sense", "d": "Graze from noticeably farther out.", "max": 4},
    {"id": "stat", "n": "Static coat", "d": "Each graze charges your ring 40% faster.", "max": 4},
    {"id": "shock", "n": "Wide shock", "d": "Your burst reaches 35% farther.", "max": 3},
    {"id": "plate", "n": "Plating", "d": "One more shield, and all shields refill now.", "max": 5},
    {"id": "chron", "n": "Chronosense", "d": "Close grazes slow time harder and for longer.", "max": 3},
    {"id": "drone", "n": "Companion", "d": "An orbiting companion clears whatever it touches.", "max": 4},
    {"id": "spin", "n": "Spin up", "d": "Companions orbit wider and much faster.", "max": 3, "need": "drone"},
    {"id": "split", "n": "Splinters", "d": "Every burst flings three homing splinters.", "max": 3},
    {"id": "salv", "n": "Salvage", "d": "Wrecks drop far more pickups.", "max": 3},
    {"id": "lode", "n": "Lodestone", "d": "Pull pickups toward you from across the screen.", "max": 3},
    {"id": "mom", "n": "Momentum", "d": "Your chain takes much longer to fade.", "max": 3},
    {"id": "after", "n": "Afterimage", "d": "Bursting leaves you untouchable for a moment.", "max": 2},
    {"id": "bounty", "n": "Bounty", "d": "Everything you score is worth 25% more.", "max": 6},
    {"id": "kick", "n": "Recoil", "d": "Bursts knock survivors away from you.", "max": 2},
]

# What the screen says instead of "game over". Nothing here is a failure — the
# session is the thing, and the session is still running.
RESPAWN_LINES = [
    "Back in. The clock is still yours.",
    "That run ended. Nothing else did.",
    "Reset. Take the next one slower.",
    "Fine. Breathe out, go again.",
    "Nothing lost. Off you go.",
]


def graze_as_js_data() -> dict:
    return {
        "kinds": KINDS,
        "themes": THEMES,
        "upgrades": UPGRADES,
        "respawn": RESPAWN_LINES,
        "lengths": LENGTHS,
    }


if __name__ == "__main__":
    for key, t in THEMES.items():
        print(f"{key:11s} {t['name']:11s} {t['blurb']}")
    print(f"\n{len(UPGRADES)} upgrades, lengths {LENGTHS}")
