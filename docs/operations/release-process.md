# Release Process

The project uses trunk-based development, Conventional Commits, Semantic Versioning, and Keep a
Changelog. Pre-production versions remain `0.x.y`.

Before a release candidate: review scope and ADRs, synchronize docs/changelog/version, install the
locked environment, run Ruff/mypy/pytest/coverage/pre-commit and dependency audit, review migrations
and downgrade behavior, scan staged files for secrets, test Windows scripts, and document any
unavailable MetaEditor/PostgreSQL validation. CI must be green.

Build artifacts and future strategy/update packages require integrity metadata and an approved
rollback plan. Never promote a paper/demo validation result into live authorization. Do not create
a Git tag unless the release is explicitly authorized.

For 0.5.0 specifically, controlled EURUSD and GBPUSD validation is complete, but do not merge, tag,
or publish until the reviewed inverse-conversion change passes all quality gates, is deployed to
Windows, and the operator reviews sanitized conversion-gated USDJPY execution, reconciliation,
duplicate, kill-switch, and restart evidence as applicable. Any later MQL5 change must first compile
in Windows MetaEditor with `0 errors, 0 warnings` and be installed as the exact reviewed artifact.
