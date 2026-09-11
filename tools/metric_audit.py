#!/usr/bin/env python3
"""Audit the controller's cognitive metric layer.

The suite has grown ~90 metrics that read a session history and return a
number. Nothing in the repository answers the question a reader of the
README naturally asks: *is each of these earning its keep?*

This tool answers the parts of that question that can be answered without
labelled task outcomes, by measuring the metric layer against a corpus it
builds itself:

  coverage      every public hist-taking metric, and whether it ran at all
  crashes       metrics that raise on a legal, boundary-sanitized row
  dead          metrics whose value never changes across the corpus — a
                constant carries no information, whatever its docstring says
  range         metrics whose docstring declares a 0-100 / 0-1 scale and
                which leave it
  redundancy    metrics that move together (|Pearson r| above the cut),
                i.e. candidates for merging
  sensitivity   which row fields each metric actually responds to, so a
                metric that ignores the thing it is named for is visible

It needs no ground truth, so it cannot say whether a metric is *right* —
only whether it is alive, bounded, distinct, and responsive. Those are the
properties that can be settled from the outside, and a metric that fails
one of them cannot be validated by any amount of downstream evidence.

Known detection limit, learned the hard way. ``book_thread_alignment``
was dead for every ledger the controller writes — its eleven unit tests
feed it a hand-written ``domain: text`` row while ``note --open`` writes
``?NN <question> — settled by: <answer>`` — and this tool does *not*
catch it. The detector still returns 100 whenever there is no Open row to
compare against, so its modal share sits at 88.6%, just under the pinning
cut, and a corpus statistic cannot separate "usually unmeasurable" from
"never fires". Source inspection and an end-to-end run did. Treat the
pinned list as triage and the source as the verdict.

Usage:
    <python> tools/metric_audit.py
    <python> tools/metric_audit.py --json
    <python> tools/metric_audit.py --samples 2000 --corr 0.9
    <python> tools/metric_audit.py --history .mindseam/history.json
    <python> tools/metric_audit.py --check          # CI gate

Stdlib only, like the controller it audits.
"""

import argparse
import collections
import importlib.util
import inspect
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

CONFIDENCE = ("strong", "thin", "shaky")
RISK = ("low", "medium", "high")
MARKERS = ("", "OPEN", "DONE", "GRRR", "GAAAH", "PHEW")
DOMAINS = ("build", "review", "test", "docs", "deploy", "audit")
VERIFIERS = ("", "pytest", "command exit 0", "manual review", "ci")
# Deliberately mixed lengths: error_silence_ratio scores low on stubs under
# eight characters, so a corpus of only substantive messages would make a
# live metric look dead.
ERRORS = ("", "", "", "db timeout", "import failed", "assertion failed",
          "x", "err", "??", "no")
OUTCOMES = ("", "ok", "error", "partial")

# next-action shapes chosen to straddle the thresholds the specificity and
# stub detectors use, so the two are not accidentally identical on the
# corpus: "step 42" is too short to be specific but not a stub, and
# "think about ..." starts with a vague verb but is not in the stub list.
NEXT_SHAPES = (
    "{domain}: step {i}",
    "{domain}: {i}",
    "step {i}",
    "think about step {i} carefully",
    "continue",
    "todo",
    "x",
    "review the {domain} plan for step {i}",
)

ROW_FIELDS = ("t", "next", "verified", "open", "marker", "confidence",
              "verifier", "risk", "error", "outcome", "extra_steps")

BOOK = {"Goal": ["audit the metric layer"],
        "Core": ["capacity"],
        "Verified": ["\u271301 probe \u2014 verified by: pytest"],
        "Open": ["?1 does the metric move"],
        "Next": ["run the audit"]}


def load_controller():
    spec = importlib.util.spec_from_file_location("mindseam_audited", MINDSEAM)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mindseam_audited"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

def _row(t, domain, next_action, **kw):
    row = {"t": t, "next": "%s: %s" % (domain, next_action), "verified": 0,
           "open": 0, "marker": "", "confidence": "strong", "verifier": "",
           "risk": "low", "error": "", "outcome": "", "extra_steps": 0}
    row.update(kw)
    return row


ARCHETYPES = ("healthy", "stall", "escalating", "decaying", "error_loop",
              "recovering", "random", "empty", "single", "long",
              "bare", "frozen_t", "gapped_t", "time_jump")

# Planted session quality. A metric layer that claims to measure a
# session should separate these two groups; one that cannot is not
# measuring quality, whatever its docstring says. The labels come from
# how the session was built, not from an external judgement, so the
# comparison needs no ground truth — only that the shapes are genuinely
# different, which is checkable by reading `session()`.
GOOD_ARCHETYPES = frozenset(("healthy", "recovering"))
BAD_ARCHETYPES = frozenset(("stall", "error_loop", "escalating", "decaying"))

# The fields a planted shape may leave to chance.
DECORATED = ("open", "marker", "confidence", "verifier", "risk", "error",
             "outcome", "extra_steps")


def _decorate(rows, rng, controlled):
    """Randomise the fields an archetype does not deliberately control.

    Each archetype plants one axis — a stall, a risk ramp, an error loop.
    Without this, every other field keeps its default across that whole
    slice of the corpus, so a detector reading one of those fields looks
    pinned when it is merely unexercised. That mistake was made once here
    and produced three false "effectively pinned" findings.
    """
    for row in rows:
        for field in DECORATED:
            if field in controlled:
                continue
            if field == "open":
                row["open"] = rng.choice((0, 0, 1, 2))
            elif field == "marker":
                row["marker"] = rng.choice(MARKERS)
            elif field == "confidence":
                row["confidence"] = rng.choice(CONFIDENCE)
            elif field == "verifier":
                row["verifier"] = rng.choice(VERIFIERS)
            elif field == "risk":
                row["risk"] = rng.choice(RISK)
            elif field == "error":
                row["error"] = rng.choice(ERRORS)
            elif field == "outcome":
                row["outcome"] = rng.choice(OUTCOMES)
            else:
                row["extra_steps"] = rng.choice((0, 0, 1, 2, 3, 6, 9, 15))
    return rows


def session(rng, now, kind=None):
    """Build one synthetic session with a planted shape.

    ``t`` is a Unix timestamp, not an index: the controller computes ages
    as ``now - t``, so a corpus of small integers makes every age-dependent
    metric degenerate and manufactures false correlations between them.
    Stamps are therefore anchored to ``now`` and spaced realistically.
    """
    kind = kind or rng.choice(ARCHETYPES)

    def stamps(count, step=None):
        """Increasing stamps ending at roughly ``now``."""
        gap = step or rng.choice((15, 30, 60, 120, 300, 900))
        start = now - count * gap
        return [start + i * gap for i in range(count)]

    if kind == "empty":
        return []
    if kind == "single":
        return _decorate([_row(now - 60, rng.choice(DOMAINS), "a")], rng, set())
    if kind == "bare":
        # Only the two fields the schema cannot drop: a session whose
        # optional labels were never recorded. A metric that reads only
        # "there is a confidence label somewhere" is constant here.
        count = rng.randint(3, 12)
        return [{"t": t, "next": "%s: step %d" % (rng.choice(DOMAINS), i)}
                for i, t in enumerate(stamps(count))]
    if kind == "frozen_t":
        # Every row stamped the same second: no time gaps to measure.
        count = rng.randint(4, 10)
        rows = [_row(now - 60, rng.choice(DOMAINS), "step %d" % i, verified=1)
                for i in range(count)]
        return _decorate(rows, rng, {"verified"})
    if kind == "gapped_t":
        # Widely separated stamps, including a long hole.
        count = rng.randint(4, 10)
        ts, t = [], now - 86400 * count
        for _ in range(count):
            t += rng.choice((1, 2, 3600, 86400))
            ts.append(t)
        rows = [_row(ts[i], rng.choice(DOMAINS), "step %d" % i, verified=1)
                for i in range(count)]
        return _decorate(rows, rng, {"verified"})
    if kind == "time_jump":
        # A clock that goes backwards mid-session: temporal_continuity only
        # drops below 100 when a stamp regresses, so a monotone corpus
        # would make it look dead.
        count = rng.randint(4, 10)
        ts, t = [], now - 3600 * count
        for i in range(count):
            t += rng.choice((1, 2, 5))
            if i and rng.random() < 0.4:
                t -= rng.choice((10, 500, 100000))
            ts.append(t)
        rows = [_row(ts[i], rng.choice(DOMAINS), "step %d" % i, verified=1)
                for i in range(count)]
        return _decorate(rows, rng, {"verified"})

    n = rng.randint(2, 40) if kind != "long" else rng.randint(60, 120)
    ts = stamps(n)
    rows = []
    controlled = set()
    for i in range(n):
        t = ts[i]
        domain = rng.choice(DOMAINS)
        if kind == "stall":
            controlled |= {"confidence"}
            rows.append(_row(t, "build", "same step", verified=0,
                             confidence=rng.choice(("thin", "shaky"))))
            continue
        if kind == "escalating":
            controlled |= {"risk", "verified"}
            risk = RISK[min(2, i * 3 // max(n, 1))]
            rows.append(_row(t, domain, "step %d" % i, risk=risk,
                             verified=rng.choice((0, 1))))
            continue
        if kind == "decaying":
            controlled |= {"confidence", "verified"}
            idx = min(2, i * 3 // max(n, 1))
            rows.append(_row(t, domain, "step %d" % i,
                             confidence=CONFIDENCE[2 - idx],
                             verified=rng.choice((0, 0, 1))))
            continue
        if kind == "error_loop":
            controlled |= {"error", "outcome", "verified"}
            rows.append(_row(t, domain, "retry step %d" % i,
                             error="db timeout", verified=0,
                             outcome=rng.choice(("", "error"))))
            continue
        if kind == "recovering":
            controlled |= {"error", "outcome", "verifier", "confidence", "risk"}
            bad = i < n // 2
            rows.append(_row(t, domain, "step %d" % i,
                             error="db timeout" if bad else "",
                             verified=0 if bad else 2,
                             outcome="error" if bad else "ok",
                             verifier="" if bad else "pytest",
                             confidence="shaky" if bad else "strong",
                             risk="high" if bad else "low"))
            continue
        if kind == "healthy":
            controlled |= {"verifier", "outcome", "confidence", "marker"}
            rows.append(_row(t, domain, "step %d" % i, verified=2,
                             verifier=rng.choice(VERIFIERS[1:]),
                             outcome="ok", confidence="strong",
                             marker=rng.choice(("OPEN", "DONE"))))
            continue
        controlled |= set(DECORATED)
        row = _row(t, rng.choice(DOMAINS), "step %d" % i,
                   verified=rng.choice((0, 0, 1, 2)),
                   open=rng.choice((0, 1)),
                   marker=rng.choice(MARKERS),
                   confidence=rng.choice(CONFIDENCE),
                   verifier=rng.choice(VERIFIERS),
                   risk=rng.choice(RISK),
                   error=rng.choice(ERRORS),
                   outcome=rng.choice(OUTCOMES),
                   extra_steps=rng.choice((0, 0, 1, 2, 3, 6, 9, 15)))
        if rng.random() < 0.5:
            row["next"] = rng.choice(NEXT_SHAPES).format(
                domain=rng.choice(DOMAINS), i=i)
        rows.append(row)
    return _decorate(rows, rng, controlled)


def corpus(n, seed, extra_files=()):
    rng = random.Random(seed)
    now = int(time.time())
    sessions = []
    for _ in range(n):
        kind = rng.choice(ARCHETYPES)
        rows = session(rng, now, kind)
        sessions.append({"rows": rows, "book": make_book(rng, rows),
                         "kind": kind})
    for path in extra_files:
        try:
            rows = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("skipping %s (%s)" % (path, exc), file=sys.stderr)
            continue
        if isinstance(rows, list) and rows:
            rows = [r for r in rows if isinstance(r, dict)]
            sessions.append({"rows": rows, "book": make_book(rng, rows),
                             "kind": "external"})
    return sessions


# --------------------------------------------------------------------------
# metric discovery and invocation
# --------------------------------------------------------------------------

def make_book(rng, rows):
    """A ledger for one session, written the way the controller writes it.

    ``note --open`` appends ``?NN <question> — settled by: <answer>``, so
    that is the shape a metric reading ``book["Open"]`` actually meets in
    production. A corpus that only ever hands over a hand-written
    ``domain: text`` row cannot tell a working metric from one that only
    works on that shape.
    """
    goal = rng.choice(("build", "review", "test", "docs", "deploy",
                       "ship the release", "audit the metric layer"))
    opens = []
    if rng.random() < 0.95:
        opens.append("?%02d %s — settled by: %s"
                     % (rng.randint(1, 9),
                        rng.choice(("which cache policy",
                                    "does the metric move",
                                    "is the retry safe")),
                        rng.choice(("a benchmark", "one command", "a probe"))))
    # Deliberately NOT including the hand-written ``domain: text`` shape:
    # the controller never writes it, so a metric that only works on that
    # shape must show up here as pinned rather than be propped up by it.
    return {"Goal": [goal], "Core": [], "Verified": [], "Open": opens,
            "Next": ["keep going"]}


def discover(module):
    """Public metrics whose first parameter is a history and which need nothing else.

    Returns ``{name: (fn, uses_book)}``.
    """
    found = {}
    for name, obj in sorted(vars(module).items()):
        if name.startswith("_") or not inspect.isfunction(obj):
            continue
        if getattr(obj, "__module__", None) != module.__name__:
            continue
        try:
            params = list(inspect.signature(obj).parameters.values())
        except (TypeError, ValueError):
            continue
        if not params or params[0].name not in ("hist", "history", "rows"):
            continue
        uses_book = False
        usable = True
        for param in params[1:]:
            if param.name == "book":
                uses_book = True
                continue
            if param.default is not inspect.Parameter.empty:
                continue
            usable = False
            break
        if usable:
            found[name] = (obj, uses_book)
    return found


def measure(fn, uses_book, hist, book):
    kwargs = {"book": book} if uses_book else {}
    try:
        return fn(hist, **kwargs), None
    except Exception as exc:                      # noqa: BLE001 - audit tool
        return None, "%s: %s" % (type(exc).__name__, exc)


def declared_range(doc):
    if not doc:
        return None
    if "0-100" in doc:
        return (0, 100)
    if "0-1" in doc or "0.0-1.0" in doc:
        return (0, 1)
    return None


# --------------------------------------------------------------------------
# analyses
# --------------------------------------------------------------------------

def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def analyse(module, sessions, corr_cut):
    metrics = discover(module)
    names = list(metrics)
    crashes = {}
    non_numeric = {}

    per_session = []
    for sess in sessions:
        hist = sess["rows"]
        book = sess["book"]
        values = {}
        for name, (fn, uses_book) in metrics.items():
            value, error = measure(fn, uses_book, [dict(r) for r in hist], book)
            if error:
                crashes.setdefault(name, error)
                values[name] = None
            elif numeric(value):
                values[name] = float(value)
            else:
                non_numeric.setdefault(name, repr(value))
                values[name] = None
        per_session.append((sess["kind"], values))

    vectors = {name: [vals[name] for _, vals in per_session] for name in names}

    stats = {}
    for name in names:
        values = [v for v in vectors[name] if v is not None]
        entry = {"samples": len(values), "crashed": name in crashes,
                 "categorical": name in non_numeric}
        if values:
            counts = collections.Counter(values)
            modal, modal_n = counts.most_common(1)[0]
            entry.update({
                "min": min(values), "max": max(values),
                "mean": round(statistics.fmean(values), 4),
                "stdev": round(statistics.pstdev(values), 4),
                "distinct": len(set(values)),
                "modal": modal,
                "modal_share": round(modal_n / float(len(values)), 4),
            })
            entry["declared"] = declared_range(
                inspect.getdoc(metrics[name][0]) or "")
        stats[name] = entry

    live = [n for n in names
            if stats[n]["samples"] and stats[n].get("distinct", 0) > 1]
    dead = [n for n in names
            if stats[n]["samples"] and stats[n].get("distinct", 0) <= 1]
    # Alive but effectively pinned: one value covers almost every session,
    # so the metric is a near-constant with a rare exception. This is the
    # shape a detector takes when it can only fire on input its own writer
    # never produces — it looks live in a unit test and never moves in use.
    # The cut is a triage threshold, not a verdict: read the source of
    # anything listed here before acting on it.
    skewed = sorted(
        ({"metric": n, "modal": stats[n]["modal"],
          "share": stats[n]["modal_share"]} for n in live
         if stats[n].get("modal_share", 0) >= 0.9),
        key=lambda e: -e["share"])
    out_of_range = []
    for name in names:
        declared = stats[name].get("declared")
        if not declared or not stats[name]["samples"]:
            continue
        low, high = declared
        if stats[name]["min"] < low or stats[name]["max"] > high:
            out_of_range.append({"metric": name, "declared": [low, high],
                                 "observed": [stats[name]["min"],
                                              stats[name]["max"]]})

    # pairwise correlation over the live metrics
    pairs = []
    for i, a in enumerate(live):
        va = vectors[a]
        for b in live[i + 1:]:
            vb = vectors[b]
            paired = [(x, y) for x, y in zip(va, vb)
                      if x is not None and y is not None]
            if len(paired) < 8:
                continue
            xs = [p[0] for p in paired]
            ys = [p[1] for p in paired]
            r = pearson(xs, ys)
            if r is not None and abs(r) >= corr_cut:
                pairs.append({"a": a, "b": b, "r": round(r, 4),
                              "relation": classify(paired)})
    pairs.sort(key=lambda p: -abs(p["r"]))

    # field sensitivity: flip one field to an extreme and see what moves
    sensitivity = {}
    baseline_hist = [_row(1757000000 + i * 60, "build", "step %d" % i,
                          verified=1, verifier="pytest", outcome="ok",
                          confidence="strong", marker="DONE", risk="low")
                     for i in range(8)]
    base_book = make_book(random.Random(0), baseline_hist)
    base_values = {}
    for name, (fn, uses_book) in metrics.items():
        value, error = measure(fn, uses_book,
                               [dict(r) for r in baseline_hist], base_book)
        base_values[name] = value if not error else None
    # Two mutations per field: push it to an extreme, and remove it. A
    # metric counts as responsive if either moves it, so "only matters
    # when present" and "only matters when extreme" are both caught.
    perturbations = {
        "verified": 0, "open": 5, "extra_steps": 9, "risk": "high",
        "confidence": "shaky", "marker": "GRRR", "verifier": "pytest",
        "error": "boom", "outcome": "error", "next": "zzz: other", "t": 0,
    }
    for field, extreme in perturbations.items():
        moved_by = {}
        for direction in ("set", "drop"):
            hist = [dict(r) for r in baseline_hist]
            for row in hist:
                if direction == "set":
                    row[field] = extreme
                else:
                    row.pop(field, None)
            for name, (fn, uses_book) in metrics.items():
                value, error = measure(fn, uses_book,
                                       [dict(r) for r in hist], base_book)
                base = base_values[name]
                if error or value is None or base is None or not numeric(value):
                    continue
                if abs(float(value) - float(base)) > 1e-9:
                    moved_by.setdefault(name, []).append(direction)
        sensitivity[field] = moved_by

    # Alive but attributable to no single field: it varies across the
    # corpus, so something moves it — just not one field alone.
    attributable = set()
    for moved in sensitivity.values():
        attributable |= set(moved)
    unattributed = sorted(n for n in live if n not in attributable)

    # Discriminative power: does the metric separate planted-healthy from
    # planted-degraded sessions? The labels come from how each session was
    # built, so no external ground truth is needed. Note the limit: this
    # can show that a metric fails to separate groups it should, not that
    # it measures the right thing. Effect size is the difference in means
    # over the pooled standard deviation.
    separation = []
    for name in live:
        good, bad = [], []
        for kind, vals in per_session:
            value = vals[name]
            if value is None:
                continue
            if kind in GOOD_ARCHETYPES:
                good.append(value)
            elif kind in BAD_ARCHETYPES:
                bad.append(value)
        if len(good) < 5 or len(bad) < 5:
            continue
        diff = statistics.fmean(good) - statistics.fmean(bad)
        pooled = math.sqrt((statistics.pvariance(good)
                            + statistics.pvariance(bad)) / 2.0)
        separation.append({
            "metric": name,
            "good": round(statistics.fmean(good), 3),
            "bad": round(statistics.fmean(bad), 3),
            "diff": round(diff, 3),
            "effect": round(diff / pooled, 3) if pooled > 0 else 0.0,
        })
    separation.sort(key=lambda e: abs(e["effect"]))
    uninformative = [e for e in separation if abs(e["effect"]) < 0.2]

    return {"metrics": stats, "crashes": crashes, "categorical": non_numeric,
            "dead": dead, "live_count": len(live), "out_of_range": out_of_range,
            "correlated": pairs, "sensitivity": sensitivity, "skewed": skewed,
            "separation": separation, "uninformative": uninformative,
            "unattributed": unattributed, "total": len(names)}


def classify(paired):
    """Say whether a correlation is a relationship or a coincidence.

    A perfect coefficient on a corpus is not evidence of redundancy: two
    metrics sharing an "unmeasurable" guard correlate at 1.0 while
    measuring different things. Only an exact identity, or an exact affine
    map, means one carries no information the other does not.
    """
    if all(x == y for x, y in paired):
        return "identical"
    xs = [p[0] for p in paired]
    if len(set(xs)) > 1:
        other = next(j for j in range(1, len(xs)) if xs[j] != xs[0])
        a = (paired[other][1] - paired[0][1]) / (xs[other] - xs[0])
        b = paired[0][1] - a * xs[0]
        if all(abs(y - (a * x + b)) <= 1e-9 for x, y in paired):
            return "affine"
    return "coincidental"


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    sxx = sum(d * d for d in dx)
    syy = sum(d * d for d in dy)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum(a * b for a, b in zip(dx, dy))
    return sxy / math.sqrt(sxx * syy)


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def render(report, top):
    out = []
    add = out.append
    add("Mindseam metric audit")
    add("=" * 68)
    add("metrics discovered      : %d" % report["total"])
    add("alive (value varies)    : %d" % report["live_count"])
    add("dead (never varies)     : %d" % len(report["dead"]))
    add("crash on a legal row    : %d" % len(report["crashes"]))
    add("non-numeric return      : %d" % len(report["categorical"]))
    add("out of declared range   : %d" % len(report["out_of_range"]))
    add("effectively pinned (>=90%%): %d" % len(report["skewed"]))
    add("correlated pairs (>=cut): %d" % len(report["correlated"]))

    if report["crashes"]:
        add("")
        add("-- crashes " + "-" * 56)
        for name, error in sorted(report["crashes"].items()):
            add("  %-38s %s" % (name, error[:80]))

    if report["dead"]:
        add("")
        add("-- dead: the value never changed across the corpus " + "-" * 14)
        for name in sorted(report["dead"]):
            entry = report["metrics"][name]
            add("  %-38s constant at %s" % (name, entry.get("min")))

    if report["skewed"]:
        add("")
        add("-- effectively pinned: one value covers >=90% of sessions " + "-" * 7)
        add("   (a metric that can only fire on input its own writer never")
        add("    produces looks live in a unit test and never moves in use)")
        for item in report["skewed"]:
            add("  %-38s %s in %4.1f%% of sessions"
                % (item["metric"], item["modal"], item["share"] * 100))

    if report["out_of_range"]:
        add("")
        add("-- out of declared range " + "-" * 43)
        for item in report["out_of_range"]:
            add("  %-38s declared %s, saw %s"
                % (item["metric"], item["declared"], item["observed"]))

    if report["correlated"]:
        add("")
        add("-- correlated pairs (>=cut) " + "-" * 40)
        add("   identical/affine = one carries nothing the other does not;")
        add("   coincidental = they only move together on this corpus")
        for pair in report["correlated"][:top]:
            add("  r=%+.3f  %-12s %s  <->  %s"
                % (pair["r"], pair.get("relation", "?"), pair["a"], pair["b"]))
        if len(report["correlated"]) > top:
            add("  ... %d more" % (len(report["correlated"]) - top))

    if report["separation"]:
        add("")
        add("-- discriminative power: planted-healthy vs planted-degraded " + "-")
        add("   effect = (mean_good - mean_bad) / pooled sd. Near zero means")
        add("   the metric does not separate sessions it should separate.")
        add("   Sign shows direction only; polarity is the docstring's job.")
        for item in report["separation"][:top]:
            add("  %+7.2f  %-38s good %7.1f   bad %7.1f"
                % (item["effect"], item["metric"], item["good"], item["bad"]))
        if len(report["separation"]) > top:
            add("  ... %d more" % (len(report["separation"]) - top))
        if report["uninformative"]:
            add("  uninformative (|effect| < 0.2): %d of %d"
                % (len(report["uninformative"]), len(report["separation"])))

    add("")
    add("-- field sensitivity (metrics moved by flipping one field) " + "-" * 8)
    for field, moved in report["sensitivity"].items():
        add("  %-14s %3d metrics respond" % (field, len(moved)))

    if report["unattributed"]:
        add("")
        add("-- alive but not attributable to any single field " + "-" * 17)
        add("   (they move with a combination, or with session length)")
        for name in report["unattributed"]:
            add("  " + name)
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Audit the cognitive metric layer for liveness, range, "
                    "redundancy and field sensitivity.")
    parser.add_argument("--samples", type=int, default=600,
                        help="synthetic sessions to build (default 600)")
    parser.add_argument("--seed", type=int, default=20260911)
    parser.add_argument("--corr", type=float, default=0.95,
                        help="absolute Pearson cut for a redundant pair")
    parser.add_argument("--history", action="append", default=[],
                        help="extra history.json to fold into the corpus "
                             "(repeatable)")
    parser.add_argument("--top", type=int, default=25,
                        help="correlated pairs to print")
    parser.add_argument("--json", action="store_true",
                        help="emit the report as machine-readable JSON")
    parser.add_argument("--check", action="store_true",
                        help="CI gate: exit non-zero if any metric crashes on a "
                             "legal row or leaves its declared range")
    args = parser.parse_args(argv)

    module = load_controller()
    sessions = corpus(args.samples, args.seed, args.history)
    report = analyse(module, sessions, args.corr)
    report["corpus"] = {"sessions": len(sessions),
                        "rows": sum(len(s["rows"]) for s in sessions),
                        "seed": args.seed}

    if args.check:
        # Only the invariants that hold for every legal input: a metric
        # must not raise, and a metric that documents a scale must stay on
        # it. Liveness and redundancy are reported but not gated — they
        # depend on how well the corpus happens to exercise a detector,
        # and a gate that can flake is worse than no gate.
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False,
                             sort_keys=True))
        problems = []
        if report["crashes"]:
            problems.append("%d metric(s) crash on a legal row"
                            % len(report["crashes"]))
        if report["out_of_range"]:
            problems.append("%d metric(s) leave their declared range"
                            % len(report["out_of_range"]))
        if problems:
            for line in problems:
                print("FAIL " + line, file=sys.stderr)
            for name, error in sorted(report["crashes"].items()):
                print("  %s: %s" % (name, error), file=sys.stderr)
            for item in report["out_of_range"]:
                print("  %s: declared %s, saw %s"
                      % (item["metric"], item["declared"], item["observed"]),
                      file=sys.stderr)
            return 1
        print("PASS metric layer: %d metrics, none crash, none out of range"
              % report["total"])
        return 0

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(render(report, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
