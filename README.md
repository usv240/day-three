# Day Three

Day Three turns recorded microbiology reports into a privacy-protected local antibiogram,
maintains an antibiotic-course review ladder, and produces source-grounded reconciliation
recommendations. It does not prescribe, contact clinicians autonomously, or claim unsupported
hospital-wide coverage.

- Live app: https://day-three-109051079423.us-central1.run.app
- Judge brief: https://day-three-109051079423.us-central1.run.app/judges
- Independent code root: app/

## Verify locally

    cd app
    python -m pip install -e ".[dev]"
    python -m pytest -q
    python scripts/check_a11y.py

Run with Application Default Credentials and a Google Cloud project:

    export GOOGLE_CLOUD_PROJECT=agentic-fleet-2026
    export SIM_MODE=true
    export REPLAY_MODE=true
    uvicorn service.main:app --reload

Deploying from app/ with bash deploy.sh targets the independent Cloud Run service day-three.
See REPOSITORY_MANIFEST.md for the repository boundary and SUBMISSION_KIT.md for the
evidence-backed submission copy.
