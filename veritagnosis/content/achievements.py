"""
Checkpoints for the whole app, not just meditation.

Same idea as the meditation roadmap and the same reason for living in content/
rather than in the database: these are identical for every student, so only the
*reaching* of one is stored per user. The list can be rewritten, reordered or
extended and nothing needs migrating.

What makes one of these good, and what the list is trying to avoid:

  - Reward the work, not the app. "Opened the essay screen" is a participation
    trophy and students see straight through it. "Got a draft past 300 words"
    is a thing they actually did.
  - The first ones have to be reachable in the first sitting, or the whole
    board reads as locked and nobody comes back to it.
  - Nothing rewards volume for its own sake. There is no achievement for
    adding twenty colleges to a list, because adding twenty colleges to a list
    is not progress — it is avoidance, and the app should not applaud it.
  - The largest rewards are for the things that are genuinely hard and
    genuinely matter: asking a teacher in person, finishing a real draft,
    submitting an application.

`requires` is checked against the stats dict built by
services/achievements.gather(). Adding an achievement means adding one entry
here and nothing else.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Categories, in the order they appear on screen.
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("start", "Getting going"),
    ("writing", "Writing"),
    ("applying", "Applying"),
    ("people", "Asking people"),
    ("calm", "Keeping steady"),
    ("money", "Paying for it"),
]

# stat keys available to `requires` — see services/achievements.gather():
#   essays            drafts started
#   essay_words       total words written across all drafts
#   essay_best        best coach score on any draft
#   essay_polished    drafts scoring 70 or better
#   essay_finished    drafts marked done
#   schools           colleges on the list
#   schools_started   colleges past the "just listed" stage
#   schools_ready     colleges at 80% or more
#   schools_submitted colleges actually sent
#   deadlines         colleges with a deadline recorded
#   recs_asked        teachers asked
#   recs_agreed       teachers who said yes
#   recs_submitted    letters sent
#   med_sessions      finished breathing sessions
#   med_minutes       total minutes sat
#   med_streak        current day streak
#   avatar            1 once the character has been customised
#   level             current level
#   aid_steps         financial aid checklist steps ticked
#   scholarships      scholarships being tracked
#   scholarships_sent scholarship applications submitted
#   priced            colleges with a cost recorded
#   break_minutes     minutes spent on the game or the tap screen
#   break_sessions    finished sessions on either
ACHIEVEMENTS = [
    # ---- getting going ---------------------------------------------------
    {"key": "a_avatar", "cat": "start", "title": "Made yourself",
     "blurb": "Customise your character and save the look.",
     "requires": {"avatar": 1}, "icon": "🧑‍🎨", "xp": 20},

    {"key": "a_first_school", "cat": "start", "title": "First college",
     "blurb": "Put one college on your list. Any one. You can change it later.",
     "requires": {"schools": 1}, "icon": "🎓", "xp": 20},

    {"key": "a_first_words", "cat": "start", "title": "Blank page beaten",
     "blurb": "Write your first hundred words. The hardest hundred there are.",
     "requires": {"essay_words": 100}, "icon": "✍️", "xp": 30},

    {"key": "a_level3", "cat": "start", "title": "Level three",
     "blurb": "Reach level three.",
     "requires": {"level": 3}, "icon": "⭐", "xp": 50},

    # ---- writing ---------------------------------------------------------
    {"key": "a_draft", "cat": "writing", "title": "A real draft",
     "blurb": "Get one essay past 300 words.",
     "requires": {"essay_words": 300}, "icon": "📝", "xp": 60},

    {"key": "a_full_length", "cat": "writing", "title": "Full length",
     "blurb": "Write 650 words — the length of a Common App personal statement.",
     "requires": {"essay_words": 650}, "icon": "📄", "xp": 90},

    {"key": "a_decent", "cat": "writing", "title": "Cleaned up",
     "blurb": "Get a draft to a coach score of 70.",
     "requires": {"essay_best": 70}, "icon": "🧹", "xp": 80},

    {"key": "a_sharp", "cat": "writing", "title": "Sharp",
     "blurb": "Get a draft to a coach score of 85. This is genuinely hard.",
     "requires": {"essay_best": 85}, "icon": "💎", "xp": 150},

    {"key": "a_two_polished", "cat": "writing", "title": "Two clean drafts",
     "blurb": "Two separate essays scoring 70 or better.",
     "requires": {"essay_polished": 2}, "icon": "📚", "xp": 120},

    {"key": "a_finished", "cat": "writing", "title": "Finished one",
     "blurb": "Take an essay all the way through the coach's six steps.",
     "requires": {"essay_finished": 1}, "icon": "🏁", "xp": 100},

    {"key": "a_marathon", "cat": "writing", "title": "Two thousand words",
     "blurb": "Two thousand words written across everything you are working on.",
     "requires": {"essay_words": 2000}, "icon": "🖋️", "xp": 140},

    # ---- applying --------------------------------------------------------
    {"key": "a_balanced", "cat": "applying", "title": "A balanced list",
     "blurb": "Four colleges on your list, so you have real choices.",
     "requires": {"schools": 4}, "icon": "⚖️", "xp": 50},

    {"key": "a_dates", "cat": "applying", "title": "Dates in the diary",
     "blurb": "Record the deadline for three colleges.",
     "requires": {"deadlines": 3}, "icon": "📅", "xp": 60},

    {"key": "a_halfway", "cat": "applying", "title": "One nearly there",
     "blurb": "Get a single application to 80%.",
     "requires": {"schools_ready": 1}, "icon": "📈", "xp": 110},

    {"key": "a_submitted", "cat": "applying", "title": "Sent",
     "blurb": "Submit your first application. This is the big one.",
     "requires": {"schools_submitted": 1}, "icon": "🚀", "xp": 200},

    {"key": "a_three_sent", "cat": "applying", "title": "Three away",
     "blurb": "Three applications submitted.",
     "requires": {"schools_submitted": 3}, "icon": "🛫", "xp": 250},

    # ---- asking people ---------------------------------------------------
    {"key": "a_first_ask", "cat": "people", "title": "You asked",
     "blurb": "Ask one teacher for a letter. Asking is the hard part.",
     "requires": {"recs_asked": 1}, "icon": "🙋", "xp": 70},

    {"key": "a_first_yes", "cat": "people", "title": "They said yes",
     "blurb": "One teacher agrees to write for you.",
     "requires": {"recs_agreed": 1}, "icon": "🤝", "xp": 90},

    {"key": "a_two_yes", "cat": "people", "title": "Two in your corner",
     "blurb": "Two teachers have agreed. Most colleges want two.",
     "requires": {"recs_agreed": 2}, "icon": "👥", "xp": 130},

    {"key": "a_letters_in", "cat": "people", "title": "Letters in",
     "blurb": "Two letters actually sent.",
     "requires": {"recs_submitted": 2}, "icon": "📮", "xp": 160},

    # ---- keeping steady --------------------------------------------------
    {"key": "a_first_calm", "cat": "calm", "title": "One breath",
     "blurb": "Finish one breathing session.",
     "requires": {"med_sessions": 1}, "icon": "🌱", "xp": 20},

    {"key": "a_calm_habit", "cat": "calm", "title": "Three days steady",
     "blurb": "Breathe three days in a row.",
     "requires": {"med_streak": 3}, "icon": "🔥", "xp": 70},

    {"key": "a_calm_hour", "cat": "calm", "title": "An hour of quiet",
     "blurb": "Sixty minutes of breathing, added up however you like.",
     "requires": {"med_minutes": 60}, "icon": "🕊️", "xp": 140},

    {"key": "a_first_break", "cat": "calm", "title": "You stopped",
     "blurb": "Finish one session on Graze. Stopping on purpose is a "
              "skill, and it is the one nobody teaches.",
     "requires": {"break_sessions": 1}, "icon": "🫧", "xp": 30},

    {"key": "a_break_hour", "cat": "calm", "title": "An hour off",
     "blurb": "Sixty minutes on Graze, added up however you like.",
     "requires": {"break_minutes": 60}, "icon": "🛸", "xp": 120},

    # ---- paying for it ---------------------------------------------------
    {"key": "a_aid_start", "cat": "money", "title": "Opened the envelope",
     "blurb": "Tick your first step on the financial aid checklist.",
     "requires": {"aid_steps": 1}, "icon": "📬", "xp": 30},

    {"key": "a_npc", "cat": "money", "title": "Knew the real price",
     "blurb": "Record what three colleges would actually cost you. The "
              "sticker price is almost never the number.",
     "requires": {"priced": 3}, "icon": "🔍", "xp": 90},

    {"key": "a_forms", "cat": "money", "title": "Paperwork done",
     "blurb": "Half the financial aid checklist ticked off.",
     "requires": {"aid_steps": 5}, "icon": "🗂️", "xp": 130},

    {"key": "a_scholar_five", "cat": "money", "title": "Five in the net",
     "blurb": "Track five scholarships. Local ones have a fraction of the "
              "applicants for the same work.",
     "requires": {"scholarships": 5}, "icon": "🎣", "xp": 110},

    {"key": "a_scholar_sent", "cat": "money", "title": "Actually applied",
     "blurb": "Submit three scholarship applications.",
     "requires": {"scholarships_sent": 3}, "icon": "📨", "xp": 180},

    # ---- the one that needs everything ----------------------------------
    {"key": "a_whole_thing", "cat": "applying", "title": "The whole thing",
     "blurb": "An essay past 650 words, two teachers who said yes, and an "
              "application sent. That is the entire process, done.",
     "requires": {"essay_words": 650, "recs_agreed": 2, "schools_submitted": 1},
     "icon": "👑", "xp": 400},
]

BY_KEY = {a["key"]: a for a in ACHIEVEMENTS}
TOTAL_XP = sum(a["xp"] for a in ACHIEVEMENTS)


def unlocked(stats: dict) -> list[str]:
    """Keys of every achievement the stats satisfy."""
    return [a["key"] for a in ACHIEVEMENTS
            if all(stats.get(k, 0) >= v for k, v in a["requires"].items())]


def progress_to(achievement: dict, stats: dict) -> int:
    """0-100 toward one, using whichever requirement is furthest behind — so a
    bar never shows 90% when one of two conditions has not been touched."""
    if not achievement:
        return 100
    ratios = [min(1.0, stats.get(k, 0) / v)
              for k, v in achievement["requires"].items() if v]
    return int(100 * min(ratios)) if ratios else 0


def next_up(stats: dict, count: int = 3) -> list[dict]:
    """The closest few that are not yet reached — what to point at."""
    done = set(unlocked(stats))
    todo = [a for a in ACHIEVEMENTS if a["key"] not in done]
    todo.sort(key=lambda a: (-progress_to(a, stats), a["xp"]))
    return todo[:count]


if __name__ == "__main__":
    demo = {"avatar": 1, "schools": 2, "essay_words": 420, "essay_best": 58,
            "recs_asked": 1, "med_sessions": 2, "level": 2}
    got = unlocked(demo)
    print(f"{len(got)} of {len(ACHIEVEMENTS)} unlocked, "
          f"{sum(BY_KEY[k]['xp'] for k in got)} of {TOTAL_XP} xp")
    for a in next_up(demo):
        print(f"  next: {a['title']:22s} {progress_to(a, demo):3d}%  +{a['xp']}xp")
