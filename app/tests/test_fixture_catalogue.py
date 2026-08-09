from service.day_three_routes import available_fixture_names


def test_only_complete_intake_fixtures_are_published():
    names = available_fixture_names()
    assert names == [
        "ecoli_urine",
        "ecoli_urine_with_note",
        "kleb_blood",
        "staph_wound",
    ]
    assert "gemma_names" not in names
