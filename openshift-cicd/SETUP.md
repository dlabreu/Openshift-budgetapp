# OpenShift Native CI/CD Setup Guide
# BuildConfig + ImageStream + DeploymentConfig + GitHub Webhooks

---

## Overview of files

| File                   | What it does                                      |
|------------------------|---------------------------------------------------|
| imagestream.yaml       | Stores :test and :latest image tags internally    |
| webhook-secrets.yaml   | Secrets OpenShift uses to validate GitHub calls   |
| buildconfig-test.yaml  | Builds from test branch → pushes :test tag        |
| buildconfig-prod.yaml  | Builds from main branch → pushes :latest tag      |
| deploy-test.yaml       | DeploymentConfig + Service + Route for test ns    |
| deploy-prod.yaml       | DeploymentConfig + Service + Route for prod ns    |

---

## Step 1 — Create the prod namespace

```bash
oc new-project prod
```

---

## Step 2 — Apply all the OpenShift resources

Run these in your Dev Workspaces terminal from the repo root.
Make sure you have the openshift-cicd/ folder with all the YAML files.

```bash
# Apply in the admin-devspaces namespace first
oc project admin-devspaces

oc apply -f openshift-cicd/webhook-secrets.yaml
oc apply -f openshift-cicd/imagestream.yaml
oc apply -f openshift-cicd/buildconfig-test.yaml
oc apply -f openshift-cicd/buildconfig-prod.yaml
oc apply -f openshift-cicd/deploy-test.yaml

# Apply prod resources into the prod namespace
oc apply -f openshift-cicd/deploy-prod.yaml
```

Verify everything was created:
```bash
oc get buildconfig -n admin-devspaces
oc get imagestream -n admin-devspaces
oc get deploymentconfig -n admin-devspaces
oc get deploymentconfig -n prod
```

---

## Step 3 — Trigger the first build manually

The webhook isn't set up yet — trigger the first build by hand to confirm
everything works before wiring GitHub:

```bash
# Build from the test branch
oc start-build budgetapp-test -n admin-devspaces --follow

# Once that succeeds, check the pod came up
oc get pods -n admin-devspaces -w
```

---

## Step 4 — Get the GitHub Webhook URLs

OpenShift generates unique webhook URLs for each BuildConfig.
Run these commands to get them:

```bash
# Webhook URL for the test branch BuildConfig
oc describe bc/budgetapp-test -n admin-devspaces | grep -A2 "Webhook GitHub"

# Webhook URL for the main/prod BuildConfig
oc describe bc/budgetapp-prod -n admin-devspaces | grep -A2 "Webhook GitHub"
```

The URL will look like:
https://<your-cluster>/apis/build.openshift.io/v1/namespaces/test/buildconfigs/budgetapp-test/webhooks/budgetapp-test-webhook-secret-change-me/github

---

## Step 5 — Add Webhooks to GitHub

1. Go to https://github.com/dlabreu/Openshift-budgetapp
2. Click Settings → Webhooks → Add webhook

For the TEST webhook:
- Payload URL: the URL from Step 4 for budgetapp-test
- Content type: application/json
- Secret: budgetapp-test-webhook-secret-change-me
- Which events: Just the push event
- Click Add webhook

For the PROD webhook:
- Payload URL: the URL from Step 4 for budgetapp-prod
- Content type: application/json
- Secret: budgetapp-prod-webhook-secret-change-me
- Which events: Just the push event (a merged PR is a push to main)
- Click Add webhook

---

## Step 6 — Set up quay.io push (optional but recommended)

If you want the prod image also pushed to quay.io:

### Create a quay.io robot account
1. Log in to https://quay.io
2. Go to your account → Robot Accounts → Create Robot Account
3. Name it budgetapp_ci, give it Write access to the budgetapp repo
4. Copy the token

### Create the push secret in OpenShift
```bash
oc create secret docker-registry quay-push-secret \
  --docker-server=quay.io \
  --docker-username=<youruser>+budgetapp_ci \
  --docker-password=<robot-token> \
  -n admin-devspaces

# Link it to the builder service account so BuildConfig can push
oc secrets link builder quay-push-secret -n admin-devspaces
```

Then update buildconfig-prod.yaml output section to push to quay.io instead
of (or in addition to) the ImageStream:

```yaml
output:
  to:
    kind: DockerImage
    name: quay.io/<youruser>/budgetapp:latest
  pushSecret:
    name: quay-push-secret
```

Then re-apply:
```bash
oc apply -f openshift-cicd/buildconfig-prod.yaml
```

---

## Step 7 — Test the full pipeline

```bash
# Make a small change and push to test
echo "# test pipeline" >> README.md
git add README.md
git commit -m "test CI/CD pipeline"
git push origin test
```

Then watch the build trigger automatically:
```bash
oc get builds -n admin-devspaces -w
```

Once the build completes the DeploymentConfig auto-triggers a new deployment.
Get your URLs:
```bash
echo "Test:  https://$(oc get route budgetapp -n admin-devspaces -o jsonpath='{.spec.host}')"
echo "Prod:  https://$(oc get route budgetapp -n prod -o jsonpath='{.spec.host}')"
```

---

## How the full flow works end to end

1. You push code to the test branch
2. GitHub sends a webhook POST to OpenShift
3. OpenShift validates the secret and triggers budgetapp-test BuildConfig
4. BuildConfig clones your repo (test branch) and runs the Containerfile
5. Built image is pushed to ImageStream as :test
6. DeploymentConfig in admin-devspaces namespace detects the new :test tag
7. OpenShift automatically rolls out a new pod in the admin-devspaces namespace
8. You test the app at the test Route URL
9. Happy? Open a Pull Request from test → main on GitHub
10. Merge the PR
11. GitHub sends a webhook POST to OpenShift (push to main)
12. budgetapp-prod BuildConfig runs, pushes :latest to ImageStream
13. DeploymentConfig in prod namespace detects :latest changed
14. OpenShift rolls out the new pod in prod automatically
