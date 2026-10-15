"""
Financial aid content: the paperwork checklist and the eligibility
rules behind it.

The steps are the same for everyone, so only the *doing* of one is
per-user (models.AidTask).

Merged from: aid, eligibility.
"""
from __future__ import annotations



# ====================================================================
# aid
# ====================================================================

FORMS = [
    {
        "key": "fafsa",
        "name": "FAFSA",
        "full": "Free Application for Federal Student Aid",
        "who": "Everyone. Yes, everyone — including families who assume they "
               "earn too much to qualify. It is also how you reach federal "
               "loans and many state and college programmes that have nothing "
               "to do with need.",
        "cost": "Free. Always free. The first F stands for Free.",
        "where": "studentaid.gov",
        "when": "The form for a school year normally opens in the autumn "
                "before it, around the start of October. The federal cut-off "
                "is much later — roughly the end of the following June — but "
                "that late date is a trap, because it is not the one that "
                "decides your money.",
        "watch": "Colleges and states set their own, far earlier deadlines: "
                 "college priority dates cluster from November to February, "
                 "state programmes from February to April, and several states "
                 "hand out money first-come, first-served until it runs out. "
                 "Filing in October rather than February can be the difference "
                 "between a grant and a waitlist.",
        "verify": "https://studentaid.gov/h/apply-for-aid/fafsa",
    },
    {
        "key": "css",
        "name": "CSS Profile",
        "full": "College Scholarship Service Profile",
        "who": "Only some colleges — mostly private ones, a few hundred of "
               "them — plus some scholarship programmes. Check each college on "
               "your list; most public universities do not use it.",
        "cost": "There is a fee per application, but College Board states the "
                "CSS Profile is free for families making up to $100,000 a "
                "year, and fee waivers exist beyond that. Never skip it "
                "because of the fee without checking whether you owe one.",
        "where": "cssprofile.collegeboard.org",
        "when": "Opens in the autumn alongside the FAFSA cycle. Deadlines are "
                "set by each college and are often earlier than you expect — "
                "frequently the same date as an Early Decision application.",
        "watch": "It asks for much more than the FAFSA: home equity, small "
                 "business assets, and both parents' finances where they live "
                 "apart. Gather documents before you start rather than "
                 "abandoning it halfway.",
        "verify": "https://cssprofile.collegeboard.org/",
    },
]

# --------------------------------------------------------------------------
# The paperwork, as a checklist
# --------------------------------------------------------------------------
STEPS = [
    {"key": "fsa_id", "phase": "Before you start", "title": "Create your FSA ID",
     "detail": "You and a contributing parent each need your own account at "
               "studentaid.gov. Make them at least a few days early — the "
               "details have to be matched against Social Security records, "
               "and that is not instant.",
     "xp": 30},

    {"key": "docs", "phase": "Before you start", "title": "Gather the documents",
     "detail": "Tax returns for the relevant year, records of untaxed income, "
               "and balances for savings and investments. Doing this first "
               "turns a two-hour ordeal into a thirty-minute form.",
     "xp": 30},

    {"key": "npc", "phase": "Before you start",
     "title": "Run a net price calculator for each college",
     "detail": "Every college in the US is required to publish one on its own "
               "site. It estimates what your family would actually pay, which "
               "is often nothing like the advertised price. Do this BEFORE you "
               "fall in love with a school, and before you cross one off for "
               "being expensive.",
     "xp": 50},

    {"key": "fafsa_done", "phase": "The forms", "title": "Submit the FAFSA",
     "detail": "As soon after it opens as you can manage. Early is money.",
     "xp": 120},

    {"key": "css_check", "phase": "The forms",
     "title": "Check which colleges want a CSS Profile",
     "detail": "Look each one up rather than assuming. Mark them on your "
               "college list so the deadline is somewhere you will see it.",
     "xp": 40},

    {"key": "css_done", "phase": "The forms",
     "title": "Submit the CSS Profile, if any college needs one",
     "detail": "Only if one of yours asks for it.",
     "xp": 100},

    {"key": "state", "phase": "The forms",
     "title": "Check your state's own aid programme",
     "detail": "Most states run grants with separate deadlines and sometimes "
               "a separate form. Several are first-come, first-served.",
     "xp": 60},

    {"key": "scholarships", "phase": "Beyond the forms",
     "title": "Find five local scholarships",
     "detail": "Local awards have far fewer applicants than national ones, so "
               "the odds are dramatically better for the same effort. Ask your "
               "counsellor, your library, your parents' employers, and any "
               "club or place of worship you belong to.",
     "xp": 90},

    {"key": "verify", "phase": "After you file",
     "title": "Answer anything the college asks for",
     "detail": "Some applications get selected for verification and the "
               "college will request documents. Reply quickly — aid is not "
               "finalised until you do, and this is where money quietly gets "
               "lost.",
     "xp": 60},

    {"key": "compare", "phase": "After you file",
     "title": "Compare your offers properly",
     "detail": "Line the offers up side by side and compare what you would "
               "actually pay, not the size of the award. A $40,000 award "
               "against a $70,000 price is worse than a $12,000 award against "
               "a $30,000 one.",
     "xp": 80},
]

PHASES = ["Before you start", "The forms", "Beyond the forms", "After you file"]

# --------------------------------------------------------------------------
# The words nobody explains
# --------------------------------------------------------------------------
GLOSSARY = [
    ("Sticker price", "The published cost of a year — tuition, fees, housing, "
                      "food. Most families at most colleges do not pay it."),
    ("Net price", "What you would actually pay after grants and scholarships. "
                  "This is the only number worth comparing between colleges."),
    ("Grant", "Money you are given and do not repay."),
    ("Scholarship", "Money you are given and do not repay, usually awarded for "
                    "something specific."),
    ("Loan", "Money you repay, with interest. Federal loans generally have "
             "better terms and protections than private ones."),
    ("Work-study", "A part-time job on campus, funded as part of your aid."),
    ("SAI", "Student Aid Index — the number the FAFSA produces from your "
            "family's finances. Colleges use it to work out your aid. It "
            "replaced the older term EFC."),
    ("Need-blind", "The college decides whether to admit you without looking "
                   "at whether you need aid."),
    ("Meets full need", "The college promises to cover the gap between its "
                        "price and what it calculates your family can pay. "
                        "Rarer than it sounds, and each college calculates "
                        "'can pay' its own way."),
    ("Gapping", "Being admitted but offered less aid than you need — the "
                "difference is left for you to find."),
    ("Verification", "A check where the college asks for documents to confirm "
                     "what your FAFSA said. Routine, not an accusation."),
    ("Priority deadline", "The date after which a college stops guaranteeing "
                          "consideration for its own money. Usually much "
                          "earlier than the federal deadline, and the one that "
                          "actually matters."),
]

# --------------------------------------------------------------------------
# Warnings worth shouting about
# --------------------------------------------------------------------------
TRAPS = [
    ("Never pay to file the FAFSA",
     "Any site charging you to submit it is taking money for something that is "
     "free at studentaid.gov. The same goes for services promising to 'find' "
     "you scholarships for a fee."),
    ("The federal deadline is not your deadline",
     "It is the last one, and by then the money that matters has gone. Work "
     "backwards from your colleges' and your state's dates instead."),
    ("Do not rule a college out on its sticker price",
     "The most expensive-looking colleges sometimes cost a particular family "
     "the least, because they have the most money to give away. Run the net "
     "price calculator before deciding."),
    ("Early Decision and money do not mix well",
     "ED is binding, so you commit before you can compare aid offers. If cost "
     "will decide where you go, that is a real cost of applying ED — worth "
     "talking through with your counsellor first."),
    ("An award is not a discount",
     "Compare what you would pay, not what you were given. Colleges present "
     "these numbers to flatter themselves."),
]

# Shown at the top of the screen, and it is not boilerplate — it is the honest
# limit of what a program can do here.
DISCLAIMER = (
    "This screen keeps track of the paperwork and explains the words. It is "
    "not financial advice, and it cannot tell you what to borrow or what you "
    "can afford — those depend on your family's situation and belong with your "
    "school counsellor and each college's financial aid office, who can look "
    "at the actual numbers. Dates shift every year, so confirm anything that "
    "matters against the official site before you rely on it."
)

STATUSES = {
    "found": "Found it",
    "started": "Started",
    "submitted": "Submitted",
    "won": "Won",
    "lost": "Didn't get it",
}

ROUNDS = {
    "ed": "Early Decision",
    "ed2": "Early Decision II",
    "ea": "Early Action",
    "rea": "Restrictive Early Action",
    "regular": "Regular Decision",
    "rolling": "Rolling",
}

# The rounds that legally commit you to attend if admitted.
BINDING = {"ed", "ed2"}


def step_phase(key: str) -> str:
    return next((s["phase"] for s in STEPS if s["key"] == key), "")


def total_xp() -> int:
    return sum(s["xp"] for s in STEPS)


# ====================================================================
# eligibility
# ====================================================================

GENDERS = [
    ("female", "Female"),
    ("male", "Male"),
    ("nonbinary", "Non-binary"),
    ("unspecified", "Prefer not to say"),
]

MIN_AGE, MAX_AGE = 13, 22

CAVEAT = ("Eligibility rules change every cycle and vary by provider — treat these "
          "as places to look, then confirm the current terms on the provider's site.")


def age_notes(age: int | None) -> list[dict]:
    """Age-driven items. Every claim here is a paperwork or deadline fact."""
    if age is None:
        return []
    out: list[dict] = []

    if age < 18:
        out.append({
            "icon": "✍️",
            "title": "You'll need a co-signer on some paperwork",
            "body": "Under 18, a parent or guardian has to sign housing contracts, "
                    "most private loan applications and some program waivers. Line "
                    "that up early — it is a common reason applications miss a deadline.",
        })
    else:
        out.append({
            "icon": "✅",
            "title": "You can sign for yourself",
            "body": "At 18 you can sign your own enrollment forms, housing contracts "
                    "and loan paperwork without a co-signer.",
        })

    # Dependency status is the single most consequential age rule in financial aid.
    out.append({
        "icon": "📄",
        "title": "FAFSA will treat you as a dependent student",
        "body": "Under 24, the FAFSA counts almost everyone as dependent, which means "
                "your parents' financial information is required — even if you don't "
                "live with them or they don't help pay. The exceptions are narrow "
                "(married, a veteran, a parent yourself, emancipated, or unaccompanied "
                "and homeless). If one applies to you, look up a dependency override.",
    })

    if age <= 16:
        out.append({
            "icon": "🎓",
            "title": "Dual enrollment is on the table",
            "body": "Many community colleges let high schoolers take credit-bearing "
                    "courses. Cheap college credit, and it shows up well on an "
                    "application. Ask your counselor what your school accepts.",
        })
    if age >= 16:
        out.append({
            "icon": "🔬",
            "title": "Summer programs open up at 16",
            "body": "A lot of university summer research and pre-college programs set "
                    "their minimum at 16, and they tend to have deadlines in winter — "
                    "much earlier than students expect.",
        })
    return out


def gender_notes(gender: str | None) -> list[dict]:
    """Gender-driven items. These are scholarship *pools that exist*, nothing more."""
    if not gender or gender == "unspecified":
        return []
    if gender == "female":
        return [{
            "icon": "🔎",
            "title": "Scholarship pools restricted to women",
            "body": "Sizeable ones exist in engineering, computing and business — the "
                    "Society of Women Engineers runs one of the largest single programs. "
                    "These are separate pots from general scholarships, so applying "
                    "costs you nothing on the general side.",
        }]
    if gender == "male":
        return [{
            "icon": "🔎",
            "title": "Scholarship pools restricted to men",
            "body": "Smaller than the equivalent for women, but real, and concentrated "
                    "in fields where men are underrepresented — nursing, education and "
                    "social work. The American Assembly for Men in Nursing runs one.",
        }]
    return [{
        "icon": "🔎",
        "title": "Identity-based scholarship databases",
        "body": "Point Foundation and the HRC's scholarship database index awards for "
                "LGBTQ+ students. Worth a pass alongside your general list.",
    }]


def notes_for(age: int | None, gender: str | None) -> list[dict]:
    return age_notes(age) + gender_notes(gender)


def as_js_data() -> dict:
    """Precomputed for the standalone preview, which has no Python at runtime."""
    return {
        "genders": [{"key": k, "label": l} for k, l in GENDERS],
        "minAge": MIN_AGE, "maxAge": MAX_AGE, "caveat": CAVEAT,
        "byAge": {a: age_notes(a) for a in range(MIN_AGE, MAX_AGE + 1)},
        "byGender": {k: gender_notes(k) for k, _ in GENDERS},
    }


if __name__ == "__main__":
    for a in (15, 17, 18):
        print(f"\nage {a}: {len(age_notes(a))} notes")
        for n in age_notes(a):
            print("   -", n["title"])
    for g, _ in GENDERS:
        print(f"{g:12s} {len(gender_notes(g))} notes")
