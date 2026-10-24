# Veritagnosis

Gamified college-application companion for high schoolers. Python + Reflex +
SQLite. Five themes, an avatar builder, breathing exercises, an essay lab with
a real scoring engine, and an application tracker.

---

## Running it

Extract everything from the zip, keeping the files together, then
**double-click the one for your computer**:

| Your computer | Double-click |
|---|---|
| Windows | **`Veritagnosis.bat`** |
| Mac | **`Veritagnosis.command`** |
| Linux | **`Veritagnosis.command`** |

That is the whole install. The first run takes a few minutes — it builds a
private environment, installs the pinned dependencies, generates your
encryption keys, creates the database and compiles the web page. Every run
after that starts in seconds, and running it again is the normal way to start
the app.

When it is ready your browser opens at **<http://localhost:3000>**. Leave the
window open; closing it stops the app.

**This needs Python 3.11 or newer.** The launcher checks, and tells you where
to get it if you do not have it. If you would rather hand someone a file that
needs nothing at all, see *Handing it to someone else* below.

### Mac: if double-clicking opens a text editor

Then the file lost its execute permission in the zip — some zip tools drop it.
One command fixes it for good:

```
chmod +x Veritagnosis.command
```

Right-click the folder → *New Terminal at Folder*, paste that, press Enter,
then double-click as normal.

### Other things the launcher can do

Pass these after the file name (`Veritagnosis.bat reset`, or
`./Veritagnosis.command reset`):

| option | what it does |
|---|---|
| *(nothing)* | Start the app. Use this. |
| `dev` | Hot reload, for editing the code. |
| `reset` | Rebuild the web page from scratch. Try this if it looks wrong. |
| `check` | Set everything up, verify it, and stop without starting. |

Under the hood all of these run `start.py`, which is where the actual logic
lives — the two launchers are a handful of lines each so that Windows and Mac
cannot drift apart.

---

## Handing it to someone else

If the person receiving this should not have to install anything at all — not
even Python — give them a built app instead of the source.

### The easy way: let GitHub build both

Push the repo to GitHub, then:

```
git tag v1.0.0
git push origin v1.0.0
```

`.github/workflows/build.yml` builds on GitHub's own Windows **and** macOS
machines and attaches both results to the release page:

| Your computer | Download |
|---|---|
| Windows | `Veritagnosis.exe` |
| Mac | `Veritagnosis-macOS.zip` (unzip it first) |

They download one file and double-click it. No Python, no installs, no
terminal. **You do not need a Mac for the Mac build** — GitHub rents one.

### The manual way

On the machine whose platform you are building for:

```
python build_exe.py
```

Windows gives you `dist/Veritagnosis.exe`; macOS gives you
`dist/Veritagnosis.app`; Linux gives you `dist/Veritagnosis`.

**There is no single file that runs on both Windows and macOS.** A Windows
executable is PE format and a Mac one is Mach-O — no file is both. PyInstaller
also bundles the interpreter it is run by and cannot cross-compile, which is
why each platform's build happens on that platform, and why the GitHub route
above exists.

### Warn them about the first open

Neither build is code-signed, so both systems assume the worst about an
unknown download. This is not optional and not a sign anything is wrong:

- **Windows** — "Windows protected your PC" → **More info** → **Run anyway**.
- **Mac** — **right-click the app → Open**, then **Open** again. Do *not*
  double-click it first: that shows *"Veritagnosis is damaged and can't be
  opened"*, which sounds like a corrupt download but is just Gatekeeper
  refusing an unsigned app. Right-click → Open is the documented way past it.

Only certificates remove those prompts — an Apple Developer certificate
(US$99/year, plus notarisation) and a Windows code-signing certificate.

### Where their work is saved

Next to the app, in a `data` folder, with their keys in `.env` — so the whole
thing stays portable and visible. If the app is somewhere the system protects
(`/Applications`, `Program Files`, a read-only disk), it falls back to the
normal per-user location instead:

| | |
|---|---|
| Windows | `%LOCALAPPDATA%\Veritagnosis` |
| Mac | `~/Library/Application Support/Veritagnosis` |
| Linux | `~/.local/share/veritagnosis` |

Everything the app says at startup is also written to `veritagnosis.log` beside
the data, because a Mac app has no console window to print to.

To include the full college catalogue in the build, import it first — see
*The college catalogue* below — then `python scripts/manage.py seed-colleges`
before building.

---

## Signing in

**Every sign-in needs two things**: your password, and a six-digit code. The
password alone will never open an account. This is not a setting and cannot be
turned off.

Where the code goes depends on whether email is configured.

### Without email — demo mode

Out of the box there is no mail server, so the code is **shown on screen** with
a yellow "Demo mode" banner. The app is immediately usable, which is what you
want for a demo.

Be clear-eyed about what this means: in demo mode, anyone who can see the
screen can sign in. It is fine for evaluating the app. It is not fine for real
student work.

### With email — the real thing

```
python scripts/manage.py email-setup
```

It walks you through creating a Gmail **app password** (Google Account →
Security → 2-Step Verification → App passwords) and writes it to `.env`. From
then on codes are emailed, the demo banner disappears, and 2FA is real.

Test it with `python scripts/manage.py email-test`.

**Using a dedicated sending account.** Make a new Google account for the app
(say `veritagnosis.app@gmail.com`), turn on 2-Step Verification, create an app
password for it, and put that in `.env`:

```
VG_SMTP_USER=veritagnosis.app@gmail.com
VG_SMTP_PASSWORD=aaaabbbbccccdddd
VG_MAIL_FROM_NAME=Veritagnosis
```

No code changes. That address is only ever the **sender** — each code is
delivered to whatever address the student typed when they signed up, which is
read from their own account row. One sending account serves everybody.

---

## The college catalogue

Out of the box the app knows about two dozen colleges, read by hand out of each
institution's own Common Data Set — those are the most reliable admissions
numbers that exist, and each one links to the PDF it came from.

That is not enough for a real student's list. To load every college in the
country:

1. Go to <https://collegescorecard.ed.gov/data/> (free, no account needed)
2. Download **"Most Recent Institution-Level Data"** and unzip it
3. Run:

```
python scripts/manage.py import-colleges path/to/Most-Recent-Cohorts-Institution.csv
```

That imports roughly 2,000 bachelor's-degree institutions with admission rate,
SAT/ACT ranges, cost, tuition and average net price. Importing again updates in
place rather than duplicating, so you can refresh when a new release comes out.

**Which source wins.** When a college is in both, the hand-read Common Data Set
entry is used, because it is better data. Scorecard rows are marked
`confidence: medium` and carry the real Scorecard URL for that institution, so
every number on screen can still be checked. Nothing is ever invented: a figure
the Scorecard suppresses or omits stays empty rather than becoming a zero.

It is skipped for institutions that are closed, award mostly certificates, or
have no undergraduates — a college applicant is not choosing between those.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'reflex_components_lucide'`** — or any
other `ModuleNotFoundError` coming from inside Reflex rather than from this
project.

This means the app was started with a Python that is not the one in `.venv`.
Typing `reflex run` directly does that, because it uses whichever `reflex` is
first on your PATH, and a system-wide Reflex install is often incomplete.

Use the launcher instead — `Veritagnosis.bat` on Windows,
`Veritagnosis.command` on Mac. Both run `start.py`, which always starts the app
with the interpreter inside `.venv` whatever Python launched it, and verifies
that environment can import Reflex before trying.

**Anything else environment-shaped** — delete `.venv` and double-click the
launcher again. It rebuilds from the pinned versions in `requirements.txt`.

```
Windows:  rmdir /s /q .venv
macOS:    rm -rf .venv
```

**The frontend will not build.** Reflex compiles the web page with its own
bundled toolchain. If that fails, install Node.js LTS from
<https://nodejs.org>, then run the launcher with `reset`
(`Veritagnosis.bat reset`, or `./Veritagnosis.command reset`).

---

## Running it in Docker instead

If you would rather not touch Python at all, and have Docker:

```
docker build -t veritagnosis .
docker run -p 8000:8000 --env-file .env -v vg-data:/app/data veritagnosis
```

Generate `.env` first with `python scripts/manage.py init-keys`, or copy
`.env.example` and fill it in. The named volume matters — without it the
database is lost each time the container is replaced.

---

## Folder layout

```
Veritagnosis/
├── rxconfig.py              app_name must stay "veritagnosis"
├── requirements.txt
├── .env                     SECRETS — gitignored, never commit
├── .env.example             committed; variable names only, no values
├── .gitignore
├── README.md
├── SECURITY.md              threat model, what is protected, what is not
│
├── assets/                  served at / by Reflex
│   ├── theme.css            GENERATED — do not hand-edit
│   └── motifs/              per-theme SVG artwork
│
├── data/                    gitignored
│   └── veritagnosis.db      SQLite file
│
├── design/                  theme + screen tooling, not shipped to users
│   ├── build_all.py         ONE COMMAND rebuilds everything below
│   ├── build_themes.py      palettes -> tokens, enforces WCAG AA
│   ├── build_motifs.py      SVG artwork -> data URIs
│   ├── build_showcase.py    -> themes.html
│   ├── build_screens.py     -> screens.html
│   ├── src_components.css   hand-written CSS (the editable half of theme.css)
│   ├── themes.html          preview: themes + components
│   └── screens.html         preview: signup, avatar, meditation
│
├── scripts/
│   └── manage.py            init-keys, init-db, demo-user, check
│
└── veritagnosis/            the app package
    ├── __init__.py
    ├── veritagnosis.py      app entry; registers pages
    ├── config.py            env loading, key management, fail-fast
    ├── db.py                engine, connection hardening, init_db()
    ├── models.py            SQLModel tables; encrypted columns declared here
    │
    ├── security/
    │   ├── passwords.py     Argon2id hashing
    │   ├── crypto.py        AES-256-GCM field encryption, blind indexes
    │   ├── auth.py          register, login, sessions, email codes
    │   └── audit.py         append-only security event log
    │
    ├── content/             static data, no logic
    │   ├── quotes.py        theme-tagged quote pools
    │   └── eligibility.py   age/gender -> factual eligibility pointers
    │
    ├── ui/                  design system + reusable components
    │   ├── theme.py         tokens (T), ThemeState, shell(), hero()
    │   ├── avatar.py        9-layer SVG avatar
    │   └── breathing.py     breathing patterns + per-theme figures
    │
    ├── states/              one State class per feature area
    └── pages/               one file per screen
```

### Why it is split this way

- **`security/` is its own package** so every security decision is in four files
  you can read end to end, rather than scattered through page handlers.
- **`content/` holds no logic**, so quotes and eligibility copy can be edited
  without touching code that runs.
- **`ui/` has no database access** and **`pages/` has no SQL** — pages call
  states, states call security and models. Keeping SQL out of the UI layer is
  what makes "is this query parameterised?" answerable by looking in one place.
- **`design/` is build tooling, not app code.** It never ships to a user and the
  app never imports from it. It imports *from* the package, so quotes and avatar
  parts have exactly one definition.

## Themes

Five: serenity (default), superhero, cafe, astronomy, terminal. Same layout
everywhere — only colors, artwork, display font and quote pool change.

`assets/theme.css` is generated. To change a palette or the artwork:

```
cd design
python build_all.py
```

`build_themes.py` hand-picks only base colors; tints, text-on-tint variants and
button label colors are derived and contrast-checked. **The build fails if
anything drops below WCAG AA.** Hand-picked hexes usually miss.

## Security

Short version: Argon2id passwords, AES-256-GCM
on sensitive columns, hashed session tokens with expiry and lockout, secrets
from `.env` with a fail-fast config, and mandatory two-factor sign-in. The
details are below.

```
python scripts/manage.py check
```

## Still to build

- Reflex pages for the screens (data modules, components and CSS are done;
  `design/screens.html` is the plain-JS preview).
- Remaining screens: onboarding flow, home, essay coach, recommendations,
  application progress.
- Ambient audio (player planned, tracks not sourced).


---

# Security

## Security

How Veritagnosis protects student data, and — just as importantly — what it
does not protect against.

This is a school project. Everything below is real and working, but "we thought
about it carefully" is not the same as "it has been audited." The limits section
is the honest part.

---

### What is stored, and what it is worth to an attacker

| Data | Sensitivity | Protection |
|---|---|---|
| Password | Critical | Argon2id hash. Never stored, never logged, not recoverable. |
| Session token | Critical | Random 256-bit, only its SHA-256 is stored. |
| Email | High | AES-256-GCM encrypted + blind index for lookup. |
| Age, gender | High — a minor's personal data | AES-256-GCM encrypted. |
| GPA, test scores | High — embarrassing, competitively useful | AES-256-GCM encrypted. |
| School notes | Medium | AES-256-GCM encrypted. |
| Username | Low, semi-public | Plaintext (needed for login and uniqueness). |
| School names, deadlines, status | Low | Plaintext (queried and sorted constantly). |

The line between encrypted and plaintext is a judgement call: **encrypt what
would hurt if a classmate read it, keep queryable what has to be queried.**
Encrypting the deadline column would mean decrypting every row just to sort by
date, for almost no gain.

---

### Passwords — `veritagnosis/security/passwords.py`

**Argon2id** via `argon2-cffi`, at the OWASP baseline: 19 MiB memory, 2
iterations, parallelism 1.

Argon2id is memory-hard. bcrypt and PBKDF2 are only *computation*-hard, so an
attacker with GPUs parallelises them cheaply; Argon2 makes every guess pay for
real RAM. It is the Password Hashing Competition winner and OWASP's current
first choice.

- Every hash is uniquely salted — identical passwords produce different hashes.
- Parameters are stored inside the hash string, so raising them later does not
  invalidate old hashes. On login, `check_needs_rehash` spots a weak stored hash
  and it is transparently upgraded.
- Input is capped at 128 characters. Feeding an unbounded string to a
  memory-hard function is a denial-of-service vector.
- `verify_password` never raises on a bad password, so no caller can leak
  "user exists" through an exception path.

---

### Encryption at rest — `veritagnosis/security/crypto.py`

**Two layers, because the second one keeps working after the first fails.**

1. **Whole-file** (optional): SQLCipher via `sqlcipher3-binary`, which ships
   prebuilt Windows wheels so no compiler is needed. Set `VG_ENCRYPT_DB=1`.
   Protects the `.db` file if it is copied off the disk.
2. **Field-level** (always on): AES-256-GCM per value. Protects individual
   columns even from someone who already has an open connection — SQL injection,
   a decrypted backup, or anyone running `SELECT * FROM user`.

Details that matter:

- **GCM is authenticated.** Tampering with a stored value is detected on read
  rather than silently returning wrong data.
- **Fresh 96-bit random nonce per write.** The same GPA encrypted twice produces
  different ciphertext, so nobody can tell which students share a value.
- **Associated data binds each ciphertext to its column.** A value cannot be
  lifted out of `user.gender` and pasted into `user.gpa`.
- **Keys are derived with HKDF**, and the field key and index key are
  domain-separated, so leaking one does not compromise the other.
- The `Encrypted` SQLAlchemy type means models declare intent once and no call
  site can forget to encrypt.

#### Blind indexes

Encrypted values differ every write, so `WHERE email = ?` cannot work. A blind
index — HMAC-SHA256 of the value, truncated — makes equality lookup possible.

**It is deterministic, so equal plaintexts produce equal indexes.** That leaks
which rows share a value, and for a low-cardinality column an attacker can just
compute the HMAC of every possible input and match them. So blind indexes are
used on `email` and never on `gender` or `age`.

---

### Authentication — `veritagnosis/security/auth.py`

- **No account enumeration.** Unknown username and wrong password return the
  identical message. When the username does not exist, `dummy_verify()` burns
  the same CPU and memory as a real check, so response time does not give it
  away either.
- **Session tokens**: 256 bits from `secrets.token_urlsafe`, stored as SHA-256
  only. A database leak cannot be replayed as a live session. (SHA-256 rather
  than Argon2 here on purpose: slow hashing exists to make *guessable* secrets
  expensive, and a 256-bit random token has nothing to guess.)
- **Expiry and idle timeout**: absolute 7 days, idle 24 hours, both configurable.
- **Lockout**: 8 failed attempts locks the account for 15 minutes.
- **Password change revokes every other session**, so a stolen session dies.
- **Two factors, every sign-in.** `login()` has no success path: a correct
  password raises `SecondFactorRequired` and mints no session.
  `complete_login()` is the only function that creates one. There is no flag
  that disables this, because a second factor you can switch off is a second
  factor an attacker can switch off.
- **The browser holds only an opaque handle** between the two steps — 256
  random bits, expiring in 10 minutes. Not the user id, and not the email
  address; an earlier version kept both in local storage and trusted them on
  the way back in.
- **Codes are six digits**, which is a million guesses — nothing against an
  unkeyed hash. They are stored as a **keyed HMAC** (`crypto.code_mac`) bound
  to their own challenge, so a leaked database yields no live codes and a code
  minted for one sign-in cannot be replayed against another. Single-use,
  10-minute expiry, 5 attempts. Comparison uses `hmac.compare_digest`.
- **Resending rotates the handle**, so "send a new code" cannot be used to
  reset the attempt counter.
- **Both halves are logged separately.** A run of `login_password_ok` with no
  matching `login` is what a stolen password looks like, and it is invisible
  if you only record successes.
- **Demo mode** (no mail server configured) shows the code on screen. It is
  never enabled by a setting, only by the absence of mail config; it is
  announced in a banner; and a *configured* mailer that fails leaves the code
  out of the browser, so an outage cannot become a vulnerability.

---

### Secrets — `veritagnosis/config.py`

Keys load from `.env`, which is gitignored. **The app refuses to start with a
missing, placeholder, or too-short key** rather than falling back to a default.
A hardcoded default key is the single most common way a careful project leaks
everything: it ships in the repo and every deployment shares it.

`.env.example` is committed so the variable names are discoverable; it contains
no real values.

Losing `VG_FIELD_KEY` means every encrypted column is permanently unreadable.
That is the design. Back it up somewhere that is not the repository.

---

### Database hardening — `veritagnosis/db.py`

Three PRAGMAs SQLite does not set for you:

- `foreign_keys=ON` — SQLite ignores foreign keys unless asked, **per
  connection**. Without it, deleting a user silently orphans their rows.
- `journal_mode=WAL` — readers stop blocking writers, better crash recovery.
- `secure_delete=ON` — overwrites freed pages. The difference between a deleted
  account being gone and being recoverable with a hex editor.

SQL injection is handled by using SQLModel/SQLAlchemy exclusively. Every query
is parameterised; no string-formatted SQL exists in this codebase.

---

### Reflex-specific: what reaches the browser

This is the trap most Reflex apps fall into.

**Any normal State var is synchronised to the client.** Putting a password hash,
a session token, or another student's data in a regular var ships it to the
browser, where it is visible in devtools regardless of what the UI renders.

Two rules:

1. **Backend-only vars are prefixed with an underscore** (`_session_token`).
   Reflex does not synchronise these to the frontend. Every secret in State
   gets one.
2. **`@require_login` is a redirect, not a protection.** `reflex-local-auth`
   says this in its own README: page-level guards still ship the page source.
   Private data must be fetched inside an event handler that checks the
   authenticated user, then assigned to a var.

---

### Limits — what this does NOT protect against

Stated plainly, because a security document that only lists wins is marketing.

- **Not audited.** Hand-rolled auth, written carefully, is still hand-rolled
  auth. For anything holding real students' data, use a vetted library
  (`reflex-local-auth`) and get the design reviewed.
- **Keys live next to the data.** `.env` sits on the same disk as the database,
  so anyone who can read the disk gets both. Real separation needs an OS keychain
  or a KMS. This is the biggest gap and it is inherent to a local app.
- **A running process holds decrypted data in memory.** Field encryption
  protects data at rest, not a compromised machine.
- **No transport security in local dev.** `reflex run` serves plain HTTP.
  Deploying means HTTPS, secure/httponly/samesite cookies, and a real CSRF
  story — none of which is configured here.
- **No rate limiting on registration** or per-IP throttling. Lockout is
  per-account, so an attacker spraying one password across many usernames is not
  slowed down.
- **Passwords are only checked against a hardcoded list** of obvious ones. A
  real check uses a breached-password corpus (the Pwned Passwords k-anonymity
  API).
- **Field encryption does not bind to the row id**, only the column. Someone
  with write access could swap values between rows of the same column. Fixing it
  needs the row id in the associated data on update.
- **No backups, and no recovery.** Lose the key or the file and the data is
  gone.
- **Minors' data carries legal weight** (COPPA under 13, and school-context data
  can implicate FERPA). Signup is capped at 13+ to stay clear of COPPA, but a
  real deployment serving minors needs actual legal review, not a code comment.


---

# Deploying

## Putting Veritagnosis online

The goal: someone you send a link to opens it in a browser and it works. No
Python, no install, nothing to configure. That means the app runs on a server
somewhere and they get a URL.

Everything below except the final command has already been done. Pick one path.

---

### Before either path: generate the keys

The app refuses to start without its two encryption keys, on purpose — there is
no default, because a default key is the same as no encryption.

```bash
python scripts/manage.py init-keys
```

That writes `VG_FIELD_KEY` and `VG_INDEX_KEY` into `.env`. **Keep them.** They
decrypt every GPA, test score, essay and aid figure in the database. If you lose
them, that data is gone — not recoverable, by design. If you rotate them, the
existing rows stop decrypting.

`.env` is gitignored and must stay that way.

---

### Path A — Reflex Cloud (simplest)

Made for exactly this, and the app is already shaped for it.

```bash
pip install reflex           # if you haven't
reflex login                 # opens a browser, free account
reflex deploy \
  --env VG_FIELD_KEY="<the value from .env>" \
  --env VG_INDEX_KEY="<the value from .env>" \
  --env VG_HOST="0.0.0.0" \
  --env VG_ORIGIN="https://<the-url-it-gives-you>"
```

The first deploy prints your URL. That URL is what you send.

`VG_ORIGIN` is a chicken-and-egg: you do not know the URL until the first
deploy. Deploy once without it, note the URL, then run `reflex deploy` again
with it set. Until you do, the backend accepts websocket connections from any
origin.

---

### Path B — any host that runs a container

A `Dockerfile` is in the repo. Works on Railway, Render, Fly.io, or your own
box.

```bash
docker build -t veritagnosis .
docker run -p 8000:8000 --env-file .env \
  -e VG_ORIGIN="https://your-domain" \
  -v vg-data:/app/data \
  veritagnosis
```

**Honest note:** this Dockerfile has not been built and run end to end — the
environment it was written in had no Docker daemon. The Python install, the
frontend build step and the run command inside it are each verified working;
the assembly of them is not. Expect to iterate once on the first build.

Two things that matter on any host:

- **Mount a volume on `/app/data`.** That is where the SQLite file lives.
  Without it, every student account is wiped each time the container restarts,
  which on most hosts is every deploy.
- **Run exactly one instance.** SQLite has one writer, and Reflex keeps session
  state on local disk. Two replicas behind a load balancer will split sessions
  and contend for the database file. Scale the instance up, not out.

---

### Environment variables

| Variable | Required | What it does |
|---|---|---|
| `VG_FIELD_KEY` | yes | Encrypts GPA, scores, age, gender, essays, aid figures |
| `VG_INDEX_KEY` | yes | Derives blind indexes so encrypted email stays searchable |
| `VG_ORIGIN` | **in production** | Which origins may open a websocket. Comma-separated. Defaults to localhost only — set it to your real URL |
| `VG_HOST` | **in production** | Which network interface to listen on. Defaults to `127.0.0.1`, so a copy running on a laptop is invisible to the rest of the Wi-Fi. A hosted copy needs `0.0.0.0` (the Dockerfile sets it) |
| `VG_DB_URL` | no | Defaults to `sqlite:///data/veritagnosis.db` |
| `VG_DEBUG` | no | Leave unset. `1` turns on SQL echo |
| `VG_SMTP_USER` / `VG_SMTP_PASSWORD` | no | Email verification codes. Without them, signup still works but no code is sent |

---

### Before you share the link widely

Two things are known-unfinished and worth knowing about, because the users are
minors and the app holds their grades, essays and family finances.

**1. The session token is in `localStorage`, not an HttpOnly cookie.**
`states/auth_state.py` keeps it in browser storage that JavaScript can read.
Any cross-site-scripting bug anywhere in the app — now or added later — hands
an attacker a working session. There is a Content-Security-Policy in place, but
it has to allow inline script for Reflex's own hydration, so it does not close
this off. Fixing it properly means moving the token to a server-set
HttpOnly/Secure/SameSite cookie, which is a real change to the auth flow rather
than a setting. Worth doing before this is used by people you do not know.

**2. There is no rate limiting on login or signup.** Account lockout is
per-account, so trying one password against a thousand usernames is not
slowed down, and nothing throttles mass signups. Most hosts can add a rate
limit at the edge in a few clicks; do that.

Neither is a problem for showing the app to a few people. Both matter if it
goes anywhere public.
