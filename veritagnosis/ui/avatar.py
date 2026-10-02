"""
Layered SVG avatar. Single source of truth for both the Reflex app and the
standalone design preview.

The avatar is a stack of SVG fragments drawn into one 200x200 viewBox. Every
fragment is a plain string with two optional placeholders:

    {skin}  -> the chosen skin tone
    {hair}  -> the chosen hair color

Layers paint back to front in LAYER_ORDER. A selection is just a dict of
category -> option id, so a saved avatar is a small JSON blob on the user row:

    {"head": 2, "hair": 3, "hair_color": 1, ...}

Deliberately flat and stylized: shapes stay legible at 40px in the home header
and at 200px on the customization screen, and they carry no color of their own
beyond skin and hair, so the avatar reads the same in all five themes.
"""

from __future__ import annotations

# ---------------------------------------------------------------- palettes
SKIN_TONES = ["#F7E0CE", "#F3D2BC", "#E8B991", "#D9A273", "#C98D62", "#B0754C",
              "#A2653F", "#8B5733", "#75492B", "#5E3A22", "#4A2E1C", "#38220F"]
HAIR_COLORS = ["#2B2118", "#4A3728", "#5B3A21", "#7A4E2D", "#A9691F", "#C98A3A",
               "#D9B26A", "#E8D5A3", "#8E8E93", "#D4D4D8",
               # the loud ones are rewards; see LOCKED_COLOURS
               "#7B4BC9", "#2F9E8F", "#E8590C", "#C2255C"]

# ---------------------------------------------------------------- layers
# Order matters: earlier entries paint first (further back).
LAYER_ORDER = [
    "hair_back", "clothes", "head", "eyes", "eyebrows", "nose",
    "piercings", "hair", "accessories", "hat",
]

# Categories shown as tabs, in the order Nick specified.
CATEGORIES = [
    ("head", "Head"), ("clothes", "Clothes"), ("hat", "Hat"),
    ("accessories", "Accessories"), ("hair", "Hair"), ("eyes", "Eyes"),
    ("piercings", "Piercings"), ("eyebrows", "Eyebrows"), ("nose", "Nose"),
]

NONE = ""  # an option that draws nothing

# --- head: face shape ------------------------------------------------------
# Every head shares an IDENTICAL skull dome: the arc from (58,88) over the top
# and down to (142,88), i.e. a 42-radius crown centred at (100,88), topping out
# at y=46. Face shape varies only BELOW the cheekbones.
#
# This matters: hair is a fixed drawing. When each head had its own dome, a
# taller skull poked out through the hair. Sharing the crown makes every hair
# style sit correctly on every head, which is the whole fix.
HEAD = [
    ("Round",  '<path d="M58 88 a42 42 0 0 1 84 0 v12 a42 42 0 0 1 -84 0 Z" fill="{skin}"/>'
               '<path d="M88 126 h24 v16 h-24 Z" fill="{skin}"/>'),
    ("Oval",   '<path d="M58 88 a42 42 0 0 1 84 0 v16 c0 26 -18 40 -42 40 '
               'c-24 0 -42 -14 -42 -40 Z" fill="{skin}"/>'
               '<path d="M88 138 h24 v14 h-24 Z" fill="{skin}"/>'),
    ("Square", '<path d="M58 88 a42 42 0 0 1 84 0 v24 q0 20 -20 20 h-44 '
               'q-20 0 -20 -20 Z" fill="{skin}"/>'
               '<path d="M88 128 h24 v16 h-24 Z" fill="{skin}"/>'),
    ("Heart",  '<path d="M58 88 a42 42 0 0 1 84 0 v6 c0 30 -20 46 -42 58 '
               'c-22 -12 -42 -28 -42 -58 Z" fill="{skin}"/>'
               '<path d="M90 140 h20 v14 h-20 Z" fill="{skin}"/>'),
    ("Long",   '<path d="M58 88 a42 42 0 0 1 84 0 v22 c0 28 -16 44 -42 44 '
               'c-26 0 -42 -16 -42 -44 Z" fill="{skin}"/>'
               '<path d="M89 150 h22 v14 h-22 Z" fill="{skin}"/>'),
    ("Soft",   '<path d="M58 88 a42 42 0 0 1 84 0 v10 q0 34 -42 40 '
               'q-42 -6 -42 -40 Z" fill="{skin}"/>'
               '<path d="M88 134 h24 v16 h-24 Z" fill="{skin}"/>'),
    ("Angular",'<path d="M58 88 a42 42 0 0 1 84 0 v14 l-14 30 h-56 l-14 -30 Z" '
               'fill="{skin}"/>'
               '<path d="M88 132 h24 v14 h-24 Z" fill="{skin}"/>'),
]

# --- hair: front piece plus an optional back mass -------------------------
HAIR = [
    ("Bald", NONE, NONE),
    ("Short", '<path d="M56 90 a44 44 0 0 1 88 0 c-6 -12 -15 -17 -24 -19 '
              'c-13 9 -35 11 -50 2 c-9 5 -12 9 -14 17 Z" fill="{hair}"/>', NONE),
    ("Curly", '<path d="M60 82 a40 40 0 0 1 80 0 a12 12 0 0 0 -12 -14 '
              'a12 12 0 0 0 -14 -8 a12 12 0 0 0 -14 -4 a12 12 0 0 0 -16 4 '
              'a12 12 0 0 0 -14 8 a12 12 0 0 0 -10 14 Z" fill="{hair}"/>'
              '<circle cx="68" cy="70" r="11" fill="{hair}"/>'
              '<circle cx="132" cy="70" r="11" fill="{hair}"/>'
              '<circle cx="100" cy="46" r="13" fill="{hair}"/>', NONE),
    ("Long",  '<path d="M58 84 a42 42 0 0 1 84 0 c-4 -14 -12 -20 -22 -22 '
              'c-14 8 -32 8 -46 0 c-10 4 -14 10 -16 22 Z" fill="{hair}"/>',
              '<path d="M56 78 c0 -30 20 -46 44 -46 s44 16 44 46 v66 '
              'c-8 4 -14 -2 -14 -18 v-40 h-60 v40 c0 16 -6 22 -14 18 Z" fill="{hair}"/>'),
    ("Bun",   '<path d="M60 80 a40 40 0 0 1 80 0 c-6 -12 -14 -17 -22 -19 '
              'c-13 7 -33 7 -46 0 c-8 3 -10 8 -12 19 Z" fill="{hair}"/>',
              '<circle cx="100" cy="30" r="16" fill="{hair}"/>'),
    ("Afro",  '<path d="M62 84 a38 38 0 0 1 76 0 Z" fill="{hair}"/>'
              '<circle cx="100" cy="48" r="34" fill="{hair}"/>'
              '<circle cx="66" cy="70" r="17" fill="{hair}"/>'
              '<circle cx="134" cy="70" r="17" fill="{hair}"/>', NONE),
    ("Braids", '<path d="M58 82 a42 42 0 0 1 84 0 c-6 -12 -16 -18 -24 -20 '
               'c-12 8 -30 8 -44 2 c-8 4 -14 8 -16 18 Z" fill="{hair}"/>',
               '<path d="M62 84 q-8 30 -2 56" stroke="{hair}" stroke-width="11" '
               'fill="none" stroke-linecap="round"/>'
               '<path d="M138 84 q8 30 2 56" stroke="{hair}" stroke-width="11" '
               'fill="none" stroke-linecap="round"/>'),
    ("Waves",  '<path d="M56 88 a44 44 0 0 1 88 0 q-6 -14 -16 -18 '
               'q-10 8 -20 2 q-10 8 -20 2 q-10 6 -20 -2 q-9 5 -12 16 Z" '
               'fill="{hair}"/>', NONE),
    ("Pigtails",
               '<path d="M58 86 a42 42 0 0 1 84 0 c-5 -13 -14 -19 -23 -21 '
               'c-13 8 -33 8 -46 0 c-9 3 -13 9 -15 21 Z" fill="{hair}"/>',
               '<circle cx="50" cy="104" r="15" fill="{hair}"/>'
               '<circle cx="150" cy="104" r="15" fill="{hair}"/>'),
    ("Undercut",
               '<path d="M58 84 a42 42 0 0 1 84 0 c-4 -16 -14 -22 -26 -24 '
               'c-16 10 -30 6 -44 -2 c-8 6 -12 14 -14 26 Z" fill="{hair}"/>'
               '<path d="M58 92 q20 -6 40 -2" stroke="{hair}" stroke-width="3" '
               'fill="none" opacity=".45"/>', NONE),
    ("Topknot",
               '<path d="M60 82 a40 40 0 0 1 80 0 c-6 -11 -14 -16 -22 -18 '
               'c-13 7 -33 7 -46 0 c-8 3 -10 7 -12 18 Z" fill="{hair}"/>',
               '<ellipse cx="100" cy="26" rx="13" ry="17" fill="{hair}"/>'
               '<path d="M92 42 h16" stroke="{hair}" stroke-width="5" '
               'stroke-linecap="round"/>'),
    ("Locs",   '<path d="M58 84 a42 42 0 0 1 84 0 c-6 -14 -16 -20 -26 -22 '
               'c-14 8 -30 8 -44 0 c-9 4 -12 10 -14 22 Z" fill="{hair}"/>',
               '<path d="M60 86 v58 M72 88 v62 M128 88 v62 M140 86 v58" '
               'stroke="{hair}" stroke-width="9" stroke-linecap="round"/>'),
    ("Shaved", '<path d="M58 88 a42 42 0 0 1 84 0 a42 38 0 0 0 -84 0 Z" '
               'fill="{hair}" opacity=".55"/>', NONE),
]

# --- eyes -----------------------------------------------------------------
EYES = [
    ("Round",  '<circle cx="84" cy="88" r="7" fill="#fff"/><circle cx="116" cy="88" r="7" fill="#fff"/>'
               '<circle cx="84" cy="88" r="4" fill="#26303F"/><circle cx="116" cy="88" r="4" fill="#26303F"/>'),
    ("Almond", '<path d="M75 88 q9 -9 18 0 q-9 8 -18 0 Z" fill="#fff"/>'
               '<path d="M107 88 q9 -9 18 0 q-9 8 -18 0 Z" fill="#fff"/>'
               '<circle cx="84" cy="88" r="3.6" fill="#26303F"/><circle cx="116" cy="88" r="3.6" fill="#26303F"/>'),
    ("Happy",  '<path d="M76 90 q8 -10 16 0" stroke="#26303F" stroke-width="3.4" fill="none" stroke-linecap="round"/>'
               '<path d="M108 90 q8 -10 16 0" stroke="#26303F" stroke-width="3.4" fill="none" stroke-linecap="round"/>'),
    ("Wide",   '<ellipse cx="84" cy="88" rx="8" ry="9" fill="#fff"/><ellipse cx="116" cy="88" rx="8" ry="9" fill="#fff"/>'
               '<circle cx="84" cy="89" r="4.4" fill="#26303F"/><circle cx="116" cy="89" r="4.4" fill="#26303F"/>'
               '<circle cx="82" cy="86" r="1.5" fill="#fff"/><circle cx="114" cy="86" r="1.5" fill="#fff"/>'),
    ("Sleepy", '<path d="M76 88 h16" stroke="#26303F" stroke-width="3.4" stroke-linecap="round"/>'
               '<path d="M108 88 h16" stroke="#26303F" stroke-width="3.4" stroke-linecap="round"/>'
               '<path d="M76 84 q8 -5 16 0" stroke="#26303F" stroke-width="2" fill="none" opacity=".5"/>'
               '<path d="M108 84 q8 -5 16 0" stroke="#26303F" stroke-width="2" fill="none" opacity=".5"/>'),
    ("Focused",'<path d="M75 86 q9 -6 18 0 q-9 7 -18 0 Z" fill="#fff"/>'
               '<path d="M107 86 q9 -6 18 0 q-9 7 -18 0 Z" fill="#fff"/>'
               '<circle cx="84" cy="86" r="3.2" fill="#26303F"/>'
               '<circle cx="116" cy="86" r="3.2" fill="#26303F"/>'
               '<path d="M74 80 q10 -3 20 1 M106 81 q10 -4 20 -1" '
               'stroke="#26303F" stroke-width="2.6" fill="none" stroke-linecap="round"/>'),
    ("Bright", '<circle cx="84" cy="88" r="8" fill="#fff"/><circle cx="116" cy="88" r="8" fill="#fff"/>'
               '<circle cx="84" cy="88" r="4.4" fill="#26303F"/><circle cx="116" cy="88" r="4.4" fill="#26303F"/>'
               '<circle cx="81.5" cy="85" r="2.1" fill="#fff"/><circle cx="113.5" cy="85" r="2.1" fill="#fff"/>'
               '<circle cx="86" cy="91" r="1.1" fill="#fff" opacity=".8"/>'
               '<circle cx="118" cy="91" r="1.1" fill="#fff" opacity=".8"/>'),
    ("Wink",   '<circle cx="84" cy="88" r="7" fill="#fff"/>'
               '<circle cx="84" cy="88" r="4" fill="#26303F"/>'
               '<path d="M108 89 q8 -9 16 0" stroke="#26303F" stroke-width="3.4" '
               'fill="none" stroke-linecap="round"/>'),
    ("Tired",  '<path d="M75 88 q9 -7 18 0 q-9 7 -18 0 Z" fill="#fff"/>'
               '<path d="M107 88 q9 -7 18 0 q-9 7 -18 0 Z" fill="#fff"/>'
               '<circle cx="84" cy="88" r="3.4" fill="#26303F"/>'
               '<circle cx="116" cy="88" r="3.4" fill="#26303F"/>'
               '<path d="M77 96 q7 3 14 0 M109 96 q7 3 14 0" stroke="#B98263" '
               'stroke-width="1.8" fill="none" opacity=".7"/>'),
]

# --- eyebrows -------------------------------------------------------------
EYEBROWS = [
    ("Soft",    '<path d="M75 76 q9 -5 18 -1" stroke="{hair}" stroke-width="3.6" fill="none" stroke-linecap="round"/>'
                '<path d="M107 75 q9 -4 18 1" stroke="{hair}" stroke-width="3.6" fill="none" stroke-linecap="round"/>'),
    ("Bold",    '<path d="M74 76 q10 -7 20 -1" stroke="{hair}" stroke-width="6" fill="none" stroke-linecap="round"/>'
                '<path d="M106 75 q10 -6 20 1" stroke="{hair}" stroke-width="6" fill="none" stroke-linecap="round"/>'),
    ("Straight",'<path d="M75 76 h18" stroke="{hair}" stroke-width="4.2" stroke-linecap="round"/>'
                '<path d="M107 76 h18" stroke="{hair}" stroke-width="4.2" stroke-linecap="round"/>'),
    ("Raised",  '<path d="M75 78 q9 -9 18 -2" stroke="{hair}" stroke-width="4" fill="none" stroke-linecap="round"/>'
                '<path d="M107 74 h18" stroke="{hair}" stroke-width="4" stroke-linecap="round"/>'),
    ("Thin",    '<path d="M76 76 q8 -4 17 -1" stroke="{hair}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
                '<path d="M107 75 q9 -3 17 1" stroke="{hair}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'),
    ("Arched",  '<path d="M74 78 q10 -11 20 -1" stroke="{hair}" stroke-width="4" fill="none" stroke-linecap="round"/>'
                '<path d="M106 77 q10 -10 20 1" stroke="{hair}" stroke-width="4" fill="none" stroke-linecap="round"/>'),
    ("Worried", '<path d="M75 73 q9 3 18 4" stroke="{hair}" stroke-width="3.8" fill="none" stroke-linecap="round"/>'
                '<path d="M107 77 q9 -1 18 -4" stroke="{hair}" stroke-width="3.8" fill="none" stroke-linecap="round"/>'),
]

# --- nose -----------------------------------------------------------------
NOSE = [
    ("Button", '<path d="M100 96 q5 8 -1 10" stroke="#B98263" stroke-width="3" fill="none" stroke-linecap="round"/>'),
    ("Straight", '<path d="M100 92 v12 h-5" stroke="#B98263" stroke-width="3" fill="none" '
                 'stroke-linecap="round" stroke-linejoin="round"/>'),
    ("Wide",   '<path d="M94 104 q6 5 12 0" stroke="#B98263" stroke-width="3" fill="none" stroke-linecap="round"/>'
               '<path d="M100 93 v9" stroke="#B98263" stroke-width="2.4" stroke-linecap="round"/>'),
    ("Upturn", '<path d="M100 93 q-6 9 2 11 q4 1 4 -3" stroke="#B98263" stroke-width="3" fill="none" '
               'stroke-linecap="round"/>'),
    ("Small",  '<path d="M99 99 q4 5 -1 6" stroke="#B98263" stroke-width="2.6" fill="none" '
               'stroke-linecap="round"/>'),
    ("Roman",  '<path d="M101 91 q-3 7 -2 13 h-5" stroke="#B98263" stroke-width="2.8" fill="none" '
               'stroke-linecap="round" stroke-linejoin="round"/>'),
]

# --- clothes: shoulders/torso behind the head ------------------------------
CLOTHES = [
    ("Tee",     '<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#4C6EF5"/>'
                '<path d="M86 142 q14 12 28 0 l-6 -6 q-8 6 -16 0 Z" fill="#3B5BDB"/>'),
    ("Hoodie",  '<path d="M54 200 v-32 a46 32 0 0 1 92 0 v32 Z" fill="#495057"/>'
                '<path d="M80 146 q20 16 40 0 l-4 -8 q-16 12 -32 0 Z" fill="#343A40"/>'
                '<path d="M96 160 v22 M104 160 v22" stroke="#DEE2E6" stroke-width="3" stroke-linecap="round"/>'),
    ("Collar",  '<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#F1F3F5"/>'
                '<path d="M86 142 l14 20 l14 -20 l-8 -4 l-6 8 l-6 -8 Z" fill="#DEE2E6"/>'
                '<path d="M100 162 v20" stroke="#ADB5BD" stroke-width="2"/>'),
    ("Varsity", '<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#C92A2A"/>'
                '<path d="M58 200 v-30 a42 30 0 0 1 20 -25 v55 Z" fill="#F1F3F5"/>'
                '<path d="M142 200 v-30 a42 30 0 0 0 -20 -25 v55 Z" fill="#F1F3F5"/>'
                '<text x="100" y="186" font-size="22" font-family="Georgia,serif" font-weight="700" '
                'fill="#F1F3F5" text-anchor="middle">V</text>'),
    ("Overalls",'<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#EDEDED"/>'
                '<path d="M70 200 v-24 a30 22 0 0 1 60 0 v24 Z" fill="#3B6EA5"/>'
                '<path d="M84 154 l6 18 M116 154 l-6 18" stroke="#3B6EA5" stroke-width="7" stroke-linecap="round"/>'),
    ("Stripes", '<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#F8F9FA"/>'
                '<path d="M58 176 h84 M58 188 h84 M58 200 h84" stroke="#364FC7" '
                'stroke-width="6"/>'
                '<path d="M86 142 q14 12 28 0 l-6 -6 q-8 6 -16 0 Z" fill="#DEE2E6"/>'),
    ("Cardigan",'<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#8B6F47"/>'
                '<path d="M92 148 v52 M108 148 v52" stroke="#6B5333" stroke-width="4"/>'
                '<path d="M96 156 h8 v44 h-8 Z" fill="#F1F3F5"/>'
                '<circle cx="100" cy="166" r="2" fill="#6B5333"/>'
                '<circle cx="100" cy="182" r="2" fill="#6B5333"/>'),
    ("Jersey",  '<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#2B8A3E"/>'
                '<path d="M86 142 q14 12 28 0 l-6 -6 q-8 6 -16 0 Z" fill="#237032"/>'
                '<text x="100" y="192" font-size="26" font-family="Georgia,serif" '
                'font-weight="700" fill="#F1F3F5" text-anchor="middle">7</text>'),
    ("Turtle",  '<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#343A40"/>'
                '<path d="M84 140 q16 14 32 0 v12 q-16 14 -32 0 Z" fill="#495057"/>'),
    ("Denim",   '<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#4C6EF5" opacity=".85"/>'
                '<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="none" '
                'stroke="#DBE4FF" stroke-width="2" stroke-dasharray="4 4"/>'
                '<path d="M86 142 q14 12 28 0 l-6 -6 q-8 6 -16 0 Z" fill="#3B5BDB"/>'),
    ("Lab coat",'<path d="M58 200 v-30 a42 30 0 0 1 84 0 v30 Z" fill="#F8F9FA"/>'
                '<path d="M90 146 l10 18 l10 -18 l-7 -4 l-3 6 l-3 -6 Z" fill="#E9ECEF"/>'
                '<path d="M100 164 v36" stroke="#CED4DA" stroke-width="2"/>'
                '<rect x="116" y="176" width="16" height="12" rx="2" fill="#E9ECEF"/>'
                '<path d="M120 176 v-6" stroke="#4C6EF5" stroke-width="2.4" stroke-linecap="round"/>'),
]

# --- hat ------------------------------------------------------------------
HAT = [
    ("None", NONE),
    ("Cap",  '<path d="M62 68 a38 34 0 0 1 76 0 Z" fill="#E8590C"/>'
             '<path d="M136 68 q22 2 24 12 h-26 Z" fill="#D9480F"/>'
             '<circle cx="100" cy="36" r="4" fill="#D9480F"/>'),
    ("Beanie",'<path d="M60 72 a40 38 0 0 1 80 0 Z" fill="#5F3DC4"/>'
             '<rect x="58" y="68" width="84" height="12" rx="6" fill="#7048E8"/>'
             '<circle cx="100" cy="32" r="7" fill="#7048E8"/>'),
    ("Grad", '<path d="M100 30 L156 52 L100 74 L44 52 Z" fill="#212529"/>'
             '<path d="M74 62 v18 q26 14 52 0 v-18" fill="#343A40"/>'
             '<path d="M152 53 v22" stroke="#F5C518" stroke-width="3"/>'
             '<circle cx="152" cy="77" r="5" fill="#F5C518"/>'),
    ("Bow",  '<path d="M88 54 l-16 -9 v18 Z" fill="#E64980"/>'
             '<path d="M112 54 l16 -9 v18 Z" fill="#E64980"/>'
             '<circle cx="100" cy="54" r="7" fill="#F06595"/>'),
    ("Bucket",'<path d="M58 70 h84 q-4 12 -16 14 h-52 q-12 -2 -16 -14 Z" fill="#74B816"/>'
             '<path d="M66 70 a34 30 0 0 1 68 0 Z" fill="#8CE99A"/>'
             '<path d="M66 60 h68" stroke="#5C940D" stroke-width="4"/>'),
    ("Headband",'<path d="M58 74 q42 -16 84 0 v10 q-42 -16 -84 0 Z" fill="#F76707"/>'
             '<circle cx="100" cy="66" r="5" fill="#FFA94D"/>'),
    ("Beret",'<path d="M60 70 q10 -30 42 -30 q34 0 38 26 q-38 14 -80 4 Z" fill="#C2255C"/>'
             '<circle cx="128" cy="40" r="6" fill="#E64980"/>'),
    ("Crown",'<path d="M64 68 l6 -30 l14 16 l16 -24 l16 24 l14 -16 l6 30 Z" fill="#F5C518"/>'
             '<path d="M64 68 h72 v8 h-72 Z" fill="#E0A800"/>'
             '<circle cx="100" cy="52" r="4" fill="#E64980"/>'
             '<circle cx="78" cy="58" r="3" fill="#4C6EF5"/>'
             '<circle cx="122" cy="58" r="3" fill="#40C057"/>'),
    ("Laurel",'<path d="M62 84 q-14 -30 6 -48" stroke="#2B8A3E" stroke-width="5" '
             'fill="none" stroke-linecap="round"/>'
             '<path d="M138 84 q14 -30 -6 -48" stroke="#2B8A3E" stroke-width="5" '
             'fill="none" stroke-linecap="round"/>'
             '<ellipse cx="62" cy="70" rx="7" ry="4" fill="#40C057" transform="rotate(-40 62 70)"/>'
             '<ellipse cx="66" cy="56" rx="7" ry="4" fill="#40C057" transform="rotate(-25 66 56)"/>'
             '<ellipse cx="138" cy="70" rx="7" ry="4" fill="#40C057" transform="rotate(40 138 70)"/>'
             '<ellipse cx="134" cy="56" rx="7" ry="4" fill="#40C057" transform="rotate(25 134 56)"/>'),
]

# --- accessories ----------------------------------------------------------
ACCESSORIES = [
    ("None", NONE),
    ("Glasses", '<circle cx="84" cy="88" r="13" fill="none" stroke="#343A40" stroke-width="3"/>'
                '<circle cx="116" cy="88" r="13" fill="none" stroke="#343A40" stroke-width="3"/>'
                '<path d="M97 88 h6" stroke="#343A40" stroke-width="3"/>'
                '<path d="M71 86 l-9 -3 M129 86 l9 -3" stroke="#343A40" stroke-width="3" stroke-linecap="round"/>'),
    ("Headphones", '<path d="M60 88 v-8 a40 40 0 0 1 80 0 v8" fill="none" stroke="#212529" stroke-width="6"/>'
                   '<rect x="52" y="84" width="16" height="26" rx="8" fill="#212529"/>'
                   '<rect x="132" y="84" width="16" height="26" rx="8" fill="#212529"/>'),
    ("Scarf",  '<path d="M74 132 q26 16 52 0 v14 q-26 16 -52 0 Z" fill="#E03131"/>'
               '<path d="M118 146 l10 30 h-12 l-6 -26 Z" fill="#C92A2A"/>'),
    ("Freckles", '<circle cx="78" cy="100" r="1.8" fill="#B5714E" opacity=".8"/>'
                 '<circle cx="86" cy="104" r="1.6" fill="#B5714E" opacity=".8"/>'
                 '<circle cx="82" cy="108" r="1.5" fill="#B5714E" opacity=".7"/>'
                 '<circle cx="122" cy="100" r="1.8" fill="#B5714E" opacity=".8"/>'
                 '<circle cx="114" cy="104" r="1.6" fill="#B5714E" opacity=".8"/>'
                 '<circle cx="118" cy="108" r="1.5" fill="#B5714E" opacity=".7"/>'),
    ("Round specs", '<circle cx="84" cy="88" r="11" fill="#DBE4FF" opacity=".35"/>'
                 '<circle cx="116" cy="88" r="11" fill="#DBE4FF" opacity=".35"/>'
                 '<circle cx="84" cy="88" r="11" fill="none" stroke="#B08968" stroke-width="2.6"/>'
                 '<circle cx="116" cy="88" r="11" fill="none" stroke="#B08968" stroke-width="2.6"/>'
                 '<path d="M95 88 h10" stroke="#B08968" stroke-width="2.6"/>'
                 '<path d="M73 86 l-11 -3 M127 86 l11 -3" stroke="#B08968" '
                 'stroke-width="2.6" stroke-linecap="round"/>'),
    ("Shades", '<path d="M68 82 h26 q3 0 3 4 v5 q0 7 -8 7 h-11 q-10 0 -10 -9 Z" fill="#212529"/>'
                 '<path d="M106 82 h26 v7 q0 9 -10 9 h-11 q-8 0 -8 -7 v-5 q0 -4 3 -4 Z" fill="#212529"/>'
                 '<path d="M97 85 h6" stroke="#212529" stroke-width="3"/>'
                 '<path d="M68 83 l-7 -2 M132 83 l7 -2" stroke="#212529" '
                 'stroke-width="3" stroke-linecap="round"/>'),
    ("Earbuds", '<circle cx="62" cy="100" r="5" fill="#F8F9FA" stroke="#ADB5BD" stroke-width="1.5"/>'
                 '<path d="M62 105 v12" stroke="#F8F9FA" stroke-width="3.4" stroke-linecap="round"/>'
                 '<circle cx="138" cy="100" r="5" fill="#F8F9FA" stroke="#ADB5BD" stroke-width="1.5"/>'
                 '<path d="M138 105 v12" stroke="#F8F9FA" stroke-width="3.4" stroke-linecap="round"/>'),
    ("Blush",  '<ellipse cx="74" cy="104" rx="9" ry="5" fill="#F06595" opacity=".35"/>'
                 '<ellipse cx="126" cy="104" rx="9" ry="5" fill="#F06595" opacity=".35"/>'),
    ("Medal",  '<path d="M92 140 l8 22 M108 140 l-8 22" stroke="#4C6EF5" stroke-width="5"/>'
                 '<circle cx="100" cy="172" r="13" fill="#F5C518" stroke="#E0A800" stroke-width="2.5"/>'
                 '<text x="100" y="178" font-size="14" font-family="Georgia,serif" '
                 'font-weight="700" fill="#8A6D00" text-anchor="middle">1</text>'),
]

# --- piercings ------------------------------------------------------------
PIERCINGS = [
    ("None", NONE),
    ("Studs", '<circle cx="61" cy="100" r="3.2" fill="#F5C518"/>'
              '<circle cx="139" cy="100" r="3.2" fill="#F5C518"/>'),
    ("Hoops", '<circle cx="61" cy="104" r="6.5" fill="none" stroke="#F5C518" stroke-width="2.6"/>'
              '<circle cx="139" cy="104" r="6.5" fill="none" stroke="#F5C518" stroke-width="2.6"/>'),
    ("Nose ring", '<circle cx="107" cy="104" r="4.6" fill="none" stroke="#C0C4CC" stroke-width="2.2"/>'),
    ("Both", '<circle cx="61" cy="100" r="3.2" fill="#F5C518"/>'
             '<circle cx="139" cy="100" r="3.2" fill="#F5C518"/>'
             '<circle cx="107" cy="104" r="4.6" fill="none" stroke="#C0C4CC" stroke-width="2.2"/>'),
    ("Drops", '<circle cx="61" cy="98" r="2.6" fill="#C0C4CC"/>'
              '<path d="M61 101 v7" stroke="#C0C4CC" stroke-width="1.6"/>'
              '<circle cx="61" cy="111" r="3.4" fill="#4C6EF5"/>'
              '<circle cx="139" cy="98" r="2.6" fill="#C0C4CC"/>'
              '<path d="M139 101 v7" stroke="#C0C4CC" stroke-width="1.6"/>'
              '<circle cx="139" cy="111" r="3.4" fill="#4C6EF5"/>'),
    ("Cuffs", '<circle cx="61" cy="96" r="2.6" fill="#F5C518"/>'
              '<circle cx="60" cy="88" r="2.4" fill="#F5C518"/>'
              '<circle cx="139" cy="96" r="2.6" fill="#F5C518"/>'
              '<circle cx="140" cy="88" r="2.4" fill="#F5C518"/>'),
]

# ---------------------------------------------------------------- assembly
OPTIONS = {
    "head": [n for n, _ in HEAD],
    "hair": [n for n, _, _ in HAIR],
    "eyes": [n for n, _ in EYES],
    "eyebrows": [n for n, _ in EYEBROWS],
    "nose": [n for n, _ in NOSE],
    "clothes": [n for n, _ in CLOTHES],
    "hat": [n for n, _ in HAT],
    "accessories": [n for n, _ in ACCESSORIES],
    "piercings": [n for n, _ in PIERCINGS],
}

DEFAULT_AVATAR = {
    "head": 0, "skin": 1, "hair": 1, "hair_color": 1, "eyes": 0, "eyebrows": 0,
    "nose": 0, "clothes": 0, "hat": 0, "accessories": 0, "piercings": 0,
}

# --------------------------------------------------------------- what's locked
# (category, option index) -> the achievement key that opens it.
#
# Only ever the *decorative* categories. Faces, skin tones and the plain hair
# colours are never locked, because a student has to be able to make something
# that looks like themselves on their first visit — locking identity behind
# work would be a genuinely nasty thing to do. What is locked is the showing
# off: the hats, the loud hair, the jacket with a number on it.
#
# Each one is deliberately attached to an achievement it *reads* as a reward
# for. The graduation cap comes from sending an application, the laurel and
# the crown from the two hardest things on the board, the lab coat from a
# polished draft. The point is that somebody looking at your avatar can tell
# what you did.
LOCKED = {
    ("hat", 3): "a_submitted",          # Grad cap — you sent one
    ("hat", 7): "a_first_yes",          # Beret — somebody said yes
    ("hat", 8): "a_three_sent",         # Crown — three away
    ("hat", 9): "a_whole_thing",        # Laurel — the whole thing
    ("clothes", 5): "a_full_length",    # Stripes
    ("clothes", 6): "a_calm_habit",     # Cardigan
    ("clothes", 7): "a_break_hour",     # Jersey
    ("clothes", 9): "a_marathon",       # Denim
    ("clothes", 10): "a_two_polished",  # Lab coat
    ("accessories", 5): "a_npc",        # Round specs — you learned the price
    ("accessories", 6): "a_scholar_sent",   # Shades
    ("accessories", 8): "a_calm_hour",  # Blush
    ("accessories", 9): "a_sharp",      # Medal — the hardest writing one
    ("piercings", 5): "a_letters_in",   # Drops
    ("piercings", 6): "a_forms",        # Cuffs
    ("hair", 7): "a_draft",             # Waves
    ("hair", 9): "a_halfway",           # Undercut
    ("hair", 10): "a_finished",         # Topknot
    ("hair", 11): "a_two_yes",          # Locs
}

# Hair colours are indexed separately from the part lists, so they need their
# own map. The four loud ones at the end of HAIR_COLORS are the rewards.
LOCKED_COLOURS = {
    10: "a_first_words",     # purple
    11: "a_first_calm",      # teal
    12: "a_dates",           # orange
    13: "a_scholar_five",    # magenta
}


def lock_for(category: str, index: int) -> str | None:
    """The achievement that opens this option, or None if it was never shut."""
    return LOCKED.get((category, index))


def colour_lock_for(index: int) -> str | None:
    return LOCKED_COLOURS.get(index)


def is_available(category: str, index: int, earned: set[str]) -> bool:
    need = lock_for(category, index)
    return need is None or need in earned


def sanitise(sel: dict, earned: set[str]) -> dict:
    """Drop any selection the student is not entitled to.

    Worth doing even though the UI will not offer a locked tile: a saved
    avatar is a JSON blob on the user row, and blobs outlive the rules that
    made them. If an achievement is ever reworded or removed, this quietly
    puts the avatar back to something legitimate instead of rendering a
    reward nobody earned.
    """
    out = dict(sel)
    for (cat, idx), need in LOCKED.items():
        if out.get(cat) == idx and need not in earned:
            out[cat] = 0
    if LOCKED_COLOURS.get(out.get("hair_color", 0)) not in (None,) and \
            LOCKED_COLOURS.get(out.get("hair_color", 0)) not in earned:
        out["hair_color"] = 0
    return out

MOUTH = ('<path d="M92 112 q8 7 16 0" stroke="#B0563C" stroke-width="3" '
         'fill="none" stroke-linecap="round"/>')


def _pick(table, idx, n=2):
    """Clamp rather than raise — a stale saved index must not break a page."""
    return table[idx % len(table)][1:n]


def render(sel: dict | None = None, size: int = 200) -> str:
    """Compose the full avatar SVG for a selection dict."""
    s = {**DEFAULT_AVATAR, **(sel or {})}
    skin = SKIN_TONES[s["skin"] % len(SKIN_TONES)]
    hair = HAIR_COLORS[s["hair_color"] % len(HAIR_COLORS)]

    hair_front, hair_back = _pick(HAIR, s["hair"], 3)
    layers = {
        "hair_back": hair_back,
        "clothes": CLOTHES[s["clothes"] % len(CLOTHES)][1],
        "head": HEAD[s["head"] % len(HEAD)][1] + MOUTH,
        "eyes": EYES[s["eyes"] % len(EYES)][1],
        "eyebrows": EYEBROWS[s["eyebrows"] % len(EYEBROWS)][1],
        "nose": NOSE[s["nose"] % len(NOSE)][1],
        "piercings": PIERCINGS[s["piercings"] % len(PIERCINGS)][1],
        "hair": hair_front,
        "accessories": ACCESSORIES[s["accessories"] % len(ACCESSORIES)][1],
        "hat": HAT[s["hat"] % len(HAT)][1],
    }
    body = "".join(layers[k] for k in LAYER_ORDER)
    body = body.replace("{skin}", skin).replace("{hair}", hair)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" '
            f'width="{size}" height="{size}">{body}</svg>')


def as_js_data() -> dict:
    """The same tables, shaped for the standalone preview page."""
    return {
        "skin": SKIN_TONES,
        "hairColors": HAIR_COLORS,
        "layerOrder": LAYER_ORDER,
        "categories": [{"key": k, "label": l} for k, l in CATEGORIES],
        "mouth": MOUTH,
        "parts": {
            "head": [{"name": n, "svg": v} for n, v in HEAD],
            "hair": [{"name": n, "svg": f, "back": b} for n, f, b in HAIR],
            "eyes": [{"name": n, "svg": v} for n, v in EYES],
            "eyebrows": [{"name": n, "svg": v} for n, v in EYEBROWS],
            "nose": [{"name": n, "svg": v} for n, v in NOSE],
            "clothes": [{"name": n, "svg": v} for n, v in CLOTHES],
            "hat": [{"name": n, "svg": v} for n, v in HAT],
            "accessories": [{"name": n, "svg": v} for n, v in ACCESSORIES],
            "piercings": [{"name": n, "svg": v} for n, v in PIERCINGS],
        },
        "default": DEFAULT_AVATAR,
    }


if __name__ == "__main__":
    total = 1
    for k, v in OPTIONS.items():
        total *= len(v)
        print(f"  {k:12s} {len(v)} options")
    total *= len(SKIN_TONES) * len(HAIR_COLORS)
    print(f"\n{total:,} distinct avatars")
