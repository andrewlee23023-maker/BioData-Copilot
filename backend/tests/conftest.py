import pytest


@pytest.fixture(autouse=True)
def offline_agent(monkeypatch):
    """
    Keep the suite deterministic and offline: no test may call the real Gemini API,
    even if GEMINI_API_KEY is set in the developer's .env. Tests that exercise the
    Gemini code paths set a fake key and mock the HTTP-calling functions themselves.
    """
    import backend.agent as agent
    monkeypatch.setattr(agent, "GEMINI_API_KEY", "")
