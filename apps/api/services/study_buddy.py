"""Screen 25 · AI Study Buddy: a hint-first tutor for students.

Rules:
- The tutor gives hints, questions and explanations, not finished solutions, and is
  switched off while the student has a practice-test attempt in progress.
- Minors' data (Master Plan): the model sees only the question, recent turns of this
  student's own chat and the topic. No names, ids, emails or phone numbers are sent:
  emails and phone numbers are redacted before anything is stored or sent.
- Every call is one `ai_calls` row in usage_ledger. The daily cap comes from the
  college's active MoU (ai_calls_per_day). Trainers see counts (L21), never the chat.
- The model is called outside any database transaction (architecture rule 3).

STUDY_BUDDY_ADAPTER=fake (default) answers deterministically; =anthropic calls Claude.
"""
import datetime
import re
from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import MouTerm, UsageLedger

DEFAULT_DAILY_CAP = 30
HISTORY_TURNS = 6
MIN_GAP_SECONDS = 3

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")

SYSTEM_PROMPT = """You are IREP Study Buddy, a patient tutor for engineering college students in India \
preparing for placements (DSA, aptitude, SQL, web development, cloud and AI basics).

How you help:
- Lead with a hint or a guiding question, then a short explanation of the idea. Give a small \
example that is different from the student's exact task. Do not write the complete solution to \
an assignment, coding problem or test question, even if asked; offer the next step instead.
- Keep answers short: at most about 150 words unless the student asks for more detail.
- Reply in the language the student writes in. If they write in Tamil, reply in simple Tamil \
and keep technical terms in English.
- If the question is not about studies or careers, say briefly that you can only help with \
studies and suggest talking to their trainer.
- Never ask for personal details. If the student shares worries about safety or wellbeing, \
answer kindly and ask them to talk to their trainer or college counsellor."""


def redact(text: str) -> str:
    return PHONE.sub("[phone removed]", EMAIL.sub("[email removed]", text))


class BuddyAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def reply(self, history: List[Dict[str, str]], question: str, topic: Optional[str], lang: str,
              context: Optional[str] = None) -> str:
        """history: earlier turns as [{"role": "user"|"assistant", "content": str}].
        context: an operator instruction for this turn (the course being studied, practice mode), or None."""


class FakeBuddyAdapter(BuddyAdapter):
    name = "fake"

    def reply(self, history, question, topic, lang, context=None):
        about = f" about {topic}" if topic else ""
        if context and PRACTICE_MARK in context:
            if lang == "ta":
                return "பயிற்சிக் கேள்வி: ஒரு வரிசையில் இரண்டு எண்களின் கூட்டுத்தொகை இலக்குக்குச் சமமாக உள்ள குறியீடுகளை எப்படிக் கண்டுபிடிப்பீர்கள்? உங்கள் அணுகுமுறையை எழுதுங்கள்."
            return ("Practice question: given an array of numbers and a target, how would you find two positions whose values "
                    "add up to the target in one pass? Write your approach, then I will give feedback.")
        if lang == "ta":
            return (f"நல்ல கேள்வி{about}! முதலில் இதை யோசியுங்கள்: உள்ளீடு என்ன, எதிர்பார்க்கும் வெளியீடு என்ன? "
                    "ஒரு சிறிய உதாரணத்தைக் கையால் செய்து பாருங்கள், பிறகு எந்தப் படி மீண்டும் வருகிறது என்று கவனியுங்கள்.")
        return (f"Good question{about}! Start here: what is the input, and what exactly should the output be? "
                "Work one small example by hand, then look for the step that repeats. That step is usually your loop or recursion.")


class ClaudeBuddyAdapter(BuddyAdapter):
    """Claude via the official Anthropic Python SDK (imported only when this adapter is used)."""
    name = "anthropic"

    def __init__(self, client=None, model: Optional[str] = None):
        if client is None:
            import anthropic   # optional dependency: install it where STUDY_BUDDY_ADAPTER=anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.model = model or settings.STUDY_BUDDY_MODEL

    def reply(self, history, question, topic, lang, context=None):
        content = question if not topic else f"(Topic: {topic})\n{question}"
        turn = [{"role": "user", "content": content}]
        if context:
            # The per-turn instruction (course, practice mode) goes after the user turn as a mid-conversation system
            # message, so the cached system prompt stays byte-identical. Models without that support get it inline.
            if supports_mid_system(self.model):
                turn.append({"role": "system", "content": context})
            else:
                turn = [{"role": "user", "content": f"[Tutor instructions: {context}]\n{content}"}]
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[*history, *turn],
            output_config={"effort": "low"},                       # short tutoring turns
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                                     # a policy decline is retried on a fallback model
        )
        if response.stop_reason == "refusal":
            return ("I can't help with that one. Try asking about the concept behind it, or talk to your trainer."
                    if lang != "ta" else "இதற்கு என்னால் உதவ முடியாது. இதன் அடிப்படைக் கருத்தைப் பற்றிக் கேளுங்கள் அல்லது பயிற்சியாளரிடம் பேசுங்கள்.")
        return "".join(b.text for b in response.content if b.type == "text").strip()


# Models that accept {"role": "system"} inside messages (Claude Opus 5 / 5.5, Opus 4.8, Fable and Mythos 5.x,
# Sonnet 5.5, Haiku 5.5; not Sonnet 5).
_MID_SYSTEM_PREFIXES = ("claude-opus-5", "claude-opus-4-8", "claude-fable-5", "claude-mythos-5", "claude-sonnet-5-5", "claude-haiku-5-5")


def supports_mid_system(model: str) -> bool:
    return any((model or "").startswith(p) for p in _MID_SYSTEM_PREFIXES)


PRACTICE_MARK = "PRACTICE MODE"


def turn_context(course_title: Optional[str], course_lessons: List[str], mode: str) -> Optional[str]:
    """The operator instruction for one turn: which course the student is studying, and practice mode."""
    parts = []
    if course_title:
        lessons = "; ".join(course_lessons[:12])
        parts.append(f"The student is studying the course \"{course_title}\"" + (f" (lessons: {lessons})" if lessons else "")
                     + ". Keep explanations and examples within this course.")
    if mode == "practice":
        parts.append(f"{PRACTICE_MARK}: quiz the student. Ask one short question at a time on the course or topic, wait for "
                     "their answer, then say what was right, what was missing, and ask the next question. Do not give the "
                     "answer before they try.")
    return " ".join(parts) or None


def get_adapter() -> BuddyAdapter:
    if (settings.STUDY_BUDDY_ADAPTER or "fake").lower() == "anthropic":
        return ClaudeBuddyAdapter()
    return FakeBuddyAdapter()


# ---------------------------------------------------------------------------
# quota and usage (L21, L36)
# ---------------------------------------------------------------------------

def daily_cap(db: Session, college_id: str) -> int:
    """L36: the AI-call cap comes from the college's MoU (services/quotas, screen 47)."""
    from services.quotas import ai_calls_per_day
    return ai_calls_per_day(db, college_id)


def calls_since(db: Session, student_id: str, since: datetime.datetime) -> int:
    return int(db.execute(select(func.count(UsageLedger.id)).where(
        UsageLedger.student_id == student_id, UsageLedger.kind == "ai_calls", UsageLedger.created_at >= since)).scalar_one())


def day_start(now: Optional[datetime.datetime] = None) -> datetime.datetime:
    now = now or datetime.datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def calls_by_student(db: Session, student_ids: Iterable[str], days: int = 7) -> Dict[str, int]:
    """L21: AI usage counts per student for 13 and 14 (counts only, never content)."""
    ids = list(student_ids)
    if not ids:
        return {}
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    return dict(db.execute(select(UsageLedger.student_id, func.count(UsageLedger.id)).where(
        UsageLedger.student_id.in_(ids), UsageLedger.kind == "ai_calls", UsageLedger.created_at >= since)
        .group_by(UsageLedger.student_id)).all())
