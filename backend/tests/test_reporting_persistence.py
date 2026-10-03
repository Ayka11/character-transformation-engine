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

        from cte.evidence_graph import register_node
        graph.nodes["c"] = register_node(
            "c", "CLAIM", "c", "DRV", "1",
            {"current_state": "REGISTERED", "state": "CONTRADICTED", "result_id": "r"},
        )
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


def test_publish_rolls_back_in_memory_state_when_persistence_fails():
    import pytest

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Persistence failure"))
        service.create("rr-publish-fail", "rs", "study", ["r"])
        for ordinal, code in enumerate(SECTION_CODES):
            service.add_section("rr-publish-fail", code, {"section": code}, ["r"], ordinal)
        service.bind_claim("rr-publish-fail", "c")
        assert service.qc_run("rr-publish-fail")["status"] == "QC_PASSED"
        original = store.put_snapshot_if_hash
        def fail_report_run(namespace, key, payload, version, *, expected_hash):
            if namespace == "report.run" and key == "rr-publish-fail":
                raise OSError("simulated storage failure")
            return original(namespace, key, payload, version, expected_hash=expected_hash)
        store.put_snapshot_if_hash = fail_report_run
        with pytest.raises(OSError, match="simulated storage failure"):
            service.publish("rr-publish-fail")
        run = service.runs["rr-publish-fail"]
        assert run.status == "QC_PASSED"
        assert run.report_output_hash is None
        assert run.report_output_hash_version == 1


def test_supersede_rolls_back_in_memory_state_when_persistence_fails():
    import pytest

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Supersede failure"))
        for run_id in ("rr-old-fail", "rr-new-fail"):
            service.create(run_id, "rs", "study", ["r"])
            for ordinal, code in enumerate(SECTION_CODES):
                service.add_section(run_id, code, {"section": code}, ["r"], ordinal)
            service.bind_claim(run_id, "c")
            assert service.qc_run(run_id)["status"] == "QC_PASSED"
            service.publish(run_id)
        original = store.put_snapshot_if_hash
        def fail_old(namespace, key, payload, version, *, expected_hash):
            if namespace == "report.run" and key == "rr-old-fail":
                raise OSError("simulated storage failure")
            return original(namespace, key, payload, version, expected_hash=expected_hash)
        store.put_snapshot_if_hash = fail_old
        with pytest.raises(OSError, match="simulated storage failure"):
            service.supersede("rr-old-fail", "rr-new-fail")
        old = service.runs["rr-old-fail"]
        assert old.status == "PUBLISHED"
        assert old.superseded_by is None


def test_recovery_rejects_missing_supersession_successor():
    import json
    import sqlite3
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Supersession integrity"))
        for run_id in ("rr-lineage-old", "rr-lineage-new"):
            service.create(run_id, "rs", "study", ["r"])
            for ordinal, code in enumerate(SECTION_CODES):
                service.add_section(run_id, code, {"section": code}, ["r"], ordinal)
            service.bind_claim(run_id, "c")
            assert service.qc_run(run_id)["status"] == "QC_PASSED"
            service.publish(run_id)
        service.supersede("rr-lineage-old", "rr-lineage-new")

        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("report.run", "rr-lineage-old"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["superseded_by"] = "rr-does-not-exist"
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), content_hash(payload),
                 "report.run", "rr-lineage-old"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="references missing successor rr-does-not-exist"):
            ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))


def test_recovery_rejects_supersession_cycle():
    import json
    import sqlite3
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs", "Supersession cycle"))
        for run_id in ("rr-cycle-a", "rr-cycle-b"):
            service.create(run_id, "rs", "study", ["r"])
            for ordinal, code in enumerate(SECTION_CODES):
                service.add_section(run_id, code, {"section": code}, ["r"], ordinal)
            service.bind_claim(run_id, "c")
            assert service.qc_run(run_id)["status"] == "QC_PASSED"
            service.publish(run_id)
        service.supersede("rr-cycle-a", "rr-cycle-b")

        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("report.run", "rr-cycle-b"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["status"] = "SUPERSEDED"
            payload["superseded_by"] = "rr-cycle-a"
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), content_hash(payload),
                 "report.run", "rr-cycle-b"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="supersession cycle"):
            ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))



def test_report_run_compare_and_swap_rejects_stale_service_writer():
    import pytest

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store_a = SQLiteRuntimeStore(path)
        graph = _graph(store_a)
        service_a = ReportService(graph, store_a)
        service_a.register_spec(register_spec("rs", "Concurrent writer"))
        service_a.create("rr-cas", "rs", "study", ["r"])

        # A second service hydrates the same version before the first writer updates it.
        store_b = SQLiteRuntimeStore(path)
        service_b = ReportService(build_registry(store_b), store_b)
        service_a.add_decision("rr-cas", "decision-a", "QC", "allow", "rule", {}, "first writer")

        with pytest.raises(ValueError, match="snapshot concurrent update conflict"):
            service_b.add_decision("rr-cas", "decision-b", "QC", "deny", "rule", {}, "stale writer")

        # A failed persistence operation must roll back the stale service's in-memory mutation too.
        assert "decision-b" not in service_b.runs["rr-cas"].decisions
        assert "decision-a" not in service_b.runs["rr-cas"].decisions

        recovered = ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))
        assert "decision-a" in recovered.runs["rr-cas"].decisions
        assert "decision-b" not in recovered.runs["rr-cas"].decisions

def test_report_spec_registration_rolls_back_memory_on_persistence_failure():
    import pytest

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        service = ReportService(_graph(store), store)
        spec = register_spec("rs-fail", "Spec persistence failure")
        original = store.put_snapshot

        def fail_spec(namespace, key, payload, version):
            if namespace == "report.spec" and key == "rs-fail":
                raise OSError("simulated spec storage failure")
            return original(namespace, key, payload, version)

        store.put_snapshot = fail_spec
        with pytest.raises(OSError, match="simulated spec storage failure"):
            service.register_spec(spec)
        assert "rs-fail" not in service.specs

        store.put_snapshot = original
        service.register_spec(spec)
        assert "rs-fail" in service.specs


def test_report_service_serializes_concurrent_run_mutations():
    import threading
    from threading import Event, Lock

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        service = ReportService(_graph(store), store)
        service.register_spec(register_spec("rs-concurrent", "Concurrent"))
        service.create("rr-concurrent", "rs-concurrent", "study", ["r"])
        original = store.put_snapshot_if_hash
        first_entered = Event()
        second_started = Event()
        second_entered_persistence = Event()
        release_first = Event()
        calls_lock = Lock()
        calls = 0

        def pause_first_write(namespace, key, payload, version, *, expected_hash):
            nonlocal calls
            if namespace == "report.run" and key == "rr-concurrent":
                with calls_lock:
                    calls += 1
                    call_number = calls
                if call_number == 1:
                    first_entered.set()
                    if not release_first.wait(timeout=5):
                        raise TimeoutError("test did not release first report write")
                elif call_number == 2:
                    second_entered_persistence.set()
            return original(namespace, key, payload, version, expected_hash=expected_hash)

        store.put_snapshot_if_hash = pause_first_write
        errors = []

        def add_decision(decision_id, started=None):
            if started is not None:
                started.set()
            try:
                service.add_decision("rr-concurrent", decision_id, "REVIEW", decision_id, "RULE", {}, decision_id)
            except Exception as exc:
                errors.append(exc)

        first = threading.Thread(target=add_decision, args=("decision-z",))
        second = threading.Thread(target=add_decision, args=("decision-a", second_started))
        first.start()
        assert first_entered.wait(timeout=5)
        second.start()
        assert second_started.wait(timeout=5)
        try:
            # With the service lock, the second mutation cannot reach persistence
            # while the first operation is paused inside its durable write.
            assert not second_entered_persistence.wait(timeout=0.1)
        finally:
            release_first.set()
        first.join(timeout=5)
        second.join(timeout=5)
        assert not first.is_alive() and not second.is_alive()
        assert errors == []
        assert set(service.runs["rr-concurrent"].decisions) == {"decision-z", "decision-a"}
        persisted = store.get_snapshot("report.run", "rr-concurrent").payload
        assert set(persisted["decisions"]) == {"decision-z", "decision-a"}

def test_report_spec_section_and_decision_payloads_are_immutable():
    import pytest

    graph = _graph(None)
    service = ReportService(graph)
    rendering_rules = {"nested": {"items": [1]}}
    spec = register_spec("rs-frozen", "Frozen", rendering_rules=rendering_rules)
    registered = service.register_spec(spec)
    rendering_rules["nested"]["items"].append(2)
    assert list(registered.rendering_rules["nested"]["items"]) == [1]
    with pytest.raises(TypeError, match="immutable"):
        registered.rendering_rules["nested"]["items"].append(3)
    service.create("rr-frozen", "rs-frozen", "study", ["r"])
    section_content = {"nested": {"items": [1]}}
    section = service.add_section("rr-frozen", "EXECUTIVE_SUMMARY", section_content, ["r"], 0)
    section_content["nested"]["items"].append(2)
    assert list(section.content["nested"]["items"]) == [1]
    with pytest.raises(TypeError, match="immutable"):
        section.content["nested"]["items"].append(3)
    decision_inputs = {"nested": {"items": [1]}}
    decision = service.add_decision("rr-frozen", "decision-frozen", "REVIEW", "keep", "RULE", decision_inputs, "test")
    decision_inputs["nested"]["items"].append(2)
    assert list(decision["inputs"]["nested"]["items"]) == [1]
    with pytest.raises(TypeError, match="immutable"):
        decision["inputs"]["nested"]["items"].append(3)
    with pytest.raises(TypeError, match="immutable"):
        decision["decision"] = "mutated"


def test_recovery_validates_report_spec_hash_even_without_report_runs():
    import json
    import sqlite3
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        service = ReportService(_graph(store), store)
        service.register_spec(register_spec("rs-unreferenced", "Unreferenced"))
        with sqlite3.connect(path) as conn:
            row = conn.execute("SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("report.spec", "rs-unreferenced")).fetchone()
            payload = json.loads(row[0])
            payload["rendering_rules"] = {"tampered": True}
            conn.execute("UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), content_hash(payload),
                 "report.spec", "rs-unreferenced"))
            conn.commit()
        with pytest.raises(ValueError, match="report.spec/rs-unreferenced immutable hash"):
            ReportService(_graph(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))


def test_recovery_rejects_report_snapshot_key_or_version_envelope_mismatch():
    import sqlite3
    import pytest

    cases = [
        ("report.spec", "key", "wrong-report-spec", "report.spec/wrong-report-spec envelope mismatch"),
        ("report.spec", "version", "2.0", "report.spec/rs-envelope envelope mismatch"),
        ("report.run", "key", "wrong-report-run", "report.run/wrong-report-run envelope mismatch"),
        ("report.run", "version", "2.0", "report.run/rr-envelope envelope mismatch"),
    ]
    for namespace, field, replacement, message in cases:
        with TemporaryDirectory() as d:
            path = str(Path(d) / "runtime.sqlite3")
            store = SQLiteRuntimeStore(path)
            graph = _graph(store)
            service = ReportService(graph, store)
            service.register_spec(register_spec("rs-envelope", "Envelope integrity"))
            if namespace == "report.run":
                service.create("rr-envelope", "rs-envelope", "study", ["r"])

            original_key = "rs-envelope" if namespace == "report.spec" else "rr-envelope"
            with sqlite3.connect(path) as conn:
                if field == "key":
                    conn.execute(
                        "UPDATE runtime_snapshots SET key=? WHERE namespace=? AND key=?",
                        (replacement, namespace, original_key),
                    )
                else:
                    conn.execute(
                        "UPDATE runtime_snapshots SET version=? WHERE namespace=? AND key=?",
                        (replacement, namespace, original_key),
                    )
                conn.commit()

            with pytest.raises(ValueError, match=message):
                ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))


def test_report_spec_rejects_duplicate_section_codes_even_when_all_codes_are_present():
    import pytest

    duplicated_order = [*SECTION_CODES, SECTION_CODES[0]]
    with pytest.raises(ValueError, match="report specification must contain the V1.6 section set"):
        register_spec(
            "rs-duplicate-sections",
            "Duplicate section order",
            section_order=duplicated_order,
        )


def test_report_sections_require_unique_non_negative_integer_ordinals():
    import pytest

    with TemporaryDirectory() as d:
        store = SQLiteRuntimeStore(str(Path(d) / "runtime.sqlite3"))
        graph = _graph(store)
        service = ReportService(graph, store)
        service.register_spec(register_spec("rs-ordinals", "Ordinal validation"))
        service.create("rr-ordinals", "rs-ordinals", "study", ["r"])
        service.add_section("rr-ordinals", SECTION_CODES[0], {"section": SECTION_CODES[0]}, ["r"], 0)

        with pytest.raises(ValueError, match="report section ordinal already registered"):
            service.add_section("rr-ordinals", SECTION_CODES[1], {"section": SECTION_CODES[1]}, ["r"], 0)

        for invalid_ordinal in (-1, 1.5, True):
            with pytest.raises(ValueError, match="report section ordinal must be a non-negative integer"):
                service.add_section(
                    "rr-ordinals", SECTION_CODES[1], {"section": SECTION_CODES[1]},
                    ["r"], invalid_ordinal,
                )


def test_recovery_rejects_report_children_owned_by_another_run():
    import json
    import sqlite3
    import pytest
    from cte.provenance import content_hash

    cases = [
        ("sections", "EXECUTIVE_SUMMARY", "section/EXECUTIVE_SUMMARY"),
        ("bindings", "c", "binding/c"),
        ("decisions", "decision-ownership", "decision/decision-ownership"),
        ("qc", "REQUIRED_SECTIONS", "qc/REQUIRED_SECTIONS"),
    ]
    for collection, child_key, error_fragment in cases:
        with TemporaryDirectory() as d:
            path = str(Path(d) / "runtime.sqlite3")
            store = SQLiteRuntimeStore(path)
            graph = _graph(store)
            service = ReportService(graph, store)
            service.register_spec(register_spec("rs-child-owner", "Child ownership"))
            service.create("rr-child-owner", "rs-child-owner", "study", ["r"])
            for ordinal, code in enumerate(SECTION_CODES):
                service.add_section("rr-child-owner", code, {"section": code}, ["r"], ordinal)
            service.bind_claim("rr-child-owner", "c")
            service.add_decision(
                "rr-child-owner", "decision-ownership", "REPORT_SCOPE",
                "Use registered source set", "RULE-1", {"source": "r"}, "Bounded to registered evidence",
            )
            service.qc_run("rr-child-owner")

            with sqlite3.connect(path) as conn:
                row = conn.execute(
                    "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                    ("report.run", "rr-child-owner"),
                ).fetchone()
                payload = json.loads(row[0])
                child = payload[collection][child_key]
                child["report_run_id"] = "different-run"
                if collection in {"sections", "bindings", "decisions"}:
                    child_payload = {key: value for key, value in child.items() if key != "immutable_hash"}
                    child["immutable_hash"] = content_hash(child_payload)
                serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                conn.execute(
                    "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                    (serialized, content_hash(payload), "report.run", "rr-child-owner"),
                )
                conn.commit()

            with pytest.raises(ValueError, match=error_fragment):
                ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))


def test_recovery_rejects_duplicate_sections_in_report_spec_even_with_recomputed_hashes():
    import json
    import sqlite3
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        service = ReportService(_graph(store), store)
        service.register_spec(register_spec("rs-duplicate-recovery", "Duplicate recovery"))
        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("report.spec", "rs-duplicate-recovery"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["section_order"].append(SECTION_CODES[0])
            immutable_payload = {
                "report_spec_id": payload["report_spec_id"],
                "name": payload["name"],
                "version": payload["version"],
                "section_order": tuple(payload["section_order"]),
                "rendering_rules": payload["rendering_rules"],
                "claim_language_rules": payload["claim_language_rules"],
            }
            payload["immutable_hash"] = content_hash(immutable_payload)
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), content_hash(payload),
                 "report.spec", "rs-duplicate-recovery"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="report.spec/rs-duplicate-recovery section order invalid"):
            ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))


def test_recovery_rejects_duplicate_report_section_ordinals_even_with_recomputed_hashes():
    import json
    import sqlite3
    import pytest
    from cte.provenance import content_hash

    with TemporaryDirectory() as d:
        path = str(Path(d) / "runtime.sqlite3")
        store = SQLiteRuntimeStore(path)
        service = ReportService(_graph(store), store)
        service.register_spec(register_spec("rs-ordinal-recovery", "Ordinal recovery"))
        service.create("rr-ordinal-recovery", "rs-ordinal-recovery", "study", ["r"])
        for ordinal, code in enumerate(SECTION_CODES):
            service.add_section("rr-ordinal-recovery", code, {"section": code}, ["r"], ordinal)

        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM runtime_snapshots WHERE namespace=? AND key=?",
                ("report.run", "rr-ordinal-recovery"),
            ).fetchone()
            payload = json.loads(row[0])
            payload["sections"][SECTION_CODES[1]]["ordinal"] = payload["sections"][SECTION_CODES[0]]["ordinal"]
            section = payload["sections"][SECTION_CODES[1]]
            section["immutable_hash"] = content_hash({
                key: value for key, value in section.items() if key != "immutable_hash"
            })
            conn.execute(
                "UPDATE runtime_snapshots SET payload_json=?, payload_hash=? WHERE namespace=? AND key=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), content_hash(payload),
                 "report.run", "rr-ordinal-recovery"),
            )
            conn.commit()

        with pytest.raises(ValueError, match="section ordinals invalid"):
            ReportService(build_registry(SQLiteRuntimeStore(path)), SQLiteRuntimeStore(path))
