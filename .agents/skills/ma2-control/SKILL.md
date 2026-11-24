---
name: ma2-control
description: Connect to grandMA2 onPC and MA3D over Telnet, inspect and program Show objects, adjust scene fixtures and cameras, and collect visual acceptance evidence through the grandma2-toolkit CLI or MCP.
---

# MA2 / MA3D control

Use the repository's `grandma2` CLI or `grandma2-toolkit` MCP tools. They share one implementation.
Prefer MCP when configured; otherwise use `python scripts/ma2.py ...` relative to this skill directory.
The launcher resolves this repository or `MA2_TOOLKIT_ROOT`; an installed `grandma2` command also works.

Read [references/commands.md](references/commands.md) for native object, playback, geometry and camera examples.
For fixture libraries and patching, ordered pixel groups, Screen/ViewButton, MAtricks, Presets/Effects
and Sequence-to-Executor assignments, use the [Telnet command reference](references/telnet-workflows.md).

## Connect and scope

- Call `ma2_connections` / CLI `connections`. Both sockets are held open concurrently during discovery.
  Inspect identity, active Show and session state. onPC and MA3D may occupy either configured port.
- Password is supplied through `MA2_PASSWORD`, never copied into commands, logs or repository files.
  Do not invent a password or echo existing credentials. Server startup/tool discovery needs no credential.
- onPC is the programming target; MA3D is the default scene/camera transform target. Same Show names alone do
  not prove shared-session membership. MA3D geometry edits can synchronize back into onPC.
- Preserve current user scope: a read-only Page remains read-only even when scene edits are authorized.
  No fixed Page number, fixture count, Root mapping, camera or show name is intrinsic to this skill.

## Query and mutate

- To survey a live Show without touching its files, use `ma2_status`, `ma2_probe` and `ma2_read_dmx` with writes disabled.
  Inspect object rows in the audit: an acknowledgement alone may contain the current directory listing.
  For explicit executor control use `ma2_playback` only when playback/output changes are in scope.
  Read the [onPC survey and DMX notes](references/telnet-workflows.md#只读抽查与-dmx-采样) for inputs and evidence boundaries.
- Use `ma2_list` for queries; use `ma2_export` when exact object contents or before/after comparison matters.
  Pass only the object expression, e.g. `Root 10.4.*` or `Sequence 121 Cue 1 Thru 5`.
  XML fingerprints omit timestamps and whitespace, retaining object data including embedded Cue effects.
- For an explicitly authorized onPC Show switch, `ma2_new_show` saves the current changes before
  switching. Verify the returned active name. `ma2_save_show` saves in place or saves as a new name
  on the selected drive. The local internal drive permits gzip verification; remote saves return
  acknowledgement only. After a timeout or disconnect inspect the console and status before any retry.
  Avoid new/save/backup when the task requires leaving Show files untouched.
- Before authorized programming/geometry changes, use `ma2_backup` if a saved baseline is needed.
  It waits for a new complete SaveShow gzip. A command acknowledgement alone is not a saved-file check.
- Writes require process configuration `MA2_ALLOW_WRITE=1` and exact `expected_show`; these do not grant
  user authorization. Existing authorization need not be requested again for routine steps in scope.
- Use `ma3d_transform` for known scene bodies or cameras; it returns before/after native text.
  Inspect requested values in that readback. `rx/ry/rz` set installation rotation, not Cue Pan/Tilt.
- `ma2_execute` accepts authorized general commands, including Lua. It is not sandboxed. Batch maximum
  is 100 lines; each line is at most 480 UTF-8 bytes. On failure, prior commands may already be applied.
  After uncertain completion, query state instead of replaying writes or automatically reconnecting.
- Record actual changes and limits in the project's AGENT.md when maintaining a project.

## Verify appearance

- Export/read back relevant objects. Confirm coordinates, rotations, Cue references and saved files as applicable.
- For visual acceptance use `ma3d_capture` on a visible local MA3D window, then open its returned PNG with
  the host's image viewer. Confirm the displayed camera and playback state before judging beams.
- A screenshot call does not select Front, advance playback or prove movement. Inspect multiple times for
  dynamic effects, and keep song synchronization checks separate from static composition checks.
- If capture fails or camera/render UI interaction is necessary, use available computer-use tools within
  the user's authorized scope. Do not infer success from a blank/old frame. Store evidence under the user's
  specified folder via `MA2_OUTPUT_DIR`; default is repository `.data`.
- Report parameter verification separately from visual acceptance, including unresolved rendering issues.
