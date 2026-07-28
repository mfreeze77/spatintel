from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, Request

from .errors import AuthenticationError
from .models import Audience, SignedPrincipal


@dataclass(frozen=True)
class RequestIdentity:
    principal: SignedPrincipal
    authentication_method: str


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def authenticate_request(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_sip_tenant: Annotated[str | None, Header()] = None,
    x_sip_subject: Annotated[str | None, Header()] = None,
    x_sip_projects: Annotated[str | None, Header()] = None,
    x_sip_roles: Annotated[str | None, Header()] = None,
    x_sip_purposes: Annotated[str | None, Header()] = None,
    x_sip_audience: Annotated[str | None, Header()] = None,
) -> SignedPrincipal:
    """Authenticate a request.

    Production deployments use a short-lived, signed SIP workload/user token. Development
    headers are intentionally unavailable unless ``allow_development_auth`` is enabled.
    The method is fail-closed: malformed, expired, or missing credentials never become an
    anonymous principal.
    """

    context = request.app.state.platform
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthenticationError("AUTH_SCHEME_INVALID", "expected a Bearer token")
        claims = context.assets.token_codec.decode(token)
        if claims.get("token_type") not in {"principal", "workload"}:
            raise AuthenticationError("AUTH_TOKEN_TYPE_INVALID", "token cannot authenticate an API principal")
        try:
            principal = SignedPrincipal.model_validate(claims["principal"])
            request.state.principal = principal
            return principal
        except Exception as exc:  # pydantic detail must not leak credential material
            raise AuthenticationError("AUTH_CLAIMS_INVALID", "signed principal claims are invalid") from exc

    if not context.settings.allow_development_auth:
        raise AuthenticationError("AUTH_REQUIRED", "authentication is required")
    if not x_sip_tenant or not x_sip_subject:
        raise AuthenticationError("DEV_AUTH_INCOMPLETE", "development authentication requires tenant and subject headers")
    try:
        audience = Audience(x_sip_audience or Audience.PRIVATE.value)
    except ValueError as exc:
        raise AuthenticationError("DEV_AUTH_AUDIENCE_INVALID", "development audience is invalid") from exc
    principal = SignedPrincipal(
        subject_id=x_sip_subject,
        tenant_id=x_sip_tenant,
        project_ids=_csv(x_sip_projects),
        roles=_csv(x_sip_roles),
        purposes=_csv(x_sip_purposes),
        audience=audience,
        attributes={},
    )
    request.state.principal = principal
    return principal
