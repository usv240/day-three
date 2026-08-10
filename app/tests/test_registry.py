"""Agent Registry tests.

Rules.md line 378 requires demonstrating how agents are cataloged for cross-department use. These
tests pin the behaviour the demo films: another department discovering an agent, consuming it
under enforced scopes, and being refused when it should be.
"""

from datetime import datetime, timezone

import pytest

from day_three.registry import (
    AgentCard,
    AgentNotFound,
    Department,
    Registry,
    ScopeDenied,
    Stability,
    day_three_catalog,
)

NOW = datetime(2026, 8, 8, tzinfo=timezone.utc)


@pytest.fixture
def catalog():
    return day_three_catalog(NOW)


# --- Discovery --------------------------------------------------------------------


def test_infection_prevention_discovers_the_antibiogram(catalog):
    """The beat the demo films. A department outside pharmacy finds the Curator."""
    found = catalog.discover(Department.INFECTION_PREVENTION)
    assert [c.name for c in found] == ["curator"]


def test_the_catalogue_only_publishes_built_agents(catalog):
    """Shortage Watch appears only because its official feed, store, route, and tests exist."""
    published = {c.name for c in catalog.discover(Department.PHARMACY)}
    assert published == {"curator", "intake", "reconciler", "shortage-watch"}


def test_supply_chain_discovers_only_the_operational_shortage_agent(catalog):
    assert [card.name for card in catalog.discover(Department.SUPPLY_CHAIN)] == ["shortage-watch"]


def test_quality_reporting_discovers_intake(catalog):
    assert [c.name for c in catalog.discover(Department.QUALITY_REPORTING)] == ["intake"]


def test_pharmacy_sees_everything_it_owns(catalog):
    names = {c.name for c in catalog.discover(Department.PHARMACY)}
    assert names == {"curator", "intake", "reconciler", "shortage-watch"}


def test_discovery_is_scoped_not_a_public_directory(catalog):
    """Supply Chain has no business seeing a clinical recommendation agent."""
    assert "reconciler" not in {c.name for c in catalog.discover(Department.SUPPLY_CHAIN)}


# --- Consumption and scope enforcement ---------------------------------------------


def test_a_granted_department_can_consume(catalog):
    catalog.grant(Department.INFECTION_PREVENTION, "read:antibiogram")
    card = catalog.consume(Department.INFECTION_PREVENTION, "curator")
    assert card.name == "curator"
    assert card.version == "1.1.0"


def test_consuming_without_the_scope_is_refused(catalog):
    """Discovery without enforcement would be a directory, not governance."""
    with pytest.raises(ScopeDenied, match="lacks required scopes"):
        catalog.consume(Department.INFECTION_PREVENTION, "curator")


def test_an_undeclared_consumer_is_refused_even_with_scopes(catalog):
    catalog.grant(Department.SUPPLY_CHAIN, "read:antibiogram")
    with pytest.raises(ScopeDenied, match="not a declared consumer"):
        catalog.consume(Department.SUPPLY_CHAIN, "curator")


def test_every_access_attempt_is_logged(catalog):
    catalog.grant(Department.INFECTION_PREVENTION, "read:antibiogram")
    catalog.consume(Department.INFECTION_PREVENTION, "curator")
    try:
        catalog.consume(Department.SUPPLY_CHAIN, "curator")
    except ScopeDenied:
        pass

    assert len(catalog.access_log) == 2
    assert catalog.access_log[0]["allowed"] is True
    assert catalog.access_log[1]["allowed"] is False
    assert "not a declared consumer" in catalog.access_log[1]["reason"]


def test_a_denied_attempt_appears_in_the_audit_trail(catalog):
    """The denial we film. A refusal that leaves a record is a security control; a silent one
    is not."""
    with pytest.raises(ScopeDenied):
        catalog.consume(Department.INFECTION_PREVENTION, "curator")
    assert catalog.access_log[-1] == {
        "department": "infection_prevention",
        "agent": "curator@1.1.0",
        "allowed": False,
        "reason": "missing scopes: ['read:antibiogram']",
    }


# --- Versioning -------------------------------------------------------------------


def test_versions_are_immutable(catalog):
    with pytest.raises(ValueError, match="already published"):
        catalog.publish(
            AgentCard(
                name="curator",
                version="1.1.0",
                owner="someone-else",
                summary="hijack",
                produces="nothing",
                consumed_by=(Department.PHARMACY,),
                required_scopes=(),
            )
        )


def test_latest_returns_the_newest_non_deprecated(catalog):
    assert catalog.latest("curator").version == "1.1.0"


def test_a_specific_version_can_be_pinned(catalog):
    catalog.publish(
        AgentCard(
            name="curator",
            version="2.0.0",
            owner="pharmacy",
            summary="next major",
            produces="grid",
            consumed_by=(Department.PHARMACY,),
            required_scopes=("read:antibiogram",),
        )
    )
    assert catalog.get("curator", "1.1.0").version == "1.1.0"
    assert catalog.latest("curator").version == "2.0.0"


def test_deprecated_versions_are_skipped_by_latest():
    registry = Registry()
    registry.publish(
        AgentCard("thing", "1.0.0", "team", "s", "p", (Department.PHARMACY,), (), Stability.STABLE)
    )
    registry.publish(
        AgentCard(
            "thing", "2.0.0", "team", "s", "p", (Department.PHARMACY,), (), Stability.DEPRECATED
        )
    )
    assert registry.latest("thing").version == "1.0.0"


def test_the_changelog_records_the_clsi_correction(catalog):
    """The methodological fix is in the public history rather than quietly patched."""
    history = catalog.latest("curator").history
    assert any("irrespective of body site" in v.changelog for v in history)


def test_unknown_agents_raise_clearly(catalog):
    with pytest.raises(AgentNotFound):
        catalog.latest("does-not-exist")


# --- Governance signals -----------------------------------------------------------


def test_the_clinical_agent_declares_that_it_needs_a_human(catalog):
    """A consuming team must be able to see this before depending on it."""
    assert catalog.latest("reconciler").human_approval_required is True


def test_data_agents_do_not_require_human_approval(catalog):
    assert catalog.latest("curator").human_approval_required is False


def test_stability_is_declared_so_consumers_can_judge_risk(catalog):
    assert catalog.latest("curator").stability is Stability.STABLE
    assert catalog.latest("reconciler").stability is Stability.EXPERIMENTAL


def test_every_published_agent_declares_what_it_produces(catalog):
    for name in ("curator", "intake", "reconciler", "shortage-watch"):
        card = catalog.latest(name)
        assert len(card.produces) > 20
        assert len(card.summary) > 20
        assert card.owner
