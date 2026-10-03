# Protocol Role Authorization V1 — policy primitive

## Purpose

Define a fail-closed authorization policy for a future authenticated protocol-governance API.
This document and protocol_authorization.py do not mean registry mutations are currently
protected by role-based authorization. The policy must be wired into every mutation handler
before such handlers are exposed.

## Trusted principal boundary

- The principal is built server-side from verified identity-provider claims.
- Never accept subject, authenticated, or roles from request-body fields.
- A caller-provided actor_id is audit metadata only and is not identity proof.
- Missing, malformed, unauthenticated, or unknown inputs are denied by default.

## Action-to-role mapping

| Action | Required role | Additional rule |
| --- | --- | --- |
| Register definition | protocol_author | New immutable version begins in DRAFT |
| Review definition | protocol_reviewer | Reviewer must differ from author |
| Activate version | protocol_approver | Author, reviewer, and approver must be three distinct identities; reviewer attestation is required |
| Suspend version | protocol_safety_officer | Protective action; no author/reviewer equality restriction |
| Retire version | protocol_approver | Existing lifecycle transition rules still apply |

Roles must be granted through an administrator-controlled identity system, not by the
application user. Role names are stable policy identifiers and require mapping to actual
identity-provider groups/claims before production use.

## Integration gate

Before adding public mutation routes:

1. Integrate verified identity claims (OIDC/SSO or another reviewed authentication provider).
2. Construct a trusted principal in server-side request context.
3. Enforce this policy at every registration, review, activation, suspension, and retirement boundary.
4. Persist a review attestation and validate author/reviewer/approver identities transactionally.
5. Add API tests proving unauthenticated requests, forged body roles, missing roles, and separation-of-duties violations are rejected.
6. Keep storage-level compare-and-append concurrency controls enabled.
7. Run SQLite, PostgreSQL, migration/rollback, and release-gate workflows.

The current lifecycle model allows DRAFT → ACTIVE directly and does not yet persist a distinct
review-attestation object. Therefore activation must not be exposed merely because this policy
primitive exists; a durable review record and transactional enforcement are prerequisites.

## Limitations

This is an authorization policy primitive, not authentication, an identity provider, or a
scientific quality gate. Role authorization does not establish protocol efficacy, safety, or
validity. Registry status remains governance metadata; selection remains review-only and does
not authorize protocol execution.
