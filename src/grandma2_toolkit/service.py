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
from typing import Literal
import uuid
import xml.etree.ElementTree as ET
import zlib

from .config import Config
from .transport import CommandRejected, FEEDBACK_PREFIX, MA2Client, MA2Error, validate_command

POOLS = (
    "Page", "Executor", "Sequence", "Effect", "Preset", "Camera", "Group", "View",
    "ViewButton", "Layout", "Fixture", "Channel", "Root", "UserProfile", "MAtricks", "Macro",
)
POOL = "(?:" + "|".join(POOLS) + ")"
ADDRESS = r"[0-9]+(?:\.[0-9]+)*"
OBJECT = re.compile(rf"{POOL}(?: {ADDRESS}(?: Thru {ADDRESS})?)?", re.I)
# List supports child enumeration, Cue ranges and a screen qualifier. Export takes
# an object followed by a filename, so its argument grammar stays separate.
LIST_RANGE = rf"{ADDRESS}(?:\.\*| Thru(?: {ADDRESS})?)?"
# These objects are queryable with List. Native export directories and formats
# are object-specific, so adding a query does not automatically enable export.
LIST_ONLY = (
    "Screen", "Layer", "FixtureType", "Timecode", "TimecodeSlot", "Timer", "Agenda",
    "World", "Filter", "Mask", "Form", "Plugin", "SpecialMaster", "Attribute", "Feature",
    "PresetType", "ChannelPage", "ButtonPage", "FaderPage", "ViewPage", "Remote", "Cue",
)
LIST_OBJECT = re.compile(
    rf"(?:(?:{POOL}|{'|'.join(LIST_ONLY)})(?: {LIST_RANGE})?"
    rf"|Sequence [0-9]+ Cue(?: {LIST_RANGE})?"
    rf"|ViewButton {LIST_RANGE} /screen=[0-9]+"
    r"|LiveSetup\.(?:FixtureTypes|Layers)|NetworkInfo)", re.I)
EXPORT_DIRS = {"effect": "effects", "matricks": "matricks", "macro": "macros"}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
NS = {"m": "http://schemas.malighting.de/grandma2/xml/MA"}
PlaybackAction = Literal["go", "back", "pause", "off", "goto", "level"]


def object_path(value: str) -> str:
    """A narrow object grammar prevents query/export arguments becoming command chains."""
    if not OBJECT.fullmatch(value):
        raise ValueError("Use an object path such as 'Executor 3.1 Thru 3.8' or 'Root 10.6.3.76'")
    return value


def validate_show_name(name: str) -> None:
    """Use a bare MA show name as a quoted command argument or native file stem."""
    if (not re.fullmatch(r"[\w .-]+", name) or name != name.strip() or name.endswith(".")
            or name.lower().endswith(".show.gz")):
        raise ValueError("Supply a Show name without a path, command syntax or .show.gz suffix")


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
        if not LIST_OBJECT.fullmatch(object):
            raise ValueError("Use a List object such as 'Root 10.4.*' or 'Sequence 121 Cue 1 Thru 5'")
        command = "List " + object
        with self.operation("list", target, object) as (folder, record), self.client_factory(self.config, target) as client:
            return {"reply": self._send(client, record, command, True), "audit_dir": str(folder)}

    def probe(self, objects: list[str] | None = None, target="onpc"):
        """Sample first slots by default. Retain native replies for inspecting the evidence."""
        if objects is None:
            objects = [f"{pool} 1 Thru 3" for pool in (*POOLS, *LIST_ONLY)]
            objects.extend(("LiveSetup.Layers", "LiveSetup.FixtureTypes", "NetworkInfo"))
        if not 1 <= len(objects) <= 64 or not all(LIST_OBJECT.fullmatch(obj) for obj in objects):
            raise ValueError("Supply 1 to 64 List object expressions")
        for obj in objects:
            validate_command("List " + obj)
        with self.operation("probe", target, objects) as (folder, record), self.client_factory(self.config, target) as client:
            show = client.value("SHOWFILE")
            results = []
            for obj in objects:
                try:
                    reply = self._send(client, record, "List " + obj, True)
                except CommandRejected as exc:
                    # Only explicit rejections are local to one query. Lost framing,
                    # disconnects or timeouts must stop the rest of the batch.
                    record["commands"][-1].update(outcome="rejected", error=str(exc))
                    results.append({"object": obj, "status": "rejected", "sample": str(exc)[:512]})
                    continue
                empty = re.search(FEEDBACK_PREFIX + r"(?:WARNING,\s*)?NO OBJECTS FOUND\b", reply, re.I | re.M)
                status = "empty" if empty else "acknowledged"
                results.append({"object": obj, "status": status, "sample": reply[:512]})
            return {"target": target, "show_at_start": show, "results": results, "audit_dir": str(folder)}

    def read_dmx(self, universe: int, address: int, count: int = 1, target="onpc"):
        """Read consecutive slots via a fixed Lua expression; one request stays in one universe."""
        if not all(type(n) is int for n in (universe, address, count)):
            raise ValueError("Universe, address and count must be integers")
        if not (1 <= universe <= 256 and 1 <= address <= 512 and 1 <= count <= 64 and address + count - 1 <= 512):
            raise ValueError("Use universe 1..256, address 1..512 and 1..64 slots within that universe")
        start = (universe - 1) * 512 + address
        cmd = (f'Lua "local r={{}};for i={start},{start + count - 1} do '
               "r[#r+1]=tostring(gma.show.getdmx(i)) end;"
               "gma.feedback('G2TK_DMX='..table.concat(r,','))\"")
        with self.operation("read_dmx", target) as (folder, record), self.client_factory(self.config, target) as client:
            reply = self._send(client, record, cmd)
            # MA2 Lua can render integral DMX bytes as "0.0". Preserve a bad
            # or fractional sample as an error instead of rounding it to a byte.
            byte = r"[0-9]{1,3}(?:\.0+)?"
            match = re.search(FEEDBACK_PREFIX + rf"G2TK_DMX=({byte}(?:,{byte})*)[ \t]*$", reply, re.M)
            values = [int(s.partition(".")[0]) for s in match[1].split(",")] if match else []
            if len(values) != count or any(value > 255 for value in values):
                raise MA2Error("Incomplete or invalid DMX feedback; no sample confirmed")
            return {"universe": universe, "address": address, "values": values, "audit_dir": str(folder)}

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

    def playback(self, executor: str, action: PlaybackAction, expected_show: str,
                 cue: str | None = None, level: int | None = None):
        """Always address one explicit onPC executor, independent of the user's current page."""
        if not re.fullmatch(r"[1-9][0-9]*\.[1-9][0-9]*", executor):
            raise ValueError("Use one executor as page.slot, e.g. 2.1")
        obj = "Executor " + executor
        if action == "goto" and isinstance(cue, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", cue) and level is None:
            command = f"Goto Cue {cue} {obj}"
        elif action == "level" and type(level) is int and 0 <= level <= 100 and cue is None:
            command = f"{obj} At {level}"
        elif action in ("go", "back", "pause", "off") and cue is None and level is None:
            verb = {"go": "Go", "back": "GoBack", "pause": "Pause", "off": "Off"}[action]
            command = f"{verb} {obj}"
        else:
            raise ValueError("goto needs a Cue number, level needs 0..100, other actions take neither")
        return self.execute([command], expected_show, "onpc")

    def _local_runtime(self, client) -> Path:
        # Native export/save files exist on the endpoint machine, not on a remote caller.
        if self.config.host not in LOCAL_HOSTS:
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
            directory = EXPORT_DIRS.get(object.split()[0].lower(), "importexport")
            source = runtime / directory / (name + ".xml")
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
                raise MA2Error(f"Export did not finish; check native {directory} folder")
            output = folder / "object.xml"
            output.write_bytes(data)
            result = {"file": str(output), "native_file": str(source), "fingerprint": digest, "audit_dir": str(folder)}
            record["result"] = result
            return result

    def new_show(self, name: str, expected_show: str):
        """Save the previous show and switch onPC; confirm the active name over Telnet."""
        validate_show_name(name)
        if name.casefold() == expected_show.casefold():
            raise ValueError("Choose a different name for the new Show")
        with self.operation("new_show", "onpc", name) as (folder, record), self.client_factory(self.config, "onpc") as client:
            self._guard(client, expected_show)
            if self.config.host in LOCAL_HOSTS:
                if (self._local_runtime(client) / "shows" / (name + ".show.gz")).exists():
                    raise FileExistsError("New Show destination already exists")
            # /save explicitly preserves outstanding work. Keep native prompts for
            # any other conflict instead of forcing a reset or an overwrite.
            self._send(client, record, f'NewShow "{name}" /save')
            deadline = time.monotonic() + self.config.timeout
            while time.monotonic() < deadline:
                if client.value("SHOWFILE") == name:
                    result = {"previous_show": expected_show, "active_show": name,
                              "file_verified": False, "audit_dir": str(folder)}
                    record["result"] = result
                    return result
                time.sleep(.2)
            raise MA2Error("NewShow not confirmed; inspect the active Show and console prompts before retrying")

    def save_show(self, expected_show: str, name: str | None = None):
        return self._save_show(expected_show, name, backup=False)

    def backup_show(self, expected_show: str):
        return self._save_show(expected_show, None, backup=True)

    def _save_show(self, expected_show: str, name: str | None, backup: bool):
        verify_file = backup or self.config.host in LOCAL_HOSTS
        stem = name if name is not None else expected_show
        if name is not None:
            validate_show_name(name)
            if name.casefold() == expected_show.casefold():
                raise ValueError("Omit the name to save the current Show in place")
        elif verify_file and (not re.fullmatch(r"[\w .-]+", stem) or stem in (".", "..")):
            raise ValueError("Show name cannot contain path or console syntax characters")
        action = "backup" if backup else "save_show"
        with self.operation(action, "onpc", name or expected_show) as (folder, record), self.client_factory(self.config, "onpc") as client:
            self._guard(client, expected_show)
            source = None
            if verify_file:
                source = self._local_runtime(client) / "shows" / (stem + ".show.gz")
                if name is not None and source.exists():
                    raise FileExistsError("Save As destination already exists")
            before = source.stat().st_mtime_ns if source is not None and source.exists() else None
            command = f'SaveShow "{name}"' if name is not None else "SaveShow /noconfirm"
            reply = self._send(client, record, command)
            result = {"reply": reply, "file_verified": False, "audit_dir": str(folder)}
            if source is not None:
                data = self._wait_for_saved_show(source, before)
                output = source
                if backup:
                    output = folder / source.name
                    output.write_bytes(data)
                result.update(file=str(output), sha256=hashlib.sha256(data).hexdigest(), file_verified=True)
            record["result"] = result
            return result

    def _wait_for_saved_show(self, source: Path, before: int | None) -> bytes:
        deadline = time.monotonic() + max(30, self.config.timeout)
        while time.monotonic() < deadline:
            try:
                stamp = (source.stat().st_mtime_ns, source.stat().st_size)
                if stamp[0] != before:
                    data = source.read_bytes()
                    if not data.startswith(b"\x1f\x8b"):
                        raise gzip.BadGzipFile("Waiting for native gzip header")
                    gzip.decompress(data)
                    time.sleep(.5)
                    if stamp == (source.stat().st_mtime_ns, source.stat().st_size):
                        return data
            except (OSError, EOFError, zlib.error):
                pass
            time.sleep(.1)
        raise MA2Error("New SaveShow file not confirmed; inspect the selected drive before retrying")

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
