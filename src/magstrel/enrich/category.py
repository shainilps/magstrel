import re

from magstrel.models import Category

_RULES: list[tuple[Category, str]] = [
    ("ml", r"machine learning|\bml\b|\bai\b|deep learning|\bnlp\b|computer vision|research (scientist|engineer)|applied scientist|\bllms?\b"),
    ("security", r"security|\bsecops\b|appsec|infosec|\bdetection\b|\bthreat"),
    ("mobile", r"\bios\b|android|mobile"),
    ("fullstack", r"full[- ]?stack"),
    ("frontend", r"front[- ]?end|\bui engineer|web developer"),
    ("backend", r"back[- ]?end|server[- ]side"),
    ("data", r"\bdata\b|analytics|\banalyst\b|business intelligence"),
    ("devops", r"devops|\bsre\b|site reliability|infrastructure|\bplatform\b|\bcloud\b|network engineer|systems engineer"),
    ("embedded", r"embedded|firmware|hardware|electrical|mechanical|robotics|\bfpga\b|\basic\b"),
    ("qa", r"\bqa\b|quality assurance|\btest(ing)? engineer|\bsdet\b"),
    ("design", r"design(er)?\b|\bux\b|\bui\b"),
    ("product", r"product manager|product owner|product management|\bproduct lead"),
    ("sales", r"account executive|\bsales\b|\bsdr\b|\bbdr\b|business development|account manager|solutions engineer|partnerships"),
    ("marketing", r"marketing|\bcontent\b|\bbrand\b|\bseo\b|communications"),
    ("support", r"customer success|\bsupport\b|customer experience|implementation|onboarding"),
    ("people", r"recruit|talent|\bpeople\b|\bhr\b|human resources"),
    ("finance", r"finance|accounting|accountant|controller|\btax\b|treasury|payroll"),
    ("legal", r"legal|counsel|attorney|lawyer|compliance|paralegal"),
    ("operations", r"operations|\bops\b|program manager|project manager|chief of staff|workplace|supply chain|logistics"),
    ("engineering", r"engineer|developer|programmer|software"),
]
_COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in _RULES]


def category(title: str) -> Category | None:
    for name, pattern in _COMPILED:
        if pattern.search(title):
            return name
    return None
