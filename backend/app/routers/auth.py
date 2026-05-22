from fastapi import APIRouter, Depends, HTTPException

from app.schemas import AuthLoginRequest, AuthRegisterRequest, AuthResponse, UserPublic
from app.services.auth_service import create_access_token, demo_login, get_current_user, login_user, register_user, user_public

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=AuthResponse)
def register(payload: AuthRegisterRequest) -> AuthResponse:
    user = register_user(payload.email, payload.password, payload.display_name)
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(user=UserPublic.model_validate(user_public(user)), access_token=token)


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthLoginRequest) -> AuthResponse:
    user = login_user(payload.email, payload.password)
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(user=UserPublic.model_validate(user_public(user)), access_token=token)


@router.post("/auth/demo-login", response_model=AuthResponse)
def login_demo() -> AuthResponse:
    user = demo_login()
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(user=UserPublic.model_validate(user_public(user)), access_token=token)


@router.get("/auth/me", response_model=UserPublic)
def me(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return UserPublic.model_validate(user_public(user))
