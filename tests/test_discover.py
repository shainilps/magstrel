import pytest

from magstrel.sources.company.discover import _mentions, _registrable_domain


@pytest.mark.parametrize(
    ("text", "name", "website", "expected"),
    [
        ("Alex is an AI recruiter. Alex screens candidates...", "Alex", "https://alex.com", True),
        ("Nikon microscopy, with over 130 years of Dentalex experience", "Alex", "https://alex.com", False),
        ("Join MangoDesk to build data infrastructure", "MangoDesk", None, True),
        ("We're a YC-backed startup building data infra", "MangoDesk", "https://www.mangodesk.com/", False),
        ("Read more at usedots.com", "Dots 💸", "https://usedots.com", True),
        ("Our team at Acme Robotics builds arms", "Acme Robotics", None, True),
        ("You will work with our agency partners worldwide", "Agency", "https://GetAgency.com", False),
        ("At Agency we replace compliance headcount with AI", "Agency", "https://GetAgency.com", True),
    ],
)
def test_mentions_matches_whole_words_only(text, name, website, expected):
    assert bool(_mentions(text, name, website)) is expected


@pytest.mark.parametrize(
    ("website", "expected"),
    [
        ("https://www.bunq.com", "bunq.com"),
        ("http://www.bego.ai", "bego.ai"),
        ("https://careers.example.co", "example.co"),
        (None, None),
    ],
)
def test_registrable_domain(website, expected):
    assert _registrable_domain(website) == expected
