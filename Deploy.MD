# BudgetApp — Container Build & Deploy Guide
# Dev Workspaces → OpenShift namespace

## Prerequisites

- You are inside a Dev Workspaces session with the repo cloned on the `test` branch
- `oc` CLI is logged in to your OpenShift cluster (`oc whoami` returns your user)
- `podman` is available (it is included in the universal-developer-image)
- You have replaced the files in your repo with the corrected versions from this PR

---

## Step 1 — Copy the corrected files into your repo

Replace these files with the corrected versions:

| File | What changed |
|---|---|
| `Containerfile` | Fixed base image, COPY path, CMD entry point |
| `devfile.yaml` | Fixed port (5000→8080), removed broken DB script, added build/push commands |
| `openshift-template.yaml` | Added Service, Route, data PVC, Secret; removed unused DB |
| `Openshift-App/requirements.txt` | Added gunicorn |

---

## Step 2 — Set your target namespace

```bash
# Switch to the namespace you want to deploy into
oc project <your-test-namespace>

# Verify
oc project -q
```

---

## Step 3 — Build the container image

Run the **build-image** command from the devfile, or manually:

```bash
IMAGE_REGISTRY="image-registry.openshift-image-registry.svc:5000"
NAMESPACE=$(oc project -q)
IMAGE_TAG="${IMAGE_REGISTRY}/${NAMESPACE}/budgetapp:latest"

podman build \
  --format=docker \
  -f Containerfile \
  -t "${IMAGE_TAG}" \
  .
```

Expected: you see layers being downloaded and built, ending with:
```
Successfully tagged image-registry.../budgetapp:latest
```

---

## Step 4 — Push the image to the internal registry

Run the **push-image** command from the devfile, or manually:

```bash
IMAGE_REGISTRY="image-registry.openshift-image-registry.svc:5000"
NAMESPACE=$(oc project -q)
IMAGE_TAG="${IMAGE_REGISTRY}/${NAMESPACE}/budgetapp:latest"

podman login \
  --username=$(oc whoami) \
  --password=$(oc whoami -t) \
  --tls-verify=false \
  "${IMAGE_REGISTRY}"

podman push --tls-verify=false "${IMAGE_TAG}"
```

---

## Step 5 — Deploy with the OpenShift template

Run the **deploy** command from the devfile, or manually:

```bash
NAMESPACE=$(oc project -q)
IMAGE_REGISTRY="image-registry.openshift-image-registry.svc:5000"
IMAGE_TAG="${IMAGE_REGISTRY}/${NAMESPACE}/budgetapp:latest"

oc process -f openshift-template.yaml \
  -p NAMESPACE="${NAMESPACE}" \
  -p IMAGE_TAG="${IMAGE_TAG}" \
  | oc apply -f -
```

This creates:
- A Secret (Flask secret key)
- A PVC (1Gi for /app/data JSON files)
- A Deployment (your app pod)
- A Service (internal networking)
- A Route (HTTPS external URL)

---

## Step 6 — Verify the deployment

```bash
# Watch the pod come up
oc get pods -w

# Once Running, get the public URL
oc get route budgetapp -o jsonpath='{.spec.host}'

# Check logs if there are issues
oc logs deployment/budgetapp
```

The app should be accessible at `https://<route-host>/`

---

## Troubleshooting

**Pod crashes immediately:**
```bash
oc logs deployment/budgetapp --previous
```
Look for `ModuleNotFoundError` (requirements not installed) or `FileNotFoundError` (wrong COPY path).

**ImagePullBackOff:**
```bash
oc describe pod <pod-name>
```
The image reference in the Deployment doesn't match what was pushed. Re-run Step 4 and 5.

**Permission denied on /app/data:**
The Containerfile already sets `chmod -R 777 /app/data` and `chmod -R g=u /app` for OpenShift arbitrary UIDs. If you see this error, check that the PVC was created and mounted correctly:
```bash
oc get pvc budgetapp-data
oc describe pod <pod-name> | grep -A5 Volumes
```

**Route returns 503:**
The Service selector doesn't match the pod label. Verify:
```bash
oc get endpoints budgetapp
```
Should show an IP:port entry. If empty, the pod label `app: budgetapp` is mismatched.