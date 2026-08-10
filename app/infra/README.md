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

`provision_platform.ps1` creates the regional Model Armor templates and the managed
Client-to-Agent Gateway. `deploy_runtimes.py` creates one Agent Runtime resource for each of the
four published roles with `identity_type=AGENT_IDENTITY`, zero idle instances, and the same ingress
gateway binding. `/day-three/platform` reads these resources from their managed APIs live.

Security status: Google documents disabling agent-token-sharing prevention when a gateway-bound
Agent Identity calls other Google Cloud services. That exception is not persisted here and is not
active on the deployed resources. Direct Runtime calls therefore fail closed at Model Armor until
that specific security tradeoff is explicitly approved. Registry, Runtime, Identity, Gateway, and
the two Model Armor resources are real; full governed invocation is not claimed in this state.
