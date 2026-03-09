from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class CompareRequest:
    file_a_name: str
    file_b_name: str
    code_a: str
    code_b: str
    prompt_text: str
    response_language: str
    provider_name: str
    model_name: str
    review_mode: str = "file_compare"
    diff_text: str = ""


@dataclass
class ProviderConfig:
    provider_name: str
    model_name: str
    api_key: str = ""
    base_url: str = ""
    timeout_seconds: int = 120
    max_prompt_chars: int = 0


@dataclass
class Issue:
    severity: str
    category: str
    title: str
    description: str
    file: Optional[str] = None
    line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Suggestion:
    title: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StructuredCompareResult:
    summary: str
    score: float
    issues: List[Issue] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    changes_detected: List[str] = field(default_factory=list)
    raw_response: str = ""
    parsing_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "score": self.score,
            "issues": [issue.to_dict() for issue in self.issues],
            "suggestions": [suggestion.to_dict() for suggestion in self.suggestions],
            "changes_detected": list(self.changes_detected),
            "raw_response": self.raw_response,
            "parsing_notes": list(self.parsing_notes),
        }
