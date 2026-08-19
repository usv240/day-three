from datetime import datetime, timezone

from day_three.managed_memory import ManagedMemoryBank, ManagedMemoryError


class Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class Session:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        if url.endswith("memories:retrieve"):
            return Response(
                {
                    "retrievedMemories": [
                        {
                            "memory": {
                                "name": "memory/1",
                                "fact": "A deidentified synthetic handoff.",
                                "scope": json["scope"],
                            }
                        }
                    ]
                },
                self.status_code,
            )
        return Response(
            {"response": {"name": "memory/1"}},
            self.status_code,
        )


def test_course_scope_is_stable_and_does_not_expose_the_course_identifier():
    scope = ManagedMemoryBank.course_scope("crs_patient-123_999")
    assert scope == ManagedMemoryBank.course_scope("crs_patient-123_999")
    assert scope["application"] == "day-three"
    assert "patient-123" not in scope["course_ref"]


def test_course_handoff_contains_no_patient_identifier_or_raw_report():
    session = Session()
    memory = ManagedMemoryBank("p", session_factory=lambda: session)
    result = memory.remember_course(
        course_id="crs_patient-123_999",
        regimen=("ceftriaxone",),
        indication="urinary tract infection",
        first_review_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    body = session.calls[0][1]

    assert result["stored"] is True
    assert result["contains_patient_identifier"] is False
    assert "patient-123" not in str(body)
    assert "raw report" not in str(body).lower()
    assert body["scope"] == ManagedMemoryBank.course_scope("crs_patient-123_999")


def test_recall_uses_exact_scope_and_marks_firestore_authoritative():
    session = Session()
    memory = ManagedMemoryBank("p", session_factory=lambda: session)
    result = memory.recall_course("course_demo")

    assert result["recalled"] is True
    assert result["count"] == 1
    assert result["authoritative_store"] == "Firestore"
    assert session.calls[0][0].endswith("memories:retrieve")
    assert session.calls[0][1] == {"scope": ManagedMemoryBank.course_scope("course_demo")}


def test_managed_failure_exposes_no_submitted_content():
    memory = ManagedMemoryBank("p", session_factory=lambda: Session(503))
    try:
        memory.remember_course(
            course_id="secret-course",
            regimen=("ceftriaxone",),
            indication="private indication",
            first_review_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
    except ManagedMemoryError as exc:
        message = str(exc)
        assert "secret-course" not in message
        assert "private indication" not in message
        assert "Firestore remains authoritative" in message
    else:
        raise AssertionError("managed memory failure must be explicit")


def test_credential_or_network_failure_is_bounded_and_exposes_no_content():
    def unavailable_session():
        raise RuntimeError("transport failed near private indication")

    memory = ManagedMemoryBank("p", session_factory=unavailable_session)
    try:
        memory.remember_course(
            course_id="secret-course",
            regimen=("ceftriaxone",),
            indication="private indication",
            first_review_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
    except ManagedMemoryError as exc:
        message = str(exc)
        assert "secret-course" not in message
        assert "private indication" not in message
        assert "transport failed" not in message
        assert "Firestore remains authoritative" in message
    else:
        raise AssertionError("transport failures must preserve the Firestore workflow")
