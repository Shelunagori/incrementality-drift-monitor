"""Guards for the deployment files (the image itself is built by Railway, not in CI)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_start_script_order():
    lines = [
        ln.strip()
        for ln in (ROOT / "backend/start.sh").read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    body = "\n".join(lines)
    assert (
        body.index("alembic upgrade head")
        < body.index("scripts.seed --if-empty")
        < body.index("uvicorn app.main:app")
    )
    assert '--port "${PORT:-8000}"' in body and "--workers 1" in body


def test_dockerfile_ships_docs_and_uses_start_script():
    text = (ROOT / "backend/Dockerfile").read_text()
    assert "COPY docs/ /app/docs/" in text
    assert 'CMD ["./start.sh"]' in text
    assert "uv sync --frozen --no-dev" in text


def test_railway_points_at_backend_dockerfile():
    text = (ROOT / "railway.toml").read_text()
    assert 'dockerfilePath = "backend/Dockerfile"' in text
    assert 'healthcheckPath = "/health"' in text


def test_keepalive_skips_without_secret():
    text = (ROOT / ".github/workflows/keepalive.yml").read_text()
    assert "*/3" in text and "secrets.HEALTH_URL" in text
    assert 'if [ -z "$HEALTH_URL" ]' in text and "exit 0" in text
