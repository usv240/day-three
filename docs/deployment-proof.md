# Deployment proof

The rules ask for proof the backend was built and deployed on Google Cloud, and the FAQ asks for
that proof to be backed up in the repository as well as shown in the video. A screenshot proves
little on its own, so this page records values a reader can re-fetch themselves. Every line below
came from `gcloud` or from the live service; nothing here is typed by hand.

Captured 2026-08-22 04:01 UTC.

## Cloud Run

| | |
|---|---|
| Service | `day-three` |
| Region | `us-central1` |
| Serving revision | `day-three-00079-shs` |
| Service account | `sa-reason@agentic-fleet-2026.iam.gserviceaccount.com` |
| Minimum instances | 0 (scales to zero) |
| Public URL | https://day-three-109051079423.us-central1.run.app |

## Cloud Scheduler

```
  day-three-realtime-wake-scan	* * * * *	ENABLED
  day-three-shortage-refresh	0 5 * * *	ENABLED
```

The every-minute job is what claims wall-clock work; the daily job refreshes the openFDA shortage
snapshot. Neither is triggered by the browser.

## Firestore

```
  projects/agentic-fleet-2026/databases/(default)   us-central1   FIRESTORE_NATIVE
```

## Re-fetch it yourself

```bash
BASE=https://day-three-109051079423.us-central1.run.app
curl $BASE/health
curl -X POST -H "Content-Type: application/json" -d '{}' $BASE/exit-test   # expect 10/10
curl $BASE/day-three/platform                                              # managed platform, read live

gcloud run services describe day-three --region us-central1   --format='value(metadata.name,status.url,status.latestReadyRevisionName)'
gcloud scheduler jobs list --location us-central1 --filter='name~day-three'
```

## What `/health` reported at capture time

```json
{
  "ok": true,
  "project": "agentic-fleet-2026",
  "region": "us-central1",
  "sim_mode": true,
  "replay_mode": true,
  "tracing": true,
  "beta_api": "configured",
  "developer_key_issuance": "open",
  "worker": "worker_day-three-00079-shs_fbe290"
}
```

`sim_mode` is true because the public console runs a simulated clock and says so on screen. The
wall-clock scanner and its public proof route are unaffected by it; that separation is the point
of the timer check on the landing page.
