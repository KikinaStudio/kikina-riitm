"""Test local complet OSC -> MIDI, sur un port isolé (macOS/Linux)."""
import os, signal, socket, subprocess, tempfile, time
from pathlib import Path
import rtmidi
from pythonosc.udp_client import SimpleUDPClient
root = Path(__file__).resolve().parents[1]
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
name = f'KIKINA Verification {os.getpid()}'
config = (root / 'config.toml').read_text().replace('osc_port = 7001', f'osc_port = {port}').replace('midi_port = "KIKINA Audio"', f'midi_port = "{name}"')
with tempfile.TemporaryDirectory(prefix='kikina-midi-') as tmp:
    cfg = Path(tmp) / 'config.toml'
    cfg.write_text(config)
    process = subprocess.Popen([str(root / '.venv/bin/python'), str(root / 'audio_live.py'), '--config', str(cfg)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    midi = rtmidi.MidiIn()
    client = SimpleUDPClient('127.0.0.1', port)
    messages = []
    try:
        for _ in range(50):
            names = midi.get_ports()
            found = [i for i, p in enumerate(names) if name in p]
            if found:
                break
            if process.poll() is not None:
                raise AssertionError(process.stdout.read())
            time.sleep(0.1)
        assert found, names
        midi.open_port(found[0])
        client.send_message('/zone/3/energie', 0.9)
        end = time.monotonic() + 1.2
        while time.monotonic() < end:
            msg = midi.get_message()
            if msg:
                messages.append(msg[0])
            time.sleep(0.002)
        assert any(m[0] == 0xB0 and m[1] == 20 and m[2] > 100 for m in messages), messages
        assert any(m[0] == 0xB0 and m[1] == 21 and m[2] > 0 for m in messages), messages
        assert any(m[0] == 0x91 and m[1] == 69 and m[2] > 0 for m in messages), messages
        assert [0x81, 69, 0] in messages, messages
        client.send_message('/accueil/pas', 1)
        time.sleep(0.08)
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=3)
        while (msg := midi.get_message()) is not None:
            messages.append(msg[0])
        assert [0x81, 62, 0] in messages, messages
        assert [0xB0, 20, 0] in messages and [0xB0, 21, 0] in messages, messages
        assert process.returncode == 0, process.stdout.read()
        print(f'PASS: OSC -> bridge -> CoreMIDI, {len(messages)} messages; piano/noise CC, movement/step notes, note-offs and SIGTERM cleanup verified.')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
        midi.close_port()
        client.close()
        process.stdout.close()
