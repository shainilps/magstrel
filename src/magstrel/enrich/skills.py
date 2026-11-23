import re

# (skill, pattern, case_sensitive): case-sensitive ones are everyday words in lowercase (go, react)
_SKILLS: list[tuple[str, str, bool]] = [
    ("python", r"python", False),
    ("java", r"java", False),
    ("javascript", r"javascript|js", False),
    ("typescript", r"typescript", False),
    ("go", r"golang", False),
    ("go", r"(?<![\w-])Go(?=\s*[,/)])|(?<=[/(])\s?Go\b|(?<=, )Go\b|\bGo (?:and|or) (?=[A-Z])|\b(?:in|with|using|like) Go(?=[\s.,)])", True),
    ("rust", r"rust", False),
    ("c++", r"c\+\+", False),
    ("c#", r"c#", False),
    ("ruby", r"ruby", False),
    ("rails", r"ruby on rails|rails", False),
    ("php", r"php", False),
    ("scala", r"scala", False),
    ("kotlin", r"kotlin", False),
    ("swift", r"Swift(?:UI)?", True),
    ("objective-c", r"objective-c", False),
    ("elixir", r"elixir", False),
    ("haskell", r"haskell", False),
    ("clojure", r"clojure", False),
    ("sql", r"sql", False),
    ("react", r"React(?:\.?js)?(?! Native)", True),
    ("react", r"reactjs|react\.js", False),
    ("react native", r"react native", False),
    ("vue", r"vue(?:\.js)?", False),
    ("angular", r"angular(?:js)?", False),
    ("next.js", r"next\.?js", False),
    ("node.js", r"node\.?js", False),
    ("django", r"django", False),
    ("flask", r"flask", False),
    ("fastapi", r"fastapi", False),
    ("spring", r"spring boot|spring framework", False),
    (".net", r"\.net|asp\.net", False),
    ("graphql", r"graphql", False),
    ("grpc", r"grpc", False),
    ("kafka", r"kafka", False),
    ("spark", r"Spark|pyspark", True),
    ("airflow", r"airflow", False),
    ("dbt", r"dbt", False),
    ("snowflake", r"Snowflake", True),
    ("bigquery", r"bigquery", False),
    ("databricks", r"databricks", False),
    ("postgresql", r"postgres(?:ql)?", False),
    ("mysql", r"mysql", False),
    ("mongodb", r"mongo(?:db)?", False),
    ("redis", r"redis", False),
    ("elasticsearch", r"elastic ?search", False),
    ("dynamodb", r"dynamodb", False),
    ("cassandra", r"cassandra", False),
    ("aws", r"aws|amazon web services", False),
    ("gcp", r"gcp|google cloud", False),
    ("azure", r"azure", False),
    ("kubernetes", r"kubernetes|k8s", False),
    ("docker", r"docker", False),
    ("terraform", r"terraform", False),
    ("ansible", r"ansible", False),
    ("linux", r"linux", False),
    ("pytorch", r"pytorch", False),
    ("tensorflow", r"tensorflow", False),
    ("jax", r"JAX", True),
    ("pandas", r"pandas", False),
    ("numpy", r"numpy", False),
    ("scikit-learn", r"scikit-learn|sklearn", False),
    ("llm", r"llms?", False),
    ("langchain", r"langchain", False),
    ("cuda", r"cuda", False),
    ("figma", r"figma", False),
    ("tableau", r"tableau", False),
    ("looker", r"looker", False),
    ("salesforce", r"Salesforce", True),
]

_EDGE_BEFORE, _EDGE_AFTER = r"(?<![A-Za-z0-9_+#])", r"(?![A-Za-z0-9_+#])"
_COMPILED = [
    (name, re.compile(_EDGE_BEFORE + f"(?:{pattern})" + _EDGE_AFTER, 0 if exact else re.I))
    for name, pattern, exact in _SKILLS
]


def skills(title: str, description: str) -> list[str]:
    text = f"{title}\n{description}"
    found: list[str] = []
    for name, pattern in _COMPILED:
        if name not in found and pattern.search(text):
            found.append(name)
    return found
