from fastapi import Request, HTTPException, status
from typing import Optional, Dict, Any

class AuthMiddleware:
    """
    Authentication Middleware Architecture.
    Prepares backend for production Firebase/JWT bearer token authentication
    while gracefully supporting local demo mode.
    """
    @staticmethod
    async def get_current_user(request: Request) -> Dict[str, Any]:
        auth_header = request.headers.get("Authorization")
        
        # If no auth header provided, check if running in prototype/demo mode
        if not auth_header:
            return {
                "id": "usr-demo",
                "name": "Ansh (Demo Engineer)",
                "email": "ansh@devrescue.ai",
                "role": "Staff Engineer",
                "is_authenticated": False,
                "auth_provider": "Demo Authentication"
            }

        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization format. Expected 'Bearer <token>'."
            )

        token = auth_header.split(" ")[1]

        # Future production Firebase Admin SDK token verification:
        # try:
        #     decoded_token = auth.verify_id_token(token)
        #     return decoded_token
        # except Exception as e:
        #     raise HTTPException(status_code=401, detail="Invalid token")

        return {
            "id": f"usr-{token[:8]}",
            "token": token,
            "is_authenticated": True,
            "auth_provider": "Bearer Token"
        }

auth_middleware = AuthMiddleware()
