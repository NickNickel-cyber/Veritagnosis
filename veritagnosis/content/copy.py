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
    ("One essay. One evening. That is the whole job tonight.", None),
    ("You do not have to finish the application today. You have to start it.", None),
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
    ("Order something warm. Open the doc. That is the whole ritual.", None),
    ("Two hundred words and a refill. That is a good night's work.", None),
],
"astronomy": [
    ("Somewhere, something incredible is waiting to be known.", "Carl Sagan"),
    ("The important thing is not to stop questioning.", "Albert Einstein"),
    ("We are made of star-stuff.", "Carl Sagan"),
    ("Equipped with his five senses, man explores the universe around him "
     "and calls the adventure Science.", "Edwin Hubble"),
    ("Every school on your list is a planet you have not visited yet.", None),
    ("You are not behind. You are in transit.", None),
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
     "note": "The most open one, which makes it the easiest to waste. Pick one "
             "narrow thing you could talk about for an hour, not the whole of "
             "who you are.",
     "words": 650},

    {"key": "obstacle",
     "text": "The lessons we take from obstacles we encounter can be "
             "fundamental to later success. Recount a time when you faced a "
             "challenge, setback, or failure. How did it affect you, and what "
             "did you learn?",
     "note": "Most of the essay should be what you did afterwards, not how bad "
             "it was. And the failure can be small — a genuinely small one, "
             "honestly told, beats a large one told carefully.",
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
     "note": "Watch out: this one is about you, not about them. The person is "
             "the setting; the change in you is the subject.",
     "words": 650},

    {"key": "growth",
     "text": "Discuss an accomplishment, event, or realization that sparked a "
             "period of personal growth and a new understanding of yourself or "
             "others.",
     "note": "'A period of growth' means show the before and the after. If the "
             "reader cannot tell what changed, the essay has not answered it.",
     "words": 650},

    {"key": "engaging",
     "text": "Describe a topic, idea, or concept you find so engaging that it "
             "makes you lose all track of time. Why does it captivate you? "
             "What or who do you turn to when you want to learn more?",
     "note": "The best answers here are specific to the point of being odd. "
             "Enthusiasm is only convincing when it is detailed.",
     "words": 650},

    {"key": "free",
     "text": "Share an essay on any topic of your choice. It can be one you've "
             "already written, one that responds to a different prompt, or one "
             "of your own design.",
     "note": "Freedom is harder, not easier. Only take this one if you already "
             "know exactly what you are writing.",
     "words": 650},
]

# The supplemental questions almost every college asks in some form.
SUPPLEMENTAL = [
    {"key": "why_us", "text": "Why do you want to attend this college?",
     "note": "Name things that could only be said about this one place. If the "
             "paragraph would survive a find-and-replace of the college name, "
             "it is not finished.",
     "words": 250},

    {"key": "why_major", "text": "Why do you want to study this subject?",
     "note": "Start with the moment you got interested, not with the career it "
             "leads to.",
     "words": 250},

    {"key": "community", "text": "How will you contribute to our community?",
     "note": "Describe something you have already done for a group you already "
             "belong to. Promises are worthless here; evidence is not.",
     "words": 250},

    {"key": "activity", "text": "Elaborate on one of your extracurricular "
                                "activities or work experiences.",
     "note": "Very short. Cut every word that is not the specific thing you did "
             "and the specific difference it made.",
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
    {"say": "Before anything else — who is reading this, and what do you want "
            "them to remember about you afterwards? Write that in one line.",
     "hint": "One sentence. It's for you, not them."},
    {"say": "Next, you need a hook to attract the reader. Start in the middle of "
            "something happening, not with a summary.",
     "hint": "Try opening on a specific moment: a room, a sound, a thing you said."},
    {"say": "Good. Now widen out — why did that moment matter to you? This is "
            "where most essays go generic. Stay specific.",
     "hint": "Avoid 'I learned that hard work pays off'. What did YOU learn?"},
    {"say": "Give me the turn. What changed in how you think or act? Show it, "
            "don't announce it.",
     "hint": "A small concrete change beats a big abstract one."},
    {"say": "Land it. End somewhere slightly forward-looking, but don't promise "
            "to change the world.",
     "hint": "The last line should feel inevitable, not tacked on."},
    {"say": "Now read it out loud. Every sentence you stumble on is a sentence "
            "to rewrite. That's the whole editing trick.",
     "hint": "Out loud. Genuinely."},
]

DONE = {"say": "That's a draft. Leave it overnight before you touch it again — "
               "you'll see it much more clearly tomorrow.",
        "hint": "Drafts are supposed to be bad. That's what makes them drafts."}


# ====================================================================
# asking
# ====================================================================

TEMPLATES = {
    "teacher": {
        "title": "Asking a teacher",
        "when": "Ask at least a month before your first deadline. Teachers "
                "write dozens of these and the good ones fill up early.",
        "how": "In person if you possibly can, then follow up by email so they "
               "have the details in writing. Asking face to face is the whole "
               "difference between a warm letter and a generic one.",
        "body": (
            "Hi {teacher},\n\n"
            "I'm applying to college this year and I was hoping you might be "
            "willing to write me a letter of recommendation.\n\n"
            "I asked you because {reason}. If you're able to, my first deadline "
            "is {deadline}.\n\n"
            "I can send you anything that would help — a list of where I'm "
            "applying, my draft essay, or a reminder of what I worked on in "
            "your class.\n\n"
            "Completely understand if you're already writing too many.\n\n"
            "Thank you,\n{name}"
        ),
        "reason_hint": "…your class was the one where I actually changed how I "
                       "think about the subject — say the real reason, and be "
                       "specific about a moment they will remember.",
    },
    "guidance": {
        "title": "Asking your counsellor",
        "when": "Early in the autumn term. Counsellors write for the whole year "
                "group, so the ones who ask first get the most attention.",
        "how": "Book a slot rather than catching them in a corridor. Bring your "
               "list of colleges — it makes the meeting useful for both of you.",
        "body": (
            "Hi {teacher},\n\n"
            "Could I book a short meeting about my college applications? I'd "
            "like to go through my list and ask about the counsellor "
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
    "It has been {days} days. A short, friendly follow-up is completely normal "
    "and teachers expect it — they are not ignoring you, they have forty of "
    "these. One line is enough: “Just checking you still have room to write "
    "for me — happy to send anything that helps.”"
)

# What each status means and what to do next.
STATUS_HELP = {
    "not_asked": "Nothing has happened yet. Pick a moment and ask them in "
                 "person — it takes about thirty seconds and it is the single "
                 "highest-value thing on this screen.",
    "asked": "You have asked. Give them a week or two before you follow up.",
    "agreed": "They said yes. Send them your essay draft and your college list "
              "so the letter can be specific rather than generic.",
    "submitted": "The letter is in. Send a thank-you note — it costs nothing "
                 "and these are the people who will write for you again.",
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
     "blurb": "Three finished sessions. This is where it starts to feel normal.",
     "requires": {"sessions": 3}, "icon": "🍃", "xp": 30},

    {"key": "all_three", "title": "All three techniques",
     "blurb": "Try box breathing, 4-7-8 and 4-6-8 at least once each.",
     "requires": {"patterns": 3}, "icon": "🧭", "xp": 50},

    {"key": "ten_minutes", "title": "Ten minutes total",
     "blurb": "Ten minutes of sitting, added up however you like.",
     "requires": {"minutes": 10}, "icon": "⏳", "xp": 40},

    {"key": "three_day", "title": "Three days running",
     "blurb": "Sit three days in a row. Short counts.",
     "requires": {"streak": 3}, "icon": "🔥", "xp": 60},

    {"key": "long_sit", "title": "A long one",
     "blurb": "Finish a full ten-minute session in one go.",
     "requires": {"minutes": 10, "sessions": 4}, "icon": "🕊️", "xp": 70},

    {"key": "thirty_total", "title": "Half an hour",
     "blurb": "Thirty minutes of sitting in total.",
     "requires": {"minutes": 30}, "icon": "🌊", "xp": 80},

    {"key": "week_streak", "title": "A full week",
     "blurb": "Seven days in a row. This is the one that changes things.",
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
