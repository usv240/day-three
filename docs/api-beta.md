# Day Three integration beta

The public judge workflow remains credential-free. The `/v1` API is a separate, key-protected
integration surface with server-derived tenant isolation.

## Get a temporary key from the website

1. Ask the project owner for a private invitation code.
2. Open [https://day-three-109051079423.us-central1.run.app/developer](https://day-three-109051079423.us-central1.run.app/developer).
3. Choose a lowercase workspace ID and a human-readable label.
4. Accept the project-specific safety contract.
5. Generate the key, save it immediately, and run the built-in connection test.
6. Open [the interactive API reference](https://day-three-109051079423.us-central1.run.app/docs) for schemas and operations.

Temporary keys expire after 168 hours. The plaintext value is returned once and remains only in
page memory. Firestore stores its SHA-256 digest, project, tenant, scope, issuance time, expiry, and
optional revocation time. The holder can revoke the key immediately with `DELETE /v1/key`.

This is invite-gated self-service, not anonymous public issuance. The invitation code protects the
project's model and infrastructure budget. Rotate it immediately if it is exposed.

## Configure website issuance

Generate a separate invitation code for this project:

```bash
cd app
python scripts/create_enrollment_code.py
```

Save the printed hash, never the plaintext invitation code, in an ignored local file such as
`.beta-keys/enrollment-hash.txt`. Create a regional Secret Manager secret and grant only the
Cloud Run service account access:

```bash
gcloud secrets create day-three-beta-enrollment \
  --replication-policy=user-managed \
  --locations=us-central1 \
  --data-file=.beta-keys/enrollment-hash.txt
gcloud secrets add-iam-policy-binding day-three-beta-enrollment \
  --member=serviceAccount:sa-reason@agentic-fleet-2026.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
BETA_API_SECRET=day-three-beta-api-keys \
BETA_ENROLLMENT_SECRET=day-three-beta-enrollment \
bash deploy.sh
```

The deployment mounts the hash as `BETA_ENROLLMENT_CODE_HASH` and pins
`BETA_DEVELOPER_KEY_TTL_HOURS=168`. Neither plaintext API keys nor plaintext invitation codes
belong in Cloud Run configuration, source control, screenshots, or logs.

## Provision an operator-managed key

For a longer controlled beta, generate a key directly:

```bash
cd app
python scripts/create_beta_key.py --tenant clinic_one --label "Clinic one"
```

Store the printed hash-only JSON in the `day-three-beta-api-keys` Secret Manager secret. Give the
plaintext key only to its intended caller. For an existing secret, add a new version containing all
active digests. Revoke one of these operator-managed keys by removing its digest, adding a secret
version, and deploying a revision.

The service account also uses the custom `betaModelPredictor` role containing only
`aiplatform.endpoints.predict`. It does not grant model, endpoint, dataset, job, or IAM
management.

## API contract

- Header: `X-API-Key`
- Scope: `day-three:use`
- Input: deliberately deidentified microbiology text and a `SUBJECT-*` pseudonym
- Storage: cumulative structured counts only; no raw report text
- Isolation: the key-derived tenant selects an opaque facility and its own antibiogram
- Safety: no orders, doses, prescribing, paging, or chart mutation

The app rejects detected direct identifiers and requires an explicit deidentification
acknowledgement. That gate reduces accidental misuse but does not certify arbitrary text as
deidentified. Do not use this hackathon beta for protected health information.

## Security and rollout boundary

- Missing, invalid, expired, and revoked keys fail closed.
- A Firestore outage returns 503 rather than bypassing authentication.
- Invitation codes and API keys are compared through SHA-256 digests.
- API keys are never accepted from query strings.
- The browser does not place credentials in cookies, local storage, or session storage.
- Cloud Run is capped at three instances to bound infrastructure cost.
- Permanent and temporary keys use the same authorization and tenant boundary.

Before a broad external program, place API Gateway in front of `/v1` for per-consumer quotas,
rate limits, abuse controls, and formal onboarding. The invitation boundary and Cloud Run cap make
this suitable for an invited hackathon beta, not an unrestricted public service.
