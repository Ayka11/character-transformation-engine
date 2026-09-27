"""API surface for transformation lineage, recovery and integrity inspection."""
from __future__ import annotations
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from .state_snapshot_store import StateSnapshotStore
from .transformation_ledger import TransformationLedger
from .transformation_recovery import TransformationRecoveryService
from .transformation_integrity import TransformationIntegrityVerifier
from .transformation_provenance import TransformationProvenanceBinder

def install_transformation_api(app, runtime_store):
    snapshots=StateSnapshotStore(runtime_store)
    ledger=TransformationLedger(runtime_store)
    recovery=TransformationRecoveryService(snapshots,ledger)
    integrity=TransformationIntegrityVerifier(snapshots,ledger)
    provenance=TransformationProvenanceBinder(runtime_store)
    router=APIRouter(prefix="/transformation",tags=["transformation"])

    @router.get("/lineage/{character_id}")
    def lineage(character_id: str):
        items=snapshots.get_lineage(character_id)
        return {"character_id":character_id,"count":len(items),
                "snapshots":[asdict(item) for item in items],
                "integrity":[{"snapshot_id":item.snapshot_id,"verified":snapshots.verify(item.snapshot_id)} for item in items]}

    @router.get("/snapshots/{snapshot_id}")
    def snapshot(snapshot_id: str):
        item=snapshots.get(snapshot_id)
        if item is None:
            raise HTTPException(status_code=404, detail="snapshot not found")
        return {"snapshot":asdict(item),"verified":snapshots.verify(snapshot_id)}

    @router.get("/ledger")
    def ledger_list():
        return {"entries":[asdict(item) for item in ledger.list()]}

    @router.get("/ledger/{ledger_id}")
    def ledger_get(ledger_id: str):
        item=ledger.get(ledger_id)
        if item is None:
            raise HTTPException(status_code=404, detail="ledger entry not found")
        return {"entry":asdict(item),"integrity":asdict(integrity.verify(ledger_id))}

    @router.get("/integrity")
    def integrity_all():
        findings=integrity.verify_all()
        return {"count":len(findings),"findings":[asdict(item) for item in findings]}

    @router.get("/provenance/{execution_id}")
    def provenance_endpoint(execution_id: str):
        return provenance.bind_execution(execution_id)

    @router.get("/recovery/scan")
    def recovery_scan():
        attempts=recovery.scan()
        return {"count":len(attempts),"attempts":[asdict(item) for item in attempts]}

    @router.get("/journal/{attempt_id}")
    def journal_attempt(attempt_id: str):
        attempts=[item for item in recovery.journal.attempts() if item.attempt_id==attempt_id]
        if not attempts:
            raise HTTPException(status_code=404, detail="journal attempt not found")
        return {"attempt":asdict(attempts[0]),"events":recovery.journal.events(attempt_id)}

    app.include_router(router)
    return recovery
