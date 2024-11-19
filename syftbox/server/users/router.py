from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from syftbox.lib.email import send_token_email
from syftbox.server.settings import ServerSettings, get_server_settings
from syftbox.server.users.auth import generate_access_token, generate_email_token, get_user_from_email_token

router = APIRouter(prefix="/auth", tags=["authentication"])


class EmailTokenRequest(BaseModel):
    email: EmailStr

class EmailTokenResponse(BaseModel):
    email_token: Optional[str] = None

class AccessTokenResponse(BaseModel):
    access_token: str


@router.post("/request_email_token")
def get_token(req: EmailTokenRequest, server_settings: ServerSettings = Depends(get_server_settings)):
    email = req.email
    token = generate_email_token(server_settings, email)

    response = EmailTokenResponse()
    if server_settings.auth_enabled:
        send_token_email(server_settings, email, token)
    else:
        # Only return token if auth is disabled, it will be a base64 encoded json string
        response.email_token = token

    return response


@router.post("/validate_email_token")
def get_token(
    email: str = Depends(get_user_from_email_token),
    server_settings: ServerSettings = Depends(get_server_settings),
):
    access_token = generate_access_token(server_settings, email)
    return AccessTokenResponse(access_token=access_token)