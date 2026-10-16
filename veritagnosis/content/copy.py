"""
Words the app says: quotes, essay prompts, coaching lines, the
scripts for asking a teacher, and the meditation roadmap.

All of it is content rather than logic — the same for every
student, changed by editing text, never by a migration.

Merged from: quotes, prompts, essay_coach, asking, meditation.
"""
from __future__ import annotations



# ====================================================================
# quotes
# ====================================================================

QUOTES = {
"serenity": [
    ("Nature does not hurry, yet everything is accomplished.", "Lao Tzu"),
    ("Almost everything will work again if you unplug it for a few minutes, including you.", "Anne Lamott"),
    ("You are allowed to be both a work in progress and a masterpiece.", "Sophia Bush"),
    ("The best time to plant a tree was twenty years ago. The second best time is now.", "Proverb"),
    ("One essay tonight. That's plenty.", None),
    ("You don't have to finish the application today. Just start it.", None),
],
"superhero": [
    ("Courage is not the absence of fear, but the triumph over it.", "Nelson Mandela"),
    ("A hero is an ordinary individual who finds the strength to persevere.", "Christopher Reeve"),
    ("It is not who I am underneath, but what I do that defines me.", "Batman Begins"),
    ("With great power comes great responsibility.", "Amazing Fantasy #15"),
    ("Every application is an origin story. This one is yours.", None),
    ("Suit up. The deadline is the villain, not the essay.", None),
],
"cafe": [
    ("Great things are done by a series of small things brought together.", "Vincent van Gogh"),
    ("Start where you are. Use what you have. Do what you can.", "Arthur Ashe"),
    ("A journey of a thousand miles begins with a single step.", "Lao Tzu"),
    ("It always seems impossible until it is done.", "Nelson Mandela"),
    ('Get something warm to drink and open the doc.', None),
    ('Two hundred words and a refill is a good night.', None),
],
"astronomy": [
    ("Somewhere, something incredible is waiting to be known.", "Carl Sagan"),
    ("The important thing is not to stop questioning.", "Albert Einstein"),
    ("We are made of star-stuff.", "Carl Sagan"),
    ("Equipped with his five senses, man explores the universe around him "
     "and calls the adventure Science.", "Edwin Hubble"),
    ("Every school on your list is a planet you haven't visited yet.", None),
    ("You're not behind. You're on your way.", None),
],
"terminal": [
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("Programs must be written for people to read, and only incidentally "
     "for machines to execute.", "Abelson & Sussman"),
    ("The best way to predict the future is to invent it.", "Alan Kay"),
    ("$ ./apply --relentless", None),
    ("Ship the draft. Refactor the draft. Ship it again.", None),
],
}

# Shown on the signup screen regardless of theme (the wireframe's three
# education quotes above the account form).
EDUCATION = [
    ("Education is the most powerful weapon which you can use to change the world.", "Nelson Mandela"),
    ("The beautiful thing about learning is that no one can take it away from you.", "B.B. King"),
    ("Develop a passion for learning. If you do, you will never cease to grow.", "Anthony J. D'Angelo"),
]

def seed_rows():
    """Flat rows ready for an INSERT into the quote table."""
    rows = [(theme, text, src) for theme, items in QUOTES.items() for text, src in items]
    rows += [("education", text, src) for text, src in EDUCATION]
    return rows

if __name__ == "__main__":
    rows = seed_rows()
    print(f"{len(rows)} quotes across {len(QUOTES)+1} pools")
    for t in list(QUOTES) + ["education"]:
        print(f"  {t:10s} {sum(1 for r in rows if r[0]==t)}")


# ====================================================================
# prompts
# ====================================================================

COMMON_APP = [
    {"key": "background",
     "text": "Some students have a background, identity, interest, or talent "
             "so meaningful they believe their application would be incomplete "
             "without it. If this sounds like you, share your story.",
     "note": ("This is the most open prompt, so it's the easiest one to waste. Pick "
              "one narrow thing you could talk about for an hour. You don't have to "
              'cover everything about yourself.'),
     "words": 650},

    {"key": "obstacle",
     "text": "The lessons we take from obstacles we encounter can be "
             "fundamental to later success. Recount a time when you faced a "
             "challenge, setback, or failure. How did it affect you, and what "
             "did you learn?",
     "note": ('Spend most of the essay on what you did afterward, not on how bad it '
              'was. The setback can be small. A small one told honestly works '
              'better than a big one told carefully.'),
     "words": 650},

    {"key": "questioned",
     "text": "Reflect on a time when you questioned or challenged a belief or "
             "idea. What prompted your thinking? What was the outcome?",
     "note": "The belief can be your own. Changing your own mind is more "
             "interesting than arguing with somebody else's.",
     "words": 650},

    {"key": "gratitude",
     "text": "Reflect on something that someone has done for you that has made "
             "you happy or thankful in a surprising way. How has this "
             "gratitude affected or motivated you?",
     "note": ('Careful: this essay is about you, not them. Keep the focus on how '
              'you changed.'),
     "words": 650},

    {"key": "growth",
     "text": "Discuss an accomplishment, event, or realization that sparked a "
             "period of personal growth and a new understanding of yourself or "
             "others.",
     "note": ("Show who you were before and who you were after. If the reader can't "
              "tell what changed, the essay hasn't answered the question."),
     "words": 650},

    {"key": "engaging",
     "text": "Describe a topic, idea, or concept you find so engaging that it "
             "makes you lose all track of time. Why does it captivate you? "
             "What or who do you turn to when you want to learn more?",
     "note": ('The best answers get oddly specific. Details are what make '
              'enthusiasm believable.'),
     "words": 650},

    {"key": "free",
     "text": "Share an essay on any topic of your choice. It can be one you've "
             "already written, one that responds to a different prompt, or one "
             "of your own design.",
     "note": ('This one is harder than it looks. Pick it only if you already know '
              'exactly what you want to write.'),
     "words": 650},
]

# The supplemental questions almost every college asks in some form.
SUPPLEMENTAL = [
    {"key": "why_us", "text": "Why do you want to attend this college?",
     "note": ('Name things that are only true of this college. If you could swap in '
              "another school's name and the paragraph still works, keep going."),
     "words": 250},

    {"key": "why_major", "text": "Why do you want to study this subject?",
     "note": "Start with the moment you got interested, not with the career it "
             "leads to.",
     "words": 250},

    {"key": "community", "text": "How will you contribute to our community?",
     "note": ("Talk about something you've already done for a group you're part of. "
              "What you've done counts for more than what you promise."),
     "words": 250},

    {"key": "activity", "text": "Elaborate on one of your extracurricular "
                                "activities or work experiences.",
     "note": ('This one is short. Keep only what you did and what difference it '
              'made.'),
     "words": 150},
]

ALL = COMMON_APP + SUPPLEMENTAL
BY_KEY = {p["key"]: p for p in ALL}


def find(text: str) -> dict | None:
    """Match a stored prompt string back to its entry, so a draft written
    before the picker existed still gets its guidance note."""
    t = (text or "").strip().lower()
    if not t:
        return None
    for p in ALL:
        if p["text"].lower().startswith(t[:60]) or t.startswith(p["text"][:60].lower()):
            return p
    return None


# ====================================================================
# essay_coach
# ====================================================================

STEPS = [
    {"say": ("First: who's reading this, and what do you want them to remember "
             'about you? Write it in one line.'),
     "hint": "One sentence. It's for you, not them."},
    {"say": ('Now the opening. Start in the middle of something happening instead '
             'of with a summary.'),
     "hint": "Try opening on a specific moment: a room, a sound, a thing you said."},
    {"say": ('Now zoom out a little. Why did that moment matter to you? This is '
             'where a lot of essays get vague, so stay specific.'),
     "hint": ("Skip 'I learned that hard work pays off.' What did you actually "
              'learn?')},
    {"say": ('What changed in how you think or act? Show it happening instead of '
             'announcing it.'),
     "hint": "A small concrete change beats a big abstract one."},
    {"say": ("Time to wrap up. Look a little ahead, but you don't need to promise "
             'to change the world.'),
     "hint": 'The last line should feel like it belongs there, not like an add-on.'},
    {"say": ('Now read it out loud. Any sentence you trip over needs rewriting. '
             "That's most of editing right there."),
     "hint": 'Really out loud, not in your head.'},
]

DONE = {"say": ("That's a draft. Leave it alone overnight. You'll see it more clearly "
                'tomorrow.'),
        "hint": "First drafts are supposed to be rough. That's normal."}


# ====================================================================
# asking
# ====================================================================

TEMPLATES = {
    "teacher": {
        "title": "Asking a teacher",
        "when": ('Ask at least a month before your first deadline. Popular teachers '
                 'get a lot of requests and fill up early.'),
        "how": ('Ask in person if you can, then send an email so they have the '
                'details in writing. Teachers tend to write warmer letters for '
                'students who asked them face to face.'),
        "body": (
            "Hi {teacher},\n\n"
            "I'm applying to college this year and I was hoping you might be "
            "willing to write me a letter of recommendation.\n\n"
            "I asked you because {reason}. If you're able to, my first deadline "
            "is {deadline}.\n\n"
            "I can send you anything that would help, like a list of where "
            "I'm applying, my draft essay, or a reminder of what I worked on "
            "in your class.\n\n"
            "I completely understand if you already have too many to write.\n\n"
            "Thank you,\n{name}"
        ),
        "reason_hint": ('…for example, your class changed how I think about the subject. Give '
                        "the real reason and mention a moment they'll remember."),
    },
    "guidance": {
        "title": 'Asking your counselor',
        "when": ('Early in the fall. Counselors write for your whole grade, so '
                 'students who ask early get more of their time.'),
        "how": ('Set up a meeting instead of catching them in the hallway, and bring '
                'your college list so you can go through it together.'),
        "body": (
            "Hi {teacher},\n\n"
            "Could I book a short meeting about my college applications? I'd "
            "like to go through my list and ask about the counselor "
            "recommendation.\n\n"
            "Where I'm at so far: {reason}\n\n"
            "My earliest deadline is {deadline}.\n\n"
            "Thank you,\n{name}"
        ),
        "reason_hint": "…a sentence on which colleges you are looking at and "
                       "what you are planning to study.",
    },
}

# Shown next to the status of someone who has been asked but has not replied.
NUDGE_DAYS = 14
NUDGE = (
    ("It's been {days} days. A short, friendly follow-up is normal, and "
     "teachers expect it. They're busy, not ignoring you. One line is "
     'enough: “Just checking in on the recommendation. Happy to send '
     'anything that would help.”')
)

# What each status means and what to do next.
STATUS_HELP = {
    "not_asked": ("You haven't asked yet. Catch them after class and ask in person. It "
                  'takes thirty seconds, and it matters more than anything else on this '
                  'page.'),
    "asked": "You've asked. Give them a week or two before you follow up.",
    "agreed": ('They said yes! Send them your essay draft and college list so they '
               'can write something specific.'),
    "submitted": ('The letter is in. Send them a thank-you note. You may need them to '
                  'write for you again.'),
}


def message(role: str, teacher: str, name: str, deadline: str, reason: str) -> str:
    """Fill in a template. Blanks stay as readable placeholders rather than
    empty gaps, so a half-finished message still makes sense to copy."""
    t = TEMPLATES.get(role, TEMPLATES["teacher"])
    return t["body"].format(
        teacher=teacher or "[their name]",
        name=name or "[your name]",
        deadline=deadline or "[your first deadline]",
        reason=reason or "[why you are asking them]",
    )


# ====================================================================
# meditation
# ====================================================================

ROADMAP = [
    {"key": "first_breath", "title": "First breath",
     "blurb": "Finish one session of any length.",
     "requires": {"sessions": 1}, "icon": "🌱", "xp": 20},

    {"key": "three_sittings", "title": "Three sittings",
     "blurb": 'Finish three sessions. Around here it starts to feel normal.',
     "requires": {"sessions": 3}, "icon": "🍃", "xp": 30},

    {"key": "all_three", "title": "All three techniques",
     "blurb": "Try box breathing, 4-7-8 and 4-6-8 at least once each.",
     "requires": {"patterns": 3}, "icon": "🧭", "xp": 50},

    {"key": "ten_minutes", "title": "Ten minutes total",
     "blurb": 'Ten minutes total, spread out however you like.',
     "requires": {"minutes": 10}, "icon": "⏳", "xp": 40},

    {"key": "three_day", "title": "Three days running",
     "blurb": 'Three days in a row. Short sessions count.',
     "requires": {"streak": 3}, "icon": "🔥", "xp": 60},

    {"key": "long_sit", "title": "A long one",
     "blurb": "Finish a full ten-minute session in one go.",
     "requires": {"minutes": 10, "sessions": 4}, "icon": "🕊️", "xp": 70},

    {"key": "thirty_total", "title": "Half an hour",
     "blurb": 'Thirty minutes total.',
     "requires": {"minutes": 30}, "icon": "🌊", "xp": 80},

    {"key": "week_streak", "title": "A full week",
     "blurb": 'Seven days in a row. This is where it turns into a habit.',
     "requires": {"streak": 7}, "icon": "👑", "xp": 150},
]

# Shown at the top of the meditation screen, above the roadmap.
MEDITATION_QUOTES = [
    ("You can't stop the waves, but you can learn to surf.", "Jon Kabat-Zinn"),
    ("Almost everything will work again if you unplug it for a few minutes, "
     "including you.", "Anne Lamott"),
    ("Within you there is a stillness and a sanctuary "
     "to which you can retreat at any time.", "Hermann Hesse"),
    ("Breathing in, I calm my body. Breathing out, I smile.", "Thich Nhat Hanh"),
    ("The application will still be there in ten minutes.", None),
]


def unlocked(stats: dict) -> list[str]:
    """Keys of every checkpoint the stats satisfy."""
    return [c["key"] for c in ROADMAP
            if all(stats.get(k, 0) >= v for k, v in c["requires"].items())]


def next_checkpoint(stats: dict) -> dict | None:
    """The first one not yet reached — what the roadmap should point at."""
    done = set(unlocked(stats))
    return next((c for c in ROADMAP if c["key"] not in done), None)


def progress_to(checkpoint: dict, stats: dict) -> int:
    """0-100 toward a checkpoint, using whichever requirement is furthest behind."""
    if not checkpoint:
        return 100
    ratios = [min(1.0, stats.get(k, 0) / v) for k, v in checkpoint["requires"].items()]
    return int(100 * min(ratios)) if ratios else 0


if __name__ == "__main__":
    demo = {"sessions": 3, "minutes": 12, "streak": 2, "patterns": 2}
    print("unlocked:", unlocked(demo))
    nxt = next_checkpoint(demo)
    print("next:", nxt["title"], f"{progress_to(nxt, demo)}%")
