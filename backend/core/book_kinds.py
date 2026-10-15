"""Book kinds: what *kind* of book is being written (guide, DIY manual,
cookbook, workbook, course, novel, children's book), as opposed to the output
format (ebook / website / blog …, `content_type`).

A kind decides how the outline is planned, how each chapter is written and
reviewed, which pipeline steps make sense (fact-checking a novel is
meaningless; fact-checking a DIY manual's safety advice is essential), and
which structured elements (ingredient lists, numbered steps, warnings,
exercises …) a chapter may carry. Those elements are "blocks": small typed
dicts the model returns and `normalize_blocks()` validates, rendered by
templates/blocks/rich.html in every format.
"""
from dataclasses import dataclass

DEFAULT_KIND = "guide"

# Block types a chapter or section may carry. Anything else the model invents
# is dropped by normalize_blocks().
BLOCK_SCHEMA = """Optional "blocks": an array of structured elements. Allowed shapes, nothing else:
  {"type": "facts", "items": [{"label": "Time", "value": "2 hours"}]}
  {"type": "list", "title": "Materials", "style": "checklist" | "bullets", "items": ["..."]}
  {"type": "steps", "title": "Steps", "items": [{"text": "...", "tip": "optional short tip"}]}
  {"type": "callout", "kind": "warning" | "tip" | "note", "title": "...", "text": "..."}
  {"type": "exercise", "title": "...", "prompt": "...", "lines": 4}
  {"type": "quiz", "title": "...", "questions": [{"q": "...", "options": ["..."], "answer": "..."}]}
Titles, labels and values are written in the book's language."""


@dataclass(frozen=True)
class BookKind:
    id: str
    label: str
    description: str
    words_per_section: int = 550
    sections_hint: str = "3-4 sections"
    default_chapters: str = "4-6 chapters"
    # Prompt fragments (empty = same behaviour as the original generic guide).
    outline_rules: str = ""
    outline_extra_json: str = ""          # extra top-level JSON fields in the outline
    writer_persona: str = ""              # replaces the default author persona
    writer_rules: str = ""                # extra RULES lines for chapter writing
    review_criteria: str = ""             # extra bullet lines for the editor's review
    block_guidance: str = ""              # which blocks to use where (empty = no blocks)
    # Pipeline behaviour
    research: bool = True
    structure: bool = True                # per-chapter summary / FAQ / checklist
    fact_check: bool = True
    show_intro: bool = True               # chapter intro paragraph
    show_takeaway: bool = True
    scene_breaks: bool = False            # "* * *" between sections (fiction)
    glossary: bool = True


KINDS: dict[str, BookKind] = {k.id: k for k in [
    BookKind(
        id="guide", label="Guide / non-fiction",
        description="Practical non-fiction: a how-to guide, self-help, business or expert book.",
    ),
    BookKind(
        id="diy", label="DIY / project manual",
        description="Hands-on projects: materials, tools, safety, numbered steps, troubleshooting.",
        words_per_section=350, sections_hint="3-5 sections",
        outline_rules=(
            "- This is a DIY / project manual. Each chapter is ONE project (or one technique) a "
            "beginner can actually carry out; sections are its phases (preparation, main work, "
            "finishing, troubleshooting)\n"
            "- Order projects from easiest to hardest, and say so in the summary"),
        writer_persona=("an experienced craftsperson and technical writer who has built every project "
                        "described, and writes clear, safe, step-by-step instructions"),
        writer_rules=(
            "- Write as instructions to the reader: imperative, concrete, one action per sentence\n"
            "- Give real quantities, dimensions, times and tolerances the project needs, or say what to measure\n"
            "- Say WHY a step matters and what can go wrong; include how to tell it went right\n"
            "- Every genuinely dangerous step (power tools, electricity, heat, chemicals, heights) "
            "gets a warning callout; never skip safety to be brief"),
        review_criteria=(
            "- could a beginner follow it without guessing? (missing quantities, tools or order of steps are defects)\n"
            "- safety: every hazard has a warning; nothing dangerous is presented as trivial"),
        block_guidance=(
            "Chapter-level blocks: one \"facts\" block (difficulty, time, estimated cost), one \"list\" "
            "block of materials (checklist), one of tools (checklist), and \"callout\" warnings where hazards "
            "exist. Put the numbered procedure in a \"steps\" block on the section where it happens."),
        research=False, structure=False, show_takeaway=False,
    ),
    BookKind(
        id="cookbook", label="Cookbook",
        description="Recipes grouped by chapter: ingredients, method, servings, timing.",
        words_per_section=120, sections_hint="4-6 recipes",
        outline_rules=(
            "- This is a cookbook. Each chapter is a CATEGORY of dishes (e.g. breakfasts, soups); "
            "every section is ONE recipe whose heading is the dish name and whose content is a "
            "one-paragraph headnote (what it is, why it works)\n"
            "- Recipes within a chapter must be distinct dishes, not variations of one"),
        writer_persona="a professional recipe developer and food writer whose recipes work the first time",
        writer_rules=(
            "- Section \"content\" is a short, appetising headnote (about 60-120 words): the dish, when to make it, one tip\n"
            "- Quantities are exact and use one consistent unit system (metric unless the audience implies otherwise)\n"
            "- Do not invent nutrition figures or health claims"),
        review_criteria=(
            "- can each recipe be cooked as written? (missing quantities, steps, times or temperatures are defects)\n"
            "- ingredient lists match the method; no ingredient appears from nowhere"),
        block_guidance=(
            "On EVERY section (one recipe) include: a \"facts\" block (servings, prep time, cook time), "
            "a \"list\" block of ingredients with quantities (bullets), and a \"steps\" block with the method."),
        research=False, structure=False, fact_check=False, show_intro=True, show_takeaway=False, glossary=False,
    ),
    BookKind(
        id="workbook", label="Workbook / planner",
        description="An interactive book: explanations plus exercises, checklists and reflection prompts.",
        words_per_section=250, sections_hint="3-4 sections",
        outline_rules=(
            "- This is a WORKBOOK: the reader writes in it. Each chapter teaches one idea briefly, "
            "then makes the reader apply it through exercises"),
        writer_persona="an instructional designer who writes workbooks people actually complete",
        writer_rules=(
            "- Keep explanations short (about 150-250 words) and move quickly to something the reader does\n"
            "- Exercises are specific and answerable in minutes, never \"reflect on your life\""),
        review_criteria="- every chapter has exercises the reader can actually do; no exercise is vague",
        block_guidance=(
            "Each chapter: 2-3 \"exercise\" blocks (with a prompt and answer lines) and one \"list\" checklist "
            "block of actions; a \"callout\" tip where helpful."),
        research=False, structure=False, show_takeaway=True,
    ),
    BookKind(
        id="course", label="Course / textbook",
        description="Teaching material: learning objectives, explanations, worked examples, quizzes.",
        words_per_section=450, sections_hint="3-4 sections",
        outline_rules=(
            "- This is a course / textbook. Chapters build on one another from fundamentals to advanced; "
            "sections within a chapter are lessons"),
        writer_persona="an experienced teacher and textbook author who explains difficult ideas simply and precisely",
        writer_rules=(
            "- Define each term when first used; introduce one new idea at a time\n"
            "- Use worked examples with the reasoning shown, not only the answer"),
        review_criteria="- ideas are introduced in order, defined before use, and illustrated with worked examples",
        block_guidance=(
            "Chapter-level blocks: a \"list\" of learning objectives (bullets) at the start, and a \"quiz\" "
            "block of 3-5 questions with answers at the end."),
        research=True, structure=True, fact_check=True,
    ),
    BookKind(
        id="novel", label="Novel / fiction",
        description="A story: characters, setting, plot and scenes written as continuous prose.",
        words_per_section=800, sections_hint="3-5 scenes", default_chapters="8-12 chapters",
        outline_rules=(
            "- This is FICTION. Plan a complete story with a beginning, escalating conflict, a "
            "turning point, a climax and a resolution; every chapter must move the plot\n"
            "- A chapter's \"introduction\" is a 1-2 sentence note of what happens in it (not shown to readers)\n"
            "- Sections are SCENES: \"heading\" is empty, \"content\" is a beat-sheet of that scene "
            "(who, where, what changes)\n"
            "- Leave \"key_takeaway\" empty; the conclusion is the story's final scene or epilogue\n"
            "- Characters must want something and be changed by the story; no chapter may reuse a scene"),
        outline_extra_json=(
            '"story": {"premise": "...", "setting": "...", "themes": ["..."], "point_of_view": '
            '"first person past | third person limited past | ...", '
            '"characters": [{"name": "...", "role": "protagonist", "description": "...", "arc": "..."}]},'),
        writer_persona=("a published novelist with a distinctive, consistent voice who shows rather than tells "
                        "and writes believable dialogue"),
        writer_rules=(
            "- Write each scene as flowing prose with dialogue, action and interiority; no summaries, "
            "no lists, no headings; \"heading\" stays empty\n"
            "- Keep the point of view, tense, character names, facts and tone from the story bible and "
            "earlier chapters exactly consistent\n"
            "- \"introduction\" and \"key_takeaway\" stay empty\n"
            "- Add \"recap\": 2 sentences saying what happened and where each main character stands "
            "(used to keep later chapters consistent)\n"
            "- End scenes on a turn, question or image, not a moral"),
        review_criteria=(
            "- voice and point of view are consistent and distinctive; dialogue sounds like people\n"
            "- scenes show instead of explain; no summary-of-feelings, no moralising\n"
            "- continuity with the story bible and earlier chapters (names, facts, timeline)"),
        research=False, structure=False, fact_check=False, show_intro=False, show_takeaway=False,
        scene_breaks=True, glossary=False,
    ),
    BookKind(
        id="children", label="Children's book",
        description="A short illustrated story for young readers: simple language, short pages.",
        words_per_section=50, sections_hint="4-6 short pages", default_chapters="3-4 chapters",
        outline_rules=(
            "- This is a CHILDREN'S picture book: a simple story with a clear character who wants "
            "something, a problem, and a happy or hopeful ending\n"
            "- Each section is ONE PAGE (a spread); \"content\" is a one-sentence description of what "
            "happens on it; \"heading\" is empty\n"
            "- Keep the number of chapters small; leave \"key_takeaway\" empty"),
        outline_extra_json=(
            '"story": {"premise": "...", "setting": "...", "themes": ["..."], '
            '"characters": [{"name": "...", "role": "hero", "description": "...", "arc": "..."}]},'),
        writer_persona="an award-winning children's author who writes for being read aloud",
        writer_rules=(
            "- Each page is 1-3 short sentences (about 20-50 words): concrete, rhythmic, fun to read aloud\n"
            "- Use simple words for ages 3-7, repetition and gentle humour; no scary or preachy content\n"
            "- \"heading\", \"introduction\" and \"key_takeaway\" stay empty"),
        review_criteria=(
            "- every page is short, vivid and easy to read aloud; vocabulary suits young children\n"
            "- the story has a clear problem and a satisfying ending"),
        research=False, structure=False, fact_check=False, show_intro=False, show_takeaway=False,
        glossary=False,
    ),
]}


def get_kind(kind_id: str | None) -> BookKind:
    return KINDS.get((kind_id or "").strip().lower(), KINDS[DEFAULT_KIND])


def list_kinds() -> list[dict]:
    return [{"id": k.id, "label": k.label, "description": k.description} for k in KINDS.values()]


# ── Block validation ──────────────────────────────────────────────────

_MAX_ITEMS = 40
_MAX_TEXT = 1200


def _text(value, limit: int = _MAX_TEXT) -> str:
    return str(value).strip()[:limit] if isinstance(value, str | int | float) else ""


def _clean_facts(block: dict) -> dict | None:
    items = [{"label": _text(i.get("label"), 60), "value": _text(i.get("value"), 120)}
             for i in block.get("items", []) if isinstance(i, dict)]
    items = [i for i in items if i["label"] and i["value"]][:12]
    return {"type": "facts", "items": items} if items else None


def _clean_list(block: dict) -> dict | None:
    items = [_text(i) for i in block.get("items", []) if _text(i)][:_MAX_ITEMS]
    style = block.get("style") if block.get("style") in ("checklist", "bullets") else "bullets"
    return {"type": "list", "title": _text(block.get("title"), 120), "style": style, "items": items} if items else None


def _clean_steps(block: dict) -> dict | None:
    steps = []
    for i in block.get("items", []):
        text = _text(i.get("text") if isinstance(i, dict) else i)
        if text:
            steps.append({"text": text, "tip": _text(i.get("tip"), 300) if isinstance(i, dict) else ""})
    return {"type": "steps", "title": _text(block.get("title"), 120), "items": steps[:_MAX_ITEMS]} if steps else None


def _clean_callout(block: dict) -> dict | None:
    text = _text(block.get("text"))
    ckind = block.get("kind") if block.get("kind") in ("warning", "tip", "note") else "note"
    return {"type": "callout", "kind": ckind, "title": _text(block.get("title"), 120), "text": text} if text else None


def _clean_exercise(block: dict) -> dict | None:
    prompt = _text(block.get("prompt"))
    try:
        lines = max(0, min(int(block.get("lines", 4)), 12))
    except (TypeError, ValueError):
        lines = 4
    return {"type": "exercise", "title": _text(block.get("title"), 120), "prompt": prompt, "lines": lines} if prompt else None


def _clean_quiz(block: dict) -> dict | None:
    questions = []
    for q in block.get("questions", []):
        if isinstance(q, dict) and _text(q.get("q")):
            options = q.get("options") if isinstance(q.get("options"), list) else []
            questions.append({"q": _text(q.get("q")),
                              "options": [_text(o, 200) for o in options if _text(o, 200)][:6],
                              "answer": _text(q.get("answer"), 300)})
    return {"type": "quiz", "title": _text(block.get("title"), 120), "questions": questions[:10]} if questions else None


_CLEANERS = {"facts": _clean_facts, "list": _clean_list, "steps": _clean_steps,
             "callout": _clean_callout, "exercise": _clean_exercise, "quiz": _clean_quiz}


def _clean_block(block: dict) -> dict | None:
    cleaner = _CLEANERS.get(block.get("type"))
    return cleaner(block) if cleaner else None


def normalize_blocks(blocks) -> list[dict]:
    """Validate model-produced blocks: known types only, bounded sizes, plain
    strings. Malformed or empty blocks are dropped, never raised on."""
    if not isinstance(blocks, list):
        return []
    cleaned = []
    for block in blocks[:20]:
        if isinstance(block, dict):
            try:
                result = _clean_block(block)
            except (AttributeError, TypeError):
                result = None
            if result:
                cleaned.append(result)
    return cleaned
