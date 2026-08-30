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
