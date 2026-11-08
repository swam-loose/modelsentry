# Changelog

## Unreleased — 0.1.0 candidate

### Added

- Model registry, immutable prompt versions, and versioned evaluation datasets.
- Deterministic mock runs with evaluator evidence, usage estimates, and latency.
- Human reviews, run comparisons, and versioned release quality gates.
- Local API-key authentication, role-based permissions, expiry, and revocation.
- Windows/Linux CI, a coverage threshold, full migration checks, and package
  build, inspection, and installed-wheel smoke checks.

### Security hardening

- Reviewer decisions are scoped to their assigned identity; administrator
  overrides retain the real actor ID without rewriting the assignment.
- Initial administrator and API key creation is atomic and protected against
  competing bootstrap attempts by a database uniqueness constraint.
- Empty credentials and weak or placeholder production secrets are rejected.

### Known limits

- Local, single-organization operation; no automatic model deployment.
- Mock provider only; no paid provider, external SSO, distributed queue, or UI.
- Remote operations need additional transport and operational safeguards.
- A public release and license choice still require maintainer confirmation.
