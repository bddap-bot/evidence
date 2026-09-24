import json, re, sys
import numpy as np
import tts_read_installed as t

text = open("repro/chrome-primary.txt", encoding="utf-8").read().strip()
spans = t.sentence_spans(text)
e = t.Engine()
rows = []
for j, (a, b) in enumerate(spans[:int(sys.argv[1])]):
    audio, _ = e.synth(text[a:b])
    rows.append({"j": j, "text": text[a:b][:60], "samples": int(len(audio)), "bytes2x": int(len(t.stretch(audio, 2.0))) * 4})
json.dump(rows, open("span_sizes.json", "w"), indent=0)
print(len(rows), "spans;", sum(r["samples"] for r in rows) / t.SAMPLE_RATE, "s audio at 1x")
