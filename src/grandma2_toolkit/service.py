"""Audited operations shared by the CLI and MCP; scene writes never imply visual acceptance."""

from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time
import uuid
import xml.etree.ElementTree as ET

from .config import Config
from .transport import MA2Client, MA2Error, validate_command

OBJECT = re.compile(r"(?:Page|Executor|Sequence|Effect|Preset|Camera|Group|View|ViewButton|Layout|Fixture|Channel|Root|UserProfile)(?: \d+(?:\.\d+)*(?: Thru \d+(?:\.\d+)*)?)?", re.I)
NS = {"m": "http://schemas.malighting.de/grandma2/xml/MA"}


def object_path(value: str) -> str:
    """A narrow object grammar prevents query/export arguments becoming command chains."""
    if not OBJECT.fullmatch(value):
        raise ValueError("Use an object path such as 'Executor 3.1 Thru 3.8' or 'Root 10.6.3.76'")
    return value


def xml_fingerprint(data: bytes) -> str:
    """Ignore export timestamps and indentation; keep every object attribute and child."""
    root = ET.fromstring(data)
    for info in root.findall("m:Info", NS):
        root.remove(info)
    for elem in root.iter():
        if elem.text is not None and not elem.text.strip():
            elem.text = None
        elem.tail = None
    return hashlib.sha256(ET.tostring(root)).hexdigest()


class Toolkit:
    """Serialize in-process commands; use a fresh verified connection for every operation."""

    def __init__(self, config: Config | None = None, client_factory=MA2Client):
        self.config = config or Config.from_env()
        self.client_factory = client_factory
        self.lock = threading.RLock()

    def _redact(self, value):
        text = json.dumps(value, ensure_ascii=False, default=str)
        if self.config.password:
            text = text.replace(self.config.password, "[redacted]")
        return json.loads(text)

    @contextmanager
    def operation(self, action: str, target: str, details=None):
        """Audit both failure and success, including partially executed batches."""
        with self.lock:
            folder = self.config.output_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:10])
            folder.mkdir(parents=True, exist_ok=False)
            record = {"action": action, "target": target, "details": details, "commands": [], "ok": False}
            try:
                yield folder, record
                record["ok"] = True
            except Exception as exc:
                record["error"] = self._redact(str(exc))
                raise
            finally:
                (folder / "audit.json").write_text(json.dumps(self._redact(record), ensure_ascii=False, indent=2), encoding="utf-8")

    def _send(self, client, record, command, allow_missing=False):
        item = {"command": command, "outcome": "unknown"}
        record["commands"].append(item)
        reply = client.command(command, allow_missing=allow_missing)
        item.update(reply=reply, outcome="acknowledged")
        return reply

    def _guard(self, client, expected_show: str):
        if not self.config.allow_write:
            raise PermissionError("Writes disabled; configure MA2_ALLOW_WRITE=1 for authorized operations")
        if not expected_show or client.value("SHOWFILE") != expected_show:
            raise MA2Error("Active Show does not match expected_show; no mutation sent")

    def status(self, target="onpc"):
        with self.operation("status", target) as (folder, record):
            with self.client_factory(self.config, target) as client:
                result = {"target": target, "host": self.config.host, "port": client.port,
                          "runtime": client.runtime, "show": client.value("SHOWFILE"),
                          "network_status": client.value("STATUS")}
                record["result"] = result
                return {**result, "audit_dir": str(folder)}

    def connections(self):
        """Keep both sockets open together and compare shows without changing either session."""
        with self.operation("connections", "both") as (folder, record), ExitStack() as stack:
            endpoints = {}
            for target in ("onpc", "ma3d"):
                try:
                    client = stack.enter_context(self.client_factory(self.config, target))
                    endpoints[target] = {"connected": True, "port": client.port, "runtime": client.runtime,
                                         "show": client.value("SHOWFILE"), "network_status": client.value("STATUS")}
                except (MA2Error, OSError, ValueError) as exc:
                    endpoints[target] = {"connected": False, "error": self._redact(str(exc))}
            matched = all(e["connected"] for e in endpoints.values()) and endpoints["onpc"]["show"] == endpoints["ma3d"]["show"]
            result = {"endpoints": endpoints, "same_show_name": matched,
                      "note": "Matching names alone do not prove both applications joined the same session."}
            record["result"] = result
            return {**result, "audit_dir": str(folder)}

    def list_objects(self, object: str, target="onpc"):
        command = "List " + object_path(object)
        with self.operation("list", target, object) as (folder, record), self.client_factory(self.config, target) as client:
            return {"reply": self._send(client, record, command, True), "audit_dir": str(folder)}

    def execute(self, commands: list[str], expected_show: str, target="onpc"):
        """Explicit general-purpose write channel. A batch is sequential, not transactional."""
        if not 1 <= len(commands) <= 100:
            raise ValueError("Send between 1 and 100 commands")
        for cmd in commands:
            validate_command(cmd)
            if re.search(r"\b(?:Login|Logout)\b", cmd, re.I):
                raise ValueError("Authentication commands are not accepted; use environment configuration")
        with self.operation("execute", target, commands) as (folder, record), self.client_factory(self.config, target) as client:
            replies = []
            for cmd in commands:
                # Another client can change the Show between commands; recheck each time.
                self._guard(client, expected_show)
                replies.append(self._send(client, record, cmd))
            return {"replies": replies, "audit_dir": str(folder), "visual_acceptance": False}

    def _local_runtime(self, client) -> Path:
        # Native export/save files exist on the endpoint machine, not on a remote caller.
        if self.config.host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("File export/backup requires a local endpoint; remote raw commands remain available")
        runtime = Path(client.runtime)
        if not runtime.is_absolute() or not runtime.is_dir():
            raise ValueError("Verified runtime directory is not locally accessible")
        return runtime

    def export_object(self, object: str, target="onpc"):
        object_path(object)
        with self.operation("export", target, object) as (folder, record), self.client_factory(self.config, target) as client:
            runtime = self._local_runtime(client)
            name = "g2tk_" + uuid.uuid4().hex
            source = runtime / "importexport" / (name + ".xml")
            self._send(client, record, f"Export {object} {name}")
            deadline = time.monotonic() + self.config.timeout
            while time.monotonic() < deadline:
                try:
                    data = source.read_bytes()
                    digest = xml_fingerprint(data)
                    break
                except (OSError, ET.ParseError):
                    time.sleep(.1)
            else:
                raise MA2Error("Export did not finish; check native importexport folder")
            output = folder / "object.xml"
            output.write_bytes(data)
            result = {"file": str(output), "native_file": str(source), "fingerprint": digest, "audit_dir": str(folder)}
            record["result"] = result
            return result

    def backup_show(self, expected_show: str):
        """Save onPC and copy only the new, stable, complete gzip; never reuse a previous save."""
        if not re.fullmatch(r"[\w .-]+", expected_show) or expected_show in (".", ".."):
            raise ValueError("Show name cannot contain path or console syntax characters")
        with self.operation("backup", "onpc", expected_show) as (folder, record), self.client_factory(self.config, "onpc") as client:
            self._guard(client, expected_show)
            source = self._local_runtime(client) / "shows" / (expected_show + ".show.gz")
            before = source.stat().st_mtime_ns if source.exists() else None
            self._send(client, record, "SaveShow /noconfirm")
            deadline = time.monotonic() + max(30, self.config.timeout)
            while time.monotonic() < deadline:
                try:
                    stamp = (source.stat().st_mtime_ns, source.stat().st_size)
                    if stamp[0] != before:
                        data = source.read_bytes()
                        gzip.decompress(data)
                        time.sleep(.5)
                        if stamp == (source.stat().st_mtime_ns, source.stat().st_size):
                            break
                except (OSError, EOFError):
                    pass
                time.sleep(.1)
            else:
                raise MA2Error("New SaveShow file not confirmed; no backup copied")
            output = folder / source.name
            output.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            result = {"file": str(output), "sha256": digest, "audit_dir": str(folder)}
            record["result"] = result
            return result

    def set_transform(self, object: str, expected_show: str, values: dict[str, float], target="ma3d"):
        """Set a verified Camera or scene body address, never fixture Pan/Tilt programmer values."""
        if not re.fullmatch(r"(?:Camera \d+|Root \d+(?:\.\d+){2,})", object, re.I):
            raise ValueError("Transform requires one Camera or explicit scene Root address")
        allowed = {"x": "X", "y": "Y", "z": "Z", "rx": "Rot.X", "ry": "Rot.Y", "rz": "Rot.Z", "fov": "FOV"}
        if not values or not set(values) <= allowed.keys():
            raise ValueError("Transform accepts x/y/z/rx/ry/rz/fov")
        if any(not math.isfinite(v) for v in values.values()):
            raise ValueError("Transform values must be finite")
        if "fov" in values and (not object.lower().startswith("camera ") or not 0 < values["fov"] < math.pi):
            raise ValueError("Camera FOV must be radians between 0 and pi")
        command = "Assign " + object + " " + " ".join(f"/{allowed[k]}={v:g}" for k, v in values.items())
        with self.operation("transform", target, {"object": object, "values": values}) as (folder, record), self.client_factory(self.config, target) as client:
            self._guard(client, expected_show)
            before = self._send(client, record, "List " + object)
            self._send(client, record, command)
            after = self._send(client, record, "List " + object)
            return {"before": before, "after": after, "audit_dir": str(folder),
                    "note": "Compare requested fields with readback. Raw List text is not an automatic numeric or visual pass.",
                    "visual_acceptance": False}

    def capture_ma3d(self, window_title: str | None = None):
        """Capture only a uniquely identified visible MA3D window; never control it."""
        from .capture import capture_window
        with self.operation("capture", "ma3d") as (folder, record):
            result = capture_window(folder / "ma3d.png", window_title)
            record["result"] = result
            return {**result, "audit_dir": str(folder), "visual_acceptance": False,
                    "note": "Inspect this image and confirm camera/lighting state; a screenshot alone does not pass acceptance."}
