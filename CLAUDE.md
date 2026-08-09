# HASS-SMS-Gammu-Gateway — repository directives

A Home Assistant add-on. The deliverable is a **Docker image** published to
`ghcr.io/homeops/hass-sms-gammu-gateway-{arch}`, not a source library.

## Release policy: release exactly when the image changes

Releases are cut by release-please from commit types listed in
`release-please-config.json`. A type that is *visible* triggers a version bump,
an image rebuild, and an "Update available" badge on every user's Home
Assistant. A *hidden* type changes the repository only.

The single question that decides the type is: **does this change what ends up
inside the image?**

Check against the Dockerfile's `COPY` list, which is the authoritative answer:

| Path | In the image? | Type to use |
|------|---------------|-------------|
| `Dockerfile`, `requirements.txt` | yes — they *build* it | `build:` (releases) |
| `run.py`, `support.py`, `urc_filter.py`, `mqtt_publisher.py`, `run.sh` | yes | `feat:` / `fix:` / `perf:` / `refactor:` |
| `config.json`, `services.yaml`, `icon.png` | yes | `feat:` / `fix:` |
| `README.md`, `DOCS.md`, `FORK.md` | **no** | `docs:` (no release) |
| `tests/**` | **no** | `test:` (no release) |
| `.github/**`, `release-please-config.json` | **no** | `ci:` / `chore:` (no release) |

### Deviation from convention, and why

Conventional Commits and every mainstream tool (semantic-release,
release-please defaults, standard-version) treat `build:` as **non-releasable**,
because in a normal project the build system is developer-facing scaffolding.

**Here it is inverted: the Dockerfile is the product.** The patched libGammu that
makes SMS work on SIMCom modems exists nowhere else in the tree — it is created
by the `git clone` / `patch` / `cmake` steps in `sms-gammu-gateway/Dockerfile`.
A Dockerfile-only change that did not release would leave every user running the
old image with no signal that anything happened.

This is not hypothetical. The build carries a deliberate tripwire that fails once
[gammu/gammu#1177](https://github.com/gammu/gammu/pull/1177) is merged upstream,
forcing a switch to a released gammu. That fix will touch only the Dockerfile.
It must ship.

`refactor:` is likewise releasable here — it changes code baked into the image.

### Consequence to remember

release-please uses one list for two jobs: `filterCommits()` keeps a commit only
if `visibleSections.includes(commit.type)`, so **hidden types are absent from
CHANGELOG.md as well as from releases**. There is no way to express "list it but
do not release on it". Documentation changes therefore do not appear in the
changelog; that is an accepted cost of never shipping an image that is byte
identical to the previous one.

## The PR title is the release instruction

The repository is **squash-only** (`allow_merge_commit` and `allow_rebase_merge` are
off) with `squash_merge_commit_title = PR_TITLE`. Every merged PR becomes exactly
one commit on `main` whose subject is the PR title, so **the PR title is what
release-please reads** — not the commit messages on the branch.

Practical consequences:

- Getting the type wrong is fixable up to the moment of merge: retitle the PR.
  Branch commit messages no longer matter to the release, which is what makes this
  safe under the no-force-push rule.
- Do not restore merge commits. With a merge commit GitHub echoes the branch
  commit subject into the merge commit body, release-please parses both, and the
  same change is listed twice in the changelog (seen on PR #16 → release PR #18).
- `squash_merge_commit_message = PR_BODY`, so the PR description becomes the commit
  body and `Fixes #N` links are picked up. Beware that a PR body containing the
  literal text `BREAKING CHANGE:` will be read as a major bump.

## Verifying a release actually shipped

A merged release PR should produce, in order: a `sms-gammu-gateway-vX.Y.Z` tag, a
successful `publish` workflow run, and new tags on the GHCR package. Check with:

```powershell
gh run list --repo HomeOps/HASS-SMS-Gammu-Gateway --workflow publish.yml --limit 5
```

Publishing is chained from `release-please.yml` via `workflow_call`. It cannot use
`on: push: tags:` — tags pushed with `GITHUB_TOKEN` do not trigger workflows, by
design, to prevent recursion.

## Privacy

Never commit real phone numbers, IMEIs, or IMSIs. Use the NANP range reserved for
fiction, `+1 555 0100`–`+1 555 0199`.

This applies to encoded forms too. SMS PDUs carry the destination number as
swapped BCD nibbles, so `0B91` `4152126421F3` is a readable phone number to anyone
who decodes it — a hexdump pasted into an issue leaks exactly as much as plain
text does.

---
*Last garbage-collected: 2026-08-08*
