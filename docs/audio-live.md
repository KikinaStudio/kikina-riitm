# Audio interaction in Ableton Live

Moving the whole show to a replacement Mac? Follow [the show Mac transfer guide](show-mac.md)
for exports, installation, three-camera setup and a full-load rehearsal. Everything
runs on that one Mac, so keep the localhost OSC settings.

The cameras send the same OSC measurements to `kikina.py` on port 7000 and
`audio_live.py` on port 7001. Ableton makes the sound; the bridge controls it
over a local MIDI port named **KIKINA Audio**. No Max for Live device is required.
These settings target Arthur's current set: track 3 contains Ambient Piano
Arpeggios, labelled D dominant. The bridge does not select a track by number;
Live's MIDI mapping and input routing determine what it controls.

## Installation and launch (Mac, same computer)

From the project directory:

```bash
python3.11 -m venv .venv                         # only if absent
.venv/bin/python -m pip install -r requirements-audio.txt
.venv/bin/python audio_live.py --learn 20
```

This installs just the audio bridge. The camera and visual programs still need
the project's main `requirements.txt` dependencies and NDI runtime.

## 1. Smooth fade of the existing piano

1. With the bridge running, open Live Preferences → Link/Tempo/MIDI.
2. On **Input: KIKINA Audio**, enable **Track** (notes) and **Remote** (mappings).
   Leave Sync and MPE off. Do not route Live's MIDI output back into this port.
3. Close Preferences. Press **Cmd+M**, click the **volume of track 3**. The bridge
   sends only CC20 in this learn mode, so the mapping should display **1/20**.
4. In Live's MIDI Mappings panel, set **Min = -inf dB, Max = 0 dB**, Absolute mode.
   Exit MIDI mapping with Cmd+M. Save the set, preferably as a new interactive copy.
5. Stop learn mode with Ctrl+C, then run `.venv/bin/python audio_live.py`.

The strongest movement across the four zones fades the piano up in about 0.5 s
and down in about 2.5 s (95% of the change). Silence is the default when no data
arrives. Readings expire after 3 s, then fade out. A small noise threshold is ignored.
The static audio track is not mapped and keeps playing normally.
Keep the piano clip playing in the arrangement or looping in Session View.
Existing volume automation can conflict with the mapping; use an unautomated
Utility Gain instead, with a suitable bounded range, if needed.

## 2. Additional piano notes from gestures and entrance steps

Create a **separate MIDI track** named `KIKINA Gestures`, copy the piano instrument
and its effects from track 3 (copy devices only, not the arrangement clips).
Set MIDI From to **KIKINA Audio → channel 2**, Monitor **In**, output **Master**.
Start the track volume at **-12 dB**. Its sound should blend beneath the existing piano.
Keep other instrument tracks from monitoring KIKINA channel 2 through All Ins;
otherwise armed tracks may also play the generated notes.

- Movement crossing 0.25 triggers a note for that zone: D4, F#4, A4, C5
  (MIDI numbers 62, 66, 69, 72; Live's octave labels can differ).
- Movement must drop below 0.12 before another gesture can trigger that zone.
- A global 1.2 s cooldown limits movement notes; the strongest simultaneous gesture wins.
- `/accueil/pas` 1, 2, 3 triggers D, F#, A promptly, with duplicate suppression.
- Notes last 0.7 s; velocity follows movement between 40 and 85.
- Held gestures do not repeat, note-offs are scheduled, and normal Ctrl+C/SIGTERM
  releases active notes. A force-kill or machine failure cannot send cleanup MIDI;
  use Live's Stop/panic if that happens.

The palette comes from the existing clip label, not a harmonic analysis of the
static soundtrack. Adjust `notes_zones` / `notes_pas` in `config.toml` if its key differs.
These are gesture-timed accents, not tempo-synchronized arpeggios.

## 3. Optional movement texture

`assets/souffle.wav` is an 8-second stereo loop of softened white noise (150 Hz
to roughly 4 kHz). Recreate it with `python outils/fabriquer_souffle.py`.

Create an audio track `KIKINA Souffle`, import the file into a Session clip,
enable Loop, and launch it. Leave Warp off at the current 120 BPM (4 bars).
Stop the bridge, run `audio_live.py --learn 21`, and map **only this track's volume**
to CC21, **Min = -inf dB, Max = -24 dB**. Exit mapping, stop learn mode, and restart
`audio_live.py`. CC21 follows average movement, so a single person produces a
small texture and a moving group produces more. Tune the maximum by listening.

## 4. EFX near the walls (CC22) and track 1 with movement (CC23)

- **CC22, track 4 EFX:** follows presence near any wall (the floor zones drawn along the walls).
  It fades in over about 2 s and out over about 4 s. Map it with `--learn 22` to **track 4's volume**,
  then set **Min = -inf dB, Max = -12 dB** in the Mapping Browser. Raise or lower Max by ear:
  audible when someone approaches, never above the music.
- **CC23, track 1:** follows the strongest movement, like CC20. Map it with `--learn 23` to
  **track 1's volume**, **Min = -18 dB** (its level when nobody moves), **Max = 0 dB**.
- CC20 (track 3 piano) still follows movement. Remove its mapping in Live if it should not.

The Live mapping range sets the loudness; the bridge only sends how near or how active people are.

## Test without webcams

Stop `capteurs.py` during this test. Keep Ableton and the bridge running:

```bash
.venv/bin/python outils/simuler_interaction.py --zone 3 --secondes 15 --pas
```

The same wave of readings goes to ports 7000 and 7001. Track 3's fader should
rise/fall; `KIKINA Gestures` should receive notes; the matching visual zone should
react if the visual engine is running. The simulator sends zero on exit.
Visual keyboard shortcuts A/Z/E/R are internal to the visual engine and do not
send audio controls: use this simulator to test both outputs together.

For the show, launch these in separate terminals:

```bash
.venv/bin/python audio_live.py
.venv/bin/python kikina.py
.venv/bin/python capteurs.py salle
```

Restart any already-running `capteurs.py`: destination changes require restart.
Choose the calibrated camera location (`salle`, `maison`, or `essai`).

**Visual audio input:** the existing config still uses `simulateur = true`, which
plays `assets/test.wav`. For the show, set it to false and choose an input carrying
the Ableton mix in `entrees.audio_entree`; use an audio interface loopback or a
virtual audio routing device with headphone output. The MIDI bridge does not carry
audio. Shared camera reactions work without this return, but music-reactive visuals
need the actual Ableton mix. Don't use the laptop mic as a substitute for clean loopback.

## Settings, other platforms, and troubleshooting

All new controls are under `[audio_live]` in `config.toml`; restart the bridge after
changes. Each control has its own CC, zones, presence/energy input, max/mean
aggregation and threshold. Zone 3 (wall) and track 3 (Live) are independent.

On Windows use `.venv\Scripts\python`, install `requirements-audio.txt`, create a
virtual bus with loopMIDI, set `midi_virtuel = false`, and put its exact output name
in `midi_port`. List names with `audio_live.py --list-ports`. For another computer,
set `osc_hote = "0.0.0.0"` on the audio computer and replace only the audio destination
in `capteurs.osc_vers` with its LAN IP and port 7001. Allow UDP 7001 through its firewall.

`audio_live.py --dry-run` prints CCs and notes without MIDI. A port-in-use error
usually means another bridge (including learn mode) is already running. Only run one.
Keep the bridge running so the virtual port remains visible to Live. After a bridge
restart, check that Live has reconnected to the port.

Verification: `.venv/bin/python -m unittest -v test_audio_live` (requires permission
to bind a localhost UDP socket). On macOS/Linux, `.venv/bin/python outils/verifier_audio_midi.py`
also tests the complete bridge with an isolated virtual MIDI port. Live mapping, instrument routing, camera calibration,
audio loopback, and the final acoustic balance still require a rehearsal.

References: [Ableton MIDI mappings](https://help.ableton.com/hc/en-us/articles/360000038859-Making-custom-MIDI-Mappings),
[Live MIDI settings](https://help.ableton.com/hc/en-us/articles/209774205-Live-s-MIDI-Settings),
[virtual MIDI buses](https://help.ableton.com/hc/en-us/articles/209774225-Setting-up-a-virtual-MIDI-bus).
