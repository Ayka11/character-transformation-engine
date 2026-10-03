# Durable protocol review attestations — v1

The registry records independent review attestations as append-only events in the
`protocol.registry.review` namespace. Each attestation is bound to the immutable
definition hash and records reviewer identity, outcome, reason, and timestamp.
An `ACTIVE` transition requires a hash-matching `APPROVED` review whose reviewer
is neither the original author nor the activating actor. Rejected reviews do not
authorize activation.

The registry primitive expects `reviewer_id` and `actor_id` to be derived by the
calling trusted server boundary from verified identity claims. It does not perform
authentication, verify identity-provider tokens, or protect API routes by itself.
Do not expose review or lifecycle mutation endpoints until verified identity and the
role policy are enforced server-side. This control records a governance decision;
it does not establish scientific validity, efficacy, or safety of a protocol.
