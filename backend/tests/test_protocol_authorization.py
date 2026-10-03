import pytest

from cte.protocol_authorization import ProtocolAuthorizationError, authorize_protocol_action


def principal(subject, *roles, authenticated=True):
    return {"authenticated": authenticated, "subject": subject, "roles": list(roles)}


def denied(code, *args, **kwargs):
    with pytest.raises(ProtocolAuthorizationError) as exc:
        authorize_protocol_action(*args, **kwargs)
    assert exc.value.code == code


def test_policy_fails_closed_for_missing_or_unverified_principal():
    denied("principal_not_authenticated", None, "register")
    denied("principal_not_authenticated", principal("author", "protocol_author", authenticated=False), "register")


def test_register_requires_author_role():
    authorize_protocol_action(principal("a", "protocol_author"), "register")
    denied("role_not_granted", principal("reader", "protocol_reviewer"), "register")


def test_reviewer_cannot_review_own_protocol():
    authorize_protocol_action(principal("reviewer", "protocol_reviewer"), "review", author_id="author")
    denied("author_cannot_review_own_protocol", principal("author", "protocol_reviewer"), "review", author_id="author")


def test_activation_requires_three_distinct_people_and_approver_role():
    authorize_protocol_action(principal("approver", "protocol_approver"), "activate", author_id="author", reviewer_id="reviewer")
    denied("role_not_granted", principal("reviewer", "protocol_reviewer"), "activate", author_id="author", reviewer_id="reviewer")
    denied("separation_of_duties_violation", principal("author", "protocol_approver"), "activate", author_id="author", reviewer_id="reviewer")
    denied("separation_of_duties_violation", principal("reviewer", "protocol_approver"), "activate", author_id="author", reviewer_id="reviewer")
    denied("reviewer_attestation_required", principal("approver", "protocol_approver"), "activate", author_id="author")


def test_suspension_and_retirement_have_separate_roles():
    authorize_protocol_action(principal("safety", "protocol_safety_officer"), "suspend")
    authorize_protocol_action(principal("approver", "protocol_approver"), "retire")
    denied("role_not_granted", principal("approver", "protocol_approver"), "suspend")
    denied("role_not_granted", principal("safety", "protocol_safety_officer"), "retire")


def test_unknown_action_and_malformed_roles_are_denied():
    denied("action_not_supported", principal("admin", "protocol_author"), "force_activate")
    denied("principal_roles_invalid", {"authenticated": True, "subject": "x", "roles": "protocol_author"}, "register")
