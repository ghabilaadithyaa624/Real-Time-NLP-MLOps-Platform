# Dataset: IMDb Large Movie Review Dataset

## Selection

The initial training dataset is the **IMDb Large Movie Review Dataset**, loaded from the Hugging Face Datasets mirror [`stanfordnlp/imdb`](https://huggingface.co/datasets/stanfordnlp/imdb). The upstream source is the Stanford-hosted [Large Movie Review Dataset](https://ai.stanford.edu/~amaas/data/sentiment/), introduced by Maas et al. in the ACL 2011 paper [Learning Word Vectors for Sentiment Analysis](https://aclanthology.org/P11-1015/).

This is a suitable first dataset because it is a well-established binary sentiment benchmark, has a stable schema, is large enough to exercise a Transformer training pipeline, and does not require silently downloading an unknown or user-uploaded dataset.

## Pinned source and schema

| Property | Value |
|---|---|
| Hugging Face dataset | `stanfordnlp/imdb` |
| Configuration | `plain_text` |
| Pinned revision | `e6281661ce1c48d982bc483cf8a173c1bbeb5d31` |
| Language | English (`en`) |
| Input column | `text` |
| Label column | `label` |
| Source label `0` | `neg` → platform class `negative` |
| Source label `1` | `pos` → platform class `positive` |
| Labeled examples | 50,000 |
| Additional unlabeled examples | 50,000; excluded from supervised training |

The revision is pinned in `training/config.yaml`. The pipeline passes this revision to `load_dataset` so a future change to the dataset repository does not silently change a training run.

## Splits

The source contains 25,000 labeled training reviews and 25,000 labeled test reviews. The source train and test splits are balanced: 12,500 negative and 12,500 positive examples in each.

The project preserves the source `test` split as a final holdout. It creates validation data only from the source `train` split using a deterministic, stratified 90/10 split with seed `42`:

| Derived split | Source | Expected examples | Expected negative / positive |
|---|---|---:|---:|
| train | source `train` | 22,500 | 11,250 / 11,250 |
| validation | source `train` | 2,500 | 1,250 / 1,250 |
| test | source `test` | 25,000 | 12,500 / 12,500 |

The exact counts are verified by `training/dataset.py` at runtime. The test set is never used to choose checkpoints or tune hyperparameters.

## Reproducibility

`training/dataset.py` enforces:

- a pinned Hugging Face dataset revision;
- an explicit `plain_text` configuration;
- an explicit train and test split;
- a configured validation fraction;
- a fixed random seed;
- stratification by the label column;
- a configurable label mapping that can be extended for a future multiclass dataset;
- JSON metadata output containing source, revision, split sizes, and class distributions.

Downloaded data and generated metadata are not committed to Git. They are cached outside the repository or under ignored paths.

## License and usage considerations

The Hugging Face dataset card declares the license as `other` and does not provide a complete license text. The original Stanford page also provides source and citation information but does not grant a broad software-style license. The reviews were scraped from IMDb and are user-generated movie reviews.

Therefore:

- this project documents and uses the dataset for reproducible educational benchmarking;
- the dataset citation must be retained in training and model documentation;
- the dataset should not be redistributed from this repository;
- commercial or public production use requires an independent legal and data-usage review;
- the IMDb benchmark is not representative of customer feedback and should not be treated as a production-domain validation set.

## Citation

```bibtex
@InProceedings{maas-EtAl:2011:ACL-HLT2011,
  author    = {Maas, Andrew L. and Daly, Raymond E. and Pham, Peter T.
               and Huang, Dan and Ng, Andrew Y. and Potts, Christopher},
  title     = {Learning Word Vectors for Sentiment Analysis},
  booktitle = {Proceedings of the 49th Annual Meeting of the Association for
               Computational Linguistics: Human Language Technologies},
  month     = {June},
  year      = {2011},
  address   = {Portland, Oregon, USA},
  publisher = {Association for Computational Linguistics},
  pages     = {142--150},
  url       = {https://aclanthology.org/P11-1015/}
}
```
