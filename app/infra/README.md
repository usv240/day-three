# Managed Agent Registry setup

Day Three uses manual standard REST registration because its public runtime is FastAPI on Cloud
Run. Google Cloud Agent Registry projects each writable Service into a discoverable Agent.

From `app/`, with Application Default Credentials for a principal holding
`roles/agentregistry.editor`:

```bash
gcloud services enable agentregistry.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"
python infra/register_agents.py
```

Grant the deployed runtime read-only access so judges can use the public proof route without their
own credentials:

```bash
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:sa-reason@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --role="roles/agentregistry.viewer"
```

Then verify:

```bash
curl "$DAY_THREE_URL/day-three/registry/managed"
```

The provisioning script is idempotent. It creates missing entries and updates existing metadata.
It does not provision Agent Runtime or claim per-agent runtime identities.
