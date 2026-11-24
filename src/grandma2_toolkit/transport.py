"""Bounded Telnet exchanges with runtime identity checks and completion markers."""

import re
import select
import socket
import time
import uuid

from .config import Config

# Feedback can follow the active destination prompt on the same line.
FEEDBACK_PREFIX = r"^[ \t]*(?:(?:\[[^\]\n]+\]|EditSetup(?:/[^>\n]+)?)[ \t]*>[ \t]*)?"


class MA2Error(RuntimeError):
    """An operation failed or its result is unknown; mutations must not be retried blindly."""


class TelnetDecoder:
    """Strip fragmented IAC negotiation; refuse options instead of treating them as text."""

    def __init__(self):
        self.state = "data"
        self.verb = 0

    def feed(self, data: bytes) -> tuple[bytes, bytes]:
        out, replies = bytearray(), bytearray()
        for b in data:
            if self.state == "data":
                if b == 255:
                    self.state = "iac"
                else:
                    out.append(b)
            elif self.state == "iac":
                if b == 255:
                    out.append(b)
                    self.state = "data"
                elif b in (251, 252, 253, 254):
                    self.verb, self.state = b, "option"
                elif b == 250:
                    self.state = "sub"
                else:
                    self.state = "data"
            elif self.state == "option":
                if self.verb in (251, 253):
                    replies.extend((255, 254 if self.verb == 251 else 252, b))
                self.state = "data"
            elif self.state == "sub":
                if b == 255:
                    self.state = "sub_iac"
            elif self.state == "sub_iac":
                self.state = "data" if b == 240 else "sub"
        return bytes(out), bytes(replies)


def clean(data: bytes) -> str:
    """Decode after collecting bytes so UTF-8 split across TCP packets remains intact."""
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", data.decode("utf-8", errors="replace")).replace("\r", "")


def validate_command(command: str) -> None:
    """MA2 3.3 has a short line buffer; larger batches must use separate commands."""
    if not command.strip() or any(ord(c) < 32 for c in command):
        raise ValueError("A command must be one nonempty line without control characters")
    if len(command.encode("utf-8")) > 480:
        raise ValueError("Command exceeds conservative MA2 limit of 480 UTF-8 bytes")


class MA2Client:
    """One operation owns one connection; only connection discovery may try another port."""

    def __init__(self, config: Config, target: str = "onpc"):
        if target not in ("onpc", "ma3d"):
            raise ValueError("Target must be onpc or ma3d")
        self.config = config
        self.target = target
        self.socket = None
        self.port = None
        self.runtime = ""
        self.decoder = TelnetDecoder()

    def __enter__(self):
        self.config.validate()
        failures = []
        for port in self.config.ports:
            try:
                self.decoder = TelnetDecoder()
                self.socket = socket.create_connection((self.config.host, port), timeout=2)
                self.socket.settimeout(self.config.timeout)
                self._banner()
                # Login responses are never returned or logged, even on failure.
                reply = self._exchange(f'Login "{self.config.user}" "{self.config.password}"')
                if f"Logged in as User '{self.config.user}'".lower() not in reply.lower():
                    raise MA2Error("Login was not acknowledged")
                self.runtime = self.value("PATH")
                normalized = self.runtime.replace("\\", "/").lower()
                identity = "onpc" if "/grandma/gma2_" in normalized else "ma3d" if "ma3d" in normalized else "unknown"
                if identity != self.target:
                    raise MA2Error("Endpoint runtime does not match the requested target")
                self.port = port
                return self
            except (OSError, MA2Error) as exc:
                # Report only error classes; echoed Login lines can contain secrets.
                failures.append(f"{port}:{type(exc).__name__}")
                self.close()
        raise MA2Error(f"No authenticated {self.target} endpoint: " + ", ".join(failures))

    def __exit__(self, *_):
        self.close()

    def close(self):
        """Close a failed or completed session without replaying any command."""
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def _recv(self) -> bytes:
        data = self.socket.recv(65536)
        if not data:
            raise MA2Error("Console disconnected; command outcome may be unknown")
        text, negotiation = self.decoder.feed(data)
        if negotiation:
            self.socket.sendall(negotiation)
        return text

    def _banner(self):
        deadline = time.monotonic() + .4
        while time.monotonic() < deadline:
            if select.select([self.socket], [], [], .1)[0]:
                self._recv()

    def _exchange(self, command: str) -> str:
        validate_command(command)
        marker = "G2TK_DONE_" + uuid.uuid4().hex
        barrier = f'Lua "gma.feedback(\'{marker}\')"'
        self.socket.sendall((command + "\r\n" + barrier + "\r\n").encode("utf-8"))
        deadline = time.monotonic() + self.config.timeout
        data = bytearray()
        # Match actual feedback, never the marker inside an echoed Lua command.
        done = re.compile(FEEDBACK_PREFIX + marker + r"[ \t]*$", re.M)
        while time.monotonic() < deadline:
            if select.select([self.socket], [], [], min(.2, max(0, deadline-time.monotonic())))[0]:
                data.extend(self._recv())
                if len(data) > 8 * 1024 * 1024:
                    raise MA2Error("Response exceeds 8 MiB; query a smaller range")
                result = clean(data)
                match = done.search(result)
                if match:
                    result = result[:match.start()]
                    # Strip our barrier echo while retaining the command's original reply.
                    result = "\n".join(line for line in result.splitlines() if marker not in line)
                    if "Executing :" not in result:
                        raise MA2Error("Command acknowledgement missing; outcome unknown")
                    return result.strip()
        raise MA2Error("Completion marker timed out; outcome unknown; do not replay writes")

    def command(self, command: str, allow_missing: bool = False) -> str:
        reply = self._exchange(command)
        # Inspect diagnostics, not echoed commands or names containing 'ERROR'.
        diagnostics = re.sub(r"(?m)^.*Executing :.*$", "", reply)
        if re.search(r"(?im)(?:^|>)\s*(?:Error\s*#|UNKNOWN COMMAND|INVALID COMMAND|ILLEGAL|ACCESS DENIED|NOT POSSIBLE|CANNOT IMPORT|OBJECT DOES NOT EXIST)", diagnostics):
            raise MA2Error("Console rejected command: " + reply)
        if not allow_missing and "NO OBJECTS FOUND" in diagnostics.upper():
            raise MA2Error("Console object not found: " + reply)
        return reply

    def value(self, name: str) -> str:
        """Only expose fixed read-only Lua expressions; user-supplied Lua uses the write gate."""
        if name not in ("PATH", "SHOWFILE", "VERSION", "HOSTNAME", "STATUS"):
            raise ValueError("Unsupported status field")
        expr = "gma.network.getstatus()" if name == "STATUS" else f"gma.show.getvar('{name}')"
        reply = self.command(f'Lua "gma.feedback(\'G2TK_VALUE=\'..tostring({expr}))"')
        found = re.search(FEEDBACK_PREFIX + r"G2TK_VALUE=([^\n]*)", reply, re.M)
        if not found:
            raise MA2Error("Status feedback missing")
        return found.group(1).strip()
