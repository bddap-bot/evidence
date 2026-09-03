import importlib.util, os, sys, wave
import numpy as np
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

spec = importlib.util.spec_from_file_location("tts_read", os.environ["TTS_MOD"])
tts_read = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tts_read)

out = sys.argv[1]
what = sys.argv[2]
speeds = [float(s) for s in sys.argv[3:]]
text = open("passage.txt").read().strip()
Gst.init(None)
engine = tts_read.Engine()


def wav(path, audio):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(tts_read.SAMPLE_RATE)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


real_parse = Gst.parse_launch
for speed in speeds:
    tag = f"{out}/s{speed:.1f}"
    if what == "bare":
        bare = tts_read.stretch(engine.synth(text)[0], speed) if hasattr(tts_read, "stretch") else engine.synth(text, speed)[0]
        wav(tag + "_bare.wav", bare)
        print(speed, "bare=%.2fs" % (len(bare) / 24000), flush=True)
        continue
    Gst.parse_launch = lambda desc, tag=tag: real_parse(desc.replace("autoaudiosink", f"identity sync=true ! wavenc ! filesink location={tag}_app.wav"))
    loop = GLib.MainLoop()
    err = []
    player = tts_read.Player(engine, text, speed, lambda e: (err.append(e), loop.quit()))
    loop.run()
    Gst.parse_launch = real_parse
    chunks = [c for c in player.chunks if c is not None]
    player.close()
    assert len(chunks) == len(player.spans), (len(chunks), len(player.spans))
    wav(tag + "_chunks.wav", np.concatenate([c[0] for c in chunks]))
    print(speed, "err=", err, "chunks=%.2fs" % (sum(len(c[0]) for c in chunks) / 24000), flush=True)
