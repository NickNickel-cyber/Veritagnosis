
from __future__ import annotations

import dataclasses
import math
import re
from collections import Counter

# The finding


@dataclasses.dataclass
class Finding:
    """One specific problem, in one specific place."""

    start: int          # character offset into the draft
    end: int            # one past the last character
    kind: str           # machine name, used for grouping and colour
    label: str          # short human name, shown on the chip
    why: str            # plain-English reason, shown when expanded
    original: str       # the text as written
    fix: str            # what to replace it with ("" means delete)
    severity: str = "med"     # "high" | "med" | "low"
    auto: bool = False        # safe to apply without a human looking?

    @property
    def has_fix(self) -> bool:
        return self.fix != self.original


# Order matters when two rules land on the same words: the earlier kind wins.
SEVERITY_RANK = {"high": 0, "med": 1, "low": 2}


# Splitting text up

_ABBREV = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "mt", "vs",
           "etc", "eg", "ie", "approx", "dept", "univ", "inc", "co", "u.s",
           "a.m", "p.m", "ph.d", "b.a", "m.a"}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def sentences(text: str) -> list[tuple[int, int, str]]:
    """Split into (start, end, text). Offsets are into the original string, so
    a finding inside a sentence can still point at the real draft."""
    text = text or ""
    out: list[tuple[int, int, str]] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ".!?":
            # Walk over "?!" and "..." so they count as one ending.
            j = i
            while j + 1 < n and text[j + 1] in ".!?":
                j += 1
            after = text[j + 1:j + 3]
            before = text[max(0, i - 12):i].lower()
            last = re.split(r"[\s(]", before)[-1] if before else ""
            is_abbrev = last.rstrip(".") in _ABBREV
            # A single capital letter then a period is an initial: "J. K."
            is_initial = bool(re.search(r"\b[A-Za-z]$", text[:i]))and (i - start) < 3
            ends = (not is_abbrev and not is_initial
                    and (j + 1 >= n or after[:1] in {" ", "\n", "\t", "", '"', "'", ")"}))
            if ends:
                seg = text[start:j + 1]
                if seg.strip():
                    out.append((start + len(seg) - len(seg.lstrip()),
                                j + 1, seg.strip()))
                start = j + 1
            i = j
        elif ch == "\n" and text[start:i].strip():
            # A hard line break also ends a thought, even with no period —
            # students write that way and the rhythm maths should reflect it.
            nxt = text[i + 1:i + 2]
            if nxt == "\n":
                seg = text[start:i]
                if seg.strip():
                    out.append((start + len(seg) - len(seg.lstrip()), i, seg.strip()))
                start = i + 1
        i += 1
    tail = text[start:]
    if tail.strip():
        out.append((start + len(tail) - len(tail.lstrip()), len(text), tail.strip()))
    return out


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]


# Words that add length and subtract force. Deleting them never changes the
# meaning of a sentence, which is what makes them safe to auto-fix.
FILLER = {
    "very": "Almost always weaker than the stronger word it is propping up. "
            "'Very tired' is 'exhausted'.",
    "really": ("Same problem as 'very'. It asks the reader to take your word for it "
               "instead of showing it."),
    "quite": "Hedges the sentence without adding information.",
    "extremely": "An intensifier doing the work a precise word should do.",
    "incredibly": "An intensifier doing the work a precise word should do.",
    "actually": "Usually leftover from speech. Cut it and the sentence is fine.",
    "basically": "Signals you are about to simplify. Just say the simple thing.",
    "literally": "Almost never literal, and readers notice.",
    "definitely": "If it needs saying, say it plainly; the word does not add "
                  "certainty.",
    "totally": "Conversational filler.",
    "simply": "Often condescending, always removable.",
    "certainly": "Adds no information the sentence did not already carry.",
    "truly": "Adds no information the sentence did not already carry.",
    "absolutely": "An intensifier standing in for a stronger word.",
    "somewhat": "Weakens the claim without qualifying it usefully.",
    "rather": "Weakens the claim without qualifying it usefully.",
    "pretty": "A casual hedge. 'Pretty good' tells the reader nothing.",
    "kind of": "Hedge. Either you mean it or you do not.",
    "sort of": "Hedge. Either you mean it or you do not.",
    "just": "Nine times out of ten it is filler. Read the sentence without it.",
    "in fact": "Rarely earns its place at the front of a sentence.",
    "of course": "Tells the reader they should already know this, which is "
                 "either untrue or unnecessary.",
    "needless to say": "If it is needless, do not say it.",
    "it should be noted that": "Note it, then.",
}

VAGUE_QUANTITY = {
    "a lot of": ("Vague. A number is more convincing. 'A lot of meetings' could be "
                 "four or forty, and readers assume four."),
    "lots of": "Vague quantity. Give the number.",
    "many times": "How many? A specific count is more convincing.",
    "several times": "How many? A specific count is more convincing.",
    "a few times": "How many? A specific count is more convincing.",
    "some of the": "Which ones? Naming them is stronger.",
    "various": "Names beat 'various' every time.",
    "numerous": "Vague, and slightly formal. Give the number.",
    "countless": "Almost always an exaggeration the reader discounts.",
    "tons of": "Vague quantity, and conversational.",
}

HEDGES = {
    "i think": "You are the writer; the reader already knows it is your view. "
               "Stating it flat is more convincing.",
    "i believe": ("Same as 'I think'. It puts distance between you and what you're "
                  "saying."),
    "i feel like": "Softens the sentence to nothing. Say the thing.",
    "i guess": "Reads as if you do not trust your own point.",
    "in my opinion": "The essay is your opinion by definition.",
    "i would say that": "Say it.",
    "it seems like": "Either it is or it is not; you were there.",
    "i suppose": "Reads as if you do not trust your own point.",
    "maybe": "In a personal statement, uncertainty about your own life reads "
             "as evasion.",
    "perhaps": "In a personal statement, uncertainty about your own life reads "
               "as evasion.",
    "probably": "Vague where you could be specific.",
}

# Long ways of saying short things. High confidence, so these auto-fix.
WORDY = {
    "in order to": "to",
    "in order for": "for",
    "due to the fact that": "because",
    "owing to the fact that": "because",
    "despite the fact that": "although",
    "in spite of the fact that": "although",
    "the fact that": "that",
    "at this point in time": "now",
    "at the present time": "now",
    "in the event that": "if",
    "for the purpose of": "to",
    "with regard to": "about",
    "with respect to": "about",
    "in terms of": "in",
    "a large number of": "many",
    "a great deal of": "much",
    "the majority of": "most",
    "on a daily basis": "daily",
    "on a regular basis": "regularly",
    "in the near future": "soon",
    "at all times": "always",
    "has the ability to": "can",
    "have the ability to": "can",
    "is able to": "can",
    "are able to": "can",
    "was able to": "could",
    "were able to": "could",
    "made the decision to": "decided to",
    "make the decision to": "decide to",
    "came to the realization that": "realised that",
    "reached the conclusion that": "concluded that",
    "conducted an investigation of": "investigated",
    "gave consideration to": "considered",
    "provided assistance to": "helped",
    "took part in": "joined",
    "put an end to": "ended",
    "in close proximity to": "near",
    "a number of": "several",
    "each and every": "every",
    "first and foremost": "first",
    "end result": "result",
    "final outcome": "outcome",
    "past history": "history",
    "advance planning": "planning",
    "completely eliminate": "eliminate",
    "absolutely essential": "essential",
    "close proximity": "proximity",
    "unexpected surprise": "surprise",
    "free gift": "gift",
    "brief moment": "moment",
    "personal opinion": "opinion",
    "true fact": "fact",
    "revert back": "revert",
    "return back": "return",
    "repeat again": "repeat",
    "combine together": "combine",
    "join together": "join",
    "plan ahead": "plan",
    "collaborate together": "collaborate",
}

# The phrases that appear in tens of thousands of application essays every
# year. They are not wrong; they are invisible, which is worse.
CLICHES = {
    "ever since i was little": ("A lot of essays open this way. The moment you're about to describe "
                                "is more interesting than the lead-up to it."),
    "ever since i was young": "An extremely common opening. Start at the moment "
                              "itself instead.",
    "for as long as i can remember": "A very common opening. Start with the scene.",
    "from a young age": "A very common opening. Start with the scene.",
    "at the end of the day": "Filler phrase that delays the point.",
    "think outside the box": "So worn it now signals the opposite.",
    "changed my life": "Everyone says it. Show the change and let the reader "
                       "conclude it.",
    "life-changing": "Everyone says it. Show the change instead.",
    "eye-opening": "Tells the reader the effect instead of producing it.",
    "learning experience": "Nearly meaningless. Name what you learned.",
    "taught me the value of": "A very common construction. Show the moment it "
                              "landed instead.",
    "taught me a valuable lesson": "Extremely common. Name the lesson concretely.",
    "hard work pays off": "A cliché, and also not always true, which readers know.",
    "step out of my comfort zone": "Appears constantly. Describe what was "
                                   "uncomfortable and why.",
    "outside my comfort zone": "Appears constantly. Describe the discomfort.",
    "make a difference": "Vague. What difference, to whom?",
    "making a difference": "Vague. What difference, to whom?",
    "give back to the community": "One of the most common phrases in the genre.",
    "helping people": "Almost every applicant wants to help people. What did "
                      "you actually do?",
    "passion for": ("One of the most overused words in application essays. Show what you "
                    "did that proves it."),
    "i am passionate about": "Show the passion through what you did with your "
                             "time; naming it convinces nobody.",
    "in today's society": "A dated essay-opening formula.",
    "in today's world": "A dated essay-opening formula.",
    "since the beginning of time": "Almost never accurate and always a cliché.",
    "throughout history": "Vague scale-setting that delays your actual point.",
    "the dictionary defines": "The most recognizable weak opening there is.",
    "webster's dictionary": "The most recognizable weak opening there is.",
    "little did i know": "A stock phrase that signals a stock twist.",
    "took a deep breath": "Shows up in a lot of essays about nerves.",
    "my heart was racing": "A stock way of writing nerves.",
    "butterflies in my stomach": "A stock way of writing nerves.",
    "against all odds": "Cliché, and it overclaims.",
    "blood sweat and tears": "Cliché.",
    "last but not least": "Cliché, and usually unnecessary.",
    "words cannot describe": "Then the sentence is doing no work.",
    "it goes without saying": "Then do not say it.",
    "a whole new world": "Cliché.",
    "opened my eyes": "Very common. Show what you saw.",
    "role model": "Vague. What specifically did you copy from them?",
    "well-rounded": "A word from the brochure, not from your life.",
}

# Abstract self-description. The fix is never a word swap; it is "replace this
# claim with the evidence for it", so these explain rather than auto-fix.
TELLING = [
    (r"\bi (?:am|'m) (?:a |an |very |really |extremely )?"
     r"(hard[- ]?working|dedicated|passionate|determined|motivated|driven|"
     r"curious|creative|compassionate|empathetic|resilient|responsible|"
     r"outgoing|ambitious|diligent|persistent)\b",
     "This is the classic 'telling, not showing'. A reader believes a story "
     "about you staying until the lab closed; they do not believe the word "
     "'dedicated'. Delete the claim and keep the evidence."),
    (r"\bi have always (?:been|had|loved|wanted|known)\b",
     "'Always' covers your whole life in four words and proves nothing. One "
     "dated, specific instance does more."),
    (r"\bi learned (?:that|a lot|so much|the importance)\b",
     "Naming the lesson is the weakest way to deliver it. Show the moment you "
     "learned it and trust the reader to draw the conclusion."),
    (r"\bthis experience (?:taught|showed|made) me\b",
     "The 'and that's what I learned' ending is the most predictable close in "
     "the genre. End on the concrete image instead."),
    (r"\bi realized that\b",
     "Often a signal that the insight is being announced rather than earned."),
    (r"\bmade me who i am (?:today)?\b",
     "A stock closing line. The essay should have already shown this."),
]

# Word pairs people mix up. Only flagged where the grammar makes it clear, so
# these can be trusted enough to auto-fix.
CONFUSABLES = [
    (r"\bits\s+(a|an|the|not|been|going|too|very|so)\b", "it's",
     "'Its' shows possession (its color). Before a word like this you need "
     "'it's', short for 'it is'.", 1),
    (r"\bit's\s+(colou?r|name|shape|size|value|purpose|own|edge|surface)\b",
     "its", "'It's' means 'it is'. Possession takes 'its' with no apostrophe.", 1),
    (r"\btheir\s+(is|are|was|were)\b", "there",
     "'Their' shows possession. The word that starts a statement about "
     "existence is 'there'.", 1),
    (r"\bthere\s+(own|house|car|family|parents|friends|teacher|dog|room|"
     r"names?|ideas?)\b", "their",
     "'There' is a place. Possession takes 'their'.", 1),
    (r"\byour\s+(going|coming|right|wrong|welcome|not|the best|amazing)\b",
     "you're", "'Your' shows possession. 'You're' is short for 'you are'.", 1),
    (r"\byou're\s+(car|house|family|friend|book|idea|turn|name|fault)\b",
     "your", "'You're' means 'you are'. Possession takes 'your'.", 1),
    (r"\b(more|less|better|worse|rather|other|greater|smaller|older|younger|"
     r"bigger|faster)\s+then\b", None,
     "Comparisons use 'than'. 'Then' is about time.", 2),
    (r"\bshould of\b", "should have",
     "'Should of' is a mishearing of 'should've'.", 0),
    (r"\bcould of\b", "could have", "'Could of' is a mishearing of 'could've'.", 0),
    (r"\bwould of\b", "would have", "'Would of' is a mishearing of 'would've'.", 0),
    (r"\bmust of\b", "must have", "'Must of' is a mishearing of 'must've'.", 0),
    (r"\balot\b", "a lot", "'A lot' is two words.", 0),
    (r"\bdefinately\b", "definitely", "Spelling.", 0),
    (r"\bseperate\b", "separate", "Spelling.", 0),
    (r"\brecieve\b", "receive", "Spelling: i before e, except after c.", 0),
    (r"\boccured\b", "occurred", "Spelling: double the r.", 0),
    (r"\buntill\b", "until", "Spelling: one l.", 0),
    (r"\bteh\b", "the", "Typo.", 0),
    (r"\bthier\b", "their", "Spelling.", 0),
    (r"\bbelive\b", "believe", "Spelling.", 0),
    (r"\bacheive\b", "achieve", "Spelling.", 0),
    (r"\bbeleive\b", "believe", "Spelling.", 0),
    (r"\bwich\b", "which", "Spelling.", 0),
    (r"\bthankyou\b", "thank you", "Two words.", 0),
    (r"\beveryday\s+(i|we|he|she|they|you)\b", None,
     "'Everyday' is an adjective (an everyday problem). For 'each day' use "
     "two words: 'every day'.", 5),
    (r"\bloose\s+(the|my|his|her|their|a|an|it)\b", "lose",
     "'Loose' is the opposite of tight. To not win is 'lose'.", 1),
]

# Verbs that carry no picture. Paired with the question that unlocks a better one.
WEAK_VERBS = {
    "got": "One of the least specific verbs in English. What actually happened?",
    "get": "One of the least specific verbs in English. What actually happened?",
    "went": "Went how? Walked, ran, drove, was dragged?",
    "did": "Did what, exactly?",
    "made": "Made how? Built, cooked, forced, invented?",
    "put": "Put how? Dropped, placed, shoved, arranged?",
    "took": "Took how? Grabbed, carried, stole, accepted?",
    "had": "Often a placeholder for a more exact verb.",
    "said": "Usually fine, but check whether the moment needs more.",
    "nice": "Says nothing. What was nice about it?",
    "good": "Says nothing on its own.",
    "bad": "Says nothing on its own.",
    "big": "Compared to what?",
    "small": "Compared to what?",
    "stuff": "Name the thing.",
    "things": "Name the things.",
    "interesting": ("The classic empty adjective. It asks the reader to be interested "
                    "without giving them a reason."),
    "amazing": "An empty intensifier.",
    "awesome": "An empty intensifier.",
    "great": "An empty intensifier.",
}

# Openings that push the real subject of the sentence to the back.
EXPLETIVES = [
    (r"\bthere (is|are|was|were)\b",
     "'There is' delays the actual subject. Find the noun doing something and "
     "start with it."),
    (r"\bit (is|was) (important|clear|obvious|interesting|necessary) that\b",
     "This construction announces significance instead of demonstrating it."),
]

# Words that suggest the writing is doing its job — used for the encouragement
# half of the report, because a tool that only ever criticises stops being read.
SENSORY = {
    "smell", "smelled", "taste", "tasted", "sour", "bitter", "sweet", "salt",
    "cold", "freezing", "damp", "humid", "sticky", "rough", "smooth", "loud",
    "quiet", "silence", "hum", "buzz", "creak", "rattle", "echo", "glare",
    "shadow", "flicker", "dust", "rain", "wind", "heat", "burn", "ache",
    "breath", "sweat", "grip", "weight", "thud", "whisper", "crackle", "grain",
}


# Helpers

def _match_case(original: str, replacement: str) -> str:
    """Keep the shape of the original word so a fix does not break a sentence
    start. 'In order to' -> 'To', not 'to'."""
    if not original or not replacement:
        return replacement
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _delete_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen a deletion to swallow one adjoining space, so removing a word does
    not leave two spaces behind."""
    if end < len(text) and text[end] == " ":
        return start, end + 1
    if start > 0 and text[start - 1] == " ":
        return start - 1, end
    return start, end


def _iter(pattern: str, text: str):
    return re.finditer(pattern, text, re.IGNORECASE)


# The checks

def _check_filler(text: str) -> list[Finding]:
    out = []
    for word, why in FILLER.items():
        pat = r"\b" + re.escape(word).replace(r"\ ", r"\s+") + r"\b"
        for m in _iter(pat, text):
            s, e = _delete_span(text, m.start(), m.end())
            out.append(Finding(
                start=s, end=e, kind="filler", label="Filler word",
                why=f"“{m.group(0)}” — {why}",
                original=text[s:e], fix="", severity="med", auto=True))
    return out


def _check_vague_quantity(text: str) -> list[Finding]:
    out = []
    for phrase, why in VAGUE_QUANTITY.items():
        pat = r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b"
        for m in _iter(pat, text):
            out.append(Finding(
                start=m.start(), end=m.end(), kind="vague_qty",
                label="How many?", why=f"“{m.group(0)}” — {why}",
                original=m.group(0), fix=m.group(0), severity="med", auto=False))
    return out


def _check_hedges(text: str) -> list[Finding]:
    out = []
    for phrase, why in HEDGES.items():
        pat = r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\s*,?\s*"
        for m in _iter(pat, text):
            out.append(Finding(
                start=m.start(), end=m.end(), kind="hedge", label="Hedging",
                why=f"“{m.group(0).strip()}” — {why}",
                original=m.group(0), fix="", severity="high", auto=False))
    return out


def _check_wordy(text: str) -> list[Finding]:
    out = []
    for phrase, short in WORDY.items():
        pat = r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b"
        for m in _iter(pat, text):
            out.append(Finding(
                start=m.start(), end=m.end(), kind="wordy", label="Say it shorter",
                why=f"“{m.group(0)}” is {len(m.group(0).split())} words doing "
                    f"the job of {len(short.split())}. Word limits are real; "
                    f"spend them on your story.",
                original=m.group(0), fix=_match_case(m.group(0), short),
                severity="med", auto=True))
    return out


def _check_cliches(text: str) -> list[Finding]:
    out = []
    for phrase, why in CLICHES.items():
        pat = r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b"
        for m in _iter(pat, text):
            out.append(Finding(
                start=m.start(), end=m.end(), kind="cliche", label="Overused phrase",
                why=f"“{m.group(0)}” — {why}",
                original=m.group(0), fix=m.group(0), severity="high", auto=False))
    return out


def _check_telling(text: str) -> list[Finding]:
    out = []
    for pat, why in TELLING:
        for m in _iter(pat, text):
            out.append(Finding(
                start=m.start(), end=m.end(), kind="telling",
                label="Telling, not showing", why=why,
                original=m.group(0), fix=m.group(0), severity="high", auto=False))
    return out


def _check_confusables(text: str) -> list[Finding]:
    out = []
    for pat, repl, why, group in CONFUSABLES:
        for m in _iter(pat, text):
            if repl is None:
                # The correction targets one captured word inside the match —
                # "more then" becomes "more than", leaving "more" alone.
                if group == 2:                    # then -> than
                    idx = m.group(0).lower().rfind("then")
                    s = m.start() + idx
                    out.append(Finding(
                        start=s, end=s + 4, kind="confusable", label="Wrong word",
                        why=why, original=text[s:s + 4],
                        fix=_match_case(text[s:s + 4], "than"),
                        severity="high", auto=True))
                elif group == 5:                  # everyday -> every day
                    idx = m.group(0).lower().find("everyday")
                    s = m.start() + idx
                    out.append(Finding(
                        start=s, end=s + 8, kind="confusable", label="Wrong word",
                        why=why, original=text[s:s + 8],
                        fix=_match_case(text[s:s + 8], "every day"),
                        severity="high", auto=True))
                continue

            # Replace only the first token; whatever the pattern captured after
            # it is kept exactly as written.
            first = re.match(r"\S+", m.group(0)).group(0)
            out.append(Finding(
                start=m.start(), end=m.start() + len(first),
                kind="confusable", label="Wrong word", why=why,
                original=first, fix=_match_case(first, repl),
                severity="high", auto=True))
    return out


_PARTICIPLES = (
    r"\w+ed|known|made|given|taken|seen|done|written|built|held|told|shown|"
    r"found|kept|left|brought|thought|caught|taught|sent|spent|meant|met|paid|"
    r"chosen|driven|eaten|fallen|forgotten|gotten|grown|hidden|risen|spoken|"
    r"stolen|thrown|worn|drawn|flown|torn|sworn|beaten|broken|frozen|hurt|put|"
    r"set|cut|read|run|won|lost|sold"
)


def _check_passive(text: str) -> list[Finding]:
    out = []
    skip = {"was tired", "were tired", "was excited", "were excited",
            "was scared", "were scared", "was worried", "were worried",
            "was interested", "were interested", "was surprised",
            "were surprised", "was confused", "were confused",
            "was determined", "were determined", "was involved",
            "were involved", "was used", "were used"}
    pat = rf"\b(am|is|are|was|were|been|being|be)\s+((?:{_PARTICIPLES}))\b"
    for m in _iter(pat, text):
        if m.group(0).lower() in skip:
            continue
        out.append(Finding(
            start=m.start(), end=m.end(), kind="passive", label="Passive voice",
            why=f"“{m.group(0)}” hides who did it. Passive voice isn't wrong, "
                f"but a personal essay is about you doing things. “The team was "
                f"led by me” should be “I led the team.”",
            original=m.group(0), fix=m.group(0), severity="med", auto=False))
    return out


def _check_adverbs(text: str) -> list[Finding]:
    out = []
    keep = {"only", "family", "early", "likely", "lonely", "friendly", "ugly",
            "daily", "weekly", "monthly", "yearly", "holy", "reply", "supply",
            "apply", "rely", "july", "italy", "silly", "lovely", "gently"}
    hits = [m for m in re.finditer(r"\b(\w{4,}ly)\b", text, re.IGNORECASE)
            if m.group(1).lower() not in keep]
    if len(hits) < 3:
        return out
    for m in hits:
        s, e = _delete_span(text, m.start(), m.end())
        out.append(Finding(
            start=s, end=e, kind="adverb", label="-ly adverb",
            why=f"You use {len(hits)} '-ly' adverbs in this draft, including "
                f"“{m.group(1)}.” Most of them prop up a verb that should do the "
                f"work itself: 'walked quickly' is 'hurried'.",
            original=text[s:e], fix="", severity="low", auto=False))
    return out


def _check_expletives(text: str) -> list[Finding]:
    out = []
    for pat, why in EXPLETIVES:
        for m in _iter(pat, text):
            out.append(Finding(
                start=m.start(), end=m.end(), kind="expletive",
                label="Slow opening", why=f"“{m.group(0)}” — {why}",
                original=m.group(0), fix=m.group(0), severity="med", auto=False))
    return out


def _check_weak_words(text: str) -> list[Finding]:
    out = []
    for word, why in WEAK_VERBS.items():
        for m in _iter(r"\b" + word + r"\b", text):
            out.append(Finding(
                start=m.start(), end=m.end(), kind="weak", label="Vague word",
                why=f"“{m.group(0)}” — {why}",
                original=m.group(0), fix=m.group(0), severity="low", auto=False))
    return out


def _check_spacing(text: str) -> list[Finding]:
    out = []
    for m in re.finditer(r"  +", text):
        out.append(Finding(
            start=m.start(), end=m.end(), kind="spacing", label="Double space",
            why="Two spaces where one belongs.", original=m.group(0),
            fix=" ", severity="low", auto=True))
    for m in re.finditer(r"\s+([,.;:!?])", text):
        out.append(Finding(
            start=m.start(), end=m.end(), kind="spacing", label="Stray space",
            why="A space before punctuation.", original=m.group(0),
            fix=m.group(1), severity="low", auto=True))
    for m in re.finditer(r"([,.;:!?])([A-Za-z])", text):
        if m.group(1) == "." and re.match(r"\d", m.group(2)):
            continue
        out.append(Finding(
            start=m.start(), end=m.end(), kind="spacing", label="Missing space",
            why="Punctuation needs a space after it.", original=m.group(0),
            fix=f"{m.group(1)} {m.group(2)}", severity="low", auto=True))
    return out


def _check_long_sentences(text: str) -> list[Finding]:
    out = []
    for s, e, seg in sentences(text):
        n = len(words(seg))
        if n > 34:
            out.append(Finding(
                start=s, end=e, kind="long", label=f"{n}-word sentence",
                why=f"This sentence runs {n} words. Anything past about 30 makes "
                    f"the reader hold too much at once, and they lose the start by "
                    f"the time they reach the end. Find the natural break and split "
                    f"it in two.",
                original=seg, fix=seg, severity="high", auto=False))
    return out


def _check_openers(text: str) -> list[Finding]:
    """Three or more sentences in a row opening on the same word."""
    out = []
    segs = sentences(text)
    run: list[tuple[int, int, str]] = []
    prev = None
    for s, e, seg in segs + [(0, 0, "")]:
        first = (words(seg)[:1] or [""])[0].lower()
        if first and first == prev:
            run.append((s, e, seg))
        else:
            if len(run) >= 3:
                s0, e0, seg0 = run[0]
                out.append(Finding(
                    start=s0, end=run[-1][1], kind="rhythm",
                    label=f"{len(run)} sentences start with “{prev}”",
                    why=f"{len(run)} sentences in a row begin with “{prev}”. The "
                        f"reader notices the repetition even if they can't say "
                        f"why, and it flattens the passage. Try starting one with "
                        f"a time, a place, or the object instead of the subject.",
                    original=seg0, fix=seg0, severity="high", auto=False))
            run = [(s, e, seg)] if first else []
        prev = first
    return out


def _check_echo(text: str) -> list[Finding]:
    """A distinctive word repeated close to itself."""
    common = {
        "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at",
        "for", "with", "as", "by", "from", "that", "this", "it", "is", "was",
        "were", "are", "be", "been", "i", "me", "my", "we", "our", "you",
        "he", "she", "they", "them", "his", "her", "their", "not", "no",
        "so", "if", "than", "then", "there", "here", "what", "when", "who",
        "would", "could", "should", "will", "can", "had", "have", "has", "do",
        "did", "one", "all", "up", "out", "about", "into", "over", "just",
        "like", "time", "more", "most", "very", "also", "how", "him", "us",
    }
    out = []
    toks = [(m.start(), m.end(), m.group(0).lower())
            for m in _WORD_RE.finditer(text)]
    last: dict[str, tuple[int, int, int]] = {}
    for i, (s, e, w) in enumerate(toks):
        if len(w) < 5 or w in common:
            continue
        if w in last:
            j, ls, le = last[w]
            if i - j <= 22:
                out.append(Finding(
                    start=s, end=e, kind="echo", label="Repeated word",
                    why=f"“{text[s:e]}” appears twice within {i - j} words. "
                        f"Close repeats stand out to a reader who is skimming "
                        f"fifty essays. Use a different word, or cut one of the "
                        f"two sentences.",
                    original=text[s:e], fix=text[s:e], severity="med",
                    auto=False))
        last[w] = (i, s, e)
    return out


# Numbers

_VOWELS = "aeiouy"


def syllables(word: str) -> int:
    """Good-enough syllable count for readability. Not perfect — no small
    program is — but consistent, which is what a score needs."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    n = len(re.findall(r"[aeiouy]{1,2}", w))
    return max(1, n)


def readability(text: str) -> dict:
    ws = words(text)
    segs = sentences(text)
    if not ws or not segs:
        return {"ease": 0.0, "grade": 0.0, "avg_sentence": 0.0,
                "avg_syllables": 0.0}
    syl = sum(syllables(w) for w in ws)
    wps = len(ws) / len(segs)
    spw = syl / len(ws)
    ease = 206.835 - 1.015 * wps - 84.6 * spw
    grade = 0.39 * wps + 11.8 * spw - 15.59
    return {"ease": round(max(0.0, min(100.0, ease)), 1),
            "grade": round(max(0.0, grade), 1),
            "avg_sentence": round(wps, 1),
            "avg_syllables": round(spw, 2)}


def rhythm(text: str) -> dict:
    lens = [len(words(seg)) for _, _, seg in sentences(text)]
    if len(lens) < 3:
        return {"variety": 0, "shortest": min(lens) if lens else 0,
                "longest": max(lens) if lens else 0, "note": ""}
    mean = sum(lens) / len(lens)
    sd = math.sqrt(sum((x - mean) ** 2 for x in lens) / len(lens))
    # Coefficient of variation, scaled so a lively essay lands near 100.
    variety = int(min(100, (sd / mean) * 180)) if mean else 0
    if variety < 35:
        note = ("Your sentences are all about the same length, which makes the "
                "essay feel like a list even when the content is good. Cut one "
                "sentence down to four or five words. The contrast alone will "
                "wake the paragraph up.")
    elif variety < 55:
        note = ("Some variety, but it could swing wider. One deliberately short "
                "sentence after a long one is the cheapest way to land a point.")
    else:
        note = "Good variety. Your long and short sentences play off each other."
    return {"variety": variety, "shortest": min(lens), "longest": max(lens),
            "note": note}


def strengths(text: str, findings: list[Finding]) -> list[str]:
    out = []
    ws = [w.lower() for w in words(text)]
    if not ws:
        return out
    segs = sentences(text)

    if sum(1 for w in ws if w in SENSORY) >= 3:
        out.append(("You use concrete, physical details, which a lot of drafts are "
                    "missing."))
    if re.search(r"[“\"']\s*\w+[^\"”']{3,}[\"”']", text):
        out.append("There is dialogue in here. It breaks up the narration and "
                   "makes the scene feel witnessed.")
    if re.search(r"\b\d{1,4}\b", text):
        out.append("You use specific numbers. Specifics are the fastest way to "
                   "sound like you were actually there.")
    if len(set(ws)) / len(ws) > 0.55 and len(ws) > 80:
        out.append("Your vocabulary is varied. You're not leaning on the same "
                   "few words.")
    r = rhythm(text)
    if r["variety"] >= 55:
        out.append("Your sentence lengths vary, which keeps the writing moving.")
    if segs and len(words(segs[0][2])) <= 12:
        out.append(("You open with a short sentence. That's a strong start that pulls the "
                    "reader into the next line."))
    if not any(f.kind == "cliche" for f in findings) and len(ws) > 100:
        out.append("No stock phrases. You're writing in your own words.")
    return out[:4]


# Putting it together

CHECKS = [
    _check_confusables,      # first: highest confidence
    _check_spacing,
    _check_cliches,
    _check_telling,
    _check_hedges,
    _check_vague_quantity,
    _check_wordy,
    _check_filler,
    _check_expletives,
    _check_passive,
    _check_long_sentences,
    _check_openers,
    _check_echo,
    _check_adverbs,
    _check_weak_words,       # last: lowest confidence, most likely to be noise
]


STRUCTURAL = {"long", "rhythm"}


def _dedupe(findings: list[Finding]) -> list[Finding]:
    inline = [f for f in findings if f.kind not in STRUCTURAL]
    structural = [f for f in findings if f.kind in STRUCTURAL]

    ordered = sorted(
        inline,
        key=lambda f: (f.start, SEVERITY_RANK.get(f.severity, 1), f.end - f.start))
    kept: list[Finding] = []
    covered_end = -1
    for f in ordered:
        if f.start < covered_end:
            continue
        kept.append(f)
        covered_end = f.end

    return sorted(kept + structural, key=lambda f: (f.start, f.kind in STRUCTURAL))


def analyse(text: str) -> dict:
    """Read a draft and report on it. The single entry point."""
    text = text or ""
    findings: list[Finding] = []
    for check in CHECKS:
        try:
            findings.extend(check(text))
        except Exception:      # noqa: BLE001
            # One broken rule must never take the whole screen down mid-draft.
            continue
    findings = _dedupe(findings)

    ws = words(text)
    segs = sentences(text)
    read = readability(text)
    rhy = rhythm(text)

    counts = Counter(f.kind for f in findings)
    stats = {
        "words": len(ws),
        "sentences": len(segs),
        "paragraphs": len(paragraphs(text)),
        "characters": len(text),
        "unique_ratio": round(len(set(w.lower() for w in ws)) / len(ws), 2)
                        if ws else 0.0,
        "reading_seconds": int(len(ws) / 238 * 60) if ws else 0,
        **read,
        **{f"rhythm_{k}": v for k, v in rhy.items()},
    }

    smap = story_map(text)
    detail = score_detail(text, findings, smap)

    return {
        "findings": findings,
        "stats": stats,
        "counts": dict(counts),
        "score": detail["score"],
        "detail": detail,
        "story": smap,
        "strengths": strengths(text, findings),
        "rhythm_note": rhy["note"],
        "grade_note": _grade_note(read),
    }


def _grade_note(read: dict) -> str:
    g = read["grade"]
    if not g:
        return ""
    if g < 6:
        return (f"Reading level: grade {g:.0f}. Very plain, which is usually "
                f"good. Just make sure you're not oversimplifying your ideas.")
    if g <= 10:
        return (f"Reading level: grade {g:.0f}. That's a good level for a "
                f"personal essay: clear without sounding young.")
    if g <= 13:
        return (f"Reading level: grade {g:.0f}. Slightly formal. Fine, but read "
                f"it aloud and check it still sounds like you.")
    return (f"Reading level: grade {g:.0f}. This reads more like an academic "
            f"paper than a personal statement. Long words and long sentences "
            f"are hiding your voice, so shorten both.")


WORDS_NO_SCORE = 60        # under this there is no score at all
WORDS_PROVISIONAL = 175    # under this the score is shown as provisional
WORDS_FULL = 325           # here every dimension has enough text to read


_STORY_CUES: dict[str, str] = {
    "situation": r"\b(?:when i was|back when|last (?:summer|winter|spring|fall|autumn|year|month)|"
                 r"growing up|one (?:day|night|morning|afternoon|evening|summer|winter)|"
                 r"the (?:first|last) time|every (?:morning|night|day|week|saturday|sunday)|"
                 r"at (?:\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)|dawn|dusk|midnight|noon)|"
                 r"in (?:the )?(?:kitchen|garage|basement|gym|library|hallway|car|classroom|hospital|"
                 r"clinic|shop|field|dark)|room \d+|after school|"
                 r"in (?:ninth|tenth|eleventh|twelfth|\d{1,2}th) grade|"
                 r"every (?:monday|tuesday|wednesday|thursday|friday)|"
                 r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b|"
                 r"my (?:mother|father|mom|dad|grandmother|grandfather|"
                 r"grandma|grandpa|brother|sister|coach|teacher|neighbour|neighbor|uncle|aunt))\b",

    # "action" is built below, from an exclusion list rather than a whitelist.

    "change": r"(?:(?:^|[.!?]\s+)then\b|"
              r"\b(?:but then|but i|until|then one|suddenly|that changed|everything changed|"
              r"for the first time|instead|by the end|eventually|it turned out|turned out|"
              r"no longer|stopped|didn'?t work|went wrong|fell apart|refused to|"
              r"would ?n[o']t|could ?n[o']t|nobody (?:told|knew|came|asked)|no one (?:told|knew|came|asked)|"
              r"(?:failed|broke|collapsed|quit|lost|died|crashed)|"
              r"i was wrong|the problem was|what i had missed)\b)",

    "reflection": r"\b(?:i (?:learned|learnt|understood|understand|reali[sz]ed|reali[sz]e|"
                  r"discovered|noticed|found out|know now|see now)|taught me|showed me|"
                  r"made me (?:reali[sz]e|see|understand|think)|looking back|in hindsight|"
                  r"what i took (?:from|away)|i had been wrong|i started to see|"
                  r"i had (?:thought|assumed|believed|been)|i used to think|"
                  r"it was not (?:the|about|that)|what (?:actually )?mattered|"
                  r"the thing that mattered)\b",

    "stakes": r"\b(?:now i|today i|these days|since then|ever since|i still|i keep|i return|"
              r"i bring|i plan to|i want to|i intend|next year|in college|at university|"
              r"matters to me|still matters|because of (?:that|this|them|her|him|it)|"
              r"i carry|it is why|that is why|which is why)\b",
}

_NOT_ACTION = {
    "was", "were", "am", "is", "are", "be", "been", "being", "had", "have",
    "has", "will", "would", "could", "should", "can", "may", "might", "must",
    "do", "does", "did", "think", "thought", "feel", "felt", "know", "knew",
    "believe", "believed", "understand", "understood", "realize", "realized",
    "realise", "realised", "learn", "learned", "learnt", "see", "saw", "seen",
    "hear", "heard", "remember", "remembered", "notice", "noticed", "wish",
    "wished", "hope", "hoped", "want", "wanted", "like", "liked", "love",
    "loved", "hate", "hated", "need", "needed", "seem", "seemed", "became",
    "become", "got", "get", "guess", "guessed", "mean", "meant", "suppose",
    "supposed", "assume", "assumed", "expect", "expected", "wonder",
    "wondered", "regret", "regretted", "prefer", "preferred",
    "m", "ll", "ve", "d", "re", "s", "t",
}

_STORY_CUES["action"] = (
    r"\bi\s+(?!(?:" + "|".join(sorted(_NOT_ACTION, key=len, reverse=True)) +
    r")\b)[a-z]{2,}\b"
)


STORY_STEPS: list[tuple[str, str, str]] = [
    ("situation", "Situation",
     ("Put us in one specific place at one specific time. Not “high "
      "school,” but a Tuesday, a room, a smell.")),
    ("action", "Action",
     "Show yourself doing something. Verbs with you as the subject: what did you "
     "actually do with your hands?"),
    ("change", "Change",
     ("Something has to change. A plan fails, a belief breaks, someone "
      "surprises you. Without that it's a description, not a story.")),
    ("reflection", "Reflection",
     ("Say what you understood afterward that you didn't before. That's the "
      "part admissions officers care about most.")),
    ("stakes", "Why it matters",
     ("Bring it to the present. What do you do differently because of this? "
      "One honest sentence is enough.")),
]


def story_map(text: str) -> list[dict]:
    text = text or ""
    paras = paragraphs(text)
    # Character offset at which each paragraph starts, for locating a hit.
    bounds: list[int] = []
    pos = 0
    for p in paras:
        idx = text.find(p, pos)
        bounds.append(idx if idx >= 0 else pos)
        pos = bounds[-1] + len(p)

    low = text.lower()
    total_words = len(words(text)) or 1
    out: list[dict] = []

    for key, name, note in STORY_STEPS:
        hits = list(re.finditer(_STORY_CUES[key], low))
        n = len(hits)
        where = 0
        if hits:
            first = hits[0].start()
            where = 1
            for i, b in enumerate(bounds, 1):
                if b <= first:
                    where = i

        base = {0: 0, 1: 55, 2: 72, 3: 84}.get(n, 92)
        if n and total_words > 300:
            base -= min(18, int((total_words - 300) // 150) * 6)
        strength = int(max(0, min(100, base)))

        out.append({
            "key": key,
            "name": name,
            "note": note,
            "present": n > 0,
            "count": n,
            "strength": strength,
            "para": where,
        })
    return out


# The five dimensions

_ABSTRACT_SUFFIX = re.compile(
    r"^\w{6,}(?:tion|sion|ment|ness|ity|ance|ence|ship|ism)$", re.I)

_ABSTRACT_WORDS = {
    "passion", "dedication", "perseverance", "determination", "commitment",
    "leadership", "teamwork", "growth", "journey", "experience", "opportunity",
    "challenge", "impact", "potential", "success", "failure", "values",
    "character", "integrity", "empathy", "resilience", "diversity", "community",
    "adversity", "knowledge", "wisdom", "purpose", "identity", "mindset",
}

_PROPER_RE = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{2,})\b", re.M)
_DIALOGUE_RE = re.compile(r"[“\"'][^”\"']{6,}[”\"']")
_CONTRACTION_RE = re.compile(r"\b\w+['’](?:t|s|re|ve|ll|d|m)\b", re.I)


def _dim_craft(findings: list[Finding], n_words: int) -> float:
    if n_words <= 0:
        return 0.0
    weight = {"high": 3.0, "med": 1.6, "low": 0.45}
    penalty = sum(weight.get(f.severity, 1.0) for f in findings)
    per_100 = penalty / (n_words / 100.0)
    return max(0.0, min(100.0, 100.0 - per_100 * 5.5))


def _dim_rhythm(text: str) -> float:
    lens = [len(words(seg)) for _, _, seg in sentences(text)]
    if len(lens) < 3:
        return 0.0
    value = min(100.0, 15.0 + rhythm(text)["variety"])
    longest = max(lens)
    if longest > 40:
        value -= min(50.0, (longest - 40) * 2.2)
    return max(0.0, min(100.0, value))


def _dim_concrete(text: str, ws: list[str]) -> float:
    n = len(ws)
    if n < 20:
        return 0.0
    low = [w.lower() for w in ws]
    per = 100.0 / n

    sensory = sum(1 for w in low if w in SENSORY) * per
    numbers = len(re.findall(r"\b\d{1,4}\b", text)) * per
    proper = len(set(_PROPER_RE.findall(text))) * per
    dialogue = 1 if _DIALOGUE_RE.search(text) else 0

    abstract = sum(1 for w in low
                   if w in _ABSTRACT_WORDS or _ABSTRACT_SUFFIX.match(w)) * per

    value = 30.0
    value += min(22.0, sensory * 11.0)      # ~2 per 100 words tops this out
    value += min(14.0, numbers * 9.0)
    value += min(20.0, proper * 7.0)
    value += 8.0 * dialogue
    value += min(10.0, (sensory + numbers + proper) * 2.0)   # breadth bonus
    value -= min(34.0, abstract * 9.0)      # abstraction is what costs
    return max(0.0, min(100.0, value))


def _dim_voice(text: str, findings: list[Finding], ws: list[str]) -> float:
    """Whether it sounds like a person, and specifically like this person."""
    n = len(ws)
    if n < 20:
        return 0.0
    low = [w.lower() for w in ws]
    per = 100.0 / n

    unique = len(set(low)) / n                      # type-token ratio
    hedges = sum(1 for f in findings if f.kind in {"hedge", "filler", "weak"}) * per
    passive = sum(1 for f in findings if f.kind == "passive") * per
    telling = sum(1 for f in findings if f.kind in {"telling", "cliche"}) * per
    contractions = len(_CONTRACTION_RE.findall(text)) * per
    agency = len(re.findall(r"\bi\s+\w{3,}(?:ed|ked)\b", text.lower())) * per

    # A varied vocabulary is the base; the rest adds or removes from it.
    value = max(0.0, min(62.0, (unique - 0.30) * 195.0))
    value += min(12.0, contractions * 5.0)          # natural speech
    value += min(14.0, agency * 4.5)                # "I did", not "it happened"
    value += 12.0
    value -= min(24.0, hedges * 7.0)
    value -= min(14.0, passive * 6.0)
    value -= min(18.0, telling * 8.0)
    return max(0.0, min(100.0, value))


def _dim_structure(text: str, smap: list[dict], n_words: int) -> float:
    """Narrative shape plus paragraph balance."""
    if n_words < 20:
        return 0.0

    # Each of the five moves is worth 14 points, scaled by how established it is.
    arc = sum(0.14 * s["strength"] for s in smap)          # 0-70

    paras = [p for p in paragraphs(text) if words(p)]
    value = arc
    if len(paras) <= 1:
        value += 2.0 if n_words < 160 else 0.0             # one block of text
    elif 2 <= len(paras) <= 8:
        value += 16.0
    else:
        value += 8.0                                       # very chopped up

    if paras:
        sizes = [len(words(p)) for p in paras]
        largest = max(sizes) / max(1, sum(sizes))
        if largest < 0.45:
            value += 8.0                                   # nothing dominates
        elif largest < 0.62:
            value += 4.0

    segs = sentences(text)
    if segs and len(words(segs[0][2])) <= 14:
        value += 6.0                                       # a short way in
    return max(0.0, min(100.0, value))


DIMENSIONS: list[tuple[str, str, float, str]] = [
    ("craft", "Craft", 0.28,
     ("Filler, hedging, passive voice and wrong words: the mechanical "
      "stuff.")),
    ("structure", "Structure", 0.24,
     "Whether the five moves of a personal essay are all in here."),
    ("concrete", "Detail", 0.20,
     "Specific things you can see and touch, against abstract nouns."),
    ("voice", "Voice", 0.16,
     "Whether it sounds like a person rather than an application."),
    ("rhythm", "Rhythm", 0.12,
     "How much your sentence lengths vary."),
]


def score_detail(text: str, findings: list[Finding] | None = None,
                 smap: list[dict] | None = None) -> dict:
    text = text or ""
    if findings is None:
        findings = _dedupe([f for c in CHECKS for f in c(text)])
    if smap is None:
        smap = story_map(text)

    ws = words(text)
    n = len(ws)

    if n < WORDS_NO_SCORE:
        return {
            "score": 0,
            "ready": False,
            "provisional": False,
            "stage": "blank" if n == 0 else "early",
            "words": n,
            "needed": WORDS_NO_SCORE - n,
            "confidence": 0,
            "dimensions": [],
            "story": smap,
        }

    raw = {
        "craft": _dim_craft(findings, n),
        "rhythm": _dim_rhythm(text),
        "concrete": _dim_concrete(text, ws),
        "voice": _dim_voice(text, findings, ws),
        "structure": _dim_structure(text, smap, n),
    }
    composite = sum(raw[key] * w for key, _, w, _ in DIMENSIONS)

    if n >= WORDS_FULL:
        conf = 1.0
    else:
        span = WORDS_FULL - WORDS_NO_SCORE
        conf = 0.55 + 0.45 * ((n - WORDS_NO_SCORE) / span)
    final = 58.0 + (composite - 58.0) * conf

    return {
        "score": int(max(0, min(100, round(final)))),
        "ready": True,
        "provisional": n < WORDS_PROVISIONAL,
        "stage": "provisional" if n < WORDS_PROVISIONAL else "full",
        "words": n,
        "needed": 0,
        "confidence": int(round(conf * 100)),
        "dimensions": [
            {"key": key, "name": name, "weight": w, "note": note,
             "value": int(round(raw[key]))}
            for key, name, w, note in DIMENSIONS
        ],
        "story": smap,
    }


def score(text: str, findings: list[Finding] | None = None) -> int:
    """A single 0-100 number, or 0 when there is not enough text to judge."""
    return score_detail(text, findings)["score"]


def band(value: int) -> str:
    """Score to a word, for colour and for the headline."""
    if value <= 0:
        return "unscored"
    if value >= 85:
        return "sharp"
    if value >= 70:
        return "solid"
    if value >= 50:
        return "getting there"
    if value >= 30:
        return "rough draft"
    return "early days"


# Applying fixes

def apply_one(text: str, finding: Finding) -> str:
    """Apply a single fix. Offsets are checked against the current text first,
    so a stale finding cannot corrupt the draft."""
    if finding.start < 0 or finding.end > len(text) or finding.start >= finding.end:
        return text
    if text[finding.start:finding.end] != finding.original:
        return text        # the draft moved under us; do nothing
    return text[:finding.start] + finding.fix + text[finding.end:]


def apply_all(text: str, findings: list[Finding] | None = None) -> tuple[str, int]:
    if findings is None:
        findings = analyse(text)["findings"]
    safe = [f for f in findings if f.auto and f.has_fix]
    n = 0
    for f in sorted(safe, key=lambda f: f.start, reverse=True):
        before = text
        text = apply_one(text, f)
        if text != before:
            n += 1
    # Deleting words can leave doubled spaces or a space before a comma.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
    text = re.sub(r"(^|\n)[ \t]+", r"\1", text)
    return text, n


if __name__ == "__main__":
    sample = (
        "Ever since I was little, I have always been very passionate about "
        "helping people. I think that my experience volunteering at the animal "
        "shelter was really a life-changing experience that taught me the value "
        "of hard work. I did alot of things there and it was definately a "
        "learning experience. In order to make a difference, I decided that I "
        "would basically just try my best at all times, and their is no doubt "
        "in my mind that this experience taught me who I am today because the "
        "work was hard and long and difficult and I had to work very hard every "
        "single day of the entire summer without stopping even once."
    )
    r = analyse(sample)
    print(f"score {r['score']} ({band(r['score'])})   {r['stats']['words']} words")
    print(f"rhythm variety {r['stats']['rhythm_variety']}")
    print(f"\n{len(r['findings'])} findings:")
    for f in r["findings"]:
        arrow = f" -> {f.fix!r}" if f.has_fix else ""
        print(f"  [{f.severity:4s}] {f.label:26s} {f.original!r}{arrow}")
    fixed, n = apply_all(sample)
    print(f"\napplied {n} automatic fixes:\n{fixed}")
    print(f"\nnew score {score(fixed)}")
    for s in r["strengths"]:
        print(f"  + {s}")
