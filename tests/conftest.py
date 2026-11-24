"""A real TCP console simulator; no test sends commands to a lighting application."""

from contextlib import ExitStack, contextmanager
import gzip
import re
import socketserver
import threading
import time

import pytest

from grandma2_toolkit.config import Config


class ConsoleHandler(socketserver.StreamRequestHandler):
    def handle(self):
        prompt = " [Fixture]>"
        self.wfile.write(b"grandMA2 Telnet\r\n")
        for raw in self.rfile:
            command = raw.decode("utf-8").strip()
            if not command:
                continue
            self.server.commands.append(command)
            # Every command echoes a marker-containing Lua string before real feedback.
            self.wfile.write(("Executing : " + command + "\r\n").encode())
            if command.startswith("Login "):
                if self.server.fail_login:
                    self.wfile.write(("ACCESS DENIED " + command + "\r\n").encode())
                else:
                    self.wfile.write(b"Logged in as User 'administrator'\r\n")
            elif "G2TK_DONE_" in command:
                marker = re.search(r"G2TK_DONE_[a-f0-9]+", command)[0]
                if self.server.omit_marker:
                    continue
                time.sleep(.02)
                self.wfile.write((prompt + marker + "\r\n").encode())
            elif "G2TK_VALUE=" in command:
                if "'PATH'" in command:
                    value = str(self.server.runtime)
                elif "'SHOWFILE'" in command:
                    value = self.server.show
                elif "getstatus" in command:
                    value = "Master" if "gma2_" in str(self.server.runtime) else "Slave"
                else:
                    value = "3.3.4.3"
                self.wfile.write((prompt + "G2TK_VALUE=" + value + "\r\n").encode())
            elif command == "ChangeDest EditSetup":
                prompt = "EditSetup >"
            elif command == "ChangeDest 4" and prompt == "EditSetup >":
                prompt = "EditSetup/Layers 4 >"
            elif command == "BadCommand":
                self.wfile.write(b"Error #1: UNKNOWN COMMAND\r\n")
            elif command.startswith("List "):
                self.wfile.write("No. Name X Y Z Rot.X\r\n50 灯具 0 -58 12.8 -2\r\n".encode())
            elif command.startswith("Export "):
                name = command.split()[-1]
                directory = {"Effect": "effects", "MAtricks": "matricks", "Macro": "macros"}.get(
                    command.split()[1], "importexport")
                (self.server.runtime / directory / (name + ".xml")).write_text(
                    '<MA xmlns="http://schemas.malighting.de/grandma2/xml/MA"><Info datetime="now"/><Page index="2" name="P3"/></MA>', encoding="utf-8")
            elif command.startswith("SaveShow"):
                destination = self.server.runtime / "shows" / (self.server.show + ".show.gz")
                # Native SaveShow returns first; the file is replaced later.
                threading.Timer(.25, lambda: destination.write_bytes(gzip.compress(b"new-show"))).start()
            self.wfile.flush()


@contextmanager
def fake_console(runtime):
    for directory in ("importexport", "effects", "matricks", "macros"):
        (runtime / directory).mkdir(parents=True)
    (runtime / "shows").mkdir()
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), ConsoleHandler)
    server.daemon_threads = True
    server.runtime, server.show = runtime, "codex"
    server.commands, server.fail_login, server.omit_marker = [], False, False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def consoles(tmp_path):
    with ExitStack() as stack:
        ma3d = stack.enter_context(fake_console(tmp_path / "ma3d" / "V_3.3.4"))
        onpc = stack.enter_context(fake_console(tmp_path / "grandma" / "gma2_V_3.3.4"))
        # Deliberately put MA3D first, emulating port 30000 being owned by MA3D.
        config = Config(ports=(ma3d.server_address[1], onpc.server_address[1]), password="test-secret",
                        timeout=2, output_dir=tmp_path / "evidence")
        yield config, onpc, ma3d
