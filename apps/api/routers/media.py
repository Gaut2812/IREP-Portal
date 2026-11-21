"""Signed media access (stand-in for presigned object-storage URLs)."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response

from services.live_sessions import verify_signed
from services.storage import get_storage

router = APIRouter(tags=["Media"])


@router.get("/media/{storage_key:path}")
def get_media(storage_key: str, exp: int, sig: str):
    if not verify_signed(storage_key, exp, sig):
        raise HTTPException(status_code=403, detail="Link expired or invalid")
    storage = get_storage()
    try:
        found = storage.exists(storage_key)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    if found:
        return Response(content=storage.get(storage_key), media_type=storage.content_type(storage_key),
                        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})
    # demo recordings are links to Teams, not stored files
    return JSONResponse({"storage_key": storage_key, "status": "ok", "note": "No stored file for this key; the signed link is valid."})
