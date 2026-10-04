# Move the show to another Mac: webcams + visuals + Ableton

Target: **one M2 Pro Mac with 16 GB RAM**, running the three webcams, Kikina's
14446 × 760 visual output over NDI, and Ableton. Arthur's current Mac is only
used to prepare and transfer the files. No MIDI or OSC network between two Macs
is needed for this arrangement.

## What to transfer

There are two separate packages. The Git repository does not contain Arthur's
Ableton set, the backing soundtrack, or the licensed Splice sound library.

1. **Kikina repository**, including `audio_live.py`, `requirements-audio.txt`,
   `config.toml`, the shaders, assets and calibrated `lieux/*.toml` files.
   Clone/pull the commit containing this integration, or copy the complete source
   folder. Do not copy `.venv`; create it again on the destination Mac.
2. **Ableton Project folder**, prepared with File → **Collect All and Save**.
   Copy the whole project folder, not just the `.als`. Keep an untouched original
   set and make a separate show copy.

Install the same Live version as the source, or a compatible newer version; an
older Live version may not open a newer set. Install/authorize the same Splice
INSTRUMENT plug-in format used by the set (AU or VST3) and download the required
piano preset/sample content. Collect All and Save does not bundle third-party
plug-ins or their proprietary libraries. Open the copied set and resolve missing
media or plug-ins before arriving at the venue.

## Simplify the audio before moving it

**Recommended show set:** a static backing WAV, a separate piano WAV whose volume
responds to movement, and one live piano instrument for gesture notes. The piano
WAV is optional: the existing MIDI arrangement can remain live if desired.
The optional noise texture is already supplied as `assets/souffle.wav`.

### Static backing WAV

1. Work in the show copy. Stop any sensor simulation. Isolate the parts that must
   always play; exclude the movement-controlled piano, gesture piano and noise.
2. Select the intended full playback/loop range in Arrangement View.
3. File → Export Audio/Video (**Cmd+Shift+R**). Render the Master with only those
   backing parts audible, so their return effects are included. Use stereo PCM
   WAV, 24-bit, Normalize off, and the intended show sample rate (44.1 or 48 kHz).
4. Call it `KIKINA_Background.wav`. Reimport it and listen to the beginning, end
   and loop boundary. A full-song render may need an edited loop boundary or a
   crossfade; do not assume any arbitrary render is seamless.
5. Put it on an audio track `KIKINA Background`. Set Warp off when playing at the
   original tempo. Enable the clip's Loop if it should repeat. Remove unused
   backing instruments from the show copy after comparing the render with the
   original; simply muting tracks does not necessarily unload their sample data.

If the existing backing is already a finished WAV with the right sound and loop
length, reuse it instead of exporting it again.

### Optional rendered movement piano

The volume interaction also works on an audio track, so the repeating piano part
can be exported separately as `KIKINA_PianoLoop.wav`. Use the **same start and
duration** as the background to preserve alignment. Stop `audio_live.py` before
exporting: it normally holds the movement piano at silence without camera input.
After stopping the bridge, restore that piano's intended render volume manually,
then export it in isolation. Do not include the static background in this file.

In the destination set, put the background and piano WAVs in the same Session
scene, with matching loop ranges, and launch that scene together. Map CC20 to
the **piano audio track's volume**, never the Master or background track.

Keep `KIKINA Gestures` as a live instrument: a WAV of the repeating piano phrase
cannot play arbitrary incoming notes. If removing Splice entirely is required,
that needs a separately prepared playable sampled instrument, not just a loop.

## Install the destination Mac

Install Python 3.11 and the NDI runtime/Tools as in the main README. In Terminal,
clone the audio integration branch (GitHub access to the repository is required):

```bash
git clone --branch codex/audio-live https://github.com/KikinaStudio/kikina-riitm.git kikina
cd kikina
```

If the source folder was already copied, open that folder instead. Then run:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-audio.txt
```

Authorize camera, microphone/audio input and local-network access when macOS
requests them for the app launching the programs. Use that same launcher for
the show. Start the bridge before opening Live's MIDI preferences:

```bash
.venv/bin/python audio_live.py
```

These are the existing **single-Mac** settings in `config.toml`; keep them:

```toml
# Inside the existing [capteurs] block:
osc_vers = ["127.0.0.1:7000", "127.0.0.1:7001"]

# Inside the existing [audio_live] block:
osc_hote = "127.0.0.1"
osc_port = 7001
midi_port = "KIKINA Audio"
midi_virtuel = true
```

Edit the existing blocks; do not paste duplicate TOML sections. `127.0.0.1`
always means the computer running the program. Port 7000 serves the visuals;
port 7001 serves the audio bridge. NDI goes over Ethernet to the venue receiver.

## Reconnect Ableton on the new Mac

The mappings belong to the Live Set; the MIDI port switches and audio device
settings must be checked on the new computer even when transferring the saved set.

1. Open the show set. Preferences → Link/Tempo/MIDI: on **Input KIKINA Audio**,
   enable **Track / Piste** and **Remote / Téléc.**; leave **Sync** and **MPE** off.
   No control-surface script or network MIDI session is required.
2. Select the intended CoreAudio output/interface and show sample rate. Start
   with a **256-sample buffer** and test; use 512 if needed and if the resulting
   gesture latency is acceptable. Use native Apple Silicon plug-ins where possible.
3. Verify the movement piano mapping: **channel 1, CC20**, Absolute mode,
   **minimum -inf dB, maximum 0 dB**. It controls that track's volume.
4. For `KIKINA Gestures`, load the piano instrument/preset, no clips, MIDI From
   **KIKINA Audio → Ch. 2**, Monitor **In**, Audio To **Master**, volume **-12 dB**
   as a starting point. Record-arm is unnecessary with Monitor In. Avoid other
   armed/monitored instruments listening to this same channel via All Ins.
5. Optional `KIKINA Souffle`: loop the supplied WAV and map its volume to
   **channel 1, CC21**, range **-inf to -24 dB** to start.
6. Save the set. Confirm the background and repeating piano clips actually play;
   the bridge controls parameters/notes, not Ableton's transport or clip launch.

If the volume mapping is absent, stop the normal bridge first, then run:

```bash
.venv/bin/python audio_live.py --learn 20
```

Press Cmd+M in Live, click the movement piano volume, verify `1/20`, set the
range above and exit Cmd+M. Stop learn mode with Ctrl+C and restart the normal
bridge. For the optional noise mapping, repeat with `--learn 21`. Only run one
bridge/learn process at a time. Detailed musical controls: [audio-live.md](audio-live.md).

## Route the actual music back into the visuals

OSC carries camera numbers, not audio. The visual engine also needs the real
Ableton mix for its audio analysis. Select an interface loopback input or an
installed virtual audio loopback device, while keeping Ableton audible through
the show interface. List available inputs:

```bash
.venv/bin/python -m sounddevice
```

In the existing `[entrees]` block, set `simulateur = false` and put the chosen
input's name in `audio_entree`. Restart `kikina.py`. Verify its reported audio
level follows Ableton. Do not route the captured mix back to its own output.
With `simulateur = true`, Kikina plays `assets/test.wav`; that is a test setting,
not the show soundtrack. No audio-loopback driver is bundled in this repository.

## Connect and calibrate the three cameras

The checked-in `lieux/salle.toml` currently contains **two camera blocks**, not
three. Do not assume the third camera is configured. Each physical camera needs
its own `[[camera]]` entry and measured zones/bands for its actual placement.
Follow the camera/tracing instructions in the README. Confirm names/identifiers
on the destination Mac, because device identifiers and USB topology can change.

Use the production `capteurs.py` console to inspect **each camera's** frame rate.
Its capture workers run in parallel. `outils/test_cameras.py` is useful for
isolating a cable/camera fault, but its combined test reads cameras sequentially,
so that combined number is not the production frame-rate benchmark.

Keep capture at the project's 320 × 240 / 30 fps settings initially. Give the
third camera a separate USB path where possible; a powered hub helps power but
does not create additional USB bandwidth. Test with the exact hubs, extenders,
audio interface and Ethernet adapter intended for the show. Retake the empty-room
background after positioning and trace/calibrate the entrance bands.

## Launch and acceptance test

Before opening cameras, test the copied Ableton setup:

```bash
# Terminal 1 (leave running)
.venv/bin/python audio_live.py

# Terminal 2: camera-free test, then exits
.venv/bin/python outils/simuler_interaction.py --zone 3 --secondes 18 --pas
```

Expected: backing continues unchanged; movement piano fades; gesture piano
plays the entrance notes and sparse accents. Do not run the simulator and real
camera sender together. Then start the real programs in separate terminals:

```bash
# Terminal 2
.venv/bin/python kikina.py

# Terminal 3: use the calibrated venue file
.venv/bin/python capteurs.py salle
```

On the destination Mac, run **at least 30 minutes** with all three cameras,
the final Ableton set, real audio output/loopback, full-resolution visuals and
an actual NDI receiver connected. Test occupied/empty zones, entrance steps,
heavy movement, and disconnect/reconnect one camera.

Accept only after checking:

- The visual sender stays near its 30 fps target without sustained drops.
- All three cameras keep delivering frames; a single dead camera is not hidden
  by an average across the others.
- No audible clicks/dropouts or growing gesture delays; notes release cleanly.
- The movement piano fades down when camera messages stop (3 s expiry followed
  by its release fade); the backing keeps playing.
- Activity Monitor memory pressure remains green without continuously growing
  swap, and performance is still stable after the Mac is warm.
- The venue NDI receiver itself is smooth. Sender and receiver performance are
  separate; a receiver bottleneck is not fixed by buying a faster sender.

## Is the M2 Pro / 16 GB sufficient?

**It is a plausible target for this compact show, but the complete load has not
been benchmarked.** The project journal reports 30 fps full-resolution Kikina
output on the development M2 Pro, with roughly 14–24 ms render time with cameras
(33.3 ms frame budget). The parallel camera test reports about 29.5 fps per camera
with two cameras. Those measurements do **not** certify three cameras plus Ableton.

The latest journal update narrows the third-camera fault: it works without its
10 m active extension, but with that extension it stops after 1–3 seconds even
when powered. Replace/test that USB path independently of CPU performance.
It records a venue MadMapper receiver running around 23 fps at full
resolution despite a 30 fps sender, another separate bottleneck.

For margin, render the fixed backing and repeating piano to WAV, keep just the
gesture instrument live, use mains power, turn off Low Power Mode, and close
unneeded applications. A half-scale visual rehearsal is a fallback to test if
the full-resolution run misses its target; confirm the resulting NDI dimensions
and mapping with the venue before changing scale for the show.

## Sources

- [Project performance and camera measurements](../JOURNAL.md).
- [Ableton: Collect All and Save](https://help.ableton.com/hc/en-us/articles/209775645-Collect-All-and-Save).
- [Ableton: transferring projects](https://help.ableton.com/hc/en-us/articles/209071909-Transferring-Projects-to-another-computer).
- [Ableton: exporting stems](https://help.ableton.com/hc/en-us/articles/360000843404-Importing-and-exporting-stems).
- [Ableton: computer specifications](https://help.ableton.com/hc/en-us/articles/209775305-Computer-specifications-for-running-Ableton-Live).
- [Ableton: CPU load on macOS](https://help.ableton.com/hc/en-us/articles/5266527910812-Reducing-the-CPU-load-on-macOS).
