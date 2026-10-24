# Production image for Veritagnosis.
#
# One process, on purpose. The app stores state in SQLite and Reflex keeps
# per-session state in .states/ on local disk, so running two replicas behind a
# load balancer would split sessions across them and put two writers on one
# SQLite file. Scale this vertically, not horizontally.
#
# Build:  docker build -t veritagnosis .
# Run:    docker run -p 8000:8000 --env-file .env -v vg-data:/app/data veritagnosis

FROM python:3.12-slim AS build

# Reflex compiles the frontend with Bun/Node at build time, so that toolchain
# is needed here but not in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl unzip build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Compile the frontend now so container start is fast and a build error fails
# the build rather than the first request. The keys are placeholders that exist
# only for this step — config.py refuses to import without them, and nothing
# here touches real data.
RUN VG_FIELD_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))") \
    VG_INDEX_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))") \
    python -m reflex export --frontend-only --no-zip

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build --chown=app:app /app /app

# The SQLite file and its WAL sidecars live here. Mount a volume on it or the
# database is lost every time the container is replaced.
RUN mkdir -p /app/data && chown -R app:app /app/data
VOLUME ["/app/data"]

USER app
EXPOSE 8000

# Inside a container the server must listen on every interface, or the
# published port reaches nothing. On a laptop rxconfig.py defaults to
# 127.0.0.1 instead, so a downloaded copy is never visible to the rest of the
# network. VG_ORIGIN still has to be set to the site's real address at run time.
ENV VG_HOST=0.0.0.0

# No shell form: signals reach the process directly so the container stops
# cleanly and SQLite gets to checkpoint its WAL.
CMD ["python", "-m", "reflex", "run", "--env", "prod", "--backend-port", "8000"]
