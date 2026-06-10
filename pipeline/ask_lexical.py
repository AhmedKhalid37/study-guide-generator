"""Shared deterministic lexical tokenisation for Ask Your Guide retrieval.

Ask Slice 25B (lexical retrieval hygiene). The Ask retrieval path scores a query
against a prepared chunk index using a dependency-free tf-idf. For that to work
the *indexed* terms (built in ``ask_context``) and the *query* terms (scored in
``ask_sessions``) must be produced by the **same** normaliser — any divergence
silently breaks retrieval. Before this slice each module had its own tokenizer
(bare ``[a-z0-9]{2,}`` lowercasing) and no stopword/plural hygiene, which let
common function words ("the", "it", "on") dominate scoring and starved
paraphrased queries of signal. This module centralises that logic.

Hard constraints (mirrors the rest of the Ask stack):
  * pure stdlib, no new dependency, no model/provider/secret access;
  * fully deterministic — same input always yields the same term map;
  * conservative — only well-known English function words are dropped and only
    safe trailing-plural normalisation is applied, so domain/technical tokens
    ("l2", "dropout", "sigmoid", "f1") survive intact.

Both the index build and the query scorer call :func:`lexical_terms`, so they can
never drift apart.
"""
from __future__ import annotations

import re
from collections import Counter

# Lexical terms: lowercased alphanumeric runs (length >= 2 to drop single-char
# noise). Identical to the historical pattern so token *segmentation* is
# unchanged; the new behaviour is the stopword filter + plural normalisation.
_TERM_RE = re.compile(r"[a-z0-9]{2,}")

# A small, built-in English stopword set. Deliberately limited to function words
# (articles, pronouns, auxiliaries, prepositions, conjunctions, common
# question/determiner words) so it never strips domain vocabulary. Kept local and
# dependency-free — no NLTK / spaCy / model.
STOPWORDS: frozenset[str] = frozenset(
    {
        "about", "above", "after", "again", "against", "all", "am", "an", "and",
        "any", "are", "as", "at", "be", "because", "been", "before", "being",
        "below", "between", "both", "but", "by", "can", "could", "did", "do",
        "does", "doing", "done", "down", "during", "each", "few", "for", "from",
        "further", "had", "has", "have", "having", "he", "her", "here", "hers",
        "him", "his", "how", "if", "in", "into", "is", "it", "its", "just", "me",
        "mine", "more", "most", "my", "no", "nor", "not", "now", "of", "off",
        "on", "once", "only", "or", "other", "our", "ours", "out", "over", "own",
        "same", "she", "should", "so", "some", "such", "than", "that", "the",
        "their", "theirs", "them", "then", "there", "these", "they", "this",
        "those", "through", "to", "too", "under", "until", "up", "very", "was",
        "we", "were", "what", "when", "where", "which", "while", "who", "whom",
        "why", "will", "with", "would", "you", "your", "yours",
    }
)


def normalize_token(token: str) -> str:
    """Conservatively fold a regular trailing English plural to its singular.

    Only a single trailing ``-s`` is removed, and only when the token is long
    enough and does not end in a doubled ``ss`` (so "loss"/"class"/"process"
    survive). This deliberately covers just the regular ``word + s`` plural —
    which keeps the *singular* and *plural* forms folding to the SAME stem
    ("example"/"examples" -> "example", "weight"/"weights" -> "weight"), the
    property that lets a query term match an indexed term.

    A naive ``-es`` rule is intentionally avoided: it would map "examples" ->
    "exampl" while "example" -> "example", breaking that symmetry, and only
    helps the rarer sibilant plurals (box/boxes). Verb-tense stemming
    (``-ing``/``-ed``) is also avoided — it risks mangling technical tokens
    ("string", "based") for little retrieval gain. Deterministic and
    explainable by construction.
    """
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def lexical_terms(text: str) -> dict[str, int]:
    """Normalised term-frequency map for one piece of text.

    Lowercase → segment on ``[a-z0-9]{2,}`` → drop stopwords → fold simple
    plurals. Used for BOTH index terms and query terms so the two are always
    produced identically.
    """
    counts: Counter[str] = Counter()
    for raw in _TERM_RE.findall(text.lower()):
        if raw in STOPWORDS:
            continue
        counts[normalize_token(raw)] += 1
    return dict(counts)
