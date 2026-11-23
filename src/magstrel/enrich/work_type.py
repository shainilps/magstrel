import re

from magstrel.models import WorkType

_REMOTE_IN_TEXT = re.compile(
    r"\b(fully|100%) remote\b|\bthis (role|position) is (fully )?remote\b|\bremote[- ]first\b"
)
_HYBRID_IN_TEXT = re.compile(r"\bthis is a hybrid (role|position)\b|\bhybrid (role|position|schedule)\b")


def work_type(title: str, location: str, description: str = "") -> WorkType | None:
    text = f"{title} {location}".lower()
    if "hybrid" in text:
        return "hybrid"
    if re.search(r"\bremote\b", text):
        return "remote"
    if re.search(r"\b(on-?site|in[- ]office|in[- ]person)\b", text):
        return "in-office"
    description = description.lower()
    if _HYBRID_IN_TEXT.search(description):
        return "hybrid"
    if _REMOTE_IN_TEXT.search(description):
        return "remote"
    return None
