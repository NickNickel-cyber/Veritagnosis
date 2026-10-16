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
        "who": ("Everyone, including families who think they earn too much to "
                "qualify. It's also how you get federal loans and many state and "
                "college programs that aren't based on need."),
        "cost": "Always free. The first F in FAFSA stands for Free.",
        "where": "studentaid.gov",
        "when": ("It opens in the fall before the school year it covers. The federal "
                 "deadline isn't until the following summer, but don't go by that "
                 "date. It isn't the one that decides how much aid you get."),
        "watch": ("Colleges and states set their own deadlines, and they're much "
                  "earlier. College priority dates tend to fall between November and "
                  "February, state deadlines between February and April, and some "
                  "states give out money first-come, first-served until it runs out. "
                  "Filing in October instead of February can be the difference between "
                  "getting a grant and missing it."),
        "verify": "https://studentaid.gov/h/apply-for-aid/fafsa",
    },
    {
        "key": "css",
        "name": "CSS Profile",
        "full": "College Scholarship Service Profile",
        "who": ("Only some colleges (a few hundred, mostly private) plus some "
                "scholarship programs. Check each college on your list. Most public "
                "universities don't use it."),
        "cost": ("There's a fee for each college you send it to, but many families "
                 "qualify for a fee waiver. Check whether you do before you skip it "
                 "because of the cost."),
        "where": "cssprofile.collegeboard.org",
        "when": ("Opens in the fall, around when the FAFSA does. Each college sets its "
                 "own deadline, and it's often earlier than you'd expect, sometimes "
                 "the same day as Early Decision."),
        "watch": ("It asks for a lot more than the FAFSA, like home equity, small "
                  "business assets, and both parents' finances if they live apart. Get "
                  "your documents together before you start so you don't get stuck "
                  "halfway."),
        "verify": "https://cssprofile.collegeboard.org/",
    },
]

# --------------------------------------------------------------------------
# The paperwork, as a checklist
# --------------------------------------------------------------------------
STEPS = [
    {"key": "fsa_id", "phase": "Before you start", "title": "Create your FSA ID",
     "detail": ("You and a parent each need your own account at studentaid.gov. Make "
                "them a few days early, since they have to be checked against Social "
                "Security records and that takes time."),
     "xp": 30},

    {"key": "docs", "phase": "Before you start", "title": "Gather the documents",
     "detail": ("Tax returns for the right year, records of untaxed income, and "
                "savings and investment balances. Having these ready makes the form "
                "go much faster."),
     "xp": 30},

    {"key": "npc", "phase": "Before you start",
     "title": "Run a net price calculator for each college",
     "detail": ("Every US college has to have one on its website. It estimates what "
                "your family would actually pay, which can be very different from the "
                "listed price. Do this before you fall in love with a school, and "
                "before you rule one out for being too expensive."),
     "xp": 50},

    {"key": "fafsa_done", "phase": "The forms", "title": "Submit the FAFSA",
     "detail": "As soon after it opens as you can. Filing early can mean more aid.",
     "xp": 120},

    {"key": "css_check", "phase": "The forms",
     "title": "Check which colleges want a CSS Profile",
     "detail": ("Look each one up instead of guessing, and mark them on your college "
                "list so you see the deadline."),
     "xp": 40},

    {"key": "css_done", "phase": "The forms",
     "title": "Submit the CSS Profile, if any college needs one",
     "detail": "Only if one of yours asks for it.",
     "xp": 100},

    {"key": "state", "phase": "The forms",
     "title": "Check your state's own aid program",
     "detail": ("Most states have their own grants with separate deadlines, and "
                "sometimes a separate form. Some are first-come, first-served."),
     "xp": 60},

    {"key": "scholarships", "phase": "Beyond the forms",
     "title": "Find five local scholarships",
     "detail": ("Local scholarships get far fewer applicants than national ones, so "
                "your odds are much better. Ask your counselor, your library, your "
                "parents' employers, and any club or place of worship you're part of."),
     "xp": 90},

    {"key": "verify", "phase": "After you file",
     "title": "Answer anything the college asks for",
     "detail": ("Some FAFSAs get picked for verification, and the college will ask "
                "for documents. Reply quickly. Your aid isn't final until you do, and "
                "students lose money by missing these requests."),
     "xp": 60},

    {"key": "compare", "phase": "After you file",
     "title": "Compare your offers properly",
     "detail": ("Put the offers side by side and compare what you'd actually pay, not "
                "how big the award is. A $40,000 award at a $70,000 school is worse "
                "than a $12,000 award at a $30,000 one."),
     "xp": 80},
]

PHASES = ["Before you start", "The forms", "Beyond the forms", "After you file"]

# --------------------------------------------------------------------------
# The words nobody explains
# --------------------------------------------------------------------------
GLOSSARY = [
    ("Sticker price", ("The listed cost of one year: tuition, fees, housing and food. Many "
                       "families end up paying less.")),
    ("Net price", "What you would actually pay after grants and scholarships. "
                  "This is the only number worth comparing between colleges."),
    ("Grant", "Money you are given and do not repay."),
    ("Scholarship", "Money you are given and do not repay, usually awarded for "
                    "something specific."),
    ("Loan", "Money you repay, with interest. Federal loans generally have "
             "better terms and protections than private ones."),
    ("Work-study", "A part-time job on campus, funded as part of your aid."),
    ("SAI", ("Student Aid Index. The number the FAFSA calculates from your "
             "family's finances. Colleges use it to figure out your aid. It "
             "replaced the older EFC.")),
    ("Need-blind", "The college decides whether to admit you without looking "
                   "at whether you need aid."),
    ("Meets full need", ("The college promises to cover the gap between its price and what it "
                         "thinks your family can pay. It's less common than it sounds, and "
                         "each college decides what 'can pay' means.")),
    ("Gapping", ("When you're admitted but offered less aid than you need, and you "
                 "have to cover the difference.")),
    ("Verification", ("When the college asks for documents to confirm what's on your FAFSA. "
                      "It's routine and doesn't mean you did anything wrong.")),
    ("Priority deadline", ("The date after which a college stops guaranteeing you'll be "
                           "considered for its own aid. It's usually much earlier than the "
                           "federal deadline, and it's the one to watch.")),
]

# --------------------------------------------------------------------------
# Warnings worth shouting about
# --------------------------------------------------------------------------
TRAPS = [
    ("Never pay to file the FAFSA",
     ("If a site charges you to submit it, skip it. It's free at "
      "studentaid.gov. Be wary of services that charge to 'find' you "
      "scholarships, too.")),
    ("The federal deadline is not your deadline",
     ("It's the last deadline, and by then most of the money is gone. Plan "
      "around your colleges' and your state's dates instead.")),
    ("Do not rule a college out on its sticker price",
     ("The most expensive-looking colleges sometimes end up cheapest for a "
      "family because they have the most aid to give. Run the net price "
      "calculator before you decide.")),
    ("Early Decision and money do not mix well",
     ("ED is binding, so you commit before you can compare aid offers. If "
      "cost matters a lot, talk it through with your counselor first.")),
    ("An award is not a discount",
     ("Compare what you'd pay, not how much you were offered. Big award "
      "numbers can be misleading.")),
]

# Shown at the top of the screen, and it is not boilerplate — it is the honest
# limit of what a program can do here.
DISCLAIMER = (
    ("This page helps you keep track of the paperwork and explains the "
     "terms. It isn't financial advice, and it can't tell you what to "
     "borrow or what you can afford. Those questions depend on your "
     "family's situation, so bring them to your school counselor and each "
     "college's financial aid office. Dates change every year, so "
     "double-check anything important on the official site.")
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

CAVEAT = (("Eligibility rules change every year and vary by provider. Use these "
           "as a starting point, then check the current rules on the provider's "
           "site."))


def age_notes(age: int | None) -> list[dict]:
    """Age-driven items. Every claim here is a paperwork or deadline fact."""
    if age is None:
        return []
    out: list[dict] = []

    if age < 18:
        out.append({
            "icon": "✍️",
            "title": "You'll need a co-signer on some paperwork",
            "body": ("If you're under 18, a parent or guardian has to sign housing "
                     "contracts, most private loan applications and some program waivers. "
                     "Sort that out early so it doesn't hold anything up."),
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
        "body": ("If you're under 24, the FAFSA treats you as a dependent in almost "
                 "every case, so it needs your parents' financial information, even if "
                 "you don't live with them or they don't help pay. The exceptions are "
                 "narrow: being married, a veteran, a parent yourself, emancipated, or "
                 "unaccompanied and homeless. If one applies to you, ask about a "
                 "dependency override."),
    })

    if age <= 16:
        out.append({
            "icon": "🎓",
            "title": "Dual enrollment is on the table",
            "body": ("Many community colleges let high schoolers take courses for credit. "
                     "It's cheap college credit and looks good on an application. Ask your "
                     "counselor what your school accepts."),
        })
    if age >= 16:
        out.append({
            "icon": "🔬",
            "title": "Summer programs open up at 16",
            "body": ("A lot of university summer research and pre-college programs start "
                     "at 16, and their deadlines are usually in winter, earlier than most "
                     "students expect."),
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
            "body": ("There are big ones in engineering, computing and business. The "
                     "Society of Women Engineers runs one of the largest. They're separate "
                     "from general scholarships, so applying doesn't hurt your chances "
                     "anywhere else."),
        }]
    if gender == "male":
        return [{
            "icon": "🔎",
            "title": "Scholarship pools restricted to men",
            "body": ("There are fewer of these, mostly in fields where men are "
                     "underrepresented, like nursing, education and social work. The "
                     "American Assembly for Men in Nursing runs one."),
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
