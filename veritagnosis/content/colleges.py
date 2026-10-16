"""
Published admitted-student data, one entry per college.

Every number here came from a named source on a named date, and every entry
carries that source so the screen can show it. That is the whole point: the
app tells a student "Michigan's admitted middle 50% was 1360-1530, here is the
PDF" — never "you have a 23% chance", which would be a number nobody can
stand behind.

`confidence` is about provenance, not about the college:

  high    read directly out of the institution's own Common Data Set
  medium  the institution's own page, or a CDS quoted by a reputable
          aggregator that could not be fetched directly
  low     aggregator only, or sources that disagreed with each other

The screen shows medium and low differently, because a student deciding where
to apply deserves to know which numbers are solid.

Adding a college: append a dict. Every field may be None except name and
state. Nothing else in the app needs changing, and `python -m pytest
tests/test_colleges.py` will tell you if an entry is malformed.

Test policy: UC campuses are test-blind (scores are not considered at all), so
their test fields are None by fact, not by omission. Many other schools remain
test-optional, which means a published range describes only the self-selected
minority who submitted — `test_optional_note` says so where it matters.
"""

from __future__ import annotations

COLLEGES: list[dict] = [
    # ---- highly selective private ----------------------------------------
    dict(name="Harvard University", state="MA", accept_rate=3.6,
         sat_25=1510, sat_75=1580, act_25=34, act_75=36,
         gpa_375_plus_pct=94.6, cost_year=82866, data_year="2024-25",
         source_url="https://oira.harvard.edu/", source_kind="common_data_set",
         confidence="high",
         note="SAT composite derived by summing published EBRW and Math bands."),
    dict(name="Yale University", state="CT", accept_rate=3.9,
         sat_25=1480, sat_75=1560, act_25=33, act_75=35,
         gpa_375_plus_pct=None, cost_year=87150, data_year="2024-25",
         source_url="https://oir.yale.edu/", source_kind="common_data_set",
         confidence="high",
         note="Yale did not break out GPA bands in this CDS."),
    dict(name="Princeton University", state="NJ", accept_rate=4.6,
         sat_25=1500, sat_75=1560, act_25=34, act_75=35,
         gpa_375_plus_pct=96.2, cost_year=82650, data_year="2024-25",
         source_url="https://ir.princeton.edu/", source_kind="common_data_set",
         confidence="high",
         note="Cost is Princeton's bundled fee package; fees are not itemised."),
    dict(name="Stanford University", state="CA", accept_rate=3.6,
         sat_25=1510, sat_75=1570, act_25=34, act_75=35,
         gpa_375_plus_pct=89.8, cost_year=87225, data_year="2024-25",
         source_url="https://irds.stanford.edu/data-findings/cds",
         source_kind="aggregator", confidence="medium",
         note="CDS hosted on Drive and not directly readable; cost is from "
              "Stanford's own tuition announcement."),
    dict(name="Massachusetts Institute of Technology", state="MA",
         accept_rate=4.5, sat_25=1520, sat_75=1570, act_25=34, act_75=36,
         gpa_375_plus_pct=None, cost_year=85960, data_year="2024-25",
         source_url="https://ir.mit.edu/projects/2024-25-common-data-set/",
         source_kind="common_data_set", confidence="high",
         note="MIT reports GPA as not available. Published subscores sum to a "
              "slightly wider band than the stated composite."),
    dict(name="Columbia University", state="NY", accept_rate=3.9,
         sat_25=1510, sat_75=1560, act_25=34, act_75=36,
         gpa_375_plus_pct=None, cost_year=92860, data_year="2024-25",
         source_url="https://opir.columbia.edu/", source_kind="common_data_set",
         confidence="high",
         note="Cost line is the CDS's 2025-26 rate, a year ahead of the "
              "admissions cohort."),
    dict(name="University of Pennsylvania", state="PA", accept_rate=5.4,
         sat_25=1510, sat_75=1570, act_25=34, act_75=36,
         gpa_375_plus_pct=None, cost_year=87860, data_year="2024-25",
         source_url="https://ira.upenn.edu/", source_kind="common_data_set",
         confidence="high", note=""),
    dict(name="Brown University", state="RI", accept_rate=5.4,
         sat_25=1510, sat_75=1560, act_25=34, act_75=35,
         gpa_375_plus_pct=None, cost_year=93164, data_year="2024-25",
         source_url="https://oir.brown.edu/", source_kind="aggregator",
         confidence="medium",
         note="Brown's CDS page would not render; figures transcribed by an "
              "aggregator and not verified against the PDF."),
    dict(name="Dartmouth College", state="NH", accept_rate=5.4,
         sat_25=None, sat_75=None, act_25=None, act_75=None,
         gpa_375_plus_pct=None, cost_year=88018, data_year="2024-25",
         source_url="https://www.dartmouth.edu/oir/", source_kind="aggregator",
         confidence="medium",
         note="No composite range published for this cohort, its last "
              "test-optional year. Testing is required again from Fall 2025."),
    dict(name="Duke University", state="NC", accept_rate=5.7,
         sat_25=1500, sat_75=1570, act_25=34, act_75=35,
         gpa_375_plus_pct=None, cost_year=87357, data_year="2024-25",
         source_url="https://ir.provost.duke.edu/", source_kind="common_data_set",
         confidence="high",
         note="Duke's CDS admit rate (5.7%) differs from its own press release "
              "(5.15%); the CDS figure is used here."),
    dict(name="Northwestern University", state="IL", accept_rate=7.7,
         sat_25=1510, sat_75=1560, act_25=34, act_75=35,
         gpa_375_plus_pct=None, cost_year=89448, data_year="2024-25",
         source_url="https://enrollment.northwestern.edu/",
         source_kind="common_data_set", confidence="high", note=""),
    dict(name="Cornell University", state="NY", accept_rate=8.4,
         sat_25=1510, sat_75=1560, act_25=33, act_75=35,
         gpa_375_plus_pct=None, cost_year=92844, data_year="2024-25",
         source_url="https://irp.dpb.cornell.edu/", source_kind="aggregator",
         confidence="low",
         note="Cornell's own CDS returned a blank template on every attempt; "
              "figures are aggregator-sourced and uncorroborated."),

    # ---- public flagships -------------------------------------------------
    dict(name="UCLA", state="CA", accept_rate=9.0,
         sat_25=None, sat_75=None, act_25=None, act_75=None,
         gpa_375_plus_pct=None, cost_year=72908, data_year="2024-25",
         source_url="https://admission.universityofcalifornia.edu/",
         source_kind="aggregator", confidence="medium",
         note="University of California is test-blind: scores are not "
              "considered at all. Cost is the out-of-state rate."),
    dict(name="UC Berkeley", state="CA", accept_rate=11.0,
         sat_25=None, sat_75=None, act_25=None, act_75=None,
         gpa_375_plus_pct=None, cost_year=79177, data_year="2024-25",
         source_url="https://admission.universityofcalifornia.edu/",
         source_kind="aggregator", confidence="medium",
         note="Test-blind. Cost is the out-of-state rate."),
    dict(name="UNC Chapel Hill", state="NC", accept_rate=15.3,
         sat_25=1400, sat_75=1530, act_25=31, act_75=34,
         gpa_375_plus_pct=73.2, cost_year=60266, data_year="2024-25",
         source_url="https://oira.unc.edu/", source_kind="common_data_set",
         confidence="high", note="Cost line is the 2025-26 rate. Out-of-state."),
    dict(name="University of Michigan Ann Arbor", state="MI", accept_rate=15.6,
         sat_25=1360, sat_75=1530, act_25=31, act_75=34,
         gpa_375_plus_pct=92.8, cost_year=80208, data_year="2024-25",
         source_url="https://obp.umich.edu/", source_kind="common_data_set",
         confidence="high", note="Cost is the out-of-state rate."),
    dict(name="University of Virginia", state="VA", accept_rate=16.8,
         sat_25=1410, sat_75=1520, act_25=32, act_75=35,
         gpa_375_plus_pct=90.7, cost_year=76087, data_year="2024-25",
         source_url="https://ira.virginia.edu/", source_kind="common_data_set",
         confidence="high", note="Cost line is the 2025-26 rate. Out-of-state."),
    dict(name="University of Florida", state="FL", accept_rate=19.8,
         sat_25=1420, sat_75=1520, act_25=32, act_75=35,
         gpa_375_plus_pct=None, cost_year=45799, data_year="2025-26",
         source_url="https://admissions.ufl.edu/freshman-student-profile",
         source_kind="college_page", confidence="medium",
         note="Ranges describe ADMITTED students, not the enrolled class other "
              "entries use. Cost figure is older than the score data."),
    dict(name="UC San Diego", state="CA", accept_rate=26.8,
         sat_25=None, sat_75=None, act_25=None, act_75=None,
         gpa_375_plus_pct=None, cost_year=73820, data_year="2024-25",
         source_url="https://admission.universityofcalifornia.edu/",
         source_kind="aggregator", confidence="medium",
         note="Test-blind. Cost is the out-of-state rate."),
    dict(name="University of Texas at Austin", state="TX", accept_rate=26.6,
         sat_25=1230, sat_75=1500, act_25=29, act_75=34,
         gpa_375_plus_pct=None, cost_year=65666, data_year="2024-25",
         source_url="https://reports.utexas.edu/common-data-set",
         source_kind="aggregator", confidence="low",
         note="Sources disagreed materially on the score bands. Admission is "
              "largely by class rank, not GPA. Cost is out-of-state."),
    dict(name="UC Irvine", state="CA", accept_rate=28.8,
         sat_25=None, sat_75=None, act_25=None, act_75=None,
         gpa_375_plus_pct=None, cost_year=72796, data_year="2024-25",
         source_url="https://admission.universityofcalifornia.edu/",
         source_kind="aggregator", confidence="medium",
         note="Test-blind. Cost is the out-of-state rate."),
    dict(name="University of Washington Seattle", state="WA", accept_rate=39.0,
         sat_25=1333, sat_75=1500, act_25=28, act_75=33,
         gpa_375_plus_pct=None, cost_year=65509, data_year="2024-25",
         source_url="https://www.washington.edu/opb/uw-data/",
         source_kind="aggregator", confidence="medium",
         test_optional_note="Fewer than 1 in 5 enrolled students submitted a "
                            "score, so this band describes a small, "
                            "self-selected group.",
         note="Cost is the out-of-state rate."),
    dict(name="University of Illinois Urbana-Champaign", state="IL",
         accept_rate=42.4, sat_25=1420, sat_75=1540, act_25=31, act_75=35,
         gpa_375_plus_pct=None, cost_year=58318, data_year="2024-25",
         source_url="https://admissions.illinois.edu/apply/freshman/profile",
         source_kind="college_page", confidence="medium",
         note="Ranges are pooled over three years of admitted students, not a "
              "single class. Cost is the out-of-state rate."),
    dict(name="University of Wisconsin-Madison", state="WI", accept_rate=45.0,
         sat_25=1370, sat_75=1490, act_25=29, act_75=33,
         gpa_375_plus_pct=None, cost_year=60505, data_year="2024-25",
         source_url="https://apir.wisc.edu/", source_kind="aggregator",
         confidence="medium",
         test_optional_note="Well under half the class submitted a score.",
         note="Cost is the out-of-state rate."),
]

# Name -> entry, for the lookup the fit engine does on the student's school list.
BY_NAME = {c["name"].lower(): c for c in COLLEGES}

# What the dataset does NOT cover, stated plainly so the screen can say it.
# The set skews selective: there is nothing here above a 45% admit rate, so a
# student whose list is mostly accessible schools will find few matches. That
# is a gap in the data, not a judgement about their list, and the screen says
# so rather than leaving them to infer it.
# COVERAGE_NOTE used to live here: a paragraph naming how many universities
# were loaded and what range of admit rates they spanned, rendered under every
# statistics box. It was written when this file was the whole catalogue. The
# Scorecard import (scripts/import_colleges.py) means it no longer describes
# the data, and a student reading their own numbers does not need a paragraph
# about where the dataset came from — each entry already carries its own
# source_url for anyone who wants to check a figure.


# Nicknames -> the college's full official name, as the federal College
# Scorecard spells it. Students type "UMich" or "UPenn"; the catalogue only
# knows full names, so without this a nickname finds no data at all. The app
# saves the full name, never the nickname, so the list always says exactly
# which college it means. Only unambiguous nicknames are here: "Michigan",
# "Rutgers" or "Miami" could mean several colleges, so those get a pick-list
# instead of a guess. Every target was checked against the Scorecard import
# (Jun 2026 release); tests/test_college_names.py re-checks them.
ALIASES: dict[str, str] = {
    'umich': 'University of Michigan-Ann Arbor',
    'university of michigan': 'University of Michigan-Ann Arbor',
    'u mich': 'University of Michigan-Ann Arbor',
    'upenn': 'University of Pennsylvania',
    'penn': 'University of Pennsylvania',
    'u penn': 'University of Pennsylvania',
    'mit': 'Massachusetts Institute of Technology',
    'nyu': 'New York University',
    'ucla': 'University of California-Los Angeles',
    'uc los angeles': 'University of California-Los Angeles',
    'uc berkeley': 'University of California-Berkeley',
    'berkeley': 'University of California-Berkeley',
    'cal berkeley': 'University of California-Berkeley',
    'university of california berkeley': 'University of California-Berkeley',
    'ucsd': 'University of California-San Diego',
    'uc san diego': 'University of California-San Diego',
    'university of california san diego': 'University of California-San Diego',
    'uc davis': 'University of California-Davis',
    'ucdavis': 'University of California-Davis',
    'uci': 'University of California-Irvine',
    'uc irvine': 'University of California-Irvine',
    'ucsb': 'University of California-Santa Barbara',
    'uc santa barbara': 'University of California-Santa Barbara',
    'ucr': 'University of California-Riverside',
    'uc riverside': 'University of California-Riverside',
    'ucsc': 'University of California-Santa Cruz',
    'uc santa cruz': 'University of California-Santa Cruz',
    'uc merced': 'University of California-Merced',
    'usc': 'University of Southern California',
    'cmu': 'Carnegie Mellon University',
    'carnegie mellon': 'Carnegie Mellon University',
    'unc': 'University of North Carolina at Chapel Hill',
    'unc chapel hill': 'University of North Carolina at Chapel Hill',
    'chapel hill': 'University of North Carolina at Chapel Hill',
    'university of north carolina': 'University of North Carolina at Chapel Hill',
    'uva': 'University of Virginia-Main Campus',
    'university of virginia': 'University of Virginia-Main Campus',
    'ut austin': 'The University of Texas at Austin',
    'university of texas': 'The University of Texas at Austin',
    'university of texas austin': 'The University of Texas at Austin',
    'georgia tech': 'Georgia Institute of Technology-Main Campus',
    'gatech': 'Georgia Institute of Technology-Main Campus',
    'georgia institute of technology': 'Georgia Institute of Technology-Main Campus',
    'caltech': 'California Institute of Technology',
    'penn state': 'Pennsylvania State University-Main Campus',
    'pennsylvania state university': 'Pennsylvania State University-Main Campus',
    'psu': 'Pennsylvania State University-Main Campus',
    'ohio state': 'Ohio State University-Main Campus',
    'ohio state university': 'Ohio State University-Main Campus',
    'the ohio state university': 'Ohio State University-Main Campus',
    'asu': 'Arizona State University Campus Immersion',
    'arizona state': 'Arizona State University Campus Immersion',
    'arizona state university': 'Arizona State University Campus Immersion',
    'umd': 'University of Maryland-College Park',
    'university of maryland': 'University of Maryland-College Park',
    'umd college park': 'University of Maryland-College Park',
    'bu': 'Boston University',
    'bc': 'Boston College',
    'gwu': 'George Washington University',
    'george washington': 'George Washington University',
    'jhu': 'Johns Hopkins University',
    'johns hopkins': 'Johns Hopkins University',
    'washu': 'Washington University in St Louis',
    'wustl': 'Washington University in St Louis',
    'washington university': 'Washington University in St Louis',
    'washington university in st. louis': 'Washington University in St Louis',
    'uchicago': 'University of Chicago',
    'uiuc': 'University of Illinois Urbana-Champaign',
    'university of illinois': 'University of Illinois Urbana-Champaign',
    'illinois urbana champaign': 'University of Illinois Urbana-Champaign',
    'purdue': 'Purdue University-Main Campus',
    'purdue university': 'Purdue University-Main Campus',
    'uf': 'University of Florida',
    'fsu': 'Florida State University',
    'tcnj': 'The College of New Jersey',
    'college of new jersey': 'The College of New Jersey',
    'njit': 'New Jersey Institute of Technology',
    'rpi': 'Rensselaer Polytechnic Institute',
    'wpi': 'Worcester Polytechnic Institute',
    'rit': 'Rochester Institute of Technology',
    'uw madison': 'University of Wisconsin-Madison',
    'university of wisconsin': 'University of Wisconsin-Madison',
    'university of washington': 'University of Washington-Seattle Campus',
    'uw seattle': 'University of Washington-Seattle Campus',
    'university of washington seattle': 'University of Washington-Seattle Campus',
    'virginia tech': 'Virginia Polytechnic Institute and State University',
    'texas a&m': 'Texas A&M University-College Station',
    'tamu': 'Texas A&M University-College Station',
    'texas a and m': 'Texas A&M University-College Station',
    'lsu': 'Louisiana State University and Agricultural & Mechanical College',
    'byu': 'Brigham Young University',
    'smu': 'Southern Methodist University',
    'tcu': 'Texas Christian University',
    'uconn': 'University of Connecticut',
    'umass': 'University of Massachusetts-Amherst',
    'umass amherst': 'University of Massachusetts-Amherst',
    'stony brook': 'Stony Brook University',
    'suny stony brook': 'Stony Brook University',
    'binghamton': 'Binghamton University',
    'suny binghamton': 'Binghamton University',
    'case western': 'Case Western Reserve University',
    'cwru': 'Case Western Reserve University',
    'michigan state': 'Michigan State University',
    'umn': 'University of Minnesota-Twin Cities',
    'university of minnesota': 'University of Minnesota-Twin Cities',
    'indiana university': 'Indiana University-Bloomington',
    'iu bloomington': 'Indiana University-Bloomington',
    'notre dame': 'University of Notre Dame',
    'georgetown': 'Georgetown University',
    'columbia': 'Columbia University in the City of New York',
    'columbia university': 'Columbia University in the City of New York',
    'brown': 'Brown University',
    'dartmouth': 'Dartmouth College',
    'duke': 'Duke University',
    'harvard': 'Harvard University',
    'yale': 'Yale University',
    'princeton': 'Princeton University',
    'stanford': 'Stanford University',
    'cornell': 'Cornell University',
    'northwestern': 'Northwestern University',
    'vanderbilt': 'Vanderbilt University',
    'rice': 'Rice University',
    'emory': 'Emory University',
    'tufts': 'Tufts University',
    'northeastern': 'Northeastern University',
    'cu boulder': 'University of Colorado Boulder',
    'colorado boulder': 'University of Colorado Boulder',
    'pitt': 'University of Pittsburgh-Pittsburgh Campus',
    'university of pittsburgh': 'University of Pittsburgh-Pittsburgh Campus',
    'cal poly slo': 'California Polytechnic State University-San Luis Obispo',
    'cal poly san luis obispo': 'California Polytechnic State University-San Luis Obispo',
    'sdsu': 'San Diego State University',
    'tulane': 'Tulane University of Louisiana',
    'university of alabama': 'The University of Alabama',
    'utk': 'The University of Tennessee-Knoxville',
    'university of tennessee': 'The University of Tennessee-Knoxville',
    'uga': 'University of Georgia',
    'ucf': 'University of Central Florida',
    'wake forest': 'Wake Forest University',
    'villanova': 'Villanova University',
    'lehigh': 'Lehigh University',
    'drexel': 'Drexel University',
    'fordham': 'Fordham University',
    'syracuse': 'Syracuse University',
    'clemson': 'Clemson University',
    'howard': 'Howard University',
    'spelman': 'Spelman College',
    'morehouse': 'Morehouse College',
}
