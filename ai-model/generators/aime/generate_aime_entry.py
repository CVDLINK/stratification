#!/usr/bin/env python3
"""
CVDLINK AIMe-registry entry generator — driven by the model description.

Pipeline:  model description YAML  ->  AIMe `answers` tree (MD/P/D/M/R)  ->  write / submit

ONE developer input (../model-description) produces the AIMe entry here and the AI Card
in ../ai-card. This maps the human-readable model description fields onto the AIMe
questionnaire's field-ID tree and short option keys (e.g. classification -> P.3.1 = 'cf'),
taken from the registry's questionnaire.yaml.

Sections: MD/P/D/M/R plus PR (Privacy) and EP (Epistasis). MD/P/D/M/R follow the AIMe
backend questionnaire; PR/EP follow the live registry's 2023 questionnaire. PR/EP are
opt-in: when the model description `privacy` / `epistasis` blocks (or their gate fields) are
absent, the gating radios are set to 'na' (Doesn't apply), exactly as a developer would
leave them. The self-hosted backend (MD/P/D/M/R only) stores PR/EP verbatim without
rendering them; the live registry renders them.

The `answers` body encoding (see aime README):
  string/text -> str · boolean -> true/false · radio/select -> {custom, value}
  checkboxes/tags -> [ {custom, value}, ... ] · complex -> object keyed by child id · list -> array

Usage:
    python generate_aime_entry.py                         # build -> output/<name>.answers.json
    python generate_aime_entry.py path/to/model.yaml      # a specific model description file
    python generate_aime_entry.py submit [model.yaml]     # build + POST + round-trip diff
    python generate_aime_entry.py get <id>
    python generate_aime_entry.py update <id> <password> [model.yaml]

  Point at a self-hosted backend with --base-url (default http://localhost:9000). Submits are isPublic:false.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("Missing deps. Run:  pip install -r requirements.txt")

SCRIPT_DIR = Path(__file__).parent
AI_MODEL_DIR = SCRIPT_DIR.parent.parent
SCHEMA = AI_MODEL_DIR / "model-description.schema.json"
DEFAULT_INPUT = AI_MODEL_DIR / "model-description.yaml"
OUTPUT_DIR = SCRIPT_DIR / "output"
DEFAULT_BASE = "http://localhost:9000"


# ---------------------------------------------------------------------------
# Validation (same schema the AI Card generator uses)
# ---------------------------------------------------------------------------
def validate(data):
    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return ["/".join(str(p) for p in e.path) + ": " + e.message for e in errors]


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------
def opt(key):
    return {"custom": False, "value": key}


def custom(text):
    return {"custom": True, "value": text}


def yn(b):
    return "yes" if b else "no"


def _map_first(text, table, default="other"):
    """Return the option key whose substring trigger appears in `text` (lower-cased)."""
    t = (text or "").lower()
    for trigger, key in table:
        if trigger in t:
            return key
    return default


# value -> option-key tables (ordered; first substring match wins)
CATEGORY = {
    "classification": ("cf", None),
    "regression": ("ce", None),
    "generation": ("dg", None),
    "discovery": ("cl", None),                       # clustering
    "retrieval": ("rr", None),                       # ranking / recommendation
    "segmentation": ("other", "Segmentation"),
    "detection": ("other", "Detection"),
    "representation": ("other", "Representation / foundation model"),
    "other": ("other", None),                        # free text from model_type_other
}
KEYWORD_OPTS = {"omics", "clinical", "medical_speciality", "endocrinology", "cardiology"}
PREPROCESS = [("normal", "no"), ("missing", "md"), ("feature select", "fs"), ("outlier", "ol"),
              ("abstract", "ab"), ("reformul", "rf"), ("approxim", "ap"), ("transform", "ft")]
METRICS = [("auc", "auc"), ("f1", "f1"), ("accuracy", "acc"), ("precision", "pc"), ("recall", "rc"),
           ("confusion", "cm"), ("loss", "l"), ("mae", "me"), ("mse", "me"), ("gini", "gini"),
           ("runtime", "rt"), ("sensitivity", "sa")]
OVERFIT = [("cross", "cv"), ("shuffle", "ss"), ("independent", "id"), ("bootstrap", "bs"),
           ("regular", "rg"), ("feature select", "fs")]
RERUN = [("docker", "docker"), ("build", "build"), ("requirement", "req"), ("conda", "conda"), ("readme", "readme")]
LICENSE = [("apache", "apache_2"), ("mit", "mit"), ("mozilla", "moz_2"), ("mpl", "moz_2"),
           ("agpl", "gnu_agpl_v3"), ("lgpl", "gnu_lgpl_v3"), ("gpl", "gnu_v3"), ("boost", "boost_1")]
PLATFORM = [("windows", "win"), ("linux", "lin"), ("mac", "mac")]
COMPUTE_TRIGGERS = ("gpu", "vram", "cuda", "tpu", "cluster", "hpc", "exceed", "beyond", "more than a regular")
# PR — Privacy (live 2023 questionnaire)
COMMUNICATION = {"star_based": "star", "peer_to_peer": "p2p", "other": "other"}
TRANSMISSION = {"unpredictable": "na", "constant": "const", "sub_linear": "sublin",
                "linear": "lin", "super_linear": "suplin"}
LOCAL_PRIV = [("differential", "dp")]                                   # else -> other
FED_PRIV = [("multi-party", "smpc"), ("smpc", "smpc"), ("homomorphic", "he"), ("(he)", "he")]


def checkbox_list(items, table):
    """Map a list of free-text items to a de-duplicated list of option objects (unmapped -> 'other')."""
    keys, out = [], []
    for it in items or []:
        k = _map_first(it, table, "other")
        if k not in keys:
            keys.append(k)
            out.append(opt(k))
    return out


# ---------------------------------------------------------------------------
# model description -> AIMe answers tree
# ---------------------------------------------------------------------------
def build_answers(data):
    ident = data.get("identity", {})
    prov = data.get("provenance", {})
    intended = data.get("intended", {})
    md = data.get("method_detail", {})
    repro = data.get("reproducibility", {})

    # ---- MD — Metadata ----
    keywords = []
    for kw in ident.get("keywords", []):
        keywords.append(opt(kw.lower()) if kw.lower() in KEYWORD_OPTS else custom(kw))
    contacts = [{"1": c.get("name", ""), "2": c.get("institution", ""),
                 "3": c.get("email", ""), "4": c.get("orcid", "")} for c in prov.get("contacts", [])]
    md_block = {
        "1": ident.get("system_name", ""),
        "2": ident.get("short_title", ""),
        "3": ident.get("short_description", ""),
        "4": prov.get("paper_url", ""),
        "5": keywords,
        "6": contacts,
        "7": [prov["funding"]] if prov.get("funding") else [],
        "8": True,
        "9": [],
    }

    # ---- P — Purpose ----
    sm = intended.get("surrogate_marker", {})
    cat_key, cat_label = CATEGORY.get(ident.get("model_type", ""), ("other", None))
    p32 = ident.get("model_type_other", "") or (cat_label or "") if cat_key == "other" else ""
    p_block = {
        "1": intended.get("purpose", ""),
        "2": {"1": bool(sm.get("predicts")), "2": sm.get("details", "") if sm.get("predicts") else ""},
        "3": {"1": opt(cat_key), "2": p32},
    }

    # ---- D — Dataset (one block per dataset) ----
    d_block = []
    for ds in data.get("data", {}).get("datasets", []):
        real = ds.get("origin") == "real"
        avail_key = {"public": "a", "on_request": "r", "restricted": "na", "none": "na"}.get(ds.get("availability"), "na")
        pp_items = ds.get("preprocessing", [])
        d_block.append({
            "1": ds.get("description", ""),
            "2": {
                "1": opt("r" if real else "s"),
                "2": ds.get("simulated_how", "") if not real else "",       # D.2.2: only when simulated
                "3": opt(yn(ds.get("ethics_approval"))) if real else "",     # D.2.3: only when real
            },
            "3": {
                "1": opt(avail_key),
                "2": ds.get("location_or_request", "") if avail_key == "a" else "",
                "3": ds.get("location_or_request", "") if avail_key == "r" else "",
            },
            "4": opt(yn(ds.get("used_for_training"))),
            "5": {"1": opt(yn(ds.get("bias_checked"))),
                  "2": ds.get("bias_details", "") if ds.get("bias_checked") else ""},
            "6": {"1": str(ds.get("n_samples", "")), "2": str(ds.get("n_features", ""))},
            "7": {"1": checkbox_list(pp_items, PREPROCESS), "2": "; ".join(pp_items)},
        })

    # ---- M — Method ----
    metric_names = [m.get("name", "") for m in data.get("metrics", [])]
    metric_opts = checkbox_list(metric_names, METRICS)
    unmapped_metrics = [n for n in metric_names if _map_first(n, METRICS, "other") == "other"]
    of = md.get("overfitting", {})
    m_block = {
        "1": ", ".join(ident.get("ai_techniques", [])),
        "2": opt({"default": "default", "tuning": "hpt", "doesnt_apply": "na"}.get(md.get("hyperparameters"), "default")),
        "3": {"1": metric_opts, "2": "; ".join(unmapped_metrics)},
        "4": {"1": opt(yn(of.get("measures_taken"))),
              "2": checkbox_list(of.get("methods", []), OVERFIT) if of.get("measures_taken") else [],
              "3": of.get("details", "")},
        "5": _radio_detail(md.get("trigger_situations", {}), "checked"),
        "6": _radio_detail(md.get("randomized_steps", {}), "checked"),
        "7": _radio_detail(md.get("baseline", {}), "compared"),
        "8": _radio_detail(md.get("state_of_the_art", {}), "compared"),
    }

    # ---- R — Reproducibility ----
    rerun = repro.get("means_to_rerun", {})
    sc = repro.get("source_code", {})
    sim = repro.get("simulator_code", {})
    prep = repro.get("preprocessing_code", {})
    pre = repro.get("pretrained_model", {})
    env = repro.get("execution_environment", {})
    lic = sc.get("license", "")
    lic_key = _map_first(lic, LICENSE, "other")
    platforms = env.get("platforms", [])
    compute_txt = env.get("computing_resources", "")
    needs_compute = any(t in compute_txt.lower() for t in COMPUTE_TRIGGERS)
    r_block = {
        "1": {"1": opt(yn(rerun.get("provided"))),
              "2": checkbox_list(rerun.get("methods", []), RERUN) if rerun.get("provided") else [],
              "3": ""},
        "2": {
            # R.2.1.2–R.2.1.4 only appear when the code is public; leave blank otherwise
            "1": {"1": opt(yn(sc.get("public"))),
                  "2": sc.get("url", "") if sc.get("public") else "",
                  "3": bool(sc.get("scm_used")) if sc.get("public") else "",
                  "4": ((opt(lic_key) if lic_key != "other" else custom(lic)) if lic else "") if sc.get("public") else ""},
            "2": {"1": opt("yes" if sim.get("public") else "na"),
                  "2": sim.get("url", "") if sim.get("public") else ""},
            "3": {"1": opt(yn(prep.get("public"))),
                  "2": prep.get("url", "") if prep.get("public") else ""},
        },
        "3": {"1": opt(yn(pre.get("provided"))), "2": pre.get("url", "") if pre.get("provided") else ""},
        "4": {
            "1": {"1": checkbox_list(platforms, PLATFORM), "2": ""},
            "2": {"1": opt(yn(needs_compute)), "2": compute_txt if needs_compute else ""},
        },
    }

    # ---- PR — Privacy · EP — Epistasis (opt-in; live 2023 questionnaire) ----
    pr_block = build_privacy(data.get("privacy", {}))
    ep_block = build_epistasis(data.get("epistasis", {}))

    return {"MD": md_block, "P": p_block, "D": d_block, "M": m_block, "R": r_block,
            "PR": pr_block, "EP": ep_block}


def _radio_detail(obj, gate):
    """M.5–M.8 shape: {1: yes/no radio, 2: details when yes}."""
    yes = bool(obj.get(gate))
    return {"1": opt(yn(yes)), "2": obj.get("details", "") if yes else ""}


def build_privacy(priv):
    """model description `privacy` -> AIMe PR. Missing gate -> 'na' (Doesn't apply), matching AIMe's opt-in."""
    dt = priv.get("data_traces", {})
    fed = priv.get("federated", {})

    traces_key = yn(dt["possible"]) if "possible" in dt else "na"
    dt_applies = traces_key != "na"
    pr1 = {
        "1": opt(traces_key),
        "2": dt.get("elaboration", "") if dt_applies else "",
        "3": {"1": checkbox_list(dt.get("techniques", []), LOCAL_PRIV) if dt_applies else [], "2": ""},
    }

    fed_key = yn(fed["is_federated"]) if "is_federated" in fed else "na"
    is_fed = fed_key == "yes"
    pr2 = {
        "1": opt(fed_key),
        "2": fed.get("shared_data", "") if is_fed else "",
        # PR.2.3–PR.2.5 only appear when federated = yes; leave blank otherwise
        "3": {"1": opt(COMMUNICATION.get(fed.get("communication"), "star")) if is_fed else "", "2": ""},
        "4": {"1": checkbox_list(fed.get("privacy_techniques", []), FED_PRIV) if is_fed else [], "2": ""},
        "5": opt(TRANSMISSION.get(fed.get("transmission_ratio"), "na")) if is_fed else "",
    }
    return {"1": pr1, "2": pr2}


def build_epistasis(ep):
    """model description `epistasis` -> AIMe EP. Missing gate -> 'na' (Doesn't apply)."""
    ml = ep.get("multi_loci", {})
    bl = ep.get("biological_levels", {})

    ml_key = yn(ml["has_measure"]) if "has_measure" in ml else "na"
    ml_yes = ml_key == "yes"
    ep1 = {
        "1": opt(ml_key),
        "2": ml.get("description", "") if ml_yes else "",
        # EP.1.3 only appears when EP.1.1 = yes; leave blank otherwise (don't answer a hidden question)
        "3": opt(yn(ml.get("convertible_to_or_rr"))) if ml_yes else "",
    }

    bl_key = yn(bl["multiple"]) if "multiple" in bl else "na"
    bl_yes = bl_key == "yes"
    ep2 = {"1": opt(bl_key), "2": bl.get("elaboration", "") if bl_yes else ""}
    return {"1": ep1, "2": ep2}


# ---------------------------------------------------------------------------
# HTTP transport (self-hosted AIMe backend) — carried over from the phase-0 test
# ---------------------------------------------------------------------------
def _request(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def load_and_build(path):
    """Validate first, then map. An AIMe record cannot be deleted once submitted, so an
    invalid description must fail here rather than become a permanent public entry."""
    data = yaml.safe_load(Path(path).read_text())
    errors = validate(data)
    if errors:
        print(f"✗ {Path(path).stem}: INVALID against model-description.schema.json")
        for e in errors:
            print(f"    - {e}")
        sys.exit("Refusing to build an AIMe entry from an invalid model description.")
    return build_answers(data), Path(path).stem


def contact_email(path, override=None):
    """Email the report is filed under: --email if given, else the first contact
    in the model description. Never a baked-in address."""
    if override:
        return override
    data = yaml.safe_load(Path(path).read_text())
    contacts = data.get("provenance", {}).get("contacts", [])
    email = contacts[0].get("email") if contacts else None
    if not email:
        sys.exit("No contact email: add provenance.contacts[0].email to the model "
                 "description, or pass --email.")
    return email


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_build(args):
    answers, name = load_and_build(args.input)
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"{name}.answers.json"
    out.write_text(json.dumps(answers, indent=2))
    print(f"✓ {name}: built AIMe answers (sections {', '.join(answers)}) -> output/{name}.answers.json")


def cmd_submit(args):
    answers, name = load_and_build(args.input)
    payload = {"answers": answers, "email": contact_email(args.input, args.email),
               "isPublic": False, "attachReport": False}
    status, resp = _request("POST", f"{args.base_url}/report", payload)
    if status != 200 or not isinstance(resp, dict):
        sys.exit(f"POST /report failed: HTTP {status}: {resp}")
    rid, pw = resp["id"], resp["password"]
    print(f"Created report: id={rid}  password={pw}  version={resp['version']}")
    print(f"  -> {args.base_url}/report/{rid}")
    status, got = _request("GET", f"{args.base_url}/report/{rid}")
    if status == 200 and isinstance(got, dict) and got.get("answers") == answers:
        print("Round-trip diff: MATCH (stored answers identical to submitted payload)")
    else:
        print("Round-trip diff: MISMATCH"); sys.exit(1)


def cmd_update(args):
    answers, _ = load_and_build(args.input)
    payload = {"answers": answers, "email": contact_email(args.input, args.email),
               "password": args.password,
               "isPublic": False, "attachReport": False}
    status, resp = _request("PUT", f"{args.base_url}/report/{args.report_id}", payload)
    if status != 200 or not isinstance(resp, dict):
        sys.exit(f"PUT /report/{args.report_id} failed: HTTP {status}: {resp}")
    print(f"Updated report: id={resp['id']}  version={resp['version']}")


def cmd_get(args):
    status, got = _request("GET", f"{args.base_url}/report/{args.report_id}")
    print(f"HTTP {status}")
    print(json.dumps(got, indent=2) if isinstance(got, (dict, list)) else got)


def main():
    p = argparse.ArgumentParser(description="Generate an AIMe registry entry from a model description")
    p.add_argument("--base-url", default=DEFAULT_BASE, help=f"backend base URL (default {DEFAULT_BASE})")
    p.add_argument("--email", default=None, help="contact email (default: provenance.contacts[0].email)")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="build the answers JSON from a model description file (default)")
    b.add_argument("input", nargs="?", default=str(DEFAULT_INPUT))
    s = sub.add_parser("submit", help="build + POST + round-trip diff")
    s.add_argument("input", nargs="?", default=str(DEFAULT_INPUT))
    u = sub.add_parser("update", help="build + PUT a new revision")
    u.add_argument("report_id"); u.add_argument("password")
    u.add_argument("input", nargs="?", default=str(DEFAULT_INPUT))
    g = sub.add_parser("get", help="GET an existing report")
    g.add_argument("report_id")

    # allow a bare positional path as shorthand for `build <path>`
    argv = sys.argv[1:]
    known = {"build", "submit", "update", "get"}
    if argv and argv[0] not in known and not argv[0].startswith("-"):
        argv = ["build"] + argv
    args = p.parse_args(argv)

    if args.cmd is None:
        args.input = str(DEFAULT_INPUT)
        cmd_build(args)
    else:
        {"build": cmd_build, "submit": cmd_submit, "update": cmd_update, "get": cmd_get}[args.cmd](args)


if __name__ == "__main__":
    main()
