---
type: note
kind: model-card
slug: <kebab-case>
title: <Model Family — Variant>
created: YYYY-MM-DD
updated: YYYY-MM-DD
read: false
owner: blaz
tags: [type/model-card, status/stub, domain/models, model-type/llm]
year: YYYY
developer: <Org / Lab>
family: <Model family name, e.g. DeepSeek-V3>
variants: ["<flagship>", "<small>"]
license: <license id or url>
model_type: llm        # llm | multimodal | system-card | world-model | vision | ...
parameters_total: "<671B>"
parameters_active: "<37B>"
raw_pdf: null          # populate when archiving an official PDF
links:
  source: <paper / blog / HF card / announcement URL>
  paper:  null
  code:   null
  raw:    null
---

# <Model Family — Variant>

> *<developer>* — released <YYYY-MM-DD>

## Overview

(one paragraph: what the model is, what's notable about its architecture
or training recipe, why this card exists)

## Model Family

| Property | Value |
|---|---|
| Developer    | <org>          |
| Release date | YYYY-MM-DD     |
| Family       | <family>       |
| Variants     | <flagship>, <small>, <chat> |
| License      | <license>      |

## Architecture

| Property              | Value           |
|---|---|
| Parameters (total)    | <671B>          |
| Parameters (active)   | <37B>           |
| Layers                | <int>           |
| Hidden dim            | <int>           |
| Attention             | <MLA / GQA / MHA / ...> |
| Heads                 | <int>           |
| Positional encoding   | <RoPE / ALiBi / ...> |
| Normalization         | <RMSNorm / LayerNorm> |
| Activation            | <SwiGLU / GeGLU / ReLU²> |
| Vocabulary size       | <int>           |
| Context length        | <int>           |

### MoE properties (if applicable)

| Property              | Value           |
|---|---|
| Experts (total)       | <int>           |
| Experts (active)      | <int>           |
| Expert dim            | <int>           |
| Routing               | <top-k / shared+routed / ...> |
| Load balancing        | <method>        |

## Key Architecture Choices

- (bullet list of distinctive choices: what's unusual or load-bearing)

## Training

| Property         | Value             |
|---|---|
| Data tokens      | <T>               |
| Optimizer        | <AdamW / Muon>    |
| Schedule         | <warmup + cosine> |
| Stages           | <pretrain → mid-train → SFT → DPO/RLHF> |
| Compute          | <H100 hours>      |

## Reported Evals

| Eval | Score | Source |
|---|---|---|
| <eval-name> | — | — |

## Related

- (wikilinks to peer model-cards, the underlying paper if separate, or
  concept notes that contextualize this architecture)

## Caveats

- (what's `[needs verification]`, what the source doesn't disclose)

## Source

- <paper / blog / model card URL>
