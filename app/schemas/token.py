from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None # 'sub' is standard JWT claim for subject (usually user ID or username)
    exp: Optional[int] = None # Expiry time