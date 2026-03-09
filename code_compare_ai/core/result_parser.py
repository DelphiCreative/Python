import json
import re
from typing import Any, Dict, List

from core.models import Issue, StructuredCompareResult, Suggestion

ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
ALLOWED_CATEGORIES = {
    "bug",
    "performance",
    "security",
    "code_smell",
    "maintainability",
    "logic",
    "style",
    "refactoring",
    "other",
}


def _normalize_severity(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    return text if text in ALLOWED_SEVERITIES else "medium"



def _normalize_category(value: Any) -> str:
    text = str(value or "other").strip().lower().replace(" ", "_")
    return text if text in ALLOWED_CATEGORIES else "other"



def _to_float(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, score))



def _extract_json_candidate(response_text: str) -> str:
    text = response_text.strip()
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced[0].strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text



def _build_issue(item: Dict[str, Any]) -> Issue:
    line = item.get("line")
    try:
        line = int(line) if line not in (None, "") else None
    except (TypeError, ValueError):
        line = None

    return Issue(
        severity=_normalize_severity(item.get("severity")),
        category=_normalize_category(item.get("category")),
        title=str(item.get("title") or "Untitled issue").strip(),
        description=str(item.get("description") or "No description provided.").strip(),
        file=str(item.get("file") or "").strip() or None,
        line=line,
    )



def _build_suggestion(item: Dict[str, Any]) -> Suggestion:
    return Suggestion(
        title=str(item.get("title") or "Untitled suggestion").strip(),
        description=str(item.get("description") or "No description provided.").strip(),
    )



def parse_structured_result(response_text: str) -> StructuredCompareResult:
    notes: List[str] = []
    candidate = _extract_json_candidate(response_text)

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        notes.append("Could not parse valid JSON. Falling back to raw response.")
        return StructuredCompareResult(
            summary="The model returned a non-structured response.",
            score=0.0,
            raw_response=response_text.strip(),
            parsing_notes=notes,
        )

    if not isinstance(data, dict):
        notes.append("JSON response is not an object. Falling back to empty structured result.")
        return StructuredCompareResult(
            summary="The model returned an unsupported JSON structure.",
            score=0.0,
            raw_response=response_text.strip(),
            parsing_notes=notes,
        )

    issues_raw = data.get("issues") or []
    suggestions_raw = data.get("suggestions") or []
    changes_raw = data.get("changes_detected") or []

    issues = []
    for item in issues_raw:
        if isinstance(item, dict):
            issues.append(_build_issue(item))
        else:
            notes.append("Ignored invalid issue entry in response.")

    suggestions = []
    for item in suggestions_raw:
        if isinstance(item, dict):
            suggestions.append(_build_suggestion(item))
        else:
            notes.append("Ignored invalid suggestion entry in response.")

    changes = [str(item).strip() for item in changes_raw if str(item).strip()]

    return StructuredCompareResult(
        summary=str(data.get("summary") or "No summary provided.").strip(),
        score=_to_float(data.get("score")),
        issues=issues,
        suggestions=suggestions,
        changes_detected=changes,
        raw_response=response_text.strip(),
        parsing_notes=notes,
    )
