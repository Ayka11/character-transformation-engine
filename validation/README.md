# Validation & Analytics Engine V1.3

This directory defines statistical validation, longitudinal analytics, sensitivity analysis, replication assessment, and provenance-constrained claim derivation.

Status: **MDL/DRV design specification — not empirically validated.**

## Core rule

A numerical result is a result. It does not automatically become evidence (EVD), and statistical significance does not by itself establish causality, practical importance, replication, or generalization.

## Pipeline

REGISTER_SPEC → LOCK_DATASET_MANIFEST → QC → MISSINGNESS → PRIMARY_ANALYSIS → EFFECT_SIZE → CI → MULTIPLICITY → SENSITIVITY → REPLICATION → CLAIM_DERIVATION → EVIDENCE_GRAPH → REPORT

## Files

- validation-v1.3.sql — database layer
- validation-v1.3-api.json — API contract
- analysis-spec-v1.3.json — statistical and validation rules

## Integration

V1.3 consumes the V1.2 research execution layer and writes provenance-aware results that can feed the claim graph. It does not replace the V1.2 research pipeline.
