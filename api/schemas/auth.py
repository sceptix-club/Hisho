from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    role: str


class AuthUrlResponse(BaseModel):
    auth_url: str


class CallbackResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
