import pytest

from magstrel.enrich.category import category
from magstrel.enrich.experience import years
from magstrel.enrich.salary import salary
from magstrel.enrich.seniority import seniority
from magstrel.enrich.skills import skills
from magstrel.enrich.visa import visa
from magstrel.enrich.work_type import work_type


@pytest.mark.parametrize(
    ("title", "location", "description", "expected"),
    [
        ("Backend Engineer", "Remote - US", "", "remote"),
        ("Software Engineer (Remote)", "New York", "", "remote"),
        ("Designer", "London (Hybrid)", "", "hybrid"),
        ("Engineer", "San Francisco, CA (On-site)", "", "in-office"),
        ("Engineer", "Berlin", "This role is fully remote within the EU.", "remote"),
        ("Engineer", "Berlin", "This is a hybrid role, 3 days in office.", "hybrid"),
        ("Engineer", "San Francisco, CA", "We remotely monitor servers.", None),
    ],
)
def test_work_type(title, location, description, expected):
    assert work_type(title, location, description) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Software Engineering Intern", "intern"),
        ("Sr. Backend Engineer", "senior"),
        ("Senior Product Manager", "senior"),
        ("Staff Software Engineer", "staff"),
        ("Principal Engineer, Payments", "principal"),
        ("Engineering Manager, Platform", "manager"),
        ("Tech Lead - Infrastructure", "lead"),
        ("Director, Staff Engineering", "director"),
        ("Head of Design", "director"),
        ("Junior Data Analyst", "junior"),
        ("New Grad Software Engineer", "junior"),
        ("Software Engineer III", "senior"),
        ("Software Engineer II", "mid"),
        ("Software Engineer I", "junior"),
        ("Software Engineer", None),
        ("Account Executive", None),
    ],
)
def test_seniority(title, expected):
    assert seniority(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Machine Learning Engineer", "ml"),
        ("Senior Security Engineer", "security"),
        ("Staff iOS Engineer", "mobile"),
        ("Full Stack Developer", "fullstack"),
        ("Frontend Engineer", "frontend"),
        ("Backend Engineer, Data Platform", "backend"),
        ("Data Engineer", "data"),
        ("Site Reliability Engineer", "devops"),
        ("Firmware Engineer", "embedded"),
        ("Product Designer", "design"),
        ("Senior Product Manager", "product"),
        ("Account Executive, Mid-Market", "sales"),
        ("Customer Success Manager", "support"),
        ("Technical Recruiter", "people"),
        ("Senior Accountant", "finance"),
        ("Software Engineer", "engineering"),
        ("Office Dog", None),
    ],
)
def test_category(title, expected):
    assert category(title) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("You have 5+ years of experience building APIs.", (5, None)),
        ("3-5 years of professional experience", (3, 5)),
        ("3 – 7 yrs in backend roles", (3, 7)),
        ("At least 4 years in a similar role", (4, None)),
        ("minimum of 2 years", (2, None)),
        ("Three years of Python experience", (3, None)),
        ("Requirements: 2+ years of Go. Bonus: 5+ years of leadership.", (2, None)),
        ("We have been in business for 25 years.", (None, None)),
        ("Founded 15 years ago in Berlin.", (None, None)),
        ("No experience requirement mentioned.", (None, None)),
    ],
)
def test_years(text, expected):
    assert years(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The base salary range is $150,000 - $200,000.", "$150K - $200K"),
        ("Compensation: $150K–$210K + equity", "$150K - $210K"),
        ("£60k to £80k depending on experience", "£60K - £80K"),
        ("€95.5k - €120k", "€95.5K - €120K"),
        ("$50 - $70 per hour", None),
        ("We raised $20M last year.", None),
    ],
)
def test_salary(text, expected):
    assert salary(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Visa sponsorship is available for this role.", "sponsors visa"),
        ("We sponsor visas and help with relocation.", "sponsors visa"),
        ("We are not able to sponsor visas at this time.", "no sponsorship"),
        ("Unable to provide visa sponsorship.", "no sponsorship"),
        ("No sponsorship available.", "no sponsorship"),
        ("Great team, great snacks.", None),
    ],
)
def test_visa(text, expected):
    assert visa(text) == expected


@pytest.mark.parametrize(
    ("title", "text", "expected"),
    [
        ("Software Engineer (Go/Rust)", "", ["go", "rust"]),
        ("Backend Engineer", "Experience with Go, Python and PostgreSQL.", ["python", "go", "postgresql"]),
        ("Engineer", "Strong JavaScript and React skills; Node.js a plus.", ["javascript", "react", "node.js"]),
        ("Engineer", "We use Java on the backend.", ["java"]),
        ("Engineer", "C++ and C# experience; k8s on AWS.", ["c++", "c#", "aws", "kubernetes"]),
        ("Engineer", "Go to market and react quickly to incidents.", []),
        ("Engineer", "a swift turnaround and a spark of creativity", []),
        ("iOS Engineer", "Swift and SwiftUI", ["swift"]),
    ],
)
def test_skills(title, text, expected):
    assert skills(title, text) == expected
