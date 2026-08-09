# Third-party notices

This repository is MIT licensed (see `LICENSE`), copyright PavelVe, and that notice is retained
unchanged in this fork. The add-on it ships combines work under three different licences.

## Add-on source

| Component | Licence | Notes |
|---|---|---|
| This repository | MIT © 2025 PavelVe | `LICENSE`, unmodified |
| [pajikos/sms-gammu-gateway](https://github.com/pajikos/sms-gammu-gateway) | Apache-2.0 | `run.py` and `support.py` derive from it and keep their attribution headers |

## Runtime dependencies shipped in the container image

| Component | Licence |
|---|---|
| [gammu / libGammu](https://github.com/gammu/gammu) | **GPL-2.0** |
| [python-gammu](https://github.com/gammu/python-gammu) | **GPL-2.0** |

## GPL component built from source

The container image does **not** install libGammu from Alpine, because the packaged library cannot
send SMS on modems that emit a bare `">"` prompt
(see [gammu/gammu#1177](https://github.com/gammu/gammu/pull/1177)).

Until 2026-08-09 the image applied that fix as a patch, which made the library a *modified* GPL
work. It is no longer modified: the fix was merged upstream, and the image now builds **unmodified
upstream source** at a pinned commit. The obligation is correspondingly simpler, and is met by exact
reference:

- **Source**: `https://github.com/gammu/gammu`, at the commit pinned by the `GAMMU_COMMIT` build
  argument in `sms-gammu-gateway/Dockerfile`, distributed by GitHub as a public tarball.
- **The build recipe**: `sms-gammu-gateway/Dockerfile` in this repository.

Anyone can reproduce the exact library the image contains from those two references. Nothing is
vendored here, so there is no divergence between what is documented and what is built.

This arrangement is temporary. The Dockerfile fails the build once gammu cuts a release newer than
1.44.0 — any release after the merge date carries the fix — at which point the pinned commit is
replaced by a release tag.

## Licence interaction

The add-on's own code is MIT and Apache-2.0, and it calls libGammu through python-gammu, which is
GPL-2.0. Distributing them together means the combined work in the image is governed by the GPL for
anyone redistributing it. This is unchanged from upstream, which also ships gammu in its image; the
only difference here is that the library carries a patch, which is why its source is referenced
above.
