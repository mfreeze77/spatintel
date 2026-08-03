from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

from .capture import PolyformImporter
from .errors import AuthorizationError, ValidationError
from .geometry import (
    SimilarityTransform,
    interaction_proxy,
    mesh_to_splats,
    ransac_similarity,
    splats_to_surface,
)
from .models import Classification


@dataclass(frozen=True)
class ProviderExecutionContext:
    tenant_id: str
    project_id: str
    purpose: str
    classification: Classification
    region: str = "local"
    usage_scope: str = "local_internal"


@runtime_checkable
class CaptureImportProvider(Protocol):
    provider_id: str

    def normalize(self, source: Path, destination: Path, *, context: ProviderExecutionContext) -> dict[str, Any]: ...


@runtime_checkable
class RegistrationProvider(Protocol):
    provider_id: str

    def register(
        self,
        source: np.ndarray,
        target: np.ndarray,
        *,
        estimate_scale: bool,
        threshold_m: float,
        seed: int,
        context: ProviderExecutionContext,
    ) -> tuple[SimilarityTransform, np.ndarray]: ...


@runtime_checkable
class RepresentationConversionProvider(Protocol):
    provider_id: str

    def mesh_to_visual(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        samples: int,
        seed: int,
        context: ProviderExecutionContext,
    ) -> dict[str, Any]: ...

    def visual_to_interaction(
        self,
        positions: np.ndarray,
        *,
        context: ProviderExecutionContext,
    ) -> dict[str, Any]: ...

    def mesh_to_interaction(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        target_faces: int,
        context: ProviderExecutionContext,
    ) -> dict[str, Any]: ...


class PolyformFormatAdapter:
    """Independent adapter for documented user-export files; no Polycam runtime dependency."""

    provider_id = "polyform-format-reference"

    def normalize(self, source: Path, destination: Path, *, context: ProviderExecutionContext) -> dict[str, Any]:
        if context.region != "local":
            raise AuthorizationError("POLYFORM_EXTERNAL_DENIED", "raw capture normalization is local-only")
        return PolyformImporter().convert(source, destination)


class DeterministicRegistrationProvider:
    provider_id = "sip-reference-registration"

    def register(
        self,
        source: np.ndarray,
        target: np.ndarray,
        *,
        estimate_scale: bool,
        threshold_m: float,
        seed: int,
        context: ProviderExecutionContext,
    ) -> tuple[SimilarityTransform, np.ndarray]:
        if context.region != "local":
            raise AuthorizationError("REFERENCE_SOLVER_EXTERNAL_DENIED", "reference solver is local-only")
        return ransac_similarity(
            source,
            target,
            estimate_scale=estimate_scale,
            threshold_m=threshold_m,
            iterations=500,
            seed=seed,
        )


class DeterministicRepresentationProvider:
    provider_id = "sip-reference-representation"

    def mesh_to_visual(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        samples: int,
        seed: int,
        context: ProviderExecutionContext,
    ) -> dict[str, Any]:
        result = mesh_to_splats(vertices, faces, samples=samples, seed=seed)
        return {
            **result,
            "authority": "visual_non_metric",
            "lossy": True,
            "provider_id": self.provider_id,
            "prohibited_uses": ["verified_measurement", "survey", "fabrication", "code_compliance"],
        }

    def visual_to_interaction(
        self,
        positions: np.ndarray,
        *,
        context: ProviderExecutionContext,
    ) -> dict[str, Any]:
        result = splats_to_surface(positions)
        return {
            **result,
            "authority": "derived_non_authoritative",
            "lossy": True,
            "provider_id": self.provider_id,
            "prohibited_uses": ["verified_measurement", "survey", "fabrication", "code_compliance"],
        }

    def mesh_to_interaction(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        target_faces: int,
        context: ProviderExecutionContext,
    ) -> dict[str, Any]:
        result = interaction_proxy(vertices, faces, target_faces=target_faces)
        return {**result, "provider_id": self.provider_id, "lossy": True}


class DeniedExternalProvider:
    """Fail-closed boundary used for providers lacking an approved execution manifest."""

    def __init__(self, provider_id: str, reason: str) -> None:
        if not provider_id or not reason:
            raise ValidationError("PROVIDER_DENIAL_INVALID", "denied provider requires an identifier and reason")
        self.provider_id = provider_id
        self.reason = reason

    def execute(self, *_: Any, **__: Any) -> dict[str, Any]:
        raise AuthorizationError(
            "PROVIDER_EXECUTION_DENIED",
            "provider is unavailable until source, license, data handling, and intended-use approval pass",
            {"provider_id": self.provider_id, "reason": self.reason},
        )
