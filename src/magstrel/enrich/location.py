import re
import unicodedata

# country code -> names a location may use for it
COUNTRIES: dict[str, list[str]] = {
    "us": ["united states", "united states of america", "usa"],
    "ca": ["canada"],
    "mx": ["mexico"],
    "br": ["brazil", "brasil"],
    "ar": ["argentina"],
    "co": ["colombia"],
    "cl": ["chile"],
    "pe": ["peru"],
    "uy": ["uruguay"],
    "cr": ["costa rica"],
    "gb": ["united kingdom", "england", "scotland", "wales", "northern ireland", "great britain"],
    "ie": ["ireland"],
    "de": ["germany", "deutschland"],
    "fr": ["france"],
    "nl": ["netherlands", "the netherlands"],
    "be": ["belgium"],
    "es": ["spain"],
    "pt": ["portugal"],
    "it": ["italy"],
    "ch": ["switzerland"],
    "at": ["austria"],
    "se": ["sweden"],
    "no": ["norway"],
    "dk": ["denmark"],
    "fi": ["finland"],
    "pl": ["poland"],
    "cz": ["czech republic", "czechia"],
    "gr": ["greece"],
    "ro": ["romania"],
    "hu": ["hungary"],
    "ua": ["ukraine"],
    "rs": ["serbia"],
    "hr": ["croatia"],
    "bg": ["bulgaria"],
    "ee": ["estonia"],
    "lt": ["lithuania"],
    "lv": ["latvia"],
    "tr": ["turkey", "türkiye", "turkiye"],
    "il": ["israel"],
    "ae": ["united arab emirates", "uae"],
    "sa": ["saudi arabia"],
    "eg": ["egypt"],
    "za": ["south africa"],
    "ng": ["nigeria"],
    "ke": ["kenya"],
    "in": ["india"],
    "pk": ["pakistan"],
    "bd": ["bangladesh"],
    "lk": ["sri lanka"],
    "sg": ["singapore"],
    "my": ["malaysia"],
    "id": ["indonesia"],
    "ph": ["philippines"],
    "th": ["thailand"],
    "vn": ["vietnam", "viet nam"],
    "jp": ["japan"],
    "kr": ["south korea", "korea"],
    "cn": ["china"],
    "hk": ["hong kong"],
    "tw": ["taiwan"],
    "au": ["australia"],
    "nz": ["new zealand"],
}

# cities and states only help tag a job; a search for "london" should still mean London, not all of the UK
_PLACES: dict[str, list[str]] = {
    "us": [
        "san francisco", "bay area", "silicon valley", "new york", "nyc", "brooklyn", "seattle",
        "bellevue", "austin", "boston", "chicago", "los angeles", "palo alto", "mountain view",
        "menlo park", "sunnyvale", "cupertino", "san jose", "san mateo", "redwood city",
        "foster city", "oakland", "berkeley", "denver", "atlanta", "miami", "washington dc",
        "washington, d.c.", "washington d.c.", "pittsburgh", "philadelphia", "salt lake city", "dallas", "houston",
        "san diego", "el segundo", "detroit", "alabama", "alaska", "arizona", "arkansas",
        "california", "colorado", "connecticut", "delaware", "florida", "georgia", "hawaii",
        "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
        "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
        "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico",
        "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
        "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah",
        "vermont", "virginia", "west virginia", "wisconsin", "wyoming",
    ],
    "in": [
        "bengaluru", "bangalore", "mumbai", "delhi", "new delhi", "gurgaon", "gurugram", "noida",
        "hyderabad", "pune", "chennai", "kolkata", "ahmedabad", "kochi", "jaipur",
    ],
    "gb": ["london", "manchester", "edinburgh", "bristol"],
    "ca": ["toronto", "vancouver", "montreal", "ottawa", "waterloo", "calgary", "ontario", "british columbia", "quebec"],
    "de": ["berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne"],
    "fr": ["paris", "lyon"],
    "nl": ["amsterdam", "rotterdam"],
    "ie": ["dublin"],
    "es": ["madrid", "barcelona"],
    "pt": ["lisbon", "porto"],
    "it": ["milan", "rome"],
    "ch": ["zurich", "zürich", "geneva", "lausanne", "basel"],
    "se": ["stockholm"],
    "no": ["oslo"],
    "dk": ["copenhagen"],
    "fi": ["helsinki"],
    "pl": ["warsaw", "krakow", "kraków", "wroclaw", "wrocław"],
    "cz": ["prague", "brno"],
    "at": ["vienna"],
    "gr": ["athens"],
    "ua": ["kyiv", "kiev"],
    "tr": ["istanbul"],
    "il": ["tel aviv"],
    "ae": ["dubai", "abu dhabi"],
    "jp": ["tokyo", "osaka"],
    "kr": ["seoul"],
    "au": ["sydney", "melbourne", "brisbane"],
    "ph": ["manila"],
    "br": ["são paulo", "sao paulo", "rio de janeiro", "belo horizonte", "curitiba"],
    "mx": ["mexico city", "guadalajara"],
    "ar": ["buenos aires"],
    "co": ["bogotá", "bogota", "medellín", "medellin"],
}

_EUROPE = {
    "gb", "ie", "de", "fr", "nl", "be", "es", "pt", "it", "ch", "at", "se", "no", "dk", "fi",
    "pl", "cz", "gr", "ro", "hu", "ua", "rs", "hr", "bg", "ee", "lt", "lv",
}
_LATAM = {"mx", "br", "ar", "co", "cl", "pe", "uy", "cr"}
# a job open to a region is open to every country in it
REGIONS: dict[str, set[str]] = {
    "europe": _EUROPE,
    "emea": _EUROPE | {"tr", "il", "ae", "sa", "eg", "za", "ng", "ke"},
    "apac": {
        "in", "pk", "bd", "lk", "sg", "my", "id", "ph", "th", "vn", "jp", "kr", "cn", "hk", "tw",
        "au", "nz",
    },
    "north-america": {"us", "ca", "mx"},
    "latam": _LATAM,
    "americas": {"us", "ca"} | _LATAM,
}
ANYWHERE = "anywhere"

_REGION_NAMES: dict[str, list[str]] = {
    ANYWHERE: [
        "worldwide", "anywhere", "global", "world", "international", "most countries",
        "all countries",
    ],
    "europe": ["europe", "european union", "eastern europe", "western europe"],
    "emea": ["emea"],
    "apac": ["apac", "asia", "asia pacific", "asia-pacific", "south east asia", "southeast asia"],
    "north-america": ["north america", "namer"],
    "latam": ["latam", "latin america", "south america", "central america", "central & south america"],
    "americas": ["americas"],
}

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
}
_CODE_ALIASES = {"USA": "us", "UK": "gb", "UAE": "ae", "EU": "europe"}
# safe to spot inside free text, unlike "IN" or "DE" which are also everyday words and states
_FREE_TEXT_CODES = re.compile(r"(?<![A-Za-z])(US|USA|UK|EU)(?![A-Za-z])")

_NAMES = {name: code for code, names in COUNTRIES.items() for name in names}
_NAMES |= {name: code for code, names in _PLACES.items() for name in names}
_NAMES |= {name: region for region, names in _REGION_NAMES.items() for name in names}


def _fold(text: str) -> str:
    # "İstanbul".lower() is "i̇stanbul" with a combining dot: drop accents so it still finds "istanbul"
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


_FOLDED = {_fold(name): code for name, code in _NAMES.items()}
_NAME_PATTERN = re.compile(
    r"(?<![\w])(" + "|".join(re.escape(n) for n in sorted(_NAMES, key=len, reverse=True)) + r")(?![\w])",
    re.I,
)
_REMOTE = re.compile(r"\b(remote|distributed)\b", re.I)
_REMOTE_DASH_STATE = re.compile(r"\bremote\s*[-–]\s*([A-Z]{2})\b", re.I)
_FILLER = re.compile(r"\b(remote|hybrid|on-?site|only|based|or)\b|[-–:]", re.I)
_TOP_SEPARATORS = re.compile(r";|\||•| / | or ", re.I)


def countries(location: str) -> tuple[list[str], list[str]]:
    # (every country or region the location names, where a remote hire may live)
    # an empty second list means remote from somewhere unspecified: the text is just "Remote"
    location = re.sub(r"\bU\.S\.(?:A\.)?", "US", location)
    everywhere: set[str] = set()
    remote: set[str] = set()
    for segment in _split_top_level(location):
        found = _segment_codes(segment)
        everywhere |= found
        if _REMOTE.search(segment):
            remote |= found
    if not remote:
        # "India" on a job the board marks remote, or "Remote / USA": remote within the places named
        remote = everywhere
    return sorted(everywhere), sorted(remote)


def country_code(text: str) -> str | None:
    # a country or region name or code typed into a search, e.g. "India", "in", "apac"
    cleaned = text.strip().lower()
    if cleaned in COUNTRIES or cleaned in REGIONS or cleaned == ANYWHERE:
        return cleaned
    alias = _CODE_ALIASES.get(cleaned.upper())
    if alias:
        return alias
    for code, names in COUNTRIES.items():
        if cleaned in names:
            return code
    for region, names in _REGION_NAMES.items():
        if cleaned in names:
            return region
    return None


def open_to(code: str) -> list[str]:
    # the values a job's remote_countries may hold that let someone from `code` apply
    regions = [region for region, members in REGIONS.items() if code in members]
    return sorted({code, ANYWHERE, *regions})


def _split_top_level(text: str) -> list[str]:
    # split on separators outside parentheses: "Remote (DL, IN; Delhi, IN)" stays one segment
    segments, depth, start = [], 0, 0
    for i, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif depth == 0 and (match := _TOP_SEPARATORS.match(text, i)) and i >= start:
            segments.append(text[start:i])
            start = match.end()
    segments.append(text[start:])
    return [s.strip() for s in segments if s.strip()]


def _segment_codes(segment: str) -> set[str]:
    found: set[str] = set()
    if (match := _REMOTE_DASH_STATE.search(segment)) and match[1].upper() in _US_STATES:
        found.add("us")  # greenhouse style "Remote - CA" is California
        segment = segment[: match.start(1)] + segment[match.end(1) :]
    # inside parentheses entries are split by ";": "Remote (CA, US; GA, US)"
    outside = re.sub(r"\([^)]*\)", " ", segment)
    entries = [outside] + [e for group in re.findall(r"\(([^)]*)\)", segment) for e in group.split(";")]
    for entry in entries:
        found |= _entry_codes(entry)
    return found


def _entry_codes(entry: str) -> set[str]:
    parts = [p.strip() for p in entry.split(",") if p.strip()]
    found: set[str] = set()
    for index, part in enumerate(parts):
        code = _FILLER.sub(" ", part).strip()
        if re.fullmatch(r"[A-Z]{2,3}", code) and (from_code := _bare_code(code, index, parts)):
            found |= from_code
            continue
        found |= {code for m in _NAME_PATTERN.findall(part) if (code := _FOLDED.get(_fold(m)))}
        found |= {_CODE_ALIASES.get(m, "us") for m in _FREE_TEXT_CODES.findall(part)}
    return found


def _bare_code(code: str, index: int, parts: list[str]) -> set[str]:
    # "City, ST, CC": the last part is the country, the ones before it are states.
    # "City, ST" with a US state is the US: "Indianapolis, IN" is not India
    is_last = index == len(parts) - 1
    last = _FILLER.sub(" ", parts[-1]).strip()
    if code in _US_STATES:
        if not is_last and last in ("US", "USA"):
            return {"us"}
        if is_last and len(parts) == 2 and not re.fullmatch(r"[A-Z]{2,3}", _FILLER.sub(" ", parts[0]).strip()):
            if not _REMOTE.search(parts[0]):
                return {"us"}
    if not is_last and len(parts) >= 3:
        return set()  # a state or province code we don't track, e.g. "KA" in "Bengaluru, KA, IN"
    if code in _CODE_ALIASES:
        return {_CODE_ALIASES[code]}
    lowered = code.lower()
    return {lowered} if lowered in COUNTRIES else set()
