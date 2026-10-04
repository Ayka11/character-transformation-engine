"""Human-readable HTML renderer for Science Lab report bundles."""

from __future__ import annotations

import json
from html import escape


def render_report(bundle: dict) -> str:
    matrix=bundle["matrix"]
    stats=bundle["descriptive_statistics"]
    defs={x["scenario_id"]:x for x in bundle["scenarios"]}
    rows=[]
    for run in bundle["scenario_runs"]:
        definition=defs.get(run["scenario_id"],{})
        conditions=escape(json.dumps(definition.get("conditions",{}),sort_keys=True))
        estimate=escape(str(run["estimate_by_outcome"].get(matrix["primary_outcome"],"—")))
        rows.append(
            "<tr><td>{}</td><td><code>{}</code></td><td>{}</td><td>{}</td></tr>".format(
                escape(str(run["scenario_id"])),conditions,escape(str(run["status"])),estimate
            )
        )
    table="".join(rows) or "<tr><td colspan='4'>No scenario runs.</td></tr>"
    return """<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{title} — Science Lab Report</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;margin:40px;max-width:1100px;color:#17202c}}
table{{width:100%;border-collapse:collapse;margin:18px 0}}
th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}
code,pre{{background:#f5f7fa;padding:3px 6px;border-radius:5px}}
pre{{padding:14px;overflow:auto}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.box{{border:1px solid #ddd;border-radius:10px;padding:12px}}
.muted{{color:#657185}}
@media(max-width:800px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head>
<body>
<p class='muted'>CHARACTER TRANSFORMATION ENGINE / SCIENCE LAB V2.6</p>
<h1>{title}</h1>
<p>Primary outcome: <b>{outcome}</b></p>
<div class='grid'>
<div class='box'><b>Scenarios</b><br>{scenarios}</div>
<div class='box'><b>Runs</b><br>{runs}</div>
<div class='box'><b>Completed</b><br>{completed}</div>
<div class='box'><b>Primary estimate</b><br>{estimate}</div>
</div>
<h2>Scenario runs</h2>
<table><thead><tr><th>Scenario</th><th>Conditions</th><th>Status</th><th>Estimate</th></tr></thead><tbody>{table}</tbody></table>
<h2>Replication / Generalization</h2><pre>{rg}</pre>
<h2>Claim validation</h2><pre>{claims}</pre>
<h2>Transformation provenance</h2><pre>{transformation_provenance}</pre>
<h2>Provenance</h2><pre>{provenance}</pre>
</body></html>""".format(
        title=escape(str(matrix["name"])),
        outcome=escape(str(matrix["primary_outcome"])),
        scenarios=stats["scenario_count"],runs=stats["run_count"],completed=stats["completed_runs"],
        estimate=escape(str(stats["descriptive_estimate_mean"])),
        table=table,
        rg=escape(json.dumps({"replication":bundle["replication_assessments"],"generalization":bundle["generalization_assessments"]},indent=2,sort_keys=True)),
        claims=escape(json.dumps(bundle["claim_validation"],indent=2,sort_keys=True)),
        transformation_provenance=escape(json.dumps(bundle.get("transformation_provenance", {}),indent=2,sort_keys=True)),
        provenance=escape(json.dumps(bundle["provenance"],indent=2,sort_keys=True)),
    )