# Commands and operational distinctions

These examples are based on grandMA2/onPC 3.3.4.3 usage. Confirm objects and version on the actual endpoint;
availability and IDs are not universal. Send native commands through `ma2_execute` only inside authorized scope.

| Task | Native example | Check |
|---|---|---|
| Executor assignments | `List Executor 3.1 Thru 3.8` | Actual Sequence/Macro assignment |
| Sequence / Cues | `List Sequence 121` then `List Sequence 121 Cue` | Cue timing and contents; XML for full data |
| Effects / positions | `List Effect 1 Thru 10`, `List Preset 2.1 Thru 2.10` | Effects may also be embedded in Cue data |
| Scene root | `List Root 10.6.3` | Discover children and fixture identities before editing |
| Installation rotation | `Assign Root 10.6.3.76 /Rot.X=-180 /Rot.Y=0 /Rot.Z=0` | Address is illustrative; read back all XYZ/rotation |
| Camera | `List Camera 50` | Number exists and is the intended camera |
| Camera transform | `Assign Camera 50 /X=0 /Y=-58 /Z=12.8 /Rot.X=-2 /FOV=0.64` | Rot.X has a dot; RotX may silently do nothing |
| Copy camera | `Copy Camera 1 At 50` | Query destination first; do not overwrite an occupied slot |
| Camera label | `Label Camera 50 "OVERALL FRONT"` | Native label readback |
| Cue preview | `Goto Cue 1 Executor 3.6 Fade 2` | Playback only; it can interact with other running executors |
| Executor level | `Executor 3.6 At 100` | AutoStart/master settings affect behavior |
| Stop preview | `Off Executor 3.6` | Do not stop unrelated playback |
| Native XML | `Export Page 3 unique_name` | toolkit export waits for parseable XML and keeps a unique file |
| Save | `SaveShow /noconfirm` | toolkit backup waits for the newly written gzip |

For `ma3d_transform`, specify values as `{"x":0,"z":12.8,"rx":-2}` and `target="ma3d"`.
For synchronized scene edits via onPC specify `target="onpc"`. Always compare returned before/after text.

`Select Camera 50` on the console does not necessarily change a MA3D Stage View fixed to Front.
Check the camera name in the rendered viewport; switching its camera or adjusting Rendering may require UI.
Model rotation, fixture Pan/Tilt output and camera rotation are three different things.
`gma.show.getdmx()` can be zero when DMX output is unavailable and is not proof of a dark visualizer.

Runtime paths identify applications. Session status such as Master/Slave plus matching Show names is useful
evidence but does not prove two applications share a particular network session. Do not automatically call
JoinSession or change membership to resolve a query failure.

Tool completion markers prove the command queue reached a feedback line, not that an asynchronous file
operation, render update or whole-song playback completed. Preserve this distinction in acceptance reports.
