"""Behavior tests for runtime separation, non-replay, write scope and file completion."""

from dataclasses import replace
import gzip
import json

import pytest

from grandma2_toolkit.service import Toolkit, object_path, xml_fingerprint
from grandma2_toolkit.transport import MA2Client, MA2Error, TelnetDecoder, validate_command


def test_both_endpoints_are_identified(consoles):
    config, onpc, ma3d = consoles
    result = Toolkit(config).connections()
    assert result["same_show_name"]
    assert result["endpoints"]["onpc"]["port"] == onpc.server_address[1]
    assert result["endpoints"]["ma3d"]["port"] == ma3d.server_address[1]
    assert "test-secret" not in json.dumps(result)


def test_complete_unicode_reply_and_error(consoles):
    config, _, _ = consoles
    with MA2Client(config) as client:
        assert "灯具" in client.command("List Camera 50")
        with pytest.raises(MA2Error, match="rejected"):
            client.command("BadCommand")


def test_commands_and_show_guard_in_patch_context(consoles):
    config, _, _ = consoles
    commands = ["ChangeDest EditSetup", "ChangeDest 4", "List 1.*"]
    result = Toolkit(replace(config, allow_write=True)).execute(commands, "codex")
    assert "灯具" in result["replies"][-1]


def test_write_disabled_sends_no_mutation(consoles):
    config, onpc, _ = consoles
    with pytest.raises(PermissionError):
        Toolkit(config).execute(["Assign Camera 50 /X=1"], "codex")
    assert not any(c.startswith("Assign") for c in onpc.commands)


def test_wrong_show_sends_no_mutation(consoles):
    config, onpc, _ = consoles
    with pytest.raises(MA2Error, match="Show"):
        Toolkit(replace(config, allow_write=True)).execute(["Assign Camera 50 /X=1"], "other")
    assert not any(c.startswith("Assign") for c in onpc.commands)


def test_batch_stops_at_error_and_audits_partial_execution(consoles):
    config, onpc, _ = consoles
    toolkit = Toolkit(replace(config, allow_write=True))
    with pytest.raises(MA2Error):
        toolkit.execute(["Assign Camera 50 /X=1", "BadCommand", "Assign Camera 50 /X=2"], "codex")
    assert onpc.commands.count("Assign Camera 50 /X=1") == 1
    assert "Assign Camera 50 /X=2" not in onpc.commands
    audit = json.loads(next(config.output_dir.glob("*/audit.json")).read_text())
    assert audit["ok"] is False
    assert audit["commands"][0]["outcome"] == "acknowledged"
    assert audit["commands"][1]["outcome"] == "unknown"
    assert "test-secret" not in json.dumps(audit)


def test_marker_echo_cannot_pass_completion(consoles):
    config, onpc, _ = consoles
    with MA2Client(config) as client:
        onpc.omit_marker = True
        with pytest.raises(MA2Error, match="timed out"):
            client.command("Assign Camera 50 /X=1")
    assert onpc.commands.count("Assign Camera 50 /X=1") == 1


def test_failed_login_does_not_leak_password(consoles):
    config, onpc, ma3d = consoles
    onpc.fail_login = ma3d.fail_login = True
    with pytest.raises(MA2Error) as error:
        with MA2Client(config):
            pass
    assert config.password not in str(error.value)


@pytest.mark.parametrize("value", ["Page 3; Delete Page 3", 'Page 3 /cmd="Off"', "Page 3\nOff", "Lua 1", "Root -1"])
def test_query_rejects_command_injection(value):
    with pytest.raises(ValueError):
        object_path(value)
    with pytest.raises(ValueError):
        Toolkit().list_objects(value)


@pytest.mark.parametrize("value", ["Sequence 1 Cue 1; Off", "Root 10.4.* /nc",
                                   "ViewButton 2.1 /screen=2 /cmd=Off", "LiveSetup.Layers\nSaveShow"])
def test_list_rejects_unsupported_suffixes(value):
    with pytest.raises(ValueError):
        Toolkit().list_objects(value)


@pytest.mark.parametrize("obj, directory", [("Effect 1 Thru 10", "effects"),
                                            ("MAtricks 10", "matricks"), ("Macro 9", "macros")])
def test_native_pool_export_directory(consoles, obj, directory):
    from pathlib import Path
    config, onpc, _ = consoles
    result = Toolkit(config).export_object(obj)
    assert Path(result["native_file"]).parent == onpc.runtime / directory
    assert Path(result["file"]).read_bytes() == Path(result["native_file"]).read_bytes()


def test_export_and_fingerprint(consoles):
    config, _, _ = consoles
    result = Toolkit(config).export_object("Page 3")
    from pathlib import Path
    data = Path(result["file"]).read_bytes()
    assert result["fingerprint"] == xml_fingerprint(data.replace(b'"now"', b'"later"'))
    assert result["fingerprint"] != xml_fingerprint(data.replace(b'"P3"', b'"changed"'))


def test_backup_waits_for_new_gzip(consoles):
    config, onpc, _ = consoles
    source = onpc.runtime / "shows/codex.show.gz"
    source.write_bytes(gzip.compress(b"old-show"))
    result = Toolkit(replace(config, allow_write=True)).backup_show("codex")
    from pathlib import Path
    assert gzip.decompress(Path(result["file"]).read_bytes()) == b"new-show"


def test_transform_defaults_to_ma3d_and_uses_dotted_rotation(consoles):
    config, onpc, ma3d = consoles
    result = Toolkit(replace(config, allow_write=True)).set_transform("Camera 50", "codex", {"rx": -2, "z": 12.8})
    assert "Assign Camera 50 /Rot.X=-2 /Z=12.8" in ma3d.commands
    assert not any(c.startswith("Assign") for c in onpc.commands)
    assert result["visual_acceptance"] is False


def test_limits_and_fragmented_telnet():
    with pytest.raises(ValueError):
        validate_command("x" * 481)
    with pytest.raises(ValueError):
        validate_command("List\nPage")
    decoder = TelnetDecoder()
    assert decoder.feed(b"abc\xff")[0] == b"abc"
    assert decoder.feed(bytes([251])) == (b"", b"")
    assert decoder.feed(bytes([1]) + b"def") == (b"def", bytes([255, 254, 1]))
    assert decoder.feed(bytes([255, 250, 1, 2, 255, 240]) + b"ok")[0] == b"ok"


def test_transform_validation_before_connect(tmp_path):
    from grandma2_toolkit.config import Config
    toolkit = Toolkit(Config(output_dir=tmp_path))
    for obj, values in [("Fixture 73", {"rx": 180}), ("Camera 50", {"rx": float("nan")}),
                        ("Camera 50", {"fov": 90}), ("Root 10.6.3.76", {"fov": .64})]:
        with pytest.raises(ValueError):
            toolkit.set_transform(obj, "codex", values)
    assert not list(tmp_path.iterdir())


def test_capture_returns_image_without_claiming_acceptance(tmp_path, monkeypatch):
    from grandma2_toolkit import capture, server
    from grandma2_toolkit.config import Config
    import base64
    # A tiny fixture image tests packaging only, not the Windows capture implementation.
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8x0AAAAASUVORK5CYII=")

    def fake_capture(path, title):
        path.write_bytes(png)
        return {"file": str(path), "window_title": title, "width": 1, "height": 1}

    monkeypatch.setattr(capture, "capture_window", fake_capture)
    monkeypatch.setattr(server, "toolkit", Toolkit(Config(output_dir=tmp_path)))
    result = server.ma3d_capture("MA 3D")
    assert result.structuredContent["visual_acceptance"] is False
    assert result.content[1].type == "image"
    assert base64.b64decode(result.content[1].data) == png


def test_no_credentials_in_config_repr_and_auth_rejected(tmp_path):
    from grandma2_toolkit.config import Config
    config = Config(password="test-secret", output_dir=tmp_path)
    assert "test-secret" not in repr(config)
    with pytest.raises(ValueError, match="Authentication"):
        Toolkit(config).execute(['Login "someone" "secret"'], "codex")
    with pytest.raises(ValueError, match="unsupported"):
        replace(config, password='bad";Off').validate()
