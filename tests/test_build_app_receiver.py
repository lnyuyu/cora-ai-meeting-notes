"""scripts/build-app.sh refuses a team build without the beta receiver, before
any slow step (0.4.4: a team build made without it reached a teammate and
queued 120 events that could never leave the Mac)."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build-app.sh"


def run(tmp_path, *args, env_file: str | None = None, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CORA_BETA_")}
    env["HOME"] = str(tmp_path)
    if env_file is not None:
        (tmp_path / ".cora-signing").mkdir()
        (tmp_path / ".cora-signing/beta-receiver.env").write_text(env_file)
    env.update(extra)
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=30)


def preflight(tmp_path, env_file: str) -> dict:
    """The env-file block of the script, run on its own (the rest builds the app)."""
    lines = SCRIPT.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("BETA_ENV_FILE="))
    end = next(i for i, l in enumerate(lines) if l.startswith("HAVE_RECEIVER=0"))
    (tmp_path / ".cora-signing").mkdir()
    (tmp_path / ".cora-signing/beta-receiver.env").write_text(env_file)
    env = {k: v for k, v in os.environ.items() if not k.startswith("CORA_BETA_")}
    env["HOME"] = str(tmp_path)
    out = subprocess.run(["bash", "-c", "\n".join(lines[start:end]) + '\necho "$CORA_BETA_RECEIVER_URL|$CORA_BETA_TOKEN"'],
                         capture_output=True, text=True, env=env, timeout=10, check=True).stdout.strip()
    url, token = out.split("|", 1)
    return {"url": url, "token": token}


def test_a_team_build_without_the_receiver_stops_at_once(tmp_path):
    result = run(tmp_path, "--team")
    assert result.returncode == 1
    assert "a team build needs the beta receiver" in result.stderr
    assert "--team --no-telemetry" in result.stderr
    assert "Building native helpers" not in result.stdout


def test_an_empty_env_file_does_not_count(tmp_path):
    result = run(tmp_path, "--team", env_file="CORA_BETA_RECEIVER_URL=\nCORA_BETA_TOKEN=\n")
    assert result.returncode == 1 and "needs the beta receiver" in result.stderr


def test_no_telemetry_only_goes_with_team(tmp_path):
    result = run(tmp_path, "--no-telemetry")
    assert result.returncode == 1 and "--no-telemetry only goes with --team" in result.stderr


def test_the_env_file_supplies_the_receiver_and_a_token_may_contain_equals(tmp_path):
    got = preflight(tmp_path, "CORA_BETA_RECEIVER_URL=https://receiver.example\nCORA_BETA_TOKEN=abc=def\nOTHER=x\n")
    assert got == {"url": "https://receiver.example", "token": "abc=def"}
