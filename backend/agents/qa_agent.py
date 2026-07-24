from loguru import logger
from backend.orchestrator.agent import BaseAgent, PipelineContext
from backend.core.ai import qa_check as _qa_check


class QAAgent(BaseAgent):
    """Final quality assessment: structure, content, contrast, layout."""

    def __init__(self):
        super().__init__("QAAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("QAAgent: running quality checks")

        # 1. Local checks (no AI — fast)
        local_issues = _local_checks(ctx)
        if local_issues:
            logger.warning(f"QAAgent: {len(local_issues)} local issues found")

        # 2. AI-powered quality check
        try:
            html_snippet = ctx.html[:3000] if ctx.html else ""
            report = _qa_check(ctx.ebook_dict, ctx.design, html_snippet, ctx.provider)
            report["local_issues"] = local_issues
            ctx.qa_report = report
            score = report.get("score", 0)
            passed = report.get("passed", False)
            if passed:
                logger.success(f"QAAgent: score={score}/100 — PASSED")
            else:
                logger.warning(f"QAAgent: score={score}/100 — ISSUES FOUND")
        except Exception as e:
            logger.warning(f"QAAgent AI check skipped ({e})")
            ctx.qa_report = {
                "issues": local_issues,
                "score": 50,
                "summary": "AI quality check unavailable",
                "passed": len(local_issues) == 0,
            }

        ctx.set_progress(85)
        return ctx


def _local_checks(ctx: PipelineContext) -> list:
    """Fast local quality checks — no AI calls."""
    issues = []
    chapters = ctx.ebook_dict.get("chapters", [])

    # Empty content check
    for ci, ch in enumerate(chapters):
        for si, sec in enumerate(ch.get("sections", [])):
            content = sec.get("content", "").strip()
            heading = sec.get("heading", "").strip()
            if not content and not heading:
                issues.append({
                    "type": "content",
                    "severity": "high",
                    "description": f"Empty section at Ch{ci+1}/Sec{si+1}",
                    "location": f"chapter {ci+1}, section {si+1}",
                })
            elif not content:
                issues.append({
                    "type": "content",
                    "severity": "medium",
                    "description": f"Section with heading but no content: '{heading}'",
                    "location": f"chapter {ci+1}, section {si+1}",
                })

    # Missing introduction check
    for ci, ch in enumerate(chapters):
        if not ch.get("introduction", "").strip():
            issues.append({
                "type": "structure",
                "severity": "low",
                "description": f"Chapter {ci+1} missing introduction",
                "location": f"chapter {ci+1}",
            })

    # Missing key takeaway check
    for ci, ch in enumerate(chapters):
        if not ch.get("key_takeaway", "").strip():
            issues.append({
                "type": "structure",
                "severity": "low",
                "description": f"Chapter {ci+1} missing key takeaway",
                "location": f"chapter {ci+1}",
            })

    # Conclusion check
    conclusion = ctx.ebook_dict.get("conclusion", {})
    if not conclusion.get("content", "").strip():
        issues.append({
            "type": "structure",
            "severity": "medium",
            "description": "Conclusion is empty or missing",
            "location": "conclusion",
        })

    return issues
