# Contributing to Assemblix

Thanks for your interest in contributing! This guide covers how to get set up, the
quality bar for changes, and project conventions.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating you
agree to uphold it.

## Licensing of contributions

Assemblix is source-available under **MIT + Commons Clause** (see [LICENSE.md](LICENSE.md)).
By submitting a contribution you agree it is licensed under the same terms. Do **not**
contribute to or extend Enterprise-licensed files (those marked
`SPDX-License-Identifier: LicenseRef-Assemblix-EE`, see [LICENSE_EE.md](LICENSE_EE.md))
unless you have a commercial agreement with the maintainers.

## Getting set up

The repo is a monorepo with two independently-built apps. Read the umbrella
[CLAUDE.md](CLAUDE.md) first, then the per-app guide for whichever side you touch:

- Backend — [assemblix-app-api/CLAUDE.md](assemblix-app-api/CLAUDE.md)
- Frontend — [assemblix-app-web/CLAUDE.md](assemblix-app-web/CLAUDE.md)

Quick start (full stack with live reload):

```bash
cp .env.example .env        # then fill JWT_SECRET_KEY + ENCRYPTION_KEY (see README)
docker compose -f docker-compose.dev.yml up --build
```

See the [README](README.md) for native (non-Docker) setup.

## Quality gates

Every change must pass the same gates CI runs. Run them locally before opening a PR:

```bash
make check          # from the repo root — runs both apps' gates
```

Per app:

```bash
# backend (from assemblix-app-api/)
make check          # ruff lint + format check, mypy, bandit, pytest + coverage

# frontend (from assemblix-app-web/)
yarn lint           # eslint
yarn build          # tsc type-check + build
```

A repo-wide **gitleaks** secret scan runs on every PR. Never commit real secrets —
generate ephemeral ones at runtime (as the Makefile and CI do).

## Conventions

- **English only** in code — all comments and docstrings must be in English.
- **Comment sparingly.** Comment only non-trivial logic; don't restate what the code
  already says, and don't leave rationale-for-decision notes in the code. Fewer, precise
  comments beat many shallow ones.
- **Tests:** the backend follows TDD — see
  [assemblix-app-api/rules/writing-tests.md](assemblix-app-api/rules/writing-tests.md) for
  the harness, fixtures, and the mandatory AAA pattern.
- **Frontend i18n:** all user-facing text goes through `t("key")`; never hardcode strings.
- **Migrations:** never hand-write Alembic migrations — use `./makemigrations.sh`.

## Commit messages & releases

This project uses [Conventional Commits](https://www.conventionalcommits.org) and automates
releases with [release-please](https://github.com/googleapis/release-please). Your commit
(and squash-merge PR) titles drive the next version and the changelog, so prefix them:

```
feat: add Slack notification node          # → minor bump, "Features"
fix: prevent CEL timeout on empty input    # → patch bump, "Bug Fixes"
docs: clarify queue tier setup             # → no version bump
feat!: rename workflow export format       # "!" (or BREAKING CHANGE:) → major bump
```

Common types: `feat`, `fix`, `perf`, `security`, `docs`, `refactor`, `build`, `ci`,
`test`, `chore`. You don't tag or edit versions by hand — on merge to `main`, release-please
opens/updates a **release PR** that bumps the version in lockstep (root manifest +
`pyproject.toml` + `package.json`) and regenerates [CHANGELOG.md](CHANGELOG.md). Merging
that PR creates the `vX.Y.Z` tag and the GitHub Release.

📖 **Full branching, commit, and release rules: [internal-docs/git-workflow.md](internal-docs/git-workflow.md).**

## Adding a workflow node

Custom node types are the main extension point. See
[internal-docs/CONTRIBUTING_NODES.md](internal-docs/CONTRIBUTING_NODES.md) for a worked example and the
packaging guide (nodes register by string type and can be auto-discovered via entry
points — no core changes needed).

## Pull requests

1. Branch off `main`.
2. Keep PRs focused; write a clear description of what and why.
3. Ensure `make check` is green and the PR template checklist is satisfied.
4. Link any related issue.

## Reporting bugs / requesting features

Use the GitHub issue templates. For **security vulnerabilities**, do **not** open a public
issue — follow [SECURITY.md](SECURITY.md).
