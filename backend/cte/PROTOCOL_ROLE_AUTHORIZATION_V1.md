# Protocol Role Authorization V1 — policy primitive

## Purpose

Define a fail-closed authorization policy for a future authenticated protocol-governance API.
The policy is not currently wired to registry mutation handlers. The registry now persists
review attestations and requires an independent approved review for activation, but those
controls do not authenticate callers or prove that an actor identifier represents a real person.

## Trusted principal boundary

- The principal must be built server-side from verified identity-provider claims.
- Never accept subject, authenticated, or roles from request-body fields.
- A caller-provided actor_id or reviewer_id is audit metadata only and is not identity proof.
- The current API's shared read/write API keys authenticate possession of a key; they do not
  establish distinct human identities or trusted role membership.
- Missing, malformed, unauthenticated, or unknown inputs are denied by default.

## Action-to-role mapping

| Action | Required role | Additional rule |
| --- | --- | --- |
| Register definition | protocol_author | New immutable version begins in DRAFT |
| Review definition | protocol_reviewer | Reviewer must differ from author |
| Activate version | protocol_approver | Author, reviewer, and approver must be three distinct verified identities; durable approved review required |
| Suspend version | protocol_safety_officer | Protective action; actor must be authenticated and authorized |
| Retire version | protocol_approver | Existing lifecycle transition rules still apply |

Roles must be granted through an administrator-controlled identity system, not by the
application user. Role names are stable policy identifiers and require mapping to actual
identity-provider groups/claims before production use.

## Mutation-route exposure gate

The current API intentionally exposes protocol candidate selection only; it does not expose
public protocol-registry registration, review, or lifecycle-transition routes. Keep this gate
in place until a reviewed identity provider and trusted-principal adapter exist and the policy
is enforced on every mutation request. The route guard test is an explicit release constraint,
not a substitute for authentication.

Before adding public mutation routes:

1. Integrate verified identity claims (OIDC/SSO or another reviewed authentication provider).
2. Construct a trusted principal in server-side request context.
3. Enforce this policy at every registration, review, activation, suspension, and retirement boundary.
4. Derive actor/reviewer identity exclusively from the trusted principal, never request-body fields.
5. Persist and validate review attestations and author/reviewer/approver separation transactionally.
6. Add API tests proving unauthenticated requests, forged body roles, missing roles, and separation-of-duties violations are rejected.
7. Keep storage-level compare-and-append concurrency controls enabled.
8. Run SQLite, PostgreSQL, migration/rollback, and release-gate workflows.

## Limitations

This is an authorization policy primitive, not authentication, an identity provider, or a
scientific quality gate. Role authorization does not establish protocol efficacy, safety, or
validity. Registry status remains governance metadata; selection remains review-only and does
not authorize protocol execution.
