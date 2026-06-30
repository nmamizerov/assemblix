# Git & release workflow

How we use git in Assemblix: branching, commit conventions, and the automated release
pipeline. This is the source of truth — `CLAUDE.md` and `CONTRIBUTING.md` link here.

## Branching

- `main` is always releasable. Never commit directly to it — branch off and open a PR.
- Use short, descriptive branch names with a type prefix:
  `feat/slack-node`, `fix/cel-timeout`, `docs/self-hosting`, `chore/bump-deps`.
- Keep PRs focused and small; one logical change per PR.
- Rebase/squash so the merged history stays clean (we squash-merge — the **PR title**
  becomes the commit on `main`, so it must follow Conventional Commits, see below).
- Do **not** `git push` or open PRs on someone's behalf without being asked.

## Commit messages — Conventional Commits

Every commit (and every squash-merge PR title) follows
[Conventional Commits](https://www.conventionalcommits.org). This is not cosmetic — it is
what drives versioning and the changelog automatically.

```
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]
```

Examples:

```
feat: add Slack notification node             # → minor bump, "Features"
fix: prevent CEL timeout on empty input       # → patch bump, "Bug Fixes"
perf: cache node registry lookups             # → patch bump, "Performance"
docs: clarify queue tier setup                # → no version bump
refactor(api): extract agent loop             # → no version bump
feat!: rename workflow export format          # → MAJOR bump (breaking)
```

| Type | Meaning | Version effect (pre-1.0) |
|------|---------|--------------------------|
| `feat` | New feature | minor |
| `fix` | Bug fix | patch |
| `perf` | Performance improvement | patch |
| `security` | Security fix/hardening | patch |
| `docs` | Documentation only | none |
| `refactor` | Code change, no behavior change | none |
| `deps` | Dependency updates | patch |
| `build` / `ci` / `test` / `chore` | Tooling / housekeeping | none (hidden from changelog) |

**Breaking changes**: add `!` after the type (`feat!:`) **or** a `BREAKING CHANGE:` footer.
While the project is pre-1.0 (`0.x`), a breaking change bumps the **minor** version, per
SemVer for initial development.

The exact type→changelog-section mapping lives in
[`release-please-config.json`](https://github.com/nmamizerov/assemblix/blob/main/release-please-config.json).

## Releases — fully automated (release-please)

We use [release-please](https://github.com/googleapis/release-please). You **do not** bump
versions, edit `CHANGELOG.md`, or create tags by hand. The flow:

1. You merge Conventional-Commit PRs into `main`.
2. The [`release-please` workflow](https://github.com/nmamizerov/assemblix/blob/main/.github/workflows/release-please.yml)
   keeps a **"chore(main): release X.Y.Z" PR** open, continuously updating it: it computes
   the next version from the commits, regenerates `CHANGELOG.md`, and bumps the version in
   **lockstep** across three files via the manifest:
   - `.release-please-manifest.json` (the source of truth for the current version)
   - `assemblix-app-api/pyproject.toml` (`project.version`)
   - `assemblix-app-web/package.json` (`version`)
3. When you're ready to ship, **merge that release PR**. release-please then:
   - creates the git tag **`vX.Y.Z`**, and
   - publishes the **GitHub Release** with generated notes.

That's the whole release. One repo version, one tag, one root changelog.

### Things to NOT do

- ❌ Don't edit version numbers in `pyproject.toml` / `package.json` manually.
- ❌ Don't hand-write `CHANGELOG.md` entries (release-please owns it).
- ❌ Don't create `vX.Y.Z` tags manually (except the one-time bootstrap below).
- ❌ Don't squash-merge with a non-conventional PR title — it pollutes the changelog.

## Working with tags & versions

```bash
git tag -l                      # list released versions
git checkout v0.1.0             # inspect the code at a release (detached HEAD)
git switch -                    # go back to your branch
```

- Browse releases & notes: the **Releases** tab on GitHub.
- Compare two versions:
  `https://github.com/nmamizerov/assemblix/compare/v0.1.0...v0.2.0`.
- The current in-development version always lives in `.release-please-manifest.json`.

## Escape hatch — manual release

If you ever need to cut a release without the bot (e.g. bootstrapping the very first tag),
use the GitHub CLI:

```bash
gh release create v0.1.0 --generate-notes
```

Then make sure `.release-please-manifest.json` reflects that version so the next automated
run continues from the right baseline.
