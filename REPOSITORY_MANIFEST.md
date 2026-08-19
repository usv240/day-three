# Day Three repository manifest

This folder is a self-contained candidate root for the independent Day Three Git repository.
The original combined implementation remains in ../app/. This copy can be tested, built, and
deployed from app/ without Sixty Days code.

## Repository boundary

- app/day_three/: Day Three domain code
- app/spine/: reviewed runtime substrate required by this project
- app/service/day_three_routes.py: Day Three API only
- app/web/: shared product shell, public workflow, Developer API, branded API reference, and judge evidence pages
- app/fixtures/, app/scripts/, and app/tests/: Day Three evidence and verification

## Independent deployment

- Cloud Run service: day-three
- Hosted URL: https://day-three-109051079423.us-central1.run.app
- Public identity: day-three
- Demo gate: 18/18

Initialize or push only after the independent test, accessibility, container, and demo gates pass.
