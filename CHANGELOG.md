# CHANGELOG


## v0.1.0 (2025-02-24)

### Bug Fixes

- Add Tiny ImageNet loader to exports of data_loaders package
  ([`3add754`](https://github.com/hadarshavit/CTRAIN/commit/3add754a624db26fded1a89ce4aaad8b1faf561e))

- Fix resume_from_checkpoint functionality
  ([`015d01e`](https://github.com/hadarshavit/CTRAIN/commit/015d01ec9b5fa2747aacfc8bc401f8e71c149e98))

Until now, the start_epoch was not passed correctly to the train function. In addition, we bumped
  the SMAC dependency

- Make evaluation method in model wrappers configurable
  ([`62a704d`](https://github.com/hadarshavit/CTRAIN/commit/62a704da28558a83ff2415007d69762cea9480fc))

Until now, certified robustness evaluation using the `evaluate` method was carried out using the
  ADAPTIVE method. Now, users may provide a incomplete verification method to use. The default is
  still `ADAPTIVE`, i.e. the certification methods are carried out sequentially in ascending order
  of computational complexity.

- Pass gradient expansion alpha to STAPS loss calculation
  ([`06a4ae2`](https://github.com/hadarshavit/CTRAIN/commit/06a4ae295db69fd717426840f4c85b6f8d7f8c22))

### Continuous Integration

- Add git pull in publish workflow
  ([`3bd02a8`](https://github.com/hadarshavit/CTRAIN/commit/3bd02a8016c823802df3d7af4ba081d9681a36d4))

the commit in the previous workflow step was not present during the publish phase

- Fix versioning and publishing workflows
  ([`e003d74`](https://github.com/hadarshavit/CTRAIN/commit/e003d74c7d07de49a0d52d11af8c4a083834d337))

### Features

- Add checkpoint save interval
  ([`379f30e`](https://github.com/hadarshavit/CTRAIN/commit/379f30e18867fbf1f944df09039ee5f54f4fca4b))

Users can now specify an interval of epochs after which a checkpoint is saved. Before that, the
  checkpoints were saved every epoch which may have been undesirable due to space constraints.
