"""AI Book Coach — interviews the user via chat, then generates a complete book."""
import json

from backend.config import settings
from backend.core.ai import _try_providers
from backend.core.prompt_safety import fence

INTERVIEW_QUESTIONS = [
    "What is the main topic or subject of your book?",
    "Who is your target audience? What do they already know?",
    "What is the core message or thesis you want to convey?",
    "What are 3-5 key chapters or sections you have in mind?",
    "What tone should the book have? (professional, conversational, academic, inspirational)",
    "What length are you aiming for? (short guide ~20p, standard book ~100p, comprehensive ~200+p)",
    "What is your background or expertise on this topic?",
    "Are there any existing books or resources you want to differentiate from?",
    "What format should the final output be? (ebook, website, landing page, blog post, interactive)",
    "Do you have any specific examples, stories, or data you want included?",
]

BOOK_SPEC_KEYS = [
    "topic", "audience", "core_message", "chapters",
    "tone", "length", "expertise", "competitors", "format", "examples",
]


def start_interview() -> dict:
    """Start a new interview session and return the first question."""
    return {
        "session_id": _new_session_id(),
        "question_index": 0,
        "question": INTERVIEW_QUESTIONS[0],
        "total_questions": len(INTERVIEW_QUESTIONS),
        "answers": {},
        "done": False,
    }


def _new_session_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8]


def process_answer(session: dict, answer: str) -> dict:
    """Process an answer and return the next question or final spec."""
    idx = session.get("question_index", 0)
    session.setdefault("answers", {})[BOOK_SPEC_KEYS[idx]] = answer
    next_idx = idx + 1
    if next_idx >= len(INTERVIEW_QUESTIONS):
        session["done"] = True
        session["spec"] = _generate_book_spec(session["answers"])
        session["book"] = _generate_full_book(session["spec"])
        return session
    session["question_index"] = next_idx
    session["question"] = INTERVIEW_QUESTIONS[next_idx]
    return session


def _generate_book_spec(answers: dict) -> dict:
    """Convert interview answers into a structured book specification."""
    system = "You are a book development editor. Return only valid JSON."
    ans_str = json.dumps(answers, indent=2)
    user = f"""Based on these interview answers, create a detailed book specification:

{fence(ans_str)}

Return JSON with:
- title: compelling book title
- subtitle: subtitle
- author_name: author name
- target_audience: detailed audience description
- tone: writing tone
- estimated_pages: page count
- chapters: array of objects with title, intro (2-3 sentences), sections (array of heading strings)
- key_message: one-sentence core message"""
    raw = _try_providers(system, user, preferred=settings.ai_provider)
    return json.loads(raw)


def _generate_full_book(spec: dict) -> dict:
    """Generate the complete ebook_dict from a book specification."""
    system = "You are an expert book writer. Return only valid JSON."
    user = f"""Write a complete book based on this specification:

{json.dumps(spec, indent=2)}

Return JSON with the EXACT structure:
- title, subtitle, author, summary
- chapters: array, each with:
  - title, introduction, key_takeaway
  - sections: array with heading and content (2-3 paragraphs each)
  - chapter_summary: object with title and points array
  - faq: array with question/answer objects
  - checklist: object with title and items array
- conclusion: object with title and content
Make each chapter 3-5 sections with substantial content."""
    raw = _try_providers(system, user, preferred=settings.ai_provider, max_tokens=12000)
    return json.loads(raw)
