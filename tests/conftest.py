from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def nlp():
    from apiterm.annotate import load_model
    return load_model()


@pytest.fixture(scope="session")
def sample_spec() -> bytes:
    return (DATA / "sample_spec.yaml").read_bytes()


@pytest.fixture(scope="session")
def reference_db(tmp_path_factory, nlp):
    """Tiny synthetic 'news' reference: enough to exercise specificity, not real data."""
    from apiterm.reference import build_reference
    news = [
        "The company will file a lawsuit against the government on Monday.",
        "The minister will sign an agreement with the union.",
        "The president gave a speech about the economy.",
        "Police arrested a man after the robbery.",
        "The access to the building was restricted by the guards.",
        "Voters will create a new party before the election.",
        "The key to the success is the team.",
        "The list of guests includes the mayor.",
        "A new token of appreciation was given to the winner.",
    ] * 30 + ["The mayor will delete the old record from the archive."] * 5
    path = tmp_path_factory.mktemp("ref") / "ref.db"
    build_reference(news, path, nlp, source="synthetic test news", dedup=False)
    return path
