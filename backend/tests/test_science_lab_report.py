from cte.science_lab_report import render_report


def _bundle():
    return {
        "matrix": {"name": "Compatibility <Study>", "primary_outcome": "focus_score"},
        "descriptive_statistics": {
            "scenario_count": 1,
            "run_count": 1,
            "completed_runs": 1,
            "descriptive_estimate_mean": 0.75,
        },
        "scenarios": [
            {"scenario_id": "baseline", "conditions": {"group": "control <safe>"}}
        ],
        "scenario_runs": [
            {
                "scenario_id": "baseline",
                "status": "COMPLETED",
                "estimate_by_outcome": {"focus_score": 0.75},
            }
        ],
        "replication_assessments": [],
        "generalization_assessments": [],
        "claim_validation": {"status": "DESCRIPTIVE_ONLY"},
        "transformation_provenance": {},
        "provenance": {"run_id": "run-001"},
    }


def test_science_lab_report_displays_current_v26_label():
    html = render_report(_bundle())

    assert "CHARACTER TRANSFORMATION ENGINE / SCIENCE LAB V2.6" in html
    assert "SCIENCE LAB V2.5" not in html


def test_science_lab_report_escapes_untrusted_html_values():
    html = render_report(_bundle())

    assert "Compatibility &lt;Study&gt;" in html
    assert "control &lt;safe&gt;" in html
    assert "Compatibility <Study>" not in html
    assert "control <safe>" not in html
