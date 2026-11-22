"""Tamil <-> English translation behind an adapter (Screen 35).

TRANSLATE_ADAPTER=fake (default) uses known seeded pairs plus a small
glossary and otherwise tags the text; TRANSLATE_ADAPTER=libretranslate
calls a self-hosted LibreTranslate at TRANSLATE_URL. Every result is
cached in translations_cache so a message is translated once.
"""
import hashlib
import json
import re
import urllib.request
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import DirectMessage, TranslationCache

TAMIL = re.compile(r"[஀-௿]")

GLOSSARY = {
    "thank you": "நன்றி",
    "thank you sir.": "நன்றி சார்.",
    "good morning": "காலை வணக்கம்",
    "hello": "வணக்கம்",
    "see you on saturday.": "சனிக்கிழமை சந்திப்போம்.",
}


def detect_lang(text: str) -> str:
    return "ta" if TAMIL.search(text or "") else "en"


class FakeTranslator:
    name = "fake"

    def translate(self, db: Session, text: str, src: str, dst: str, college_id: str) -> str:
        # 1) a seeded bilingual message with this exact text
        if src == "en":
            row = db.execute(select(DirectMessage.text_ta).where(DirectMessage.text_en == text, DirectMessage.text_ta.is_not(None), DirectMessage.college_id == college_id)).scalars().first()
        else:
            row = db.execute(select(DirectMessage.text_en).where(DirectMessage.text_ta == text, DirectMessage.college_id == college_id)).scalars().first()
        if row:
            return row
        # 2) glossary
        key = text.strip().lower()
        if src == "en" and key in GLOSSARY:
            return GLOSSARY[key]
        if src == "ta":
            for en, ta in GLOSSARY.items():
                if ta == text.strip():
                    return en.capitalize()
        # 3) tagged passthrough so the reader knows it is machine output
        return f"[{'தமிழ்' if dst == 'ta' else 'English'}] {text}"


class LibreTranslateAdapter:
    name = "libretranslate"

    def translate(self, db: Session, text: str, src: str, dst: str, college_id: str) -> str:
        req = urllib.request.Request(
            f"{settings.TRANSLATE_URL.rstrip('/')}/translate",
            data=json.dumps({"q": text, "source": src, "target": dst, "format": "text"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())["translatedText"]


def get_translator():
    return LibreTranslateAdapter() if settings.TRANSLATE_ADAPTER == "libretranslate" else FakeTranslator()


def translate(db: Session, text: str, dst: str, college_id: str, src: Optional[str] = None) -> str:
    src = src or detect_lang(text)
    if not text or src == dst:
        return text
    key = hashlib.sha256(f"{src}|{dst}|{text}".encode()).hexdigest()
    hit = db.execute(select(TranslationCache).filter_by(id=key)).scalar_one_or_none()
    if hit:
        return hit.translated_text
    engine = get_translator()
    out = engine.translate(db, text, src, dst, college_id)
    db.add(TranslationCache(id=key, college_id=college_id, src=src, dst=dst, source_text=text, translated_text=out, engine=engine.name))
    db.flush()
    return out
