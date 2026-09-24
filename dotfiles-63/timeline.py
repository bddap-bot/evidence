import re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def t(s):
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)

def first_playback(path):
    pops, starts = [], []
    for line in open(path):
        if "gst_app_src_start" in line:
            starts.append((len(pops), t(line.split()[0])))
        m = re.search(r"pop buffer buffer: \S+ pts (\S+), dts \S+, dur (\S+), size (\d+)", line)
        if m:
            pops.append((t(line.split()[0]), t(m.group(1)), t(m.group(2)), int(m.group(3))))
    end = starts[1][0] if len(starts) > 1 else len(pops)
    t0 = starts[0][1]
    xs, ys, speech = [0.0], [0.0], 0.0
    for wall, pts, dur, size in pops[:end]:
        if size != 4800:
            xs.append(wall - t0)
            ys.append(speech)
            speech += dur
            xs.append(wall - t0 + dur)
            ys.append(speech)
    return xs, ys, (starts[1][1] - t0 if len(starts) > 1 else None)

bx, by, breset = first_playback(sys.argv[1])
ax_, ay, _ = first_playback(sys.argv[2])
images = [float(v) for v in sys.argv[3].split(",")]

ink, ink2, muted, surface = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb"
before, after = "#eb6834", "#2a78d6"
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
fig.patch.set_facecolor(surface)
ax.set_facecolor(surface)
for y in images:
    ax.axhline(y, color=muted, lw=0.8, ls=(0, (2, 3)), zorder=1)
ax.text(302, images[-1], "image embeds", color=ink2, fontsize=9, va="center", ha="left")
xmax = 300
bx2 = [x for x in bx if x <= xmax] + [xmax]
by2 = by[: len(bx2) - 1] + [by[len(bx2) - 2]]
ax.plot(bx2, by2, color=before, lw=2, zorder=3, solid_capstyle="round", label="before (#64 base)")
ax.plot([x for x in ax_ if x <= xmax], ay[: len([x for x in ax_ if x <= xmax])], color=after, lw=2, zorder=3, solid_capstyle="round", label="after (this PR)")
ax.text(xmax * 0.62, by2[-1] + 5, "before: no buffer after the first image", color=ink, fontsize=9)
ax.text(250, 262, "after: reads through all six", color=ink, fontsize=9, ha="right")
ax.set_xlim(0, xmax)
ax.set_ylim(0, max(ay[: len([x for x in ax_ if x <= xmax])]) + 15)
ax.set_xlabel("seconds since playback started", color=ink2)
ax.set_ylabel("speech handed to the sink (s)", color=ink2)
ax.set_title("Chrome selection of the article, 2× speed, GNOME VM", color=ink, fontsize=11, loc="left")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color(muted)
ax.tick_params(colors=ink2)
ax.grid(False)
leg = ax.legend(loc="upper left", frameon=False)
for text in leg.get_texts():
    text.set_color(ink)
fig.tight_layout()
fig.savefig(sys.argv[4], facecolor=surface)
