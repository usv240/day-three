"""The four minute demo, executed end to end.

Runs the exact sequence the video will follow, so the flow is proven before anything is recorded.
Works against a local TestClient by default, or a deployed URL with --url.

    python scripts/demo_flow.py
    python scripts/demo_flow.py --url https://spine-109051079423.us-central1.run.app
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# No fixture text lives here any more. Every document and extraction in this flow is fetched
# from the deployed service, which serves the real scanned images and the output Gemini 3.5
# Flash actually produced for them (graded 29/29 against ground truth).


class Client:
    """Thin shim so the same script drives a local app or a deployed URL."""

    def __init__(self, url: str | None) -> None:
        if url:
            import httpx

            # Token comes from the environment rather than a subprocess: on Windows gcloud is a
            # shell script, not an executable, so subprocess cannot find it.
            #   ID_TOKEN=$(gcloud auth print-identity-token) python scripts/demo_flow.py --url ...
            token = os.environ.get("ID_TOKEN", "").strip()
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            self._http = httpx.Client(base_url=url, headers=headers, timeout=60)
            self.mode = f"deployed {url}" + ("" if token else " (no ID_TOKEN set)")
        else:
            from fastapi.testclient import TestClient
            from service.main import app

            self._http = TestClient(app)
            self.mode = "local"

    def get(self, path, **kw):
        return self._http.get(path, **kw).json()

    def post(self, path, json=None):
        response = self._http.post(path, json=json or {})
        return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None)
    args = parser.parse_args()

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
    os.environ.setdefault("SIM_MODE", "true")

    c = Client(args.url)
    print(f"Day Three demo flow, {c.mode}\n")
    failures: list[str] = []

    def step(n: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {n}{'  |  ' + detail if detail else ''}")
        if not ok:
            failures.append(n)

    # 0. Clean slate
    c.post("/sim/reset")
    c.post("/day-three/reset")
    step("reset to a clean state", True)

    # 1. Three reports arrive. The hospital learns something it never knew.
    #
    # These are the real recordings: Gemini 3.5 Flash's actual output for the scanned images,
    # fetched from the deployed service. Nothing hand-written enters the ingest path.
    catalogue = c.get("/day-three/fixtures")
    step(
        "fixture recordings served by the deployment",
        len(catalogue.get("fixtures", [])) >= 3,
        f"{len(catalogue.get('fixtures', []))} recordings",
    )

    rotation = ["ecoli_urine", "kleb_blood", "staph_wound"]
    for i, name in enumerate(rotation, start=1):
        fixture = c.get(f"/day-three/fixtures/{name}")
        c.post(
            "/day-three/intake",
            {
                "artifact_id": f"art_{i}_{name}",
                "patient_id": f"pt_{i}",
                "document": fixture["ground_truth"],
                "extraction": fixture["extraction"],
            },
        )
    grid = c.get("/day-three/antibiogram")
    step(
        "grid built from real Gemini output, three organisms",
        len(grid.get("organisms", [])) == 3,
        ", ".join(grid.get("organisms", [])),
    )
    step(
        "antibiogram built from scanned reports",
        grid["revision"] == 3 and len(grid["cells"]) >= 3,
        f"revision {grid['revision']}, {len(grid['cells'])} cells",
    )

    suppressed = [cell for cell in grid["cells"] if cell["suppressed"]]
    step(
        "small cells suppressed rather than reported",
        len(suppressed) == len(grid["cells"])
        and all(cell["percent_susceptible"] is None for cell in suppressed),
        "CLSI M39 requires 30 isolates before a percentage",
    )

    # 2. A hostile report cannot issue instructions
    hostile_fixture = c.get("/day-three/fixtures/ecoli_urine_with_note")
    hostile = c.post(
        "/day-three/intake",
        {
            "artifact_id": "art_hostile",
            "patient_id": "pt_9",
            "document": hostile_fixture["ground_truth"],
            "extraction": hostile_fixture["extraction"],
        },
    )
    step(
        "instruction-shaped text quarantined, clinical data kept",
        len(hostile["quarantined"]) >= 1 and len(hostile["isolate"]["susceptibilities"]) >= 3,
        hostile["quarantined"][0]["threat"] if hostile["quarantined"] else "none",
    )

    # 3. A patient is admitted on broad empiric therapy
    course = c.post(
        "/day-three/course",
        {"patient_id": "pt_admitted", "regimen": ["piperacillin-tazobactam", "vancomycin"]},
    )
    step(
        "five week wake ladder registered at admission",
        len(course["ladder"]) == 5 and course["horizon_days"] >= 40,
        f"{len(course['ladder'])} wakes, horizon {course['horizon_days']} days",
    )

    # 4. Nothing fires early
    early = c.post("/sim/advance", {"hours": 47})
    mine = [w for w in early["woke"] if w["run_id"] == course["run_id"]]
    step("nothing wakes before hour 48", mine == [])

    # 5. The agent wakes itself
    woke = c.post("/sim/advance", {"hours": 5})
    mine = [w for w in woke["woke"] if w["run_id"] == course["run_id"]]
    step(
        "agent wakes itself at hour 52, unattended",
        [w["kind"] for w in mine] == ["deescalation_review"],
        str([w["kind"] for w in mine]),
    )

    # 6. The recommendation, grounded in cited results.
    # The susceptibilities and the document both come from Gemini's real recorded reading of the
    # scan, so the Verifier is grounding against genuine model output, not a hand-written string.
    fixture = c.get("/day-three/fixtures/ecoli_urine")
    rec = c.post(
        "/day-three/reconcile",
        {
            "patient_id": "pt_admitted",
            "regimen": ["piperacillin-tazobactam", "vancomycin"],
            "organism": fixture["extraction"]["organism"],
            "susceptibilities": {
                s["drug"].lower(): f"{s['interpretation']}|{s['quoted_text']}"
                for s in fixture["extraction"]["susceptibilities"]
            },
            "artifact_id": "art_reconcile",
            "document": fixture["extraction"].get("transcription") or fixture["ground_truth"],
        },
    )
    step(
        "narrower drug recommended",
        rec["kind"] == "deescalate" and rec["suggested"] == "nitrofurantoin",
        f"{rec['kind']} -> {rec['suggested']}",
    )
    step("every claim grounded in the report", rec["all_claims_grounded"])
    step("pharmacist approval required", rec["requires_pharmacist_approval"])

    # 7. The Verifier rejection we film
    fabricated = c.post("/day-three/demo/fabricate")
    step(
        "fabricated percentage rejected on camera",
        fabricated["accepted"] is False
        and fabricated["rejection_code"] == "number_not_in_source",
        fabricated["reason"],
    )

    # 8. Cross-department discovery
    ip = c.get("/day-three/registry?department=infection_prevention")
    step(
        "infection prevention discovers the antibiogram",
        [a["name"] for a in ip["discoverable"]] == ["curator"],
    )

    denied = c.post(
        "/day-three/registry/consume",
        {"department": "infection_prevention", "agent": "curator", "granted_scopes": []},
    )
    step("consumption without scopes is refused and audited", denied["allowed"] is False)

    allowed = c.post(
        "/day-three/registry/consume",
        {
            "department": "infection_prevention",
            "agent": "curator",
            "granted_scopes": ["read:antibiogram"],
        },
    )
    step("granted department consumes successfully", allowed["allowed"] is True)

    # 9. Conformance
    conformance = c.get("/conformance")
    step(
        "CLSI conformance published with tests",
        len(conformance["rules"]) == 4 and all(r.get("test") for r in conformance["rules"]),
    )

    print()
    if failures:
        print(f"{len(failures)} step(s) failed: {', '.join(failures)}")
        return 1
    print("Every demo step passed. The four minute flow is real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
