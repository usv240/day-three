import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from day_three.intake import IntakeAgent, ReplayClient
from service.beta_routes import build_beta_router
from spine.api_access import ApiKeyAuthenticator
from spine.redact import NameReviewer, RedactionError


class Snapshot:
    def __init__(self, document):
        self._document = document

    @property
    def exists(self):
        return self._document.data is not None

    def to_dict(self):
        return dict(self._document.data or {})


class Document:
    def __init__(self):
        self.data = None

    def set(self, data):
        self.data = dict(data)

    def get(self):
        return Snapshot(self)


class Collection:
    def __init__(self):
        self.documents = {}

    def document(self, doc_id):
        return self.documents.setdefault(doc_id, Document())


class FakeFirestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())


class FrozenClock:
    def now(self):
        return datetime(2026, 8, 18, 12, tzinfo=timezone.utc)


SAFE_REPORT = """DE-IDENTIFIED CULTURE AND SUSCEPTIBILITY REPORT
Collected: 2026-03-04 06:40
Specimen: Urine, clean catch
ORGANISM ISOLATED: Escherichia coli
AMPICILLIN                  >16        R
AMOXICILLIN-CLAVULANATE       8        I
CEFAZOLIN                  <=4        S
CEFTRIAXONE                <=1        S
CIPROFLOXACIN               >2        R
NITROFURANTOIN             <=16        S
TRIMETHOPRIM-SULFA          >4        R
MEROPENEM                <=0.25        S
"""


def client() -> TestClient:
    root = Path(__file__).resolve().parent.parent
    recording = json.loads(
        (root / "fixtures" / "recordings" / "ecoli_urine.json").read_text()
    )
    auth = ApiKeyAuthenticator.from_plaintext({
        "clinic-one-key": {
            "tenant_id": "clinic_one",
            "label": "Clinic one",
            "scopes": ["day-three:use"],
        },
        "clinic-two-key": {
            "tenant_id": "clinic_two",
            "label": "Clinic two",
            "scopes": ["day-three:use"],
        },
    })
    app = FastAPI()
    app.include_router(build_beta_router(
        FakeFirestore(),
        FrozenClock(),
        auth,
        intake_factory=lambda: IntakeAgent(ReplayClient({"default": recording})),
    ))
    return TestClient(app)


def post_report(api: TestClient, key: str = "clinic-one-key"):
    return api.post(
        "/v1/intake",
        headers={"X-API-Key": key},
        json={
            "document": SAFE_REPORT,
            "subject_ref": "SUBJECT-001",
            "acknowledge_deidentified": True,
        },
    )


def test_beta_intake_builds_private_suppressed_antibiogram_without_raw_storage():
    api = client()
    response = post_report(api)
    assert response.status_code == 201
    assert response.json()["raw_document_persisted"] is False
    grid = api.get("/v1/antibiogram", headers={"X-API-Key": "clinic-one-key"}).json()
    assert grid["revision"] == 1
    assert grid["clinical_action"] == "none"
    assert all(cell["suppressed"] for cell in grid["cells"])


def test_antibiogram_is_isolated_by_api_key_tenant():
    api = client()
    assert post_report(api).status_code == 201
    other = api.get("/v1/antibiogram", headers={"X-API-Key": "clinic-two-key"}).json()
    assert other["revision"] == 0
    assert other["cells"] == []


def test_direct_identifier_is_rejected_before_model_processing():
    api = client()
    response = api.post(
        "/v1/intake",
        headers={"X-API-Key": "clinic-one-key"},
        json={
            "document": SAFE_REPORT + "\nPatient: SEAN O'BRIEN\nMRN: 1234567",
            "subject_ref": "SUBJECT-001",
            "acknowledge_deidentified": True,
        },
    )
    assert response.status_code == 422
    assert "MRN" in response.json()["detail"]
    assert "PERSON" in response.json()["detail"]


def test_pseudonymous_subject_and_deidentification_acknowledgement_are_required():
    api = client()
    response = api.post(
        "/v1/intake",
        headers={"X-API-Key": "clinic-one-key"},
        json={
            "document": SAFE_REPORT,
            "subject_ref": "Sean O'Brien",
            "acknowledge_deidentified": False,
        },
    )
    assert response.status_code == 422

class BrokenReviewer(NameReviewer):
    def find_names(self, text: str) -> list[str]:
        raise RedactionError("reviewer unavailable")


def test_privacy_reviewer_outage_fails_closed_as_service_unavailable():
    root = Path(__file__).resolve().parent.parent
    recording = json.loads(
        (root / "fixtures" / "recordings" / "ecoli_urine.json").read_text()
    )
    auth = ApiKeyAuthenticator.from_plaintext({
        "clinic-one-key": {
            "tenant_id": "clinic_one",
            "label": "Clinic one",
            "scopes": ["day-three:use"],
        }
    })
    app = FastAPI()
    app.include_router(build_beta_router(
        FakeFirestore(),
        FrozenClock(),
        auth,
        intake_factory=lambda: IntakeAgent(
            ReplayClient({"default": recording}), reviewer=BrokenReviewer()
        ),
    ))
    response = TestClient(app).post(
        "/v1/intake",
        headers={"X-API-Key": "clinic-one-key"},
        json={
            "document": SAFE_REPORT,
            "subject_ref": "SUBJECT-001",
            "acknowledge_deidentified": True,
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Privacy review unavailable; the report was not processed."

