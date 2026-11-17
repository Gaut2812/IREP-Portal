"""Signed media access (stand-in for presigned object-storage URLs)."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from services.live_sessions import verify_signed

router = APIRouter(tags=["Media"])


@router.get("/media/{storage_key:path}")
def get_media(storage_key: str, exp: int, sig: str):
    if not verify_signed(storage_key, exp, sig):
        raise HTTPException(status_code=403, detail="Link expired or invalid")
    return JSONResponse({"storage_key": storage_key, "status": "ok",
                         "note": "Object storage is not configured in development; the signed link is valid."})
