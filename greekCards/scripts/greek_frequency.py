#!/usr/bin/env python3
"""Local Greek lemma-frequency index and deck frequency analysis.

Sources (downloaded into data/frequency/sources/, see README):
- SUBTLEX-GR full: word-form counts from Greek subtitles (spoken-like language).
- GreekLex 2: lemma frequencies per million from the Hellenic National Corpus (written).
- kaikki.org Greek (English Wiktionary): inflection tables used to fold word forms into lemmas.

Subcommands:
- download: fetch the three sources into data/frequency/sources/ (about 300 MB).
- build: parse sources into data/frequency/greek_frequency.sqlite3.
- lookup: print frequency information for one or more Greek words or card fronts.
- report: analyse a deck from data/greek_cards.sqlite3 and write a Markdown report.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import re
import sqlite3
import statistics
import sys
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


ROOT = Path(__file__).resolve().parents[1]
FREQUENCY_DIR = ROOT / "data" / "frequency"
SOURCES_DIR = FREQUENCY_DIR / "sources"
DEFAULT_INDEX_PATH = FREQUENCY_DIR / "greek_frequency.sqlite3"
DEFAULT_CARDS_DB_PATH = ROOT / "data" / "greek_cards.sqlite3"
DEFAULT_REPORT_DIR = FREQUENCY_DIR / "report"
DEFAULT_SUBTLEX_PATH = SOURCES_DIR / "subtlex-gr" / "SUBTLEX-GR_full.txt"
DEFAULT_GREEKLEX_PATH = (
    SOURCES_DIR / "greeklex2" / "unpacked" / "GreekLex2.1" / "encodings" / "UTF-8" / "GreekLex2.txt"
)
DEFAULT_KAIKKI_PATH = SOURCES_DIR / "kaikki" / "kaikki.org-dictionary-Greek.jsonl"
DEFAULT_DECK = "Πες το ελληνικά"

SOURCE_URLS = {
    DEFAULT_SUBTLEX_PATH: "https://www.bcbl.eu/sites/default/files/files/SUBTLEX-GR_full.txt",
    SOURCES_DIR / "greeklex2" / "GreekLex2.1.zip": "https://psychology.nottingham.ac.uk/greeklex/GreekLex2.1.zip",
    DEFAULT_KAIKKI_PATH: "https://kaikki.org/dictionary/Greek/kaikki.org-dictionary-Greek.jsonl",
}

GREEK_CHARS = "\u0370-\u03ff\u1f00-\u1fff"
GREEK_TOKEN_PATTERN = re.compile(rf"ό,τι|[{GREEK_CHARS}]+")
GREEK_ONLY_PATTERN = re.compile(rf"^[{GREEK_CHARS}]+$")
GLOSS_TARGET_PATTERN = re.compile(rf"\bof ([{GREEK_CHARS}]+)")

EXCLUDED_FORM_TAGS = frozenset(
    {
        "romanization",
        "table-tags",
        "inflection-template",
        "class",
        "error-unrecognized-form",
        "comparative",
        "superlative",
        "archaic",
    }
)
DERIVATION_TAGS = frozenset({"emphatic", "intensive", "diminutive", "augmentative"})
REFERENCE_POS = frozenset(
    {"noun", "verb", "adj", "adv", "pron", "prep", "conj", "intj", "particle", "num", "det", "article"}
)
CONTENT_POS = frozenset({"noun", "verb", "adj", "adv"})
NOUN_POS = frozenset({"noun", "name"})
ARTICLES = frozenset({"ο", "η", "το", "οι", "τα", "τον", "την", "τη", "του", "της", "των", "τους", "τις"})
PLURAL_ARTICLES = frozenset({"οι", "τα", "των", "τους", "τις"})
LEADING_PARTICLES = frozenset({"θα", "να", "ας"})
PARENTHESIZED_PRONOUNS = frozenset(
    {"εγώ", "εσύ", "αυτός", "αυτή", "αυτό", "εμείς", "εσείς", "αυτοί", "αυτές", "αυτά"}
)
LATIN_LOOKALIKE_TOKENS = {"o": "ο"}

GREEKLEX_ZERO_PM = 0.03
CLUSTER_OVERLAP = 0.6
PROPER_NAME_PRIOR_PM = 0.1
ZIPF_BANDS = (
    (5.0, "очень частые", "≥ 100 на млн"),
    (4.0, "частые", "10–100 на млн"),
    (3.0, "средние", "1–10 на млн"),
    (2.0, "редкие", "0.1–1 на млн"),
    (-math.inf, "очень редкие", "< 0.1 на млн"),
)
RANK_BANDS = (500, 1000, 2000, 3000, 5000, 10000, 20000)
COVERAGE_BANDS = (500, 1000, 2000, 3000, 5000, 10000)
POS_LABELS = {
    "noun": "существительное",
    "name": "имя собственное",
    "adj": "прилагательное",
    "verb": "глагол",
    "adv": "наречие",
    "num": "числительное",
    "pron": "местоимение",
}
POS_PRIORITY_WITHOUT_ARTICLE = ("verb", "adj", "adv", "noun", "name")
POS_PRIORITY_WITH_ARTICLE = ("noun", "name", "adj", "verb", "adv")


def normalize_word(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def zipf_from_count(count: float, corpus_millions: float, types_millions: float) -> float:
    """Van Heuven et al. (2014) Zipf: log10 frequency per billion with Laplace smoothing."""
    return math.log10((count + 1.0) / (corpus_millions + types_millions)) + 3.0


def zipf_from_per_million(per_million: float) -> float:
    return math.log10(max(per_million, GREEKLEX_ZERO_PM)) + 3.0


# --------------------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------------------


def read_subtlex(path: Path) -> tuple[dict[str, int], dict[str, int], int, int]:
    counts: dict[str, int] = defaultdict(int)
    contexts: dict[str, int] = defaultdict(int)
    total_tokens = 0
    total_types = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            columns = line.rstrip("\n").split("\t")
            if len(columns) < 4 or not columns[0].isdigit():
                continue
            word = normalize_word(columns[1].strip('"'))
            if not columns[2].isdigit() or not columns[3].isdigit():
                continue  # a handful of corrupted rows in the original file
            count = int(columns[2])
            total_tokens += count
            total_types += 1
            counts[word] += count
            contexts[word] = max(contexts[word], int(columns[3]))
    return dict(counts), dict(contexts), total_tokens, total_types


def read_greeklex(path: Path) -> dict[str, tuple[float, float, str]]:
    entries: dict[str, tuple[float, float, str]] = {}
    with path.open(encoding="utf-8-sig") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        word_index = header.index("Word")
        lemma_index = header.index("LemmaFreq")
        form_index = header.index("WordFreq")
        pos_index = header.index("Pos")
        for line in handle:
            columns = line.rstrip("\n").split("\t")
            if len(columns) <= pos_index:
                continue
            word = normalize_word(columns[word_index])
            if not word:
                continue
            lemma_pm = float(columns[lemma_index] or 0)
            previous = entries.get(word)
            if previous is None or lemma_pm > previous[0]:
                entries[word] = (lemma_pm, float(columns[form_index] or 0), columns[pos_index].strip())
    return entries


def clean_table_form(raw: str) -> list[str]:
    """Turn a Wiktionary table cell into single Greek tokens (drops θα/να/έχω auxiliaries)."""
    if re.search(r"[A-Za-z]", raw):
        return []  # notes such as "Derivations: … e.g. ο περισσότερος", not forms
    text = re.sub(r"\([^)]*\)", " ", unicodedata.normalize("NFC", raw))
    # Participle cells look like "γραμμένος -η -ο": the "-η -ο" endings are not words.
    text = re.sub(rf"[-‐‑–]\s*[{GREEK_CHARS}]+", " ", text)
    results = []
    for variant in re.split(r"[/,]", text):
        tokens = GREEK_TOKEN_PATTERN.findall(variant)
        if tokens:
            results.append(normalize_word(tokens[-1]))
    return results


FUNCTION_FORMS = frozenset(ARTICLES | LEADING_PARTICLES | {"και", "δεν", "μη", "μην"})
FUNCTION_POS = frozenset({"article", "pron", "particle", "det", "prep", "conj"})


def is_fragment(form: str, lemma_word: str, pos: str) -> bool:
    """Cell leftovers such as "ο" or "η" from "καλυμμένος, -η, -ο", "μ" from "Α.Φ.Μ." or a stray "να"."""
    if form == lemma_word:
        return False
    if pos in FUNCTION_POS:
        return False
    return len(form) < 3 or form in FUNCTION_FORMS or (len(lemma_word) >= 6 and len(form) * 2 < len(lemma_word))


@dataclass
class LemmaEntry:
    lemma_id: int
    word: str
    display: str
    pos: str
    has_table: bool
    gloss: str
    forms: dict[str, set[str]] = field(default_factory=dict)
    alt_targets: set[str] = field(default_factory=set)


def is_form_of_entry(entry: dict) -> bool:
    senses = entry.get("senses") or []
    return bool(senses) and all(sense.get("form_of") for sense in senses)


def read_kaikki(path: Path) -> list[LemmaEntry]:
    lemmas: list[LemmaEntry] = []
    form_claims: list[tuple[str, str, str, set[str]]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            entry = json.loads(line)
            display = unicodedata.normalize("NFC", entry.get("word", "")).strip()
            word = normalize_word(display)
            pos = entry.get("pos", "")
            if not word or re.search(r"\s", word):
                continue  # multi-word entries cannot be counted with unigram frequencies
            senses = entry.get("senses") or []
            if is_form_of_entry(entry):
                for sense in senses:
                    tags = set(sense.get("tags") or [])
                    if tags & (EXCLUDED_FORM_TAGS | DERIVATION_TAGS):
                        continue  # πανέμορφος is a derived word, not an inflected form of όμορφος
                    for target in sense.get("form_of") or []:
                        target_word = normalize_word(target.get("word", ""))
                        if target_word:
                            form_claims.append((word, pos, target_word, tags))
                continue
            raw_forms = entry.get("forms") or []
            has_table = any("inflection-template" in (form.get("tags") or []) for form in raw_forms)
            gloss = next((g for sense in senses for g in sense.get("glosses") or []), "")
            lemma = LemmaEntry(len(lemmas), word, display, pos, has_table, gloss[:120])
            if GREEK_ONLY_PATTERN.match(word) or word == "ό,τι":
                lemma.forms[word] = {"lemma"}
            for form in raw_forms:
                tags = set(form.get("tags") or [])
                if tags & EXCLUDED_FORM_TAGS:
                    continue
                for cleaned in clean_table_form(form.get("form", "")):
                    if is_fragment(cleaned, word, pos):
                        continue
                    if not has_table and tags & {"alternative", "canonical"}:
                        lemma.alt_targets.add(cleaned)
                    lemma.forms.setdefault(cleaned, set()).update(tags)
            if not has_table:
                for sense in senses:
                    for alt in sense.get("alt_of") or []:
                        lemma.alt_targets.add(normalize_word(alt.get("word", "")))
                    for gloss_text in sense.get("glosses") or []:
                        lemma.alt_targets.update(normalize_word(m) for m in GLOSS_TARGET_PATTERN.findall(gloss_text))
            lemmas.append(lemma)

    lemmas_by_word: dict[str, list[LemmaEntry]] = defaultdict(list)
    for lemma in lemmas:
        lemmas_by_word[lemma.word].append(lemma)
    for form_word, pos, target_word, tags in form_claims:
        targets = lemmas_by_word.get(target_word, [])
        same_pos = [lemma for lemma in targets if lemma.pos == pos]
        for lemma in same_pos or targets:
            lemma.forms.setdefault(form_word, set()).update(tags - {"form-of"})
    return lemmas


@dataclass
class LemmaPrior:
    per_million: float | None
    source: str
    unambiguous_count: int


def cluster_lemmas(lemmas: list[LemmaEntry], claimants: dict[str, list[int]]) -> list[int]:
    """Group duplicate Wiktionary entries of one lexeme (τρώω/τρώγω): same POS, mostly shared forms."""
    parent = list(range(len(lemmas)))

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    shared: Counter[tuple[int, int]] = Counter()
    for ids in claimants.values():
        if 1 < len(ids) <= 40:
            for position, first in enumerate(ids):
                for second in ids[position + 1 :]:
                    if lemmas[first].pos == lemmas[second].pos:
                        shared[(min(first, second), max(first, second))] += 1
    for (first, second), common in shared.items():
        smaller = min(len(lemmas[first].forms), len(lemmas[second].forms))
        if smaller >= 3 and common / smaller >= CLUSTER_OVERLAP:
            parent[find(first)] = find(second)
    return [find(lemma.lemma_id) for lemma in lemmas]


def compute_priors(
    lemmas: list[LemmaEntry],
    counts: dict[str, int],
    greeklex: dict[str, tuple[float, float, str]],
    claimants: dict[str, list[int]],
    clusters: list[int],
) -> dict[int, LemmaPrior]:
    """Cluster frequency independent of homographs, taken from GreekLex (lemmatised in context)."""
    members: dict[int, list[LemmaEntry]] = defaultdict(list)
    for lemma in lemmas:
        members[clusters[lemma.lemma_id]].append(lemma)
    priors: dict[int, LemmaPrior] = {}
    for cluster_id, group in members.items():
        forms = {form for lemma in group for form in lemma.forms}
        unambiguous = sum(
            counts.get(form, 0) for form in forms if len({clusters[i] for i in claimants[form]}) == 1
        )
        greeklex_values = [greeklex[lemma.word][0] for lemma in group if lemma.word in greeklex]
        if all(lemma.display[:1].isupper() for lemma in group):
            # Proper names (Ζωή, Πόλη, the book Αριθμοί) must not take a large part of a common word's form;
            # GreekLex is keyed by lowercase words, so its value would belong to the common noun.
            priors[cluster_id] = LemmaPrior(PROPER_NAME_PRIOR_PM, "proper", unambiguous)
        elif greeklex_values:
            priors[cluster_id] = LemmaPrior(max(max(greeklex_values), GREEKLEX_ZERO_PM), "greeklex", unambiguous)
        else:
            priors[cluster_id] = LemmaPrior(None, "none", unambiguous)
    return priors


def compute_shares(
    lemmas: list[LemmaEntry],
    priors: dict[int, LemmaPrior],
    claimants: dict[str, list[int]],
    clusters: list[int],
) -> dict[tuple[int, str], float]:
    """Split a homograph form between lemma clusters.

    Clusters with a GreekLex frequency share by that frequency spread evenly over the cluster's forms,
    so a one-form adverb keeps more of its form than an adjective with ~20 forms. A cluster without an
    independent frequency gets an equal 1/k part: there is no evidence to do better.
    """
    cluster_forms: Counter[int] = Counter()
    for lemma in lemmas:
        cluster_forms[clusters[lemma.lemma_id]] += len(lemma.forms)
    shares: dict[tuple[int, str], float] = {}
    for form, ids in claimants.items():
        form_clusters = sorted({clusters[lemma_id] for lemma_id in ids})
        if len(form_clusters) == 1:
            cluster_share = {form_clusters[0]: 1.0}
        else:
            informed = [c for c in form_clusters if priors[c].per_million is not None]
            uninformed = [c for c in form_clusters if priors[c].per_million is None]
            cluster_share = {c: 1.0 / len(form_clusters) for c in uninformed}
            remaining = 1.0 - len(uninformed) / len(form_clusters)
            weights = {c: priors[c].per_million / max(1, cluster_forms[c]) for c in informed}
            total = sum(weights.values())
            for c, weight in weights.items():
                cluster_share[c] = remaining * weight / total
        for lemma_id in ids:
            shares[(lemma_id, form)] = cluster_share[clusters[lemma_id]]
    return shares


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    plain = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    return unicodedata.normalize("NFC", plain).replace("ς", "σ")


# Accent-free endings used only for words that Wiktionary does not know.
GUESSED_NOUN_PARADIGMS = (
    ("ματα", ("μα", "ματοσ", "ματα", "ματων")),
    ("μα", ("μα", "ματοσ", "ματα", "ματων")),
    ("ση", ("ση", "σησ", "σεισ", "σεων")),
    ("ξη", ("ξη", "ξησ", "ξεισ", "ξεων")),
    ("ψη", ("ψη", "ψησ", "ψεισ", "ψεων")),
    ("οσ", ("οσ", "ου", "ο", "ε", "οι", "ων", "ουσ")),
    ("ασ", ("ασ", "α", "εσ", "ων", "αδεσ", "αδων")),
    ("ησ", ("ησ", "η", "εσ", "ων", "ηδεσ", "ηδων")),
    ("εσ", ("εσ", "ων")),
    ("η", ("η", "ησ", "εσ", "ων")),
    ("α", ("α", "ασ", "εσ", "ων")),
    ("ο", ("ο", "ου", "α", "ων")),
    ("ι", ("ι", "ιου", "ια", "ιων")),
)
_PRESENT = ("ω", "εισ", "ει", "ουμε", "ετε", "ουν", "ουνε", "α", "εσ", "ε", "αμε", "ατε", "αν", "ανε")
GUESSED_VERB_PARADIGMS = (
    ("ωνω", tuple("ων" + e for e in _PRESENT) + tuple("ωσ" + e for e in _PRESENT)),
    ("ιζω", tuple("ιζ" + e for e in _PRESENT) + tuple("ισ" + e for e in _PRESENT) + tuple("ιξ" + e for e in _PRESENT)),
    ("αζω", tuple("αζ" + e for e in _PRESENT) + tuple("ασ" + e for e in _PRESENT) + tuple("αξ" + e for e in _PRESENT)),
    ("ευω", tuple("ευ" + e for e in _PRESENT) + tuple("ευσ" + e for e in _PRESENT) + tuple("εψ" + e for e in _PRESENT)),
    ("ωνει", tuple("ων" + e for e in _PRESENT) + tuple("ωσ" + e for e in _PRESENT)),
    ("αζει", tuple("αζ" + e for e in _PRESENT) + tuple("ασ" + e for e in _PRESENT) + tuple("αξ" + e for e in _PRESENT)),
    ("ιζει", tuple("ιζ" + e for e in _PRESENT) + tuple("ισ" + e for e in _PRESENT) + tuple("ιξ" + e for e in _PRESENT)),
    ("ευει", tuple("ευ" + e for e in _PRESENT) + tuple("ευσ" + e for e in _PRESENT) + tuple("εψ" + e for e in _PRESENT)),
    ("αω", ("αω", "ασ", "αει", "α", "αμε", "ατε", "ανε", "ουν", "ουσα", "ουσεσ", "ουσε", "ουσαμε", "ουσατε",
            "ουσαν", "ησα", "ησεσ", "ησε", "ησαμε", "ησατε", "ησαν", "ησω", "ησεισ", "ησει", "ησουμε", "ησετε",
            "ησουν", "ουμε")),
    ("ομαι", ("ομαι", "εσαι", "εται", "ομαστε", "εστε", "ονται", "ομουν", "οταν", "ονταν")),
    ("εται", ("εται", "ονται", "οταν", "ονταν")),
    ("ει", ("ει", "ουν", "ε", "αν")),
    ("ω", _PRESENT),
)
ADJECTIVE_HEADWORD_PATTERN = re.compile(r"(ος|ός|μένη|μένο)$")
DICTIONARY_VERB_PATTERN = re.compile(r"(ω|ώ|ομαι|άμαι|ιέμαι|ούμαι)$")
VERB_ENDING_PATTERN = re.compile(r"(ω|ώ|ομαι|άμαι|ιέμαι|ει|εί|εται)$")
GUESSED_ADJECTIVE_ENDINGS = ("οσ", "ου", "ο", "ε", "οι", "ων", "ουσ", "η", "ησ", "εσ", "α")
GUESSED_ADJECTIVE_PATTERN = re.compile(r"(οσ|η|ο|α)$")
MIN_GUESSED_STEM = 4


def download_sources(args: argparse.Namespace) -> None:
    for target, url in SOURCE_URLS.items():
        if target.exists() and not args.force:
            print(f"{target.name}: already present", file=sys.stderr)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {url}…", file=sys.stderr)
        partial = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as handle:
            while chunk := response.read(1 << 20):
                handle.write(chunk)
        partial.replace(target)
    archive = SOURCES_DIR / "greeklex2" / "GreekLex2.1.zip"
    unpacked = archive.parent / "unpacked"
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.namelist():
            destination = (unpacked / member).resolve()
            if not destination.is_relative_to(unpacked.resolve()):
                raise SystemExit(f"Refusing to extract {member!r} outside {unpacked}")
        bundle.extractall(unpacked)
    print(f"Sources are in {SOURCES_DIR}", file=sys.stderr)


def build_index(args: argparse.Namespace) -> None:
    print("Reading SUBTLEX-GR…", file=sys.stderr)
    counts, contexts, total_tokens, total_types = read_subtlex(args.subtlex)
    print("Reading GreekLex 2…", file=sys.stderr)
    greeklex = read_greeklex(args.greeklex)
    print("Reading kaikki Wiktionary…", file=sys.stderr)
    lemmas = read_kaikki(args.kaikki)
    print("Splitting homograph counts…", file=sys.stderr)
    corpus_millions = total_tokens / 1e6
    types_millions = total_types / 1e6
    claimants: dict[str, list[int]] = defaultdict(list)
    for lemma in lemmas:
        for form in lemma.forms:
            claimants[form].append(lemma.lemma_id)
    clusters = cluster_lemmas(lemmas, claimants)
    priors = compute_priors(lemmas, counts, greeklex, claimants, clusters)
    shares = compute_shares(lemmas, priors, claimants, clusters)
    plain_counts: dict[str, int] = defaultdict(int)
    for form, count in counts.items():
        plain_counts[strip_accents(form)] += count

    args.index.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.index.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    connection.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE subtlex_forms (
            form TEXT PRIMARY KEY, count INTEGER NOT NULL, contexts INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE subtlex_plain (plain TEXT PRIMARY KEY, count INTEGER NOT NULL) WITHOUT ROWID;
        CREATE TABLE claimed_plain (plain TEXT PRIMARY KEY) WITHOUT ROWID;
        CREATE TABLE greeklex (
            word TEXT PRIMARY KEY, lemma_pm REAL NOT NULL, form_pm REAL NOT NULL, pos TEXT NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE lemmas (
            lemma_id INTEGER PRIMARY KEY, word TEXT NOT NULL, display TEXT NOT NULL, pos TEXT NOT NULL,
            has_table INTEGER NOT NULL, gloss TEXT NOT NULL, alt_targets TEXT NOT NULL,
            subtlex_count REAL NOT NULL, cluster_id INTEGER NOT NULL, prior_pm REAL,
            prior_source TEXT NOT NULL, unambiguous_count INTEGER NOT NULL
        );
        CREATE TABLE lemma_forms (
            form TEXT NOT NULL, lemma_id INTEGER NOT NULL, tags TEXT NOT NULL, share REAL NOT NULL,
            PRIMARY KEY (form, lemma_id)
        ) WITHOUT ROWID;
        CREATE TABLE words (
            word TEXT PRIMARY KEY, pos TEXT NOT NULL, gloss TEXT NOT NULL,
            subtlex_count REAL NOT NULL, subtlex_zipf REAL NOT NULL,
            greeklex_pm REAL, greeklex_zipf REAL, zipf REAL NOT NULL,
            unambiguous_share REAL NOT NULL, rank INTEGER NOT NULL
        ) WITHOUT ROWID;
        """
    )
    connection.executemany(
        "INSERT INTO meta VALUES (?, ?)",
        [
            ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            ("subtlex_tokens", str(total_tokens)),
            ("subtlex_types", str(total_types)),
            ("greeklex_entries", str(len(greeklex))),
            ("kaikki_lemma_entries", str(len(lemmas))),
        ],
    )
    connection.executemany(
        "INSERT INTO subtlex_forms VALUES (?, ?, ?)",
        ((form, count, contexts.get(form, 0)) for form, count in counts.items()),
    )
    connection.executemany("INSERT INTO subtlex_plain VALUES (?, ?)", plain_counts.items())
    connection.executemany(
        "INSERT INTO claimed_plain VALUES (?)", ((plain,) for plain in {strip_accents(form) for form in claimants})
    )
    connection.executemany(
        "INSERT INTO greeklex VALUES (?, ?, ?, ?)",
        ((word, lemma_pm, form_pm, pos) for word, (lemma_pm, form_pm, pos) in greeklex.items()),
    )
    lemma_counts = [0.0] * len(lemmas)
    for (lemma_id, form), share in shares.items():
        lemma_counts[lemma_id] += counts.get(form, 0) * share
    connection.executemany(
        "INSERT INTO lemmas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                lemma.lemma_id,
                lemma.word,
                lemma.display,
                lemma.pos,
                int(lemma.has_table),
                lemma.gloss,
                json.dumps(sorted(lemma.alt_targets), ensure_ascii=False),
                lemma_counts[lemma.lemma_id],
                clusters[lemma.lemma_id],
                priors[clusters[lemma.lemma_id]].per_million,
                priors[clusters[lemma.lemma_id]].source,
                priors[clusters[lemma.lemma_id]].unambiguous_count,
            )
            for lemma in lemmas
        ),
    )
    connection.executemany(
        "INSERT INTO lemma_forms VALUES (?, ?, ?, ?)",
        (
            (form, lemma.lemma_id, ",".join(sorted(tags)), shares[(lemma.lemma_id, form)])
            for lemma in lemmas
            for form, tags in lemma.forms.items()
        ),
    )

    reference_rows = []
    tables_by_word: dict[str, list[LemmaEntry]] = defaultdict(list)
    for lemma in lemmas:
        if lemma.has_table:
            tables_by_word[lemma.word].append(lemma)

    def is_alias(lemma: LemmaEntry) -> bool:
        """A table-less entry such as μιλώ or πάω whose forms are listed under another lemma."""
        return not lemma.has_table and any(
            lemma.word in target.forms
            for word in lemma.alt_targets - {lemma.word}
            for target in tables_by_word.get(word, [])
        )

    eligible = [
        lemma
        for lemma in lemmas
        if lemma.pos in REFERENCE_POS
        and GREEK_ONLY_PATTERN.match(lemma.word)
        and lemma.display[:1].islower()
        and not is_alias(lemma)
    ]
    cluster_members: dict[int, list[LemmaEntry]] = defaultdict(list)
    for lemma in lemmas:
        cluster_members[clusters[lemma.lemma_id]].append(lemma)
    # One reference row per headword; a cluster of duplicate entries (τρώω/τρώγω) is listed once,
    # under the headword that is most frequent as a form.
    representative: dict[int, str] = {}
    for lemma in eligible:
        cluster_id = clusters[lemma.lemma_id]
        current = representative.get(cluster_id)
        if current is None or (counts.get(lemma.word, 0), -len(lemma.word)) > (counts.get(current, 0), -len(current)):
            representative[cluster_id] = lemma.word
    by_word: dict[str, list[LemmaEntry]] = defaultdict(list)
    for lemma in eligible:
        if representative[clusters[lemma.lemma_id]] == lemma.word:
            by_word[lemma.word].append(lemma)
    for word, group in by_word.items():
        word_clusters = {clusters[lemma.lemma_id] for lemma in group}
        cluster_share: dict[tuple[int, str], float] = {}
        for cluster_id in word_clusters:
            for member in cluster_members[cluster_id]:
                for form in member.forms:
                    cluster_share[(cluster_id, form)] = shares[(member.lemma_id, form)]
        form_share: dict[str, float] = defaultdict(float)
        for (_, form), share in cluster_share.items():
            form_share[form] += share
        subtlex_count = sum(counts.get(form, 0) * min(1.0, share) for form, share in form_share.items())
        unambiguous = sum(counts.get(form, 0) for form, share in form_share.items() if share >= 0.999)
        unambiguous_share = unambiguous / subtlex_count if subtlex_count else 1.0
        subtlex_zipf = zipf_from_count(subtlex_count, corpus_millions, types_millions)
        greeklex_values = [
            priors[cluster_id].per_million
            for cluster_id in word_clusters
            if priors[cluster_id].per_million is not None
        ]
        greeklex_pm = greeklex[word][0] if word in greeklex else (max(greeklex_values) if greeklex_values else None)
        greeklex_zipf = zipf_from_per_million(greeklex_pm) if greeklex_pm is not None else None
        zipf = subtlex_zipf if greeklex_zipf is None else (subtlex_zipf + greeklex_zipf) / 2
        pos = pick_pos([lemma.pos for lemma in group], has_article=False)
        gloss = next((lemma.gloss for lemma in group if lemma.pos == pos), group[0].gloss)
        reference_rows.append(
            [word, pos, gloss, subtlex_count, subtlex_zipf, greeklex_pm, greeklex_zipf, zipf, unambiguous_share]
        )
    reference_rows.sort(key=lambda row: -row[7])
    connection.executemany(
        "INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (row + [rank] for rank, row in enumerate(reference_rows, start=1)),
    )
    connection.execute("CREATE INDEX idx_lemmas_word ON lemmas(word)")
    connection.execute("CREATE INDEX idx_lemmas_cluster ON lemmas(cluster_id)")
    connection.execute("CREATE INDEX idx_words_zipf ON words(zipf DESC)")
    connection.commit()
    connection.close()
    temporary.replace(args.index)
    print(
        f"Index written to {args.index}: {len(counts)} SUBTLEX forms, {len(greeklex)} GreekLex lemmas, "
        f"{len(lemmas)} Wiktionary lemma entries, {len(reference_rows)} reference words.",
        file=sys.stderr,
    )


# --------------------------------------------------------------------------------------
# Lookup engine
# --------------------------------------------------------------------------------------


def pick_pos(pos_values: Iterable[str], has_article: bool) -> str:
    values = set(pos_values)
    priority = POS_PRIORITY_WITH_ARTICLE if has_article else POS_PRIORITY_WITHOUT_ARTICLE
    return next((pos for pos in priority if pos in values), next(iter(sorted(values)), "other"))


@dataclass
class TokenResolution:
    token: str
    lemma_ids: list[int]
    method: str
    plural_only: bool = False
    guessed_keys: list[str] = field(default_factory=list)
    shape: str = "other"


@dataclass
class FrequencyResult:
    lemma_words: list[str]
    pos: str
    subtlex_count: float
    subtlex_upper: float
    subtlex_zipf: float
    greeklex_pm: float | None
    greeklex_zipf: float | None
    zipf: float
    rank: int
    methods: list[str]
    homograph_share: float
    found: bool


@dataclass(frozen=True)
class LemmaInfo:
    word: str
    display: str
    pos: str
    has_table: bool
    alt_targets: tuple[str, ...]
    cluster_id: int


class FrequencyIndex:
    def __init__(self, path: Path) -> None:
        if not path.exists():
            raise SystemExit(f"Index {path} not found; run `greek_frequency.py build` first.")
        self.connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        meta = dict(self.connection.execute("SELECT key, value FROM meta"))
        self.corpus_millions = int(meta["subtlex_tokens"]) / 1e6
        self.types_millions = int(meta["subtlex_types"]) / 1e6
        self.reference_zipfs = sorted(z for (z,) in self.connection.execute("SELECT zipf FROM words"))
        self._lemma_cache: dict[int, LemmaInfo] = {}

    def subtlex_count(self, form: str) -> int:
        row = self.connection.execute("SELECT count FROM subtlex_forms WHERE form = ?", (form,)).fetchone()
        return row[0] if row else 0

    def subtlex_plain_count(self, plain: str) -> int:
        row = self.connection.execute("SELECT count FROM subtlex_plain WHERE plain = ?", (plain,)).fetchone()
        return row[0] if row else 0

    def is_claimed_plain(self, plain: str) -> bool:
        return self.connection.execute("SELECT 1 FROM claimed_plain WHERE plain = ?", (plain,)).fetchone() is not None

    def greeklex_pm(self, word: str) -> float | None:
        row = self.connection.execute("SELECT lemma_pm FROM greeklex WHERE word = ?", (word,)).fetchone()
        return row[0] if row else None

    def lemma(self, lemma_id: int) -> LemmaInfo:
        cached = self._lemma_cache.get(lemma_id)
        if cached is None:
            word, display, pos, has_table, alt_targets, cluster_id = self.connection.execute(
                "SELECT word, display, pos, has_table, alt_targets, cluster_id FROM lemmas WHERE lemma_id = ?",
                (lemma_id,),
            ).fetchone()
            cached = LemmaInfo(word, display, pos, bool(has_table), tuple(json.loads(alt_targets)), cluster_id)
            self._lemma_cache[lemma_id] = cached
        return cached

    def lemma_forms(self, lemma_id: int) -> list[tuple[str, str, float]]:
        return self.connection.execute(
            "SELECT form, tags, share FROM lemma_forms WHERE lemma_id = ?", (lemma_id,)
        ).fetchall()

    def lemma_has_form(self, lemma_id: int, form: str) -> bool:
        return (
            self.connection.execute(
                "SELECT 1 FROM lemma_forms WHERE lemma_id = ? AND form = ?", (lemma_id, form)
            ).fetchone()
            is not None
        )

    def cluster_members(self, lemma_id: int) -> list[int]:
        cluster_id = self.lemma(lemma_id).cluster_id
        return [row[0] for row in self.connection.execute("SELECT lemma_id FROM lemmas WHERE cluster_id = ?", (cluster_id,))]

    def lemma_ids_for_word(self, word: str) -> list[int]:
        return [row[0] for row in self.connection.execute("SELECT lemma_id FROM lemmas WHERE word = ?", (word,))]

    def claims(self, form: str) -> list[tuple[int, str]]:
        return self.connection.execute("SELECT lemma_id, tags FROM lemma_forms WHERE form = ?", (form,)).fetchall()

    def card_greeklex_pm(self, resolutions: list[TokenResolution]) -> float | None:
        """GreekLex lemma frequency for a card: the written token itself if listed, else its lemma cluster."""
        total: float | None = None
        covered: set[int] = set()
        for resolution in resolutions:
            clusters = {self.lemma(lemma_id).cluster_id for lemma_id in resolution.lemma_ids}
            if clusters and clusters <= covered:
                continue
            value = self.greeklex_pm(resolution.token)
            if value is None and clusters:
                member_values = [
                    self.greeklex_pm(self.lemma(member).word)
                    for lemma_id in resolution.lemma_ids
                    if self.lemma(lemma_id).cluster_id not in covered
                    for member in self.cluster_members(lemma_id)
                ]
                member_values = [v for v in member_values if v is not None]
                value = max(member_values) if member_values else None
            covered |= clusters
            if value is not None:
                total = (total or 0.0) + value
        return total

    def rank_for_zipf(self, zipf: float) -> int:
        return len(self.reference_zipfs) - bisect.bisect_right(self.reference_zipfs, zipf) + 1

    def _filter_pos(self, lemma_ids: list[int], preferred: frozenset[str] | None) -> list[int]:
        if not preferred:
            return lemma_ids
        filtered = [lemma_id for lemma_id in lemma_ids if self.lemma(lemma_id).pos in preferred]
        return filtered or lemma_ids

    def resolve_token(
        self,
        token: str,
        preferred: frozenset[str] | None = None,
        plural: bool = False,
        shape: str = "other",
        capitalized: bool = False,
    ) -> TokenResolution:
        """Map a written token to Wiktionary lemma entries.

        `shape` (noun/adj/verb/other) only steers the fallback paradigm for unknown words.
        A lowercase token on the card does not match proper names (οι αριθμοί is not the book Αριθμοί).
        """
        entries = self.lemma_ids_for_word(token)
        common = [lemma_id for lemma_id in entries if not self.lemma(lemma_id).display[:1].isupper()]
        proper = [lemma_id for lemma_id in entries if lemma_id not in common]
        entries = self._filter_pos(common + proper if capitalized else common, preferred)
        resolved: list[int] = []
        for lemma_id in entries:
            info = self.lemma(lemma_id)
            if info.has_table or not info.alt_targets:
                resolved.append(lemma_id)
                continue
            # Table-less entries such as μιλώ or πάω: use the lemma whose table lists this form.
            targets = [
                target_id
                for target in info.alt_targets
                if target != info.word
                for target_id in self.lemma_ids_for_word(target)
                if self.lemma(target_id).has_table and self.lemma_has_form(target_id, token)
            ]
            resolved.extend(targets or [lemma_id])
        if resolved:
            resolved = sorted(set(resolved))
            infos = [self.lemma(lemma_id) for lemma_id in resolved]
            table_less_pos = {info.pos for info in infos if not info.has_table}
            if len(table_less_pos) == len({info.pos for info in infos}) == 1 and table_less_pos <= {"noun", "verb", "adj"}:
                # Wiktionary has the lemma but no inflection table: count a guessed paradigm instead.
                keys = guess_forms(token, {"noun": "noun", "verb": "verb", "adj": "adj"}[table_less_pos.pop()])
                if len(keys) > 1:
                    return TokenResolution(token, resolved, "lemma_guessed", guessed_keys=keys)
            return TokenResolution(token, resolved, "lemma")
        claims = self.claims(token)
        if claims and all(is_participle_tags(tags) for _, tags in claims):
            # A participle used as an adjective (διαμορφωμένος): count its own declension, not the verb.
            return TokenResolution(token, [], "participle", guessed_keys=guess_forms(token, "adj"))
        claimed_ids = sorted({lemma_id for lemma_id, _ in claims})
        if not capitalized:
            claimed_ids = [i for i in claimed_ids if not self.lemma(i).display[:1].isupper()] or claimed_ids
        claimed = self._filter_pos(claimed_ids, preferred)
        if claimed:
            return TokenResolution(token, claimed, "form_of", plural_only=plural)
        # Impersonal verbs written in the 3rd person (νυχτώνει, συμφέρει): try the dictionary form.
        for ending, lemma_ending in (("εται", "ομαι"), ("ει", "ω")):
            if token.endswith(ending):
                candidate = token[: -len(ending)] + lemma_ending
                verbs = [i for i in self.lemma_ids_for_word(candidate) if self.lemma(i).pos == "verb"]
                if verbs:
                    return TokenResolution(token, verbs, "form_of")
        if proper and not capitalized:
            return TokenResolution(token, sorted(proper), "lemma")
        keys = guess_forms(token, shape)
        if len(keys) > 1:
            return TokenResolution(token, [], "guessed", guessed_keys=keys, shape=shape)
        return TokenResolution(token, [], "unresolved", shape=shape)

    def frequency(self, resolutions: list[TokenResolution], has_article: bool = False) -> FrequencyResult:
        # Shares are identical inside a cluster of duplicate entries, so count each cluster once.
        cluster_share: dict[tuple[int, str], float] = {}
        lemma_ids: list[int] = []
        for resolution in resolutions:
            for resolved_id in resolution.lemma_ids:
                for lemma_id in self.cluster_members(resolved_id):
                    if lemma_id in lemma_ids:
                        continue
                    lemma_ids.append(lemma_id)
                    cluster_id = self.lemma(lemma_id).cluster_id
                    for form, tags, share in self.lemma_forms(lemma_id):
                        if resolution.plural_only and "plural" not in tags.split(",") and form != resolution.token:
                            continue
                        cluster_share[(cluster_id, form)] = share
        form_share: dict[str, float] = defaultdict(float)
        for (_, form), share in cluster_share.items():
            form_share[form] += share
        subtlex_count = 0.0
        subtlex_upper = 0.0
        for form, share in form_share.items():
            count = self.subtlex_count(form)
            subtlex_count += count * min(1.0, share)
            subtlex_upper += count
        guessed_keys: set[str] = set()
        counted_forms = {strip_accents(form) for form in form_share}
        for resolution in resolutions:
            if resolution.guessed_keys:
                # A guessed form that Wiktionary already lists for some lemma is that lemma's business
                # (the noun είναι must not take the verb form είναι); participles keep their own forms.
                guessed_keys.update(
                    key
                    for key in resolution.guessed_keys
                    if key not in counted_forms
                    and (resolution.method == "participle" or not self.is_claimed_plain(key))
                )
            elif not resolution.lemma_ids:
                count = self.subtlex_count(resolution.token)
                subtlex_count += count
                subtlex_upper += count
        for key in guessed_keys:
            count = self.subtlex_plain_count(key)
            subtlex_count += count
            subtlex_upper += count

        primary_ids = [lemma_id for r in resolutions for lemma_id in r.lemma_ids]
        lemma_ids += [lemma_id for lemma_id in primary_ids if lemma_id not in lemma_ids]
        lemma_words = list(dict.fromkeys(self.lemma(lemma_id).word for lemma_id in primary_ids))
        lemma_words += [r.token for r in resolutions if not r.lemma_ids and r.token not in lemma_words]
        greeklex_pm = self.card_greeklex_pm(resolutions)
        greeklex_zipf = zipf_from_per_million(greeklex_pm) if greeklex_pm is not None else None
        subtlex_zipf = zipf_from_count(subtlex_count, self.corpus_millions, self.types_millions)
        zipf = subtlex_zipf if greeklex_zipf is None else (subtlex_zipf + greeklex_zipf) / 2
        found = bool(lemma_ids) or subtlex_count > 0 or greeklex_pm is not None
        if lemma_ids:
            pos = pick_pos((self.lemma(lemma_id).pos for lemma_id in lemma_ids), has_article)
        elif any(r.method == "participle" for r in resolutions):
            pos = "adj"
        else:
            pos = next((r.shape for r in resolutions if r.shape in {"verb", "adj", "noun"}), "other")
        return FrequencyResult(
            lemma_words=lemma_words,
            pos=pos,
            subtlex_count=subtlex_count,
            subtlex_upper=subtlex_upper,
            subtlex_zipf=subtlex_zipf,
            greeklex_pm=greeklex_pm,
            greeklex_zipf=greeklex_zipf,
            zipf=zipf,
            rank=self.rank_for_zipf(zipf),
            methods=sorted({resolution.method for resolution in resolutions}),
            homograph_share=1.0 - subtlex_count / subtlex_upper if subtlex_upper else 0.0,
            found=found,
        )


def is_participle_tags(tags: str) -> bool:
    """A declinable participle cell; aorist infinitives (έχω αρέσει) are also tagged "participle"."""
    values = set(tags.split(","))
    return "participle" in values and not values & {"indicative", "infinitive-aorist", "first-person", "third-person"}


def guess_forms(token: str, shape: str) -> list[str]:
    """Accent-free candidate forms for a word missing from Wiktionary, by its ending."""
    plain = strip_accents(token)
    if shape == "adj":
        match = GUESSED_ADJECTIVE_PATTERN.search(plain)
        if match and len(plain) - len(match.group(1)) >= MIN_GUESSED_STEM:
            stem = plain[: match.start()]
            return [stem + ending for ending in GUESSED_ADJECTIVE_ENDINGS]
    elif shape == "noun":
        for ending, paradigm in GUESSED_NOUN_PARADIGMS:
            if plain.endswith(ending) and len(plain) - len(ending) >= MIN_GUESSED_STEM:
                stem = plain[: -len(ending)]
                return [stem + form for form in paradigm]
    elif shape == "verb":
        for ending, paradigm in GUESSED_VERB_PARADIGMS:
            if plain.endswith(ending) and len(plain) - len(ending) >= MIN_GUESSED_STEM - 1:
                stem = plain[: -len(ending)]
                return [stem + form for form in paradigm]
    return [plain]


def token_shape(token: str, has_article: bool, adjective: bool) -> str:
    if not has_article and DICTIONARY_VERB_PATTERN.search(token):
        return "verb"  # "φοιτάω, φοιτώ" lists two verb variants, not genders
    if adjective or (not has_article and ADJECTIVE_HEADWORD_PATTERN.search(token)):
        return "adj"  # the deck writes nouns with an article, so a bare -ος/-μένος headword is an adjective
    if has_article:
        return "noun"
    if VERB_ENDING_PATTERN.search(token):
        return "verb"
    return "other"


# --------------------------------------------------------------------------------------
# Card front parsing
# --------------------------------------------------------------------------------------


@dataclass
class ParsedFront:
    lexeme_tokens: list[str]
    phrase_parts: list[list[str]]
    articles: set[str]
    part_count: int
    sentence_like: bool = False
    capitalized: set[str] = field(default_factory=set)

    @property
    def kind(self) -> str:
        if self.phrase_parts:
            return "phrase"
        return "lexeme" if self.lexeme_tokens else "empty"


def tokenize_part(part: str, capitalized: set[str] | None = None) -> list[str]:
    tokens = []
    for raw in re.findall(rf"ό,τι|[{GREEK_CHARS}]+|[A-Za-z]+", part):
        token = LATIN_LOOKALIKE_TOKENS.get(raw.lower(), raw)
        if GREEK_TOKEN_PATTERN.fullmatch(token):
            tokens.append(normalize_word(token))
            if capitalized is not None and token[:1].isupper():
                capitalized.add(normalize_word(token))
    return tokens


def parse_front(front: str) -> ParsedFront:
    text = unicodedata.normalize("NFC", front)
    text = re.sub(r"\(\s*не\b[^)]*\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(rf"([{GREEK_CHARS}])\(([{GREEK_CHARS}]{{1,2}})\)", r"\1", text)
    alternatives: list[str] = []

    def take_parenthesized(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if inner.startswith("+") or not re.search(rf"[{GREEK_CHARS}]", inner):
            return " "
        if normalize_word(inner) not in PARENTHESIZED_PRONOUNS:
            alternatives.append(inner)
        return " "

    text = re.sub(r"\(([^)]*)\)", take_parenthesized, text)
    sentence_like = bool(re.search(r"[;;!?…]|\.\.", text))
    text = text.replace("ό,τι", "ό\u0000τι")
    parts = [part.replace("\u0000", ",") for part in re.split(r"[\n,/;:!?…«»\"]+|\.+", text)]
    parts += alternatives

    lexeme_tokens: list[str] = []
    phrase_parts: list[list[str]] = []
    articles: set[str] = set()
    part_count = 0
    capitalized: set[str] = set()
    for part in parts:
        tokens = tokenize_part(part, capitalized)
        if not tokens:
            continue
        if tokens[0] in ARTICLES:
            articles.add(tokens[0])
            tokens = tokens[1:]
            if not tokens:
                continue
        if len(tokens) > 1 and tokens[0] in LEADING_PARTICLES:
            tokens = tokens[1:]
        part_count += 1
        if len(tokens) == 1:
            if tokens[0] not in lexeme_tokens:
                lexeme_tokens.append(tokens[0])
        else:
            phrase_parts.append(tokens)
    if sentence_like and part_count >= 2:
        # "Λέγετε; Εμπρός; Ορίστε;" or "Τον λένε... Τη λένε...": several utterances, not one lexeme.
        phrase_parts += [[token] for token in lexeme_tokens]
        lexeme_tokens = []
    return ParsedFront(lexeme_tokens, phrase_parts, articles, part_count, sentence_like, capitalized)


@dataclass
class CardResult:
    note_id: int
    front: str
    kind: str
    tags: list[str]
    created: datetime
    result: FrequencyResult | None
    rarest_token: str | None = None
    unknown_tokens: list[str] = field(default_factory=list)


def drop_covered_forms(index: FrequencyIndex, resolutions: list[TokenResolution]) -> list[TokenResolution]:
    """Fold later forms into the first lemma: `μεγάλος, μεγάλη, μεγάλο` must not add μέγας,
    and `μόνος, μόνη, μόνο` must not add the adverb μόνο. A same-POS headword (`ο φίλος, η φίλη`) stays."""
    first = next((r for r in resolutions if r.lemma_ids), None)
    if first is None:
        return resolutions
    anchors = [member for lemma_id in first.lemma_ids for member in index.cluster_members(lemma_id)]
    anchor_pos = {index.lemma(lemma_id).pos for lemma_id in anchors}
    kept = []
    for resolution in resolutions:
        if resolution is first or not resolution.lemma_ids:
            kept.append(resolution)
            continue
        if not any(index.lemma_has_form(lemma_id, resolution.token) for lemma_id in anchors):
            kept.append(resolution)
            continue
        own = [
            lemma_id
            for lemma_id in resolution.lemma_ids
            if lemma_id not in anchors
            and index.lemma(lemma_id).word == resolution.token
            and index.lemma(lemma_id).pos in anchor_pos
        ]
        if own:
            kept.append(TokenResolution(resolution.token, own, resolution.method, resolution.plural_only))
    return kept


def analyse_front(index: FrequencyIndex, front: str) -> tuple[ParsedFront, FrequencyResult | None, str | None, list[str]]:
    parsed = parse_front(front)
    if parsed.kind == "lexeme":
        has_article = bool(parsed.articles)
        preferred = NOUN_POS if has_article and parsed.part_count < 3 else None
        plural = has_article and parsed.articles <= PLURAL_ARTICLES
        adjective = parsed.part_count >= 2 and not has_article or parsed.part_count >= 3
        resolutions = [
            index.resolve_token(
                token, preferred, plural, token_shape(token, has_article, adjective), token in parsed.capitalized
            )
            for token in parsed.lexeme_tokens
        ]
        resolutions = drop_covered_forms(index, resolutions)
        result = index.frequency(resolutions, has_article)
        unknown = [r.token for r in resolutions if r.method == "unresolved" and not index.subtlex_count(r.token)]
        return parsed, result, None, unknown
    if parsed.kind == "phrase":
        tokens = list(dict.fromkeys(parsed.lexeme_tokens + [t for part in parsed.phrase_parts for t in part]))
        best: tuple[FrequencyResult, str] | None = None
        unknown = []
        for token in tokens:
            resolution = index.resolve_token(
                token, shape=token_shape(token, False, False), capitalized=token in parsed.capitalized
            )
            token_result = index.frequency([resolution])
            if not token_result.found:
                unknown.append(token)
                continue
            if best is None or token_result.zipf < best[0].zipf:
                best = (token_result, token)
        if best is None:
            return parsed, None, None, unknown
        return parsed, best[0], best[1], unknown
    return parsed, None, None, []


# --------------------------------------------------------------------------------------
# Lookup command
# --------------------------------------------------------------------------------------


def lookup(args: argparse.Namespace) -> None:
    index = FrequencyIndex(args.index)
    for text in args.words:
        parsed, result, rarest, unknown = analyse_front(index, text)
        print(f"{text!r}: kind={parsed.kind}")
        if result is None:
            print("  not found")
            continue
        greeklex = f"{result.greeklex_pm:.1f}/млн (Zipf {result.greeklex_zipf:.2f})" if result.greeklex_pm is not None else "—"
        print(f"  lemmas: {', '.join(result.lemma_words) or '—'} ({result.pos}; {', '.join(result.methods)})")
        if rarest:
            print(f"  rarest word: {rarest}")
        print(f"  SUBTLEX-GR: {result.subtlex_count:.0f} occurrences (Zipf {result.subtlex_zipf:.2f})")
        print(f"  GreekLex 2: {greeklex}")
        print(f"  combined Zipf {result.zipf:.2f}, rank ≈ {result.rank}, homograph share {result.homograph_share:.0%}")
        if unknown:
            print(f"  unknown tokens: {', '.join(unknown)}")


# --------------------------------------------------------------------------------------
# Report command
# --------------------------------------------------------------------------------------


def zipf_band(zipf: float) -> str:
    return next(label for threshold, label, _ in ZIPF_BANDS if zipf >= threshold)


def rank_band(rank: int) -> str:
    lower = 1
    for upper in RANK_BANDS:
        if rank <= upper:
            return f"{lower}–{upper}"
        lower = upper + 1
    return f"> {RANK_BANDS[-1]}"


def rank_band_labels() -> list[str]:
    labels = []
    lower = 1
    for upper in RANK_BANDS:
        labels.append(f"{lower}–{upper}")
        lower = upper + 1
    return labels + [f"> {RANK_BANDS[-1]}"]


def load_cards(cards_db: Path, deck: str) -> Iterator[tuple[int, str, list[str]]]:
    connection = sqlite3.connect(f"file:{cards_db}?mode=ro", uri=True)
    rows = connection.execute(
        "SELECT note_id, front_clean, tags_json FROM anki_notes WHERE deck_name = ? AND is_present = 1 ORDER BY note_id",
        (deck,),
    ).fetchall()
    connection.close()
    for note_id, front, tags in rows:
        yield note_id, front, json.loads(tags)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " / ")


def fmt(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def report(args: argparse.Namespace) -> None:
    index = FrequencyIndex(args.index)
    cards: list[CardResult] = []
    for note_id, front, tags in load_cards(args.cards_db, args.deck):
        parsed, result, rarest, unknown = analyse_front(index, front)
        created = datetime.fromtimestamp(note_id / 1000, tz=timezone.utc)
        cards.append(CardResult(note_id, front, parsed.kind, tags, created, result, rarest, unknown))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    known_words = collect_known_words(index, cards)
    coverage = compute_coverage(index, known_words)
    write_csv(args.out_dir / "cards.csv", cards)
    charts = draw_charts(args.out_dir, cards, index, coverage)
    write_markdown(args.out_dir / "report.md", args.deck, cards, index, charts, known_words, coverage)
    print(f"Report written to {args.out_dir / 'report.md'}", file=sys.stderr)


def collect_known_words(index: FrequencyIndex, cards: list[CardResult]) -> set[str]:
    """Every token and lemma that appears on a card front, including words inside phrases."""
    known: set[str] = set()
    for card in cards:
        parsed = parse_front(card.front)
        tokens = parsed.lexeme_tokens + [t for part in parsed.phrase_parts for t in part]
        known.update(tokens)
        if card.result:
            known.update(card.result.lemma_words)
        for token in tokens:
            resolution = index.resolve_token(token, capitalized=token in parsed.capitalized)
            known.update(index.lemma(lemma_id).word for lemma_id in resolution.lemma_ids)
            for lemma_id in resolution.lemma_ids:
                known.update(index.lemma(member).word for member in index.cluster_members(lemma_id))
    return known


def reliable_reference_words(index: FrequencyIndex, limit_rank: int) -> list[tuple[str, str, str, float, int]]:
    """Reference lemmas safe to compare with the deck: in GreekLex, mostly unambiguous forms, not a variant."""
    rows = index.connection.execute(
        "SELECT word, pos, gloss, zipf, rank FROM words "
        "WHERE greeklex_pm IS NOT NULL AND unambiguous_share >= 0.5 AND rank <= ? ORDER BY rank",
        (limit_rank,),
    ).fetchall()
    return [row for row in rows if not VARIANT_GLOSS_PATTERN.search(row[2])]


@dataclass
class CoverageBand:
    label: str
    total: int
    covered: int


def compute_coverage(index: FrequencyIndex, known_words: set[str]) -> list[CoverageBand]:
    bands = []
    lower = 1
    rows = reliable_reference_words(index, COVERAGE_BANDS[-1])
    for upper in COVERAGE_BANDS:
        words = [row for row in rows if lower <= row[4] <= upper]
        bands.append(CoverageBand(f"{lower}–{upper}", len(words), sum(1 for row in words if row[0] in known_words)))
        lower = upper + 1
    return bands


def write_csv(path: Path, cards: list[CardResult]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "note_id", "created", "front", "kind", "pos", "lemmas", "rarest_word", "subtlex_count",
                "subtlex_zipf", "greeklex_pm", "greeklex_zipf", "zipf", "rank", "zipf_band", "rank_band",
                "homograph_share", "methods", "unknown_tokens", "tags",
            ]
        )
        for card in cards:
            r = card.result
            writer.writerow(
                [
                    card.note_id, card.created.date().isoformat(), card.front, card.kind,
                    r.pos if r else "", "; ".join(r.lemma_words) if r else "", card.rarest_token or "",
                    f"{r.subtlex_count:.1f}" if r else "", fmt(r.subtlex_zipf if r else None),
                    fmt(r.greeklex_pm if r else None, 1), fmt(r.greeklex_zipf if r else None),
                    fmt(r.zipf if r else None), r.rank if r else "", zipf_band(r.zipf) if r else "",
                    rank_band(r.rank) if r else "", f"{r.homograph_share:.2f}" if r else "",
                    ",".join(r.methods) if r else "", " ".join(card.unknown_tokens), " ".join(card.tags),
                ]
            )


# Chart styling follows the reference light palette of the dataviz guidelines.
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"


def style_axes(axes) -> None:
    axes.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(GRID)
    axes.tick_params(colors=TEXT_SECONDARY, labelsize=9, length=0)
    axes.yaxis.grid(True, color=GRID, linewidth=1)
    axes.set_axisbelow(True)


def draw_charts(
    out_dir: Path, cards: list[CardResult], index: FrequencyIndex, coverage: list[CoverageBand]
) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker

    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE})
    charts: dict[str, str] = {}
    lexemes = [c for c in cards if c.kind == "lexeme" and c.result and c.result.found]
    phrases = [c for c in cards if c.kind == "phrase" and c.result]

    def histogram(name: str, values: list[float], title: str, subtitle: str) -> None:
        bins = [1.5 + 0.25 * i for i in range(int((7.5 - 1.5) / 0.25) + 1)]
        figure, axes = plt.subplots(figsize=(10, 5.2))
        style_axes(axes)
        heights, edges, _ = axes.hist(values, bins=bins, color=SERIES_1, edgecolor=SURFACE, linewidth=2)
        top = max(heights) * 1.18
        axes.set_ylim(0, top)
        for threshold, label, note in ZIPF_BANDS[:-1]:
            axes.axvline(threshold, color=TEXT_SECONDARY, linewidth=1, alpha=0.35)
        band_edges = [1.5, 2.0, 3.0, 4.0, 5.0, 7.5]
        band_names = [label for _, label, _ in reversed(ZIPF_BANDS)]
        for left, right, label in zip(band_edges, band_edges[1:], band_names):
            share = sum(1 for v in values if left <= v < right or (right == 7.5 and v >= right)) / len(values)
            if left == 1.5:
                share = sum(1 for v in values if v < 2.0) / len(values)
            x, align = ((left + 0.03), "left") if left == 1.5 else ((left + right) / 2, "center")
            axes.text(x, top * 0.97, f"{label}\n{share:.0%}", ha=align, va="top", fontsize=9, color=TEXT_SECONDARY)
        median = statistics.median(values)
        axes.axvline(median, color=TEXT_PRIMARY, linewidth=1.5)
        axes.text(median + 0.05, top * 0.78, f"медиана {median:.2f}", color=TEXT_PRIMARY, fontsize=9)
        axes.set_xlabel("Zipf = log10(частота на млрд слов); 3 ≈ 1 раз на млн, 5 ≈ 100 раз на млн",
                        color=TEXT_SECONDARY, fontsize=9)
        axes.set_ylabel("карточек", color=TEXT_SECONDARY, fontsize=9)
        axes.set_xlim(1.5, 7.5)
        figure.suptitle(title, x=0.06, ha="left", fontsize=13, color=TEXT_PRIMARY)
        axes.set_title(subtitle, loc="left", fontsize=9, color=TEXT_SECONDARY)
        figure.tight_layout()
        figure.savefig(out_dir / name, dpi=150)
        plt.close(figure)
        charts[name] = title

    histogram(
        "zipf_histogram.png",
        [c.result.zipf for c in lexemes],
        f"Частотность слов колоды ({len(lexemes)} карточек-лексем)",
        "Комбинированный Zipf леммы: среднее SUBTLEX-GR (субтитры) и GreekLex 2 (письменный корпус HNC)",
    )
    if phrases:
        histogram(
            "phrase_rarest_word_histogram.png",
            [c.result.zipf for c in phrases],
            f"Фразы и предложения ({len(phrases)} карточек): самое редкое слово",
            "Zipf самого редкого слова: фраза не может встречаться чаще него, так что это верхняя граница",
        )

    counts = Counter(rank_band(c.result.rank) for c in lexemes)
    labels = [label for label in rank_band_labels() if counts.get(label)]
    values = [counts[label] for label in labels]
    figure, axes = plt.subplots(figsize=(10, 4.8))
    style_axes(axes)
    positions = range(len(labels))
    axes.bar(positions, values, width=0.6, color=SERIES_1)
    for position, value in zip(positions, values):
        axes.text(position, value + max(values) * 0.015, f"{value}\n{value / len(lexemes):.0%}", ha="center",
                  va="bottom", fontsize=9, color=TEXT_PRIMARY)
    axes.set_xticks(list(positions), labels)
    axes.set_ylim(0, max(values) * 1.22)
    axes.set_xlabel("место слова в общем частотном словаре лемм (1 = самое частое)", color=TEXT_SECONDARY, fontsize=9)
    axes.set_ylabel("карточек", color=TEXT_SECONDARY, fontsize=9)
    figure.suptitle("Где слова колоды находятся в частотном словаре", x=0.06, ha="left", fontsize=13,
                    color=TEXT_PRIMARY)
    axes.set_title(f"Ранг по комбинированному Zipf среди {len(index.reference_zipfs)} лемм Wiktionary",
                   loc="left", fontsize=9, color=TEXT_SECONDARY)
    figure.tight_layout()
    figure.savefig(out_dir / "rank_bands.png", dpi=150)
    plt.close(figure)
    charts["rank_bands.png"] = "Ранговые полосы"

    if coverage:
        figure, axes = plt.subplots(figsize=(10, 4.6))
        style_axes(axes)
        shares = [band.covered / max(1, band.total) for band in coverage]
        positions = range(len(coverage))
        axes.bar(positions, shares, width=0.6, color=SERIES_1)
        for position, band, share in zip(positions, coverage, shares):
            axes.text(position, share + 0.015, f"{share:.0%}\n{band.covered} из {band.total}", ha="center",
                      va="bottom", fontsize=9, color=TEXT_PRIMARY)
        axes.set_xticks(list(positions), [band.label for band in coverage])
        axes.set_ylim(0, 1.22)
        axes.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        axes.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        axes.set_xlabel("ранг леммы в общем частотном словаре", color=TEXT_SECONDARY, fontsize=9)
        figure.suptitle("Какая доля частотного словаря уже есть в колоде", x=0.06, ha="left", fontsize=13,
                        color=TEXT_PRIMARY)
        axes.set_title("Надёжные леммы (есть в GreekLex 2, в основном однозначные формы), найденные на лицевых сторонах",
                       loc="left", fontsize=9, color=TEXT_SECONDARY)
        figure.tight_layout()
        figure.savefig(out_dir / "coverage.png", dpi=150)
        plt.close(figure)
        charts["coverage.png"] = "Покрытие"

    both = [c for c in lexemes if c.result.greeklex_zipf is not None]
    if both:
        bins = [1.0 + 0.25 * i for i in range(29)]
        figure, axes = plt.subplots(figsize=(10, 4.8))
        style_axes(axes)
        axes.hist([c.result.subtlex_zipf for c in both], bins=bins, histtype="step", linewidth=2,
                  color=SERIES_1, label="SUBTLEX-GR — субтитры, разговорный")
        axes.hist([c.result.greeklex_zipf for c in both], bins=bins, histtype="step", linewidth=2,
                  color=SERIES_2, label="GreekLex 2 — HNC, письменный")
        axes.legend(frameon=False, fontsize=9, labelcolor=TEXT_PRIMARY, loc="upper left")
        axes.set_xlabel("Zipf леммы", color=TEXT_SECONDARY, fontsize=9)
        axes.set_ylabel("карточек", color=TEXT_SECONDARY, fontsize=9)
        figure.suptitle("Разговорная и письменная частотность тех же слов", x=0.06, ha="left", fontsize=13,
                        color=TEXT_PRIMARY)
        axes.set_title(f"{len(both)} лексем, найденных в обоих источниках", loc="left", fontsize=9,
                       color=TEXT_SECONDARY)
        figure.tight_layout()
        figure.savefig(out_dir / "sources_comparison.png", dpi=150)
        plt.close(figure)
        charts["sources_comparison.png"] = "Сравнение источников"

    by_quarter: dict[str, list[float]] = defaultdict(list)
    for card in lexemes:
        by_quarter[quarter_label(card.created)].append(card.result.zipf)
    quarters = sorted(q for q, vals in by_quarter.items() if len(vals) >= 20)
    if len(quarters) >= 2:
        figure, axes = plt.subplots(figsize=(10, 4.4))
        style_axes(axes)
        medians = [statistics.median(by_quarter[q]) for q in quarters]
        axes.plot(range(len(quarters)), medians, color=SERIES_1, linewidth=2, marker="o", markersize=6,
                  markeredgecolor=SURFACE, markeredgewidth=2, solid_capstyle="round")
        axes.set_xticks(range(len(quarters)), quarters, rotation=45, ha="right")
        axes.set_ylabel("медианный Zipf", color=TEXT_SECONDARY, fontsize=9)
        axes.text(len(quarters) - 1, medians[-1] + 0.04, f"{medians[-1]:.2f}", ha="center", fontsize=9,
                  color=TEXT_PRIMARY)
        figure.suptitle("Насколько частотны слова, добавленные в разные кварталы", x=0.06, ha="left",
                        fontsize=13, color=TEXT_PRIMARY)
        axes.set_title("Медианный Zipf новых карточек-лексем; ниже — значит слова реже", loc="left", fontsize=9,
                       color=TEXT_SECONDARY)
        figure.tight_layout()
        figure.savefig(out_dir / "timeline.png", dpi=150)
        plt.close(figure)
        charts["timeline.png"] = "Динамика"
    return charts


def quarter_label(moment: datetime) -> str:
    return f"{moment.year}-Q{(moment.month - 1) // 3 + 1}"


def write_markdown(
    path: Path,
    deck: str,
    cards: list[CardResult],
    index: FrequencyIndex,
    charts: dict[str, str],
    known_words: set[str],
    coverage: list[CoverageBand],
) -> None:
    lexemes = [c for c in cards if c.kind == "lexeme" and c.result and c.result.found]
    not_found = [c for c in cards if c.kind == "lexeme" and (not c.result or not c.result.found)]
    phrases = [c for c in cards if c.kind == "phrase" and c.result]
    phrases_missing = [c for c in cards if c.kind == "phrase" and not c.result]
    empty = [c for c in cards if c.kind == "empty"]
    zipfs = [c.result.zipf for c in lexemes]
    lines: list[str] = []
    add = lines.append

    add(f"# Частотность слов колоды «{deck}»")
    add("")
    add(f"Сгенерировано {datetime.now().strftime('%Y-%m-%d %H:%M')} скриптом `scripts/greek_frequency.py report`.")
    add("Подробные данные по каждой карточке — в `cards.csv` рядом с отчётом.")
    add("")
    add("## Коротко")
    add("")
    add(f"- Карточек в колоде: **{len(cards)}**.")
    add(f"- Карточек-лексем (одно слово, в т.ч. три рода или несколько форм): **{len(lexemes) + len(not_found)}**, "
        f"частота найдена для **{len(lexemes)}** ({len(lexemes) / max(1, len(lexemes) + len(not_found)):.1%}).")
    add(f"- Фраз и предложений: **{len(phrases) + len(phrases_missing)}**; для них считается частота самого редкого слова.")
    add(f"- Медианный Zipf лексемы: **{statistics.median(zipfs):.2f}** "
        f"(≈ {10 ** (statistics.median(zipfs) - 3):.1f} употребления на миллион слов).")
    in_top = lambda n: sum(1 for c in lexemes if c.result.rank <= n) / len(lexemes)
    add(f"- В топ-1000 лемм: **{in_top(1000):.0%}**, в топ-5000: **{in_top(5000):.0%}**, "
        f"за пределами топ-10000: **{1 - in_top(10000):.0%}** лексем.")
    add("")
    add("## Шкала")
    add("")
    add("Zipf — десятичный логарифм частоты на миллиард слов (Van Heuven et al., 2014).")
    add("Шаг в 1 единицу — разница в 10 раз. Zipf 3 ≈ 1 раз на миллион слов, Zipf 5 ≈ 100 раз на миллион.")
    add("")
    add("| Полоса | Zipf | Частота | Карточек | Доля |")
    add("|---|---|---|---:|---:|")
    band_counts = Counter(zipf_band(z) for z in zipfs)
    previous = None
    for threshold, label, note in ZIPF_BANDS:
        zipf_range = f"≥ {threshold:.0f}" if previous is None else (f"{threshold:.0f}–{previous:.0f}" if threshold > -math.inf else f"< {previous:.0f}")
        add(f"| {label} | {zipf_range} | {note} | {band_counts.get(label, 0)} | {band_counts.get(label, 0) / len(zipfs):.1%} |")
        previous = threshold
    add("")
    if "zipf_histogram.png" in charts:
        add("![Гистограмма частотности](zipf_histogram.png)")
        add("")
    add("### Ранг в частотном словаре")
    add("")
    add(f"Ранг считается по тому же комбинированному Zipf среди {len(index.reference_zipfs)} однословных лемм "
        "Wiktionary (без имён собственных).")
    add("")
    add("| Ранг | Карточек | Доля | Накопленно |")
    add("|---|---:|---:|---:|")
    rank_counts = Counter(rank_band(c.result.rank) for c in lexemes)
    cumulative = 0
    for label in rank_band_labels():
        cumulative += rank_counts.get(label, 0)
        add(f"| {label} | {rank_counts.get(label, 0)} | {rank_counts.get(label, 0) / len(lexemes):.1%} | {cumulative / len(lexemes):.1%} |")
    add("")
    if "rank_bands.png" in charts:
        add("![Ранговые полосы](rank_bands.png)")
        add("")

    add("## Статистика по лексемам")
    add("")
    add("| Показатель | Zipf | На млн слов | Примерный ранг |")
    add("|---|---:|---:|---:|")
    for label, fraction in (("10-й перцентиль (редкие)", 0.1), ("25-й перцентиль", 0.25), ("медиана", 0.5),
                            ("75-й перцентиль", 0.75), ("90-й перцентиль (частые)", 0.9)):
        value = percentile(zipfs, fraction)
        add(f"| {label} | {value:.2f} | {10 ** (value - 3):.2f} | {index.rank_for_zipf(value)} |")
    add(f"| среднее | {statistics.mean(zipfs):.2f} | | |")
    add("")
    add("### По частям речи")
    add("")
    add("| Часть речи | Карточек | Медиана Zipf | Доля в топ-5000 | Доля «редких» (Zipf < 3) |")
    add("|---|---:|---:|---:|---:|")
    by_pos: dict[str, list[CardResult]] = defaultdict(list)
    for card in lexemes:
        by_pos[POS_LABELS.get(card.result.pos, "служебные и прочие")].append(card)
    for label, group in sorted(by_pos.items(), key=lambda item: -len(item[1])):
        group_zipfs = [c.result.zipf for c in group]
        add(f"| {label} | {len(group)} | {statistics.median(group_zipfs):.2f} | "
            f"{sum(1 for c in group if c.result.rank <= 5000) / len(group):.0%} | "
            f"{sum(1 for z in group_zipfs if z < 3) / len(group):.0%} |")
    add("")
    add("### Как записана лексема на карточке")
    add("")
    add("| Запись | Карточек | Медиана Zipf |")
    add("|---|---:|---:|")
    shapes: dict[str, list[float]] = defaultdict(list)
    for card in lexemes:
        parsed = parse_front(card.front)
        if parsed.part_count >= 3:
            shape = "три рода / три формы"
        elif parsed.part_count == 2:
            shape = "две формы (два рода, варианты)"
        elif parsed.articles:
            shape = "одно слово с артиклем"
        else:
            shape = "одно слово без артикля"
        shapes[shape].append(card.result.zipf)
    for shape, values in sorted(shapes.items(), key=lambda item: -len(item[1])):
        add(f"| {shape} | {len(values)} | {statistics.median(values):.2f} |")
    add("")

    add("## Самые частые лексемы колоды")
    add("")
    add(card_table(sorted(lexemes, key=lambda c: -c.result.zipf)[:30]))
    add("")
    add("## Самые редкие лексемы колоды")
    add("")
    add("Сюда же попадают слова, которых почти нет в обоих корпусах; часть из них — ошибки лемматизации, "
        "их видно по колонке «леммы».")
    add("")
    add(card_table(sorted(lexemes, key=lambda c: c.result.zipf)[:60]))
    add("")

    add("## Разговорные и книжные слова")
    add("")
    both = [c for c in lexemes if c.result.greeklex_zipf is not None]
    if both:
        offset = statistics.median(c.result.subtlex_zipf - c.result.greeklex_zipf for c in both)
        add(f"Для {len(both)} лексем есть оба источника. Медианная разница SUBTLEX − GreekLex = {offset:+.2f}; "
            "ниже — слова, сильнее всего отклоняющиеся от неё.")
        add("")
        if "sources_comparison.png" in charts:
            add("![Сравнение источников](sources_comparison.png)")
            add("")
        delta = lambda c: c.result.subtlex_zipf - c.result.greeklex_zipf - offset
        add("Чаще в речи (субтитрах), чем в текстах:")
        add("")
        add(card_table(sorted(both, key=lambda c: -delta(c))[:20], extra=("Δ", lambda c: f"{delta(c):+.2f}")))
        add("")
        add("Чаще в текстах (пресса, книги), чем в речи:")
        add("")
        add(card_table(sorted(both, key=lambda c: delta(c))[:20], extra=("Δ", lambda c: f"{delta(c):+.2f}")))
        add("")
    add(f"GreekLex 2 содержит {sum(1 for c in lexemes if c.result.greeklex_pm is not None)} из {len(lexemes)} "
        "лексем колоды; для остальных используется только SUBTLEX-GR.")
    add("")

    add("## Фразы и предложения")
    add("")
    if phrases:
        phrase_zipfs = [c.result.zipf for c in phrases]
        add(f"Для {len(phrases)} фраз мерой служит частота самого редкого слова. Фраза не может встречаться чаще "
            "своего самого редкого слова, но обычно встречается намного реже.")
        add(f"Медианный Zipf самого редкого слова: **{statistics.median(phrase_zipfs):.2f}**.")
        add("")
        if "phrase_rarest_word_histogram.png" in charts:
            add("![Фразы](phrase_rarest_word_histogram.png)")
            add("")
        add("Фразы с самым редким словом:")
        add("")
        add(card_table(sorted(phrases, key=lambda c: c.result.zipf)[:30], extra=("Редкое слово", lambda c: c.rarest_token or "")))
        add("")

    add("## Динамика по времени добавления")
    add("")
    add("| Квартал | Новых лексем | Медиана Zipf | Доля Zipf < 3 |")
    add("|---|---:|---:|---:|")
    by_quarter: dict[str, list[float]] = defaultdict(list)
    for card in lexemes:
        by_quarter[quarter_label(card.created)].append(card.result.zipf)
    for quarter in sorted(by_quarter):
        values = by_quarter[quarter]
        add(f"| {quarter} | {len(values)} | {statistics.median(values):.2f} | {sum(1 for z in values if z < 3) / len(values):.0%} |")
    add("")
    if "timeline.png" in charts:
        add("![Динамика](timeline.png)")
        add("")

    add("## Пиявки (тег leech) и частотность")
    add("")
    add("| Полоса | Лексем | Из них leech | Доля leech |")
    add("|---|---:|---:|---:|")
    for _, label, _ in ZIPF_BANDS:
        group = [c for c in lexemes if zipf_band(c.result.zipf) == label]
        leeches = sum(1 for c in group if "leech" in c.tags)
        if group:
            add(f"| {label} | {len(group)} | {leeches} | {leeches / len(group):.1%} |")
    add("")

    add("## Повторы лемм")
    add("")
    by_lemmas: dict[tuple[str, ...], list[CardResult]] = defaultdict(list)
    for card in lexemes:
        by_lemmas[tuple(sorted(card.result.lemma_words))].append(card)
    repeated = sorted(((k, v) for k, v in by_lemmas.items() if len(v) > 1 and k), key=lambda item: -len(item[1]))
    add(f"Различных наборов лемм у лексем: **{len(by_lemmas)}**. На одну и ту же лемму приходится несколько "
        f"карточек в {len(repeated)} случаях. Это не обязательно дубликаты: бывают омонимы и разные значения.")
    add("")
    if repeated:
        add("| Лемма | Карточки |")
        add("|---|---|")
        for lemma_key, group in repeated[:40]:
            add(f"| {md_escape(', '.join(lemma_key))} | {md_escape(' · '.join(c.front for c in group))} |")
        add("")

    add("## Покрытие частотного словаря")
    add("")
    add("Какая доля надёжных лемм общего словаря встречается на лицевых сторонах карточек колоды. Учитываются "
        "отдельные лексемы и слова внутри фраз. Леммы отобраны так же, как в разделе о пропусках ниже.")
    add("")
    add("| Ранг | Лемм в словаре | Есть в колоде | Покрытие |")
    add("|---|---:|---:|---:|")
    for band in coverage:
        add(f"| {band.label} | {band.total} | {band.covered} | {band.covered / max(1, band.total):.0%} |")
    add("")
    if "coverage.png" in charts:
        add("![Покрытие](coverage.png)")
        add("")
    add("## Частые слова, которых нет в колоде")
    add("")
    missing = [
        row for row in reliable_reference_words(index, 3000) if row[1] in CONTENT_POS and row[0] not in known_words
    ]
    add(f"Слова-кандидаты (существительные, глаголы, прилагательные, наречия) с рангом до 3000 среди надёжных лемм "
        f"общего словаря, которых нет на лицевой стороне ни одной карточки, ни как лемма, ни как слово фразы: "
        f"**{len(missing)}**. «Надёжные» значит три условия: лемма есть и в Wiktionary, и в GreekLex 2; "
        f"не меньше половины её частоты дают однозначные формы; это не вариант или диалектная форма. Так "
        f"отсекаются артефакты вроде «εγώ» (ego) или «παιδιά» (игра). Первые 80:")
    add("")
    add("Список стоит проверять глазами: часть слов покрыта колодой через синоним или другую запись, а часть "
        "лемм Wiktionary — формы, которые заведены отдельной статьёй.")
    add("")
    add("| Ранг | Слово | Часть речи | Zipf | Значение (Wiktionary) |")
    add("|---:|---|---|---:|---|")
    for word, pos, gloss, zipf, rank in missing[:80]:
        add(f"| {rank} | {word} | {POS_LABELS.get(pos, pos)} | {zipf:.2f} | {md_escape(gloss)} |")
    add("")

    add("## Качество сопоставления")
    add("")
    methods = Counter(resolution_quality(c.result.methods) for c in lexemes)
    add("| Как найдены формы | Лексем |")
    add("|---|---:|")
    for label, count in methods.most_common():
        add(f"| {label} | {count} |")
    add("")
    ambiguous = sorted((c for c in lexemes if c.result.homograph_share >= 0.5), key=lambda c: -c.result.subtlex_upper)
    add(f"Лексем, у которых больше половины словоупотреблений SUBTLEX приходится на омографы: **{len(ambiguous)}**. "
        "Счёт таких форм делится между леммами пропорционально частоте лемм в GreekLex. Если у леммы нет "
        "независимой частоты, она получает равную долю. Поэтому их Zipf менее надёжен. «Верхняя граница» — "
        "Zipf при условии, что все совпадающие формы относятся к этой карточке.")
    add("")
    if ambiguous:
        add("| Карточка | Леммы | Zipf | Верхняя граница | Доля омографов |")
        add("|---|---|---:|---:|---:|")
        for card in ambiguous[:30]:
            r = card.result
            upper = zipf_from_count(r.subtlex_upper, index.corpus_millions, index.types_millions)
            add(f"| {md_escape(card.front)} | {md_escape(', '.join(r.lemma_words))} | {r.zipf:.2f} | "
                f"{upper:.2f} | {r.homograph_share:.0%} |")
        add("")
    if not_found:
        add(f"Лексемы без частоты ({len(not_found)}):")
        add("")
        add(", ".join(md_escape(c.front) for c in not_found))
        add("")
    if phrases_missing or empty:
        add(f"Карточки без распознанных греческих слов: {len(phrases_missing) + len(empty)}.")
        add("")

    add("## Метод")
    add("")
    add("- **SUBTLEX-GR** (Dimitropoulou et al., 2010) — 27.8 млн словоупотреблений из субтитров. Это частоты "
        "словоформ, поэтому они свёрнуты в леммы по таблицам склонения и спряжения английского Wiktionary "
        "(выгрузка kaikki.org). У глагола суммируются все личные формы, времена и залоги из таблицы. "
        "У прилагательного — все роды, падежи и числа, без сравнительной и превосходной степени.")
    add("- **GreekLex 2** (Kyparissiadis et al., 2017) — частоты лемм письменного Hellenic National Corpus.")
    add("- Если одна словоформа принадлежит нескольким леммам (например, «καλά»), её счёт делится между ними "
        "пропорционально общей частоте лемм.")
    add("- **Комбинированный Zipf** — среднее двух источников; если слова нет в GreekLex, берётся только SUBTLEX-GR.")
    add("- Артикль снимается. Несколько форм на карточке («μεγάλος, μεγάλη, μεγάλο», «ο φίλος, η φίλη», "
        "«μιλάω, μιλώ») объединяются, и каждая словоформа считается один раз. Артикль множественного числа "
        "(«οι σπουδές») ограничивает подсчёт формами множественного числа.")
    add("- Фразы оцениваются по самому редкому слову: в источниках нет частот словосочетаний.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolution_quality(methods: list[str]) -> str:
    if {"guessed", "participle", "lemma_guessed"} & set(methods):
        return "парадигма достроена по окончанию (в Wiktionary нет таблицы форм)"
    if "unresolved" in methods:
        return "нет в Wiktionary, только сама словоформа"
    if "form_of" in methods:
        return "через таблицу форм другой леммы (λιγοστεύει → λιγοστεύω, οι σπουδές → σπουδή)"
    return "словарная форма и таблица форм из Wiktionary"


VARIANT_GLOSS_PATTERN = re.compile(
    r"\b(form of|variant of|dialect|archaic|obsolete|dated|Cypriot|Katharevousa|Ancient Greek)\b", re.IGNORECASE
)


def card_table(cards: list[CardResult], extra: tuple[str, object] | None = None) -> str:
    header = "| Карточка | Леммы | Zipf | SUBTLEX | GreekLex | Ранг |"
    divider = "|---|---|---:|---:|---:|---:|"
    if extra:
        header += f" {extra[0]} |"
        divider += "---:|" if extra[0] == "Δ" else "---|"
    rows = [header, divider]
    for card in cards:
        r = card.result
        row = (f"| {md_escape(card.front)} | {md_escape(', '.join(r.lemma_words) or '—')} | {r.zipf:.2f} | "
               f"{r.subtlex_zipf:.2f} | {fmt(r.greeklex_zipf)} | {r.rank} |")
        if extra:
            row += f" {md_escape(str(extra[1](card)))} |"
        rows.append(row)
    return "\n".join(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="Download SUBTLEX-GR, GreekLex 2 and kaikki Greek.")
    download.add_argument("--force", action="store_true", help="Download again even if files exist.")

    build = subparsers.add_parser("build", help="Build the frequency index from downloaded sources.")
    build.add_argument("--subtlex", type=Path, default=DEFAULT_SUBTLEX_PATH)
    build.add_argument("--greeklex", type=Path, default=DEFAULT_GREEKLEX_PATH)
    build.add_argument("--kaikki", type=Path, default=DEFAULT_KAIKKI_PATH)

    lookup_parser = subparsers.add_parser("lookup", help="Look up frequency for words or card fronts.")
    lookup_parser.add_argument("words", nargs="+")

    report_parser = subparsers.add_parser("report", help="Write a deck frequency report.")
    report_parser.add_argument("--deck", default=DEFAULT_DECK)
    report_parser.add_argument("--cards-db", type=Path, default=DEFAULT_CARDS_DB_PATH)
    report_parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "download":
        download_sources(args)
    elif args.command == "build":
        build_index(args)
    elif args.command == "lookup":
        lookup(args)
    else:
        report(args)


if __name__ == "__main__":
    main()
