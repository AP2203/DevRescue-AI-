"""Backward-compatible import path for the mesh repair service."""

from app.ai.postprocessing.repair import MeshDiagnosticReport, MeshValidator, repair_mesh

__all__ = ["MeshDiagnosticReport", "MeshValidator", "repair_mesh"]
