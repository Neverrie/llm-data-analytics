from fastapi import APIRouter, Depends

from app.schemas import AuthLoginRequest, AuthRegisterRequest, AuthResponse, UserPublic
from app.services.auth_service import (
    create_access_token,
    demo_login,
    get_current_user,
    login_user,
    register_user,
    user_public,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def auth_register(payload: AuthRegisterRequest) -> AuthResponse:
    user = register_user(payload.email, payload.password, payload.display_name)
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(user=UserPublic.model_validate(user_public(user)), access_token=token)


@router.post("/login", response_model=AuthResponse)
def auth_login(payload: AuthLoginRequest) -> AuthResponse:
    user = login_user(payload.email, payload.password)
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(user=UserPublic.model_validate(user_public(user)), access_token=token)


@router.post("/demo-login", response_model=AuthResponse)
def auth_demo_login() -> AuthResponse:
    user = demo_login()
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(user=UserPublic.model_validate(user_public(user)), access_token=token)


@router.get("/me", response_model=UserPublic)
def auth_me(user: dict = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(user_public(user))
