from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    environment = os.getenv("ENVIRONMENT", "development")
    secret = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    issuer = os.getenv("JWT_ISSUER", "adgen-auth")

    decode_options = {}
    if environment == "development":
        decode_options["verify_iss"] = False

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=[algorithm],
            issuer=issuer if environment != "development" else None,
            options=decode_options,
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing sub",
            )
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "name": payload.get("name"),
            "roles": payload.get("roles", []),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )
