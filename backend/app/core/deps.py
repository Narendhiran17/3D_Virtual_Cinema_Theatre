from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.errors import APIException, TenantAccessDeniedException
from app.core.security import decode_token

security_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    def __init__(
        self,
        id: str,
        email: str,
        full_name: str,
        is_platform_admin: bool = False,
        tenant_roles: Optional[dict] = None,
    ):
        self.id = id
        self.email = email
        self.full_name = full_name
        self.is_platform_admin = is_platform_admin
        self.tenant_roles = tenant_roles or {}  # tenant_id -> role_name


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> AuthenticatedUser:
    if not auth or not auth.credentials:
        raise APIException(
            code="UNAUTHENTICATED",
            message="Authentication credentials were not provided.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        payload = decode_token(auth.credentials)
    except Exception:
        raise APIException(
            code="INVALID_TOKEN",
            message="Token is invalid or expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if payload.get("type") != "access":
        raise APIException(
            code="INVALID_TOKEN_TYPE",
            message="Expected an access token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user_id = payload.get("sub")
    if not user_id:
        raise APIException(
            code="INVALID_TOKEN",
            message="Token payload is missing subject.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Reconstruct authenticated user from claims (or loaded from session/DB)
    is_platform_admin = "PLATFORM_ADMIN" in payload.get("roles", [])
    tenant_ids = payload.get("tenant_ids", [])
    tenant_roles = {t: "OPERATOR_ADMIN" for t in tenant_ids}

    return AuthenticatedUser(
        id=user_id,
        email=payload.get("email", "user@example.com"),
        full_name=payload.get("full_name", "User"),
        is_platform_admin=is_platform_admin,
        tenant_roles=tenant_roles,
    )


async def get_optional_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[AuthenticatedUser]:
    if not auth or not auth.credentials:
        return None
    try:
        return await get_current_user(auth)
    except APIException:
        return None


async def get_current_tenant_id(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> str:
    """Enforces tenant isolation by verifying the authenticated user owns or is assigned to the tenant."""
    if not x_tenant_id:
        raise APIException(
            code="MISSING_TENANT_HEADER",
            message="X-Tenant-ID header is required for this operation.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Platform admins can manage any tenant
    if current_user.is_platform_admin:
        return x_tenant_id

    # Tenant users can only access their authorized tenant
    if x_tenant_id not in current_user.tenant_roles:
        raise TenantAccessDeniedException(
            f"User does not have access to tenant '{x_tenant_id}'."
        )

    return x_tenant_id


def require_platform_admin(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if not current_user.is_platform_admin:
        raise APIException(
            code="FORBIDDEN_PLATFORM_ADMIN_REQUIRED",
            message="This action requires central platform administrator privileges.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return current_user
