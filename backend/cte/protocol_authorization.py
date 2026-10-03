"""Fail-closed role policy for governed protocol actions.

This is a policy primitive, not an authentication provider. The principal must be
constructed from verified server-side identity claims, never request-body fields.
It does not protect registry mutations until wired into authenticated handlers.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ProtocolAuthorizationError(PermissionError):
    """Stable, machine-readable denial from the protocol role policy."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def authorize_protocol_action(
    principal: Mapping[str, Any] | None,
    action: str,
    *,
    author_id: str | None = None,
    reviewer_id: str | None = None,
) -> None:
    """Authorize an action; deny unknown or unauthorized requests by default."""
    if not isinstance(principal, Mapping) or principal.get("authenticated") is not True:
        raise ProtocolAuthorizationError("principal_not_authenticated")

    subject = principal.get("subject")
    roles = principal.get("roles")
    if not isinstance(subject, str) or not subject.strip():
        raise ProtocolAuthorizationError("principal_subject_missing")
    if not isinstance(roles, (list, tuple, set, frozenset)) or not all(
        isinstance(role, str) for role in roles
    ):
        raise ProtocolAuthorizationError("principal_roles_invalid")
    role_set = set(roles)

    required_role = {
        "register": "protocol_author",
        "review": "protocol_reviewer",
        "activate": "protocol_approver",
        "suspend": "protocol_safety_officer",
        "retire": "protocol_approver",
    }.get(action)
    if required_role is None:
        raise ProtocolAuthorizationError("action_not_supported")
    if required_role not in role_set:
        raise ProtocolAuthorizationError("role_not_granted")

    if action == "review":
        if not isinstance(author_id, str) or not author_id.strip():
            raise ProtocolAuthorizationError("author_identity_required")
        if subject == author_id:
            raise ProtocolAuthorizationError("author_cannot_review_own_protocol")

    if action == "activate":
        if not isinstance(author_id, str) or not author_id.strip():
            raise ProtocolAuthorizationError("author_identity_required")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise ProtocolAuthorizationError("reviewer_attestation_required")
        if len({subject, author_id, reviewer_id}) != 3:
            raise ProtocolAuthorizationError("separation_of_duties_violation")
    return None
