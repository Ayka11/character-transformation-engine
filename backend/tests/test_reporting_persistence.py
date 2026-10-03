from pathlib import Path
from tempfile import TemporaryDirectory
from cte.evidence_graph import register_node, register_edge
from cte.graph_registry import build_registry
from cte.persistence import SQLiteRuntimeStore
from cte.reporting import SECTION_CODES, ReportService, register_spec

def _graph(store):
    g=build_registry(store)
    d=register_node("d","DATASET","d","DRV","1",{})
    a=register_node("a","ANALYSIS","a","DRV","1",{})
    r=register_node("r","RESULT","r","DRV","1",{"qc_status":"PASS","validated_descriptive_result":True})
    for n in (d,a,r): g.add_node(n)
    g.add_edge(register_edge("ed",a,d,"ANALYZED_FROM"))
    g.add_edge(register_edge("er",a,r,"RESULTS_IN"))
    g.register_claim("c","r","REGISTERED","DESCRIPTIVE_RESULT","DRV",{})
    return g

def test_report_spec_and_snapshot_survive_restart():
    with TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        store=SQLiteRuntimeStore(path)
        g=_graph(store)
        first=ReportService(g,store)
        first.register_spec(register_spec("rs","Durable"))
        first.create("rr","rs","study",["r"])
        for i,code in enumerate(SECTION_CODES):
            first.add_section("rr",code,{"section":code},["r"],i)
        first.bind_claim("rr","c")
        first.qc_run("rr")
        first.publish("rr")
        second=ReportService(build_registry(SQLiteRuntimeStore(path)),SQLiteRuntimeStore(path))
        assert "rs" in second.specs
        assert second.runs["rr"].status=="PUBLISHED"
        assert second.runs["rr"].report_output_hash


def test_report_service_rejects_tampered_persisted_run_snapshot():
    import json
    import sqlite3
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Durable"))
        service.create("rr-tampered", "rs", "study", ["r"])

        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("report.run", "rr-tampered"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["status"] = "PUBLISHED"
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=? WHERE namespace=? AND key=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), "report.run", "rr-tampered"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="report snapshot integrity failure: report.run/rr-tampered"):
            ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))


def test_recovery_rejects_section_tampering_even_if_snapshot_hash_is_recomputed():
    import json
    import sqlite3
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Integrity"))
        service.create("rr-section-tampered", "rs", "study", ["r"])
        for ordinal, code in enumerate(SECTION_CODES):
            service.add_section("rr-section-tampered", code, {"section": code}, ["r"], ordinal)
        service.bind_claim("rr-section-tampered", "c")
        assert service.qc_run("rr-section-tampered")["status"] == "QC_PASSED"
        service.publish("rr-section-tampered")

        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("report.run", "rr-section-tampered"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["sections"]["EXECUTIVE_SUMMARY"]["content"]["section"] = "tampered"
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (serialized, content_hash(payload), "report.run", "rr-section-tampered"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="section/EXECUTIVE_SUMMARY"):
            ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))


def test_publish_rechecks_qc_after_claim_graph_changes():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Fresh QC"))
        service.create("rr-stale-qc", "rs", "study", ["r"])
        for ordinal, code in enumerate(SECTION_CODES):
            service.add_section("rr-stale-qc", code, {"section": code}, ["r"], ordinal)
        service.bind_claim("rr-stale-qc", "c")
        assert service.qc_run("rr-stale-qc")["status"] == "QC_PASSED"

        graph.nodes["c"].metadata["state"] = "CONTRADICTED"
        with pytest.raises(ValueError, match="current-state QC failed"):
            service.publish("rr-stale-qc")

        assert service.runs["rr-stale-qc"].status == "QC_FAILED"
        assert "CLAIM_BINDINGS" in service.runs["rr-stale-qc"].qc
        assert service.runs["rr-stale-qc"].report_output_hash is None


def test_supersede_rejects_unpublished_successor():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Supersede"))
        service.create("rr-old", "rs", "study", ["r"])
        for ordinal, code in enumerate(SECTION_CODES):
            service.add_section("rr-old", code, {"section": code}, ["r"], ordinal)
        service.bind_claim("rr-old", "c")
        assert service.qc_run("rr-old")["status"] == "QC_PASSED"
        service.publish("rr-old")

        service.create("rr-new-draft", "rs", "study", ["r"])
        with pytest.raises(ValueError, match="only be superseded by a published report"):
            service.supersede("rr-old", "rr-new-draft")

        assert service.runs["rr-old"].status == "PUBLISHED"
        assert service.runs["rr-old"].superseded_by is None


def test_qc_cannot_mutate_published_report():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Immutable QC"))
        service.create("rr-immutable-qc", "rs", "study", ["r"])
        for ordinal, code in enumerate(SECTION_CODES):
            service.add_section("rr-immutable-qc", code, {"section": code}, ["r"], ordinal)
        service.bind_claim("rr-immutable-qc", "c")
        assert service.qc_run("rr-immutable-qc")["status"] == "QC_PASSED"
        service.publish("rr-immutable-qc")
        before_hash = service.runs["rr-immutable-qc"].report_output_hash
        before_status = service.runs["rr-immutable-qc"].status
        with pytest.raises(ValueError, match="immutable report cannot be rechecked"):
            service.qc_run("rr-immutable-qc")
        assert service.runs["rr-immutable-qc"].report_output_hash == before_hash
        assert service.runs["rr-immutable-qc"].status == before_status
