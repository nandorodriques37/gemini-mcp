import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _nomes(linhas):
    return {re.split(r"[<>=!~ ;\[]", l.strip(), maxsplit=1)[0].lower() for l in linhas if l.strip() and not l.startswith("#")}


def test_pyproject_declara_as_mesmas_dependencias():
    """A Vercel instala pelo pyproject.toml quando ele existe; requirements.txt fica ignorado."""
    proj = tomllib.loads((RAIZ / "pyproject.toml").read_text())["project"]
    req = (RAIZ / "requirements.txt").read_text().splitlines()
    assert _nomes(proj["dependencies"]) == _nomes(req)
    assert {"fastmcp", "google-genai", "httpx", "httpx2"} <= _nomes(proj["dependencies"])
