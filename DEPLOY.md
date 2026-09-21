# Deploying Brookies to Azure

Architecture, chosen for lowest cost given the ML backend (torch + transformers +
a baked-in FinBERT model — too heavy for Azure Functions' Consumption plan):

- **Frontend**: Azure Static Web Apps, Free tier — `frontend/`.
- **Backend**: Azure Container Apps, Consumption plan, `minReplicas: 0` (scales
  to zero and costs ~$0/month when idle; a request after idle time pays a
  ~20-60s cold start while the container boots and loads the models) —
  `backend/Dockerfile`.
- **Registry**: GitHub Container Registry (ghcr.io), package set **public** so
  Container Apps can pull the image without any registry credentials. The
  image contains no secrets — just app code and the public FinBERT model — so
  this is safe.
- **Infra as code**: `infra/main.bicep`.

None of this touches Pantry or Structura — everything below is scoped to this
repo's own resource group.

## One-time setup

Run these once per environment. `<owner>` is your GitHub username/org (`redrupm`
for this repo's current `origin`), `<rg>` is the resource group name you pick
(examples below use `brookies-rg`).

### 1. Resource group

```
az group create -n brookies-rg -l eastus2
```

Pick a region that supports Container Apps; `eastus2` and `westus2` are safe
defaults.

### 2. Push the first backend image

The Container App needs an image to reference before it can be created, so
build and push once by hand before the first `az deployment group create`:

```
cd backend/..   # repo root (brookies/)
docker build -f backend/Dockerfile -t ghcr.io/<owner>/brookies-backend:latest .
echo $GH_PAT | docker login ghcr.io -u <owner> --password-stdin
docker push ghcr.io/<owner>/brookies-backend:latest
```

(`$GH_PAT` needs `write:packages` scope, or use `gh auth token` if the GitHub
CLI is already authenticated with that scope.)

Then on GitHub: **repo -> Packages -> brookies-backend -> Package settings ->
Change visibility -> Public**. This is what lets Container Apps (and anyone)
pull the image with no credentials configured anywhere.

### 3. Deploy the infra

Edit `infra/main.parameters.json` if `<owner>` isn't `redrupm`, then:

```
az deployment group create \
  -g brookies-rg \
  -f infra/main.bicep \
  -p infra/main.parameters.json
```

Note the two outputs: `staticWebAppName` and `backendUrl`.

### 4. Wire up GitHub Actions

**Secrets** (repo Settings -> Secrets and variables -> Actions -> Secrets):

- `AZURE_STATIC_WEB_APPS_API_TOKEN` — from:
  ```
  az staticwebapp secrets list --name brookies-web -g brookies-rg --query "properties.apiKey" -o tsv
  ```
- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` — from an Azure
  AD app registration used for OIDC login (no client secret needed):
  ```
  az ad app create --display-name brookies-gh-actions
  az ad sp create --id <appId-from-above>
  az role assignment create \
    --assignee <appId> \
    --role "Container Apps Contributor" \
    --scope /subscriptions/<subscriptionId>/resourceGroups/brookies-rg
  az ad app federated-credential create --id <appId> --parameters '{
    "name": "brookies-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<owner>/brookies:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
  ```

**Variables** (same page, Variables tab):

- `BACKEND_API_URL` — the `backendUrl` output from step 3 (e.g.
  `https://brookies-backend.<env-id>.eastus2.azurecontainerapps.io`).
- `AZURE_RESOURCE_GROUP` — `brookies-rg`.

### 5. Push to `main`

`deploy-frontend.yml` and `deploy-backend.yml` each trigger on changes to
their own paths (`frontend/**` and `backend/**` + `requirements.txt`
respectively), so a normal push only redeploys what actually changed.

## Cost expectations

- Static Web App Free tier: $0.
- Container Apps Consumption: $0 while idle (`minReplicas: 0`); billed per
  vCPU-second and GiB-second only while handling requests. The Consumption
  plan's monthly free grant (180,000 vCPU-seconds / 360,000 GiB-seconds) is
  very unlikely to be exceeded by personal-scale traffic.
- GHCR: $0 (public packages are free).
- Log Analytics: capped at 1GB/day ingestion in the Bicep template, well
  within its own free monthly grant for an app this size.

Total: effectively **$0/month** at low/personal traffic, plus a cold-start
delay on the first request after an idle period.
