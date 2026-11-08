# Security policy

ModelSentry 0.1 is a local, single-organization evaluation and governance API.
It is not an internet-ready hosted service, a multi-tenant platform, or an
external identity provider. Passing tests or a release gate is not a security
certification and does not deploy or promote a model.

## Credentials and deployment

- Generate independent, random API-key hashing and bootstrap secrets. Keep
  both out of Git, screenshots, issue reports, logs, and shared terminal output.
- Production secrets must be at least 32 characters; documented placeholders,
  empty secrets, and reusing the same secret for both purposes are rejected.
- Keep the hashing pepper stable. Changing it invalidates existing API keys;
  plan credential rotation and recovery before doing so.
- Complete bootstrap once on a trusted local connection. Its administrator
  and first key are committed atomically; a unique database constraint rejects
  competing bootstrap claims. Disable the bootstrap token afterward and restart.
- The API returns each raw API key only on issuance. Store it in an appropriate
  secret store, issue short-lived keys when feasible, and revoke compromised keys.
- Keep the service bound to loopback for local demonstrations. Shared access
  requires TLS, a trusted proxy, rate limiting, backups, and an operational
  security review; these are not supplied automatically by version 0.1.

## Human decisions

A `reviewer` may decide only assignments matching that account's normalized
email. An `admin` can override an assignment, but the decision retains the
actual authenticated actor in `decided_by_user_id` separately from its assigned
reviewer. Operator and viewer roles cannot submit final review decisions.
Historical reviews created before actor auditing retain a null actor ID; the
application does not invent identities for them.

Local identities are created by administrators. They are not proof of legal
identity or email ownership. Protect administrator keys and use synthetic data
for public demonstrations.

## Reporting

Do not put API keys, `.env` content, personal data, or exploit credentials in
public GitHub issues. Use a private reporting channel agreed with the maintainer
for security-sensitive findings. Include the affected commit and a minimal,
synthetic reproduction without disclosing secrets.
