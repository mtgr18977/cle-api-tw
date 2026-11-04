import pytest

from apiterm.annotate import annotate_strings
from apiterm.candidates import dependency_candidates, surface_candidates


def sents(nlp, text):
    return next(iter(annotate_strings([text], nlp)))


def keys(cands):
    return {(c.pattern, c.key) for c in cands}


def run(nlp, text, fn):
    out = set()
    for s in sents(nlp, text):
        out |= fn(s)
    return keys(out)


def test_token_is_forced_to_noun(nlp):
    toks = sents(nlp, "The refresh token expires after one hour.")[0].toks
    tok = next(t for t in toks if t.text == "token")
    assert tok.pos == "NOUN" and tok.lemma == "token"
    assert toks[toks.index(tok) - 1].dep == "compound"        # refresh -> token


@pytest.mark.parametrize("text,verb", [("List access tokens.", "list"), ("Delete a webhook endpoint.", "delete"),
                                       ("Returns a list of keys.", "return")])
def test_initial_verb_fix_and_helper_token_dropped(nlp, text, verb):
    s = sents(nlp, text)[0]
    assert s.toks[0].lemma == verb and s.toks[0].pos == "VERB"
    assert s.text.split()[0].lower().startswith(verb[:3])      # "Please"/"It" not leaked
    assert s.toks[0].head == 0                                 # still the root


def test_lead_fix_not_applied_to_noun_phrase(nlp):
    s = sents(nlp, "List of scopes is attached.")[0]
    assert s.toks[0].text == "List" and s.toks[1].text == "of"


def test_surface_patterns(nlp):
    k = run(nlp, "Create an access token. Authenticate with a token. The list of scopes is long. "
                 "Use an expired token.", surface_candidates)
    assert ("V+N", "create token") in k
    assert ("N+N", "access token") in k
    assert ("V+Prep+N", "authenticate with token") in k
    assert ("N+of+N", "list of scope") in k
    assert ("Adj+N", "expired token") in k


def test_dependency_is_robust_to_intervening_words(nlp):
    text = "Creates a new access token for the user."
    assert ("V+N", "create token") not in run(nlp, text, surface_candidates)   # adjective intervenes
    assert ("V+N", "create token") in run(nlp, text, dependency_candidates)


def test_dependency_conjoined_verbs_and_passive(nlp):
    k = run(nlp, "Create or update a token. The key is deleted.", dependency_candidates)
    assert {("V+N", "create token"), ("V+N", "update token"), ("V+N", "delete key")} <= k


def test_acronyms_keep_case_and_identifiers_are_excluded(nlp):
    k = run(nlp, "Create an API key. Set the page_size value.", surface_candidates)
    assert ("N+N", "API key") in k
    assert not any("page_size" in c[1] for c in k)
