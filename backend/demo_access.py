"""Small shared-code gate for paid actions on the hosted hackathon demo."""
import hashlib
import hmac
import os

from fastapi import HTTPException, Request

COOKIE = "atlas_demo_access"


def required():
    return bool(os.getenv("VERCEL")) or os.getenv("ATLAS_REQUIRE_DEMO_ACCESS", "").lower() == "true"


def token():
    code = os.getenv("ATLAS_DEMO_ACCESS_CODE", "")
    return hmac.new(code.encode(), b"contract-atlas-demo-v1", hashlib.sha256).hexdigest() if code else ""


def authorized(request: Request):
    expected = token()
    return not required() or bool(expected and hmac.compare_digest(request.cookies.get(COOKIE, ""), expected))


def require_live_access(request: Request):
    if required() and not token():
        raise HTTPException(503, "Live demo access has not been configured.")
    if not authorized(request):
        raise HTTPException(401, "Enter the demo access code to run live research.")
