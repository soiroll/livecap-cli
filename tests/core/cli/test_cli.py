from pathlib import Path
from io import StringIO
import sys

import pytest

from livecap_cli import cli


@pytest.mark.parametrize("ensure_ffmpeg", [False])
def test_cli_diagnose_reports_i18n(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ensure_ffmpeg: bool) -> None:
    monkeypatch.setenv("LIVECAP_CORE_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("LIVECAP_CORE_CACHE_DIR", str(tmp_path / "cache"))

    report = cli.diagnose(ensure_ffmpeg=ensure_ffmpeg)

    assert report.models_root
    assert report.cache_root
    assert report.i18n.fallback_count >= 0
    assert report.i18n.translator.registered in (True, False)
    assert isinstance(report.available_engines, list)
    # Phase 2: New diagnostic fields
    assert isinstance(report.cuda_available, bool)
    assert isinstance(report.vad_backends, list)
    # cuda_device can be None or str
    assert report.cuda_device is None or isinstance(report.cuda_device, str)


class TestCLISubcommands:
    """Tests for CLI subcommand structure (Issue #74 Phase 6B)."""

    def test_cli_no_command_shows_help(self, capsys: pytest.CaptureFixture) -> None:
        """No command shows help and returns 0."""
        result = cli.main([])
        captured = capsys.readouterr()
        assert result == 0
        assert "livecap-cli" in captured.out
        assert "info" in captured.out
        assert "devices" in captured.out
        assert "engines" in captured.out
        assert "translators" in captured.out
        assert "transcribe" in captured.out

    def test_cli_info_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """info command shows diagnostics."""
        monkeypatch.setenv("LIVECAP_CORE_MODELS_DIR", str(tmp_path / "models"))
        monkeypatch.setenv("LIVECAP_CORE_CACHE_DIR", str(tmp_path / "cache"))

        result = cli.main(["info"])
        captured = capsys.readouterr()

        assert result == 0
        assert "livecap-cli diagnostics" in captured.out
        assert "FFmpeg:" in captured.out
        assert "Models root:" in captured.out

    def test_cli_info_as_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """info --as-json outputs valid JSON."""
        import json

        monkeypatch.setenv("LIVECAP_CORE_MODELS_DIR", str(tmp_path / "models"))
        monkeypatch.setenv("LIVECAP_CORE_CACHE_DIR", str(tmp_path / "cache"))

        result = cli.main(["info", "--as-json"])
        captured = capsys.readouterr()

        assert result == 0
        data = json.loads(captured.out)
        assert "models_root" in data
        assert "ffmpeg_path" in data
        assert "available_engines" in data

    def test_cli_engines_command(self, capsys: pytest.CaptureFixture) -> None:
        """engines command lists available engines."""
        result = cli.main(["engines"])
        captured = capsys.readouterr()

        assert result == 0
        # At least whispers2t should be available
        assert "whispers2t" in captured.out

    def test_cli_translators_command(self, capsys: pytest.CaptureFixture) -> None:
        """translators command lists available translators."""
        result = cli.main(["translators"])
        captured = capsys.readouterr()

        assert result == 0
        # At least google translator should be listed
        assert "google" in captured.out

    def test_cli_transcribe_requires_input(self, capsys: pytest.CaptureFixture) -> None:
        """transcribe without input shows error."""
        result = cli.main(["transcribe"])
        captured = capsys.readouterr()

        assert result == 1
        assert "Error:" in captured.err

    def test_cli_transcribe_realtime_requires_mic(self, capsys: pytest.CaptureFixture) -> None:
        """transcribe --realtime without --mic shows error."""
        result = cli.main(["transcribe", "--realtime"])
        captured = capsys.readouterr()

        assert result == 1
        assert "--mic" in captured.err
