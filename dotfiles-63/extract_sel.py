import re, sys
log, start_marker = sys.argv[1], sys.argv[2].encode()
pat = re.compile(r'^(\d+)\s+(\S+)\s+read\((\d+), "((?:\\x[0-9a-f]{2})*)"(?:\.\.\.)?, (\d+)\)\s+=\s+(\d+)')
lines = open(log, errors="replace").read().splitlines()
reads = []
for i, line in enumerate(lines):
    m = pat.match(line)
    if m:
        reads.append((i, m.group(1), m.group(3), bytes.fromhex(m.group(4).replace("\\x", "")), int(m.group(5))))
out = []
for k, (i, pid, fd, data, size) in enumerate(reads):
    if data.lstrip().startswith(start_marker):
        blob = [data]
        for (i2, pid2, fd2, data2, size2) in reads[k + 1:]:
            if (pid2, fd2) != (pid, fd):
                continue
            if not data2:
                break
            blob.append(data2)
        out.append((lines[i].split()[1], b"".join(blob)))
for ts, blob in out:
    print(f"read at {ts}: {len(blob)} bytes", file=sys.stderr)
sys.stdout.buffer.write(out[-1][1] if out else b"")
