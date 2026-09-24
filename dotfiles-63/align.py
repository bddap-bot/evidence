import json, re, sys

def t(s):
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)

rows = json.load(open("span_sizes.json"))
pops = []
starts = []
for line in open(sys.argv[1]):
    f = line.split()
    if "gst_app_src_start" in line:
        starts.append(len(pops))
    m = re.search(r"pop buffer buffer: \S+ pts (\S+), dts \S+, dur (\S+), size (\d+)", line)
    if m:
        pops.append((t(f[0]), t(m.group(1)), t(m.group(2)), int(m.group(3))))
first = pops[starts[0]:starts[1] if len(starts) > 1 else None]
speech = [p for p in first if p[3] != 4800]
silence = [p for p in first if p[3] == 4800]
print(f"first playback: {len(first)} buffers, {len(speech)} speech, {len(silence)} silence (4800 B = 50 ms)")
nonempty = [r for r in rows if r["samples"] > 0]
empty = [r for r in rows if r["samples"] == 0]
print("empty spans:", [(r["j"], r["text"]) for r in empty])
k = 0
mism = 0
for r, p in zip(nonempty, speech):
    if abs(r["bytes2x"] - p[3]) > max(4800, 0.05 * r["bytes2x"]):
        mism += 1
print(f"aligned {min(len(nonempty), len(speech))} speech buffers to spans; size mismatches beyond 5%: {mism}")
idx = {r["j"]: i for i, r in enumerate(nonempty)}
for r in empty:
    before = idx.get(r["j"] - 1)
    if before is None or before + 1 >= len(speech):
        print(f"span {r['j']:3d} {r['text']!r}: not reached in this playback")
        continue
    b, a = speech[before], speech[before + 1]
    sil = [p for p in silence if b[1] < p[1] < a[1]]
    print(f"span {r['j']:3d} {r['text']!r}: prev ends pts {b[1] + b[2]:8.3f}, next starts pts {a[1]:8.3f} (gap {a[1] - b[1] - b[2]:+.3f} s, {len(sil)} silence buffers); wall between pops {a[0] - b[0]:6.2f} s vs prev duration {b[2]:5.2f} s")
runs = []
for p in silence:
    if runs and abs(p[1] - (runs[-1][1] + runs[-1][2])) < 1e-6:
        runs[-1] = (runs[-1][0], p[1], p[2] + runs[-1][2] if False else p[2], runs[-1][3] + 1)
    else:
        runs.append((p[1], p[1], p[2], 1))
print("silence runs (start pts, count x 50 ms):", [(round(r[0], 3), r[3]) for r in runs])
