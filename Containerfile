# Fedora 40 base — the f39/python3:3.9 tag does not exist on the registry.
# We use the full Fedora 40 image and install Python 3.11 ourselves.
FROM registry.fedoraproject.org/fedora:40

# ── Labels (good practice for OpenShift image metadata) ──────────────────────
LABEL name="budgetapp" \
      version="1.0" \
      description="Budget tracking Flask app"

# ── System packages ───────────────────────────────────────────────────────────
# Run as root only for dnf installs, then drop back to non-root immediately.
USER 0

RUN dnf install -y \
        python3.11 \
        python3.11-pip \
        python3.11-devel \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
# Copy requirements first so Docker layer-caching works: this layer is only
# rebuilt when requirements.txt changes, not every time you edit main.py.
COPY Openshift-App/requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
# The actual app lives inside the Openshift-App/ subdirectory.
# We copy its contents directly into /app so that templates/, static/,
# data/, and main.py are all at the expected relative paths.
COPY Openshift-App/ .

# ── Data directory ────────────────────────────────────────────────────────────
# Create the data directory and give it open permissions so the OpenShift
# arbitrary-UID runtime can write JSON files there.
# A PersistentVolumeClaim will be mounted at /app/data in the cluster.
RUN mkdir -p /app/data \
    && chmod -R 777 /app/data

# ── OpenShift non-root user ───────────────────────────────────────────────────
# OpenShift runs containers as a random UID in the root group (GID 0).
# Giving group-write permissions on /app lets that arbitrary UID function.
RUN chown -R 0:0 /app \
    && chmod -R g=u /app

USER 1001

# ── Runtime ───────────────────────────────────────────────────────────────────
EXPOSE 8080

# Use the correct entry-point file: main.py (NOT app.py).
CMD ["python3.11", "main.py"]