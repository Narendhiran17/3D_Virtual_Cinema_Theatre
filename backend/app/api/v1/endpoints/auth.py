import uuid
from typing import Dict
from fastapi import APIRouter, Depends, Request, status
from app.core.deps import AuthenticatedUser, get_current_user
from app.core.errors import APIException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.schemas.auth import (
    RefreshTokenRequest,
    TenantMembershipResponse,
    TokenResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)
from app.schemas.common import ResponseMeta, StandardResponse

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])

# In-memory mock store for Sprint 1/2 tests until DB connection is seeded
# Key: email -> user record
MOCK_USERS: Dict[str, dict] = {
    "admin@platform.com": {
        "id": "usr-admin-001",
        "full_name": "Platform Administrator",
        "email": "admin@platform.com",
        "phone": "+1000000000",
        "password_hash": get_password_hash("AdminPass123!"),
        "status": "ACTIVE",
        "is_platform_admin": True,
        "tenants": [],
        "roles": ["PLATFORM_ADMIN"],
    },
    "operator@apexcinemas.com": {
        "id": "usr-operator-002",
        "full_name": "Apex Cinema Manager",
        "email": "operator@apexcinemas.com",
        "phone": "+1000000001",
        "password_hash": get_password_hash("OperatorPass123!"),
        "status": "ACTIVE",
        "is_platform_admin": False,
        "tenants": [
            {
                "tenant_id": "ten-apex-001",
                "tenant_name": "Apex Cinemas International",
                "tenant_slug": "apex-cinemas",
                "role_name": "OPERATOR_ADMIN",
            }
        ],
        "roles": ["OPERATOR_ADMIN"],
    },
}


@router.post("/register", response_model=StandardResponse[UserProfileResponse])
async def register(payload: UserRegisterRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    if payload.email in MOCK_USERS:
        raise APIException(
            code="EMAIL_ALREADY_REGISTERED",
            message="A user with this email address already exists.",
            status_code=status.HTTP_409_CONFLICT,
        )

    user_id = f"usr-{uuid.uuid4().hex[:12]}"
    new_user = {
        "id": user_id,
        "full_name": payload.full_name,
        "email": payload.email,
        "phone": payload.phone,
        "password_hash": get_password_hash(payload.password),
        "status": "ACTIVE",
        "is_platform_admin": False,
        "tenants": [],
        "roles": ["CUSTOMER"],
    }
    MOCK_USERS[payload.email] = new_user

    return StandardResponse(
        data=UserProfileResponse(
            id=user_id,
            full_name=new_user["full_name"],
            email=new_user["email"],
            phone=new_user["phone"],
            status=new_user["status"],
            is_platform_admin=new_user["is_platform_admin"],
            tenants=[],
        ),
        meta=ResponseMeta(request_id=request_id),
    )


@router.post("/login", response_model=StandardResponse[TokenResponse])
async def login(payload: UserLoginRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)
    user = MOCK_USERS.get(payload.email)

    if not user or not verify_password(payload.password, user["password_hash"]):
        raise APIException(
            code="INVALID_CREDENTIALS",
            message="Invalid email address or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user["status"] != "ACTIVE":
        raise APIException(
            code="ACCOUNT_SUSPENDED",
            message="Account is inactive or suspended.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    tenant_ids = [t["tenant_id"] for t in user["tenants"]]
    access_token = create_access_token(
        subject=user["id"],
        tenant_ids=tenant_ids,
        roles=user["roles"],
    )
    refresh_token = create_refresh_token(subject=user["id"])

    user_profile = UserProfileResponse(
        id=user["id"],
        full_name=user["full_name"],
        email=user["email"],
        phone=user["phone"],
        status=user["status"],
        is_platform_admin=user["is_platform_admin"],
        tenants=[
            TenantMembershipResponse(
                tenant_id=t["tenant_id"],
                tenant_name=t["tenant_name"],
                tenant_slug=t["tenant_slug"],
                role_name=t["role_name"],
            )
            for t in user["tenants"]
        ],
    )

    return StandardResponse(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_profile,
        ),
        meta=ResponseMeta(request_id=request_id),
    )


@router.post("/refresh", response_model=StandardResponse[TokenResponse])
async def refresh_token(payload: RefreshTokenRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    try:
        token_data = decode_token(payload.refresh_token)
    except Exception:
        raise APIException(
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token is invalid or expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if token_data.get("type") != "refresh":
        raise APIException(
            code="INVALID_TOKEN_TYPE",
            message="Expected a refresh token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user_id = token_data.get("sub")
    user = next((u for u in MOCK_USERS.values() if u["id"] == user_id), None)
    if not user:
        raise APIException(
            code="USER_NOT_FOUND",
            message="User associated with token no longer exists.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    tenant_ids = [t["tenant_id"] for t in user["tenants"]]
    new_access_token = create_access_token(
        subject=user["id"],
        tenant_ids=tenant_ids,
        roles=user["roles"],
    )
    new_refresh_token = create_refresh_token(subject=user["id"])

    user_profile = UserProfileResponse(
        id=user["id"],
        full_name=user["full_name"],
        email=user["email"],
        phone=user["phone"],
        status=user["status"],
        is_platform_admin=user["is_platform_admin"],
        tenants=[
            TenantMembershipResponse(
                tenant_id=t["tenant_id"],
                tenant_name=t["tenant_name"],
                tenant_slug=t["tenant_slug"],
                role_name=t["role_name"],
            )
            for t in user["tenants"]
        ],
    )

    return StandardResponse(
        data=TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_profile,
        ),
        meta=ResponseMeta(request_id=request_id),
    )


@router.get("/me", response_model=StandardResponse[UserProfileResponse])
async def get_me(request: Request, current_user: AuthenticatedUser = Depends(get_current_user)):
    request_id = getattr(request.state, "request_id", None)
    user = next((u for u in MOCK_USERS.values() if u["id"] == current_user.id), None)
    if not user:
        raise APIException(
            code="USER_NOT_FOUND",
            message="User profile not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return StandardResponse(
        data=UserProfileResponse(
            id=user["id"],
            full_name=user["full_name"],
            email=user["email"],
            phone=user["phone"],
            status=user["status"],
            is_platform_admin=user["is_platform_admin"],
            tenants=[
                TenantMembershipResponse(
                    tenant_id=t["tenant_id"],
                    tenant_name=t["tenant_name"],
                    tenant_slug=t["tenant_slug"],
                    role_name=t["role_name"],
                )
                for t in user["tenants"]
            ],
        ),
        meta=ResponseMeta(request_id=request_id),
    )
