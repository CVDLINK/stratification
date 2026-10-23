# Describing an AI model

**This folder is for AI models only.** If your output is a tool or a dataset, delete the whole
`ai-model/` folder and follow [`../PUBLISHING.md`](../PUBLISHING.md) on its own.

An AI model gets two descriptions that other people and machines can read:

- an **AI Card** — an EU-AI-Act model card[^1] (HTML + JSON-LD) that ships with the model
- an entry in the **[AIMe registry](https://aime-registry.org/)** — a public register of AI methods
  in biomedical research

You do **not** write them separately. You write **one model description file**, and both are
generated from it. A field is required if *either* output needs it, which is why the file asks for
things that never appear on the visual card — `reproducibility`, `method_detail`, `privacy` and
`epistasis` all feed AIMe only. Nothing is lost if you don't see it on the card.

See [`examples/heartwatch-ecg.html`](examples/heartwatch-ecg.html) for a finished card — open it
in a browser. It was generated from [`examples/heartwatch-ecg.yaml`](examples/heartwatch-ecg.yaml)
and nothing else.

---

## 1 · Write the model description file

Copy the template to the name the generators expect:

```bash
cp model-description-template.yaml model-description.yaml
```

Then fill it in. Two things make this much easier:

- **In VS Code**, install the Red Hat **YAML** extension. The schema is wired in by the
  `# yaml-language-server:` line at the top of the file, so you get dropdowns of allowed values
  (`Ctrl+Space`), hover help explaining each field, and red squiggles on anything missing or
  invalid — live as you type.
- **Start from the closest example.** All content in them is invented, and the model names begin
  with `EXAMPLE` so nothing is mistaken for a real description.

| Example | Kind of model |
|---|---|
| `heartwatch-ecg` | Risk **classifier**, a standalone clinical system — the fullest card: deployment, human involvement, risk profile, governance |
| `coronaseg` | **Segmentation**, a pipeline stage |
| `stenoscan` | Object **detection**, a pipeline stage |
| `cardioembed` | **Foundation / representation** backbone — outputs embeddings |
| `omicclust` | Unsupervised **discovery** — finds subgroups, predicts nothing |

Which sections your card has depends on the model: a predictive model fills a `task` block; a
system used on patients also fills `deployment` + `governance`; a backbone or research tool fills
neither.

To check the file outside the editor:

```bash
pip install check-jsonschema
check-jsonschema --schemafile model-description.schema.json model-description.yaml
```

That checks shape and rules only — required fields, allowed values, types. It cannot tell you
whether what you wrote is *true*.

## 2 · Generate the AI Card

```bash
cd generators/ai-card
pip install -r requirements.txt
python generate_ai_card.py                     # reads ../../model-description.yaml
python generate_ai_card.py path/to/model.yaml  # or point it at a specific file
```

Writes `model-description.html` and `.jsonld` into this folder, next to the description they came
from. The input is validated first — an invalid file fails loudly rather than producing a
half-filled card.

The `.jsonld` is the same content as the visual card, expressed as linked data: field names become
URLs that other systems already understand (`schema:name`, `dcat:Dataset`), so a card can be
queried, or joined to its Zenodo record, without anyone having read the CVDLINK schema. The
vocabulary lives in [`ai-card.context.jsonld`](ai-card.context.jsonld) and is embedded into every
card, so the file stands alone with nothing to fetch.

What makes that joining possible is the card's **identity** — the DOI or URL the model is published
under. Once you have a Zenodo DOI, put it in `card_metadata.identifier` and regenerate: the card
becomes citable and can be linked to its record. Until then your source-code URL stands in, and
without either the card is anonymous — readable, but impossible to point at. `card_date` and
`spec_url` are filled in for you at generation time; leave them out of the file.

**Commit both.** They are versioned alongside the model and go into the Zenodo archive with each
release.

## 3 · Generate and submit the AIMe record

```bash
cd generators/aime
pip install -r requirements.txt
python generate_aime_entry.py         # build the entry from the same file
python submit_report.py               # submit it (not public by default)
```

> **A submitted AIMe record cannot be deleted.** Like a Zenodo DOI, it is permanent — you can
> update it, but not remove it. `submit_report.py` submits as **not public**, so the record exists
> but isn't listed; review it, then re-submit with `--public` when you're satisfied.

Because that is irreversible, the description is validated against the schema before anything is
built or sent — the same check the AI Card generator runs. An invalid file stops here rather than
becoming a permanent record.

**Keep the report key that comes back.** The API shows the password once, and you need it to
update the entry later. `submit_report.py` stores it in `output/reports.json` — that file holds
passwords, so keep it local and never commit it (it's already in `.gitignore`). Lose the key and
you can never change the entry. To see what's stored:

```bash
python submit_report.py list
```

AIMe shows a completeness **score** on the registry. It isn't something you submit — AIMe computes
it in the browser from your answers, so the way to raise it is to fill in more of the description.

Add the registry link to your `README.md` once submitted.

---

## When the model changes

Update `model-description.yaml`, regenerate the card, commit, and cut a new release — Zenodo
creates a new version with its own DOI.

For AIMe, update the existing record rather than submitting a second one:

```bash
python generate_aime_entry.py update <id> <password>
```

[^1]: Golpayegani, D., Hupont, I., Panigutti, C., Pandit, H.J., Schade, S., O'Sullivan, D., Lewis, D.
(2024). *AI Cards: Towards an Applied Framework for Machine-Readable AI and Risk Documentation
Inspired by the EU AI Act.* APF 2024, LNCS 14831, pp. 48–72.
<https://doi.org/10.1007/978-3-031-68024-3_3>
