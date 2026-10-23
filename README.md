# <Project name>

> Created from the CVDLINK **repo-template**. Fill in the placeholders below, then work
> through [PUBLISHING.md](PUBLISHING.md) to release this project to Zenodo → OpenAIRE → EOSC.
> It works for any research output — a model, a tool, or a dataset.

## What it is

<2–5 sentences: what this project is (model / tool / dataset), and its intended use.>

## Status

`experimental`  <!-- one of: experimental | prototype | stable | archived | data-only -->

## Inputs / outputs — *for a model or tool*

- **Input:** <e.g. 12-lead ECG (median beat) · OMOP EHR table · CLI arguments>
- **Output:** <e.g. class probability · segmentation mask · report file>

## Install / run

```bash
# example only — nothing below exists yet; replace with your real steps
pip install -r requirements.txt
python run.py --input example_input
```

## Model documentation — *AI models only*

If this project is an AI model, it is described by an **AI Card**: what it does, the data and
cohort it was built on, how it was evaluated, its limitations, and — for a system used on
people — its risk profile. The card is generated from the model description file and lives in
this repo, so it is versioned with the model and archived with each release.

- **AI Card:** [`ai-model/model-description.html`](ai-model/model-description.html)
- **AIMe registry:** <add the registry link once the record is submitted.>

## Maintainer

<Team or person> · <contact email>

## How to cite

Once this repo is archived to Zenodo, add the DOI here (citation metadata lives in `.zenodo.json`).
