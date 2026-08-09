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

## Modified GPL component

The container image does **not** install libGammu from Alpine. It builds it from source and applies
one upstream patch, because the packaged library cannot send SMS on modems that emit a bare `">"`
prompt (see [gammu/gammu#1177](https://github.com/gammu/gammu/pull/1177)).

GPL-2.0 section 3 requires that the corresponding source accompany a distributed modified binary.
It does, in full and by exact reference:

- **Base source**: `https://github.com/gammu/gammu.git`, tag pinned by the `GAMMU_VERSION` build
  argument in `sms-gammu-gateway/Dockerfile`.
- **The modification**: fetched during the build from
  `https://github.com/gammu/gammu/pull/${GAMMU_PR}.diff`, a public URL.
- **The build recipe**: `sms-gammu-gateway/Dockerfile` in this repository.

Anyone can reproduce the exact library the image contains from those three references. No patch is
vendored here, so there is no divergence between what is documented and what is built.

This arrangement is temporary. The Dockerfile fails the build once the upstream pull request is
merged, at which point the source build is replaced by a released gammu and this section no longer
applies.

## Licence interaction

The add-on's own code is MIT and Apache-2.0, and it calls libGammu through python-gammu, which is
GPL-2.0. Distributing them together means the combined work in the image is governed by the GPL for
anyone redistributing it. This is unchanged from upstream, which also ships gammu in its image; the
only difference here is that the library carries a patch, which is why its source is referenced
above.
