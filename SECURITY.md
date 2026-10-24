# Security

Veritagnosis is used by high school students and holds their grades, essays
and family finances. This page covers what a downloaded copy protects, what
you need to do if you host it for other people, and how to report a problem.

## Downloading and running it on your own computer

Nothing private ships in this repository. When you download the ZIP or clone
it, you get code only. Your copy creates its own private pieces the first
time it runs:

- **Your own encryption keys.** `Veritagnosis.bat` / `Veritagnosis.command`
  writes a new `.env` with keys generated on your computer. No two copies
  share a key, and the file never leaves your machine. Back it up: without
  it, the encrypted parts of your database can't be read.
- **Your own database.** `data/veritagnosis.db` is created empty on first
  run. Nobody else's accounts or essays are in the download.
- **This computer only.** The app listens on `127.0.0.1`, so other devices on
  the same Wi-Fi (a school or library network, say) can't reach it. You open
  it at `http://localhost:3000` as usual.

`.env`, `data/`, every database file and every backup are listed in
`.gitignore`, so they can't be committed by accident. Never remove those
lines, and never paste the contents of `.env` anywhere.

### Sign-in codes without email

Every sign-in needs a six-digit code. If email isn't set up, the app runs in
**demo mode** and shows the code on screen, with a banner saying so. That's
fine on your own computer. Before real students use a shared or hosted copy,
set up email:

```
python scripts/manage.py email-setup
```

Use a Google *app password*, never an account's real password. It can be
revoked on its own at any time.

## Hosting it for other people

A hosted copy has to be reachable, so a few defaults must be changed on
purpose. See "Deploying" in the README for the full steps.

- Set `VG_HOST=0.0.0.0` so the server listens on the network (the Dockerfile
  already does this).
- Set `VG_ORIGIN` to the site's real address, for example
  `https://veritagnosis.example.com`. Without it, only localhost pages may
  connect.
- Serve it over HTTPS only.
- Set up email, so sign-in codes are sent instead of shown.
- Generate new keys for the server (`python scripts/manage.py init-keys`) and
  keep them in the host's secret settings, not in the repository.
- Add a rate limit on the sign-in and sign-up pages at your host.
- The session token is kept in the browser's local storage rather than an
  HttpOnly cookie. Know this before inviting people you don't know.

## What's protected inside the app

- Passwords are hashed with Argon2id and never stored.
- GPAs, test scores, essays, profiles, email addresses and aid figures are
  encrypted in the database with AES-256-GCM.
- Every sign-in needs a one-time code, and accounts lock after repeated wrong
  passwords.
- Session tokens are random, stored only as hashes, and expire.
- A strict Content-Security-Policy blocks outside scripts and `eval`.

## Reporting a problem

If you find a security issue, please don't open a public issue. Use
GitHub's **Report a vulnerability** button on the repository's Security tab,
which reaches the maintainer privately. Include what you found, how to
reproduce it, and what someone could do with it. You'll get a reply as soon
as possible.
