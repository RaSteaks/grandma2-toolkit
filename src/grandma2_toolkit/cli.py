"""JSON CLI mirroring MCP operations; never prints login credentials."""

import argparse
import json
from pathlib import Path
import sys

from .service import Toolkit


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("onpc", "ma3d"), default="onpc")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("connections")
    sub.add_parser("status")
    sub.add_parser("probe").add_argument("objects", nargs="*", help="List expressions; default: sample all pools")
    dmx = sub.add_parser("read-dmx")
    dmx.add_argument("universe", type=int)
    dmx.add_argument("address", type=int)
    dmx.add_argument("--count", type=int, default=1)
    playback = sub.add_parser("playback", help="Operate one onPC executor")
    playback.add_argument("executor")
    playback.add_argument("operation", choices=("go", "back", "pause", "off", "goto", "level"))
    playback.add_argument("--expect-show", required=True)
    playback.add_argument("--cue")
    playback.add_argument("--level", type=int)
    for action in ("list", "export"):
        sub.add_parser(action).add_argument("object")
    backup = sub.add_parser("backup")
    backup.add_argument("--expect-show", required=True)
    new = sub.add_parser("new-show", help="Save current changes and switch onPC to a new Show")
    new.add_argument("name")
    new.add_argument("--expect-show", required=True)
    save = sub.add_parser("save-show", help="Save the current onPC Show on the selected drive")
    save.add_argument("--as", dest="name", help="Save As using this new name")
    save.add_argument("--expect-show", required=True)
    execute = sub.add_parser("execute")
    execute.add_argument("--expect-show", required=True)
    execute.add_argument("--command", "-c", action="append", default=[])
    execute.add_argument("--commands-file", type=Path)
    transform = sub.add_parser("transform")
    transform.add_argument("object")
    transform.add_argument("--expect-show", required=True)
    transform.add_argument("--values", required=True, help='JSON object, e.g. {"rx": -180}')
    sub.add_parser("capture").add_argument("--window-title")
    args = parser.parse_args()
    toolkit = Toolkit()
    try:
        if args.action == "connections":
            result = toolkit.connections()
        elif args.action == "status":
            result = toolkit.status(args.target)
        elif args.action == "probe":
            result = toolkit.probe(args.objects or None, args.target)
        elif args.action == "read-dmx":
            result = toolkit.read_dmx(args.universe, args.address, args.count, args.target)
        elif args.action == "playback":
            if args.target != "onpc":
                raise ValueError("Playback requires --target onpc")
            result = toolkit.playback(args.executor, args.operation, args.expect_show, args.cue, args.level)
        elif args.action == "list":
            result = toolkit.list_objects(args.object, args.target)
        elif args.action == "export":
            result = toolkit.export_object(args.object, args.target)
        elif args.action == "backup":
            result = toolkit.backup_show(args.expect_show)
        elif args.action in ("new-show", "save-show"):
            if args.target != "onpc":
                raise ValueError("Show management requires --target onpc")
            if args.action == "new-show":
                result = toolkit.new_show(args.name, args.expect_show)
            else:
                result = toolkit.save_show(args.expect_show, args.name)
        elif args.action == "execute":
            commands = args.command
            if args.commands_file:
                batch = json.loads(args.commands_file.read_text(encoding="utf-8-sig"))
                if not isinstance(batch, list) or not all(isinstance(c, str) for c in batch):
                    raise ValueError("commands-file must contain a JSON array of strings")
                commands += batch
            result = toolkit.execute(commands, args.expect_show, args.target)
        elif args.action == "transform":
            values = json.loads(args.values)
            if not isinstance(values, dict) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values.values()):
                raise ValueError("values must be a JSON object of numbers")
            result = toolkit.set_transform(args.object, args.expect_show, values, args.target)
        else:
            result = toolkit.capture_ma3d(args.window_title)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"error": toolkit._redact(str(exc))}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
