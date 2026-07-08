from kel.skills.authoring.contracts import AuthorOutcome, DraftSkill


def test_draft_skill_holds_the_generated_pieces() -> None:
    draft = DraftSkill(
        name="make_qr_code",
        description="Make a QR code.",
        parameters={"type": "object", "properties": {}},
        code="def run():\n    return 'ok'\n",
        invocation_args={"text": "hi"},
    )

    assert draft.name == "make_qr_code"
    assert draft.invocation_args == {"text": "hi"}


def test_author_outcome_defaults() -> None:
    outcome = AuthorOutcome(ok=True, output="done")

    assert outcome.ok is True
    assert outcome.skill_name is None
    assert outcome.attempts == 0
