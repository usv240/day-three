# Day Three integration beta

The `/v1` API is an optional, key-protected de-identified integration sandbox. It does not change
the public judge demo.

## Provision a key

```bash
cd app
python scripts/create_beta_key.py --tenant clinic_one --label "Clinic one"
```

The command prints a plaintext key once and a JSON object containing only its SHA-256 digest.
Give the plaintext value to the intended caller. Save the JSON temporarily outside the repository,
or under the ignored `.beta-keys/` directory, as `keys.json`.

```bash
gcloud secrets create day-three-beta-api-keys --data-file=.beta-keys/keys.json
gcloud secrets add-iam-policy-binding day-three-beta-api-keys \
  --member=serviceAccount:sa-reason@agentic-fleet-2026.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
gcloud iam roles create betaModelPredictor \
  --project=agentic-fleet-2026 \
  --title="Beta model predictor" \
  --permissions=aiplatform.endpoints.predict \
  --stage=GA
gcloud projects add-iam-policy-binding agentic-fleet-2026 \
  --member=serviceAccount:sa-reason@agentic-fleet-2026.iam.gserviceaccount.com \
  --role=projects/agentic-fleet-2026/roles/betaModelPredictor
BETA_API_SECRET=day-three-beta-api-keys bash deploy.sh
```

The custom role grants only model prediction. It does not grant model, endpoint, dataset, job, or IAM management. Create it once per project.

For an existing secret, use `gcloud secrets versions add` instead of `secrets create`. Merge all
active hash entries into one JSON object before adding the version. Revoke a key by removing its
digest, adding a new secret version, and deploying a new revision.

## Contract

- Header: `X-API-Key`
- Scope: `day-three:use`
- Input: de-identified text and a `SUBJECT-*` pseudonym
- Storage: cumulative structured counts only; no raw report text
- Isolation: the key-derived tenant selects an opaque facility and its own antibiogram
- Safety: no orders, doses, prescribing, paging, or chart mutation

The app rejects obvious direct identifiers and requires an explicit de-identification
acknowledgement. That gate reduces accidental misuse but does not certify arbitrary text as
de-identified. Do not use this hackathon beta for protected health information.

Cloud Run is capped at three instances in the deployment script. For a larger external program,
place API Gateway in front of `/v1` and apply per-consumer quotas before issuing more keys.
