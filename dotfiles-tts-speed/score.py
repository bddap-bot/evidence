import difflib, re, sys, json
VOW = set("aeiouy")

def norm(s):
    s = s.lower().replace("'s", "s")
    for k, v in (("12th", "twelfth"), ("12", "twelve"), ("6ths", "sixths"), ("10ths", "tenths"), ("-", " ")):
        s = s.replace(k, v)
    return [w for w in re.sub(r"[^a-z' ]", " ", s).split() if w]

def edge(w, front):
    m = re.match(r"^[^aeiou]+", w) if front else re.search(r"[^aeiou]+$", w)
    return m.group() if m else ""

def score(src, hyp):
    a, b = norm(src), norm(hyp)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    dropped = garbled = init = final = 0
    detail = []
    for op, i0, i1, j0, j1 in sm.get_opcodes():
        if op == "equal":
            continue
        sa, sb = a[i0:i1], b[j0:j1]
        if op == "delete" or not sb:
            dropped += len(sa); detail.append(("DROP", " ".join(sa), "")); continue
        if op == "insert":
            continue
        garbled += len(sa)
        detail.append(("GARBLE", " ".join(sa), " ".join(sb)))
        if len(sa) == len(sb):
            for x, y in zip(sa, sb):
                if edge(x, True) and not y.startswith(edge(x, True)): init += 1
                if edge(x, False) and not y.endswith(edge(x, False)): final += 1
        else:
            for x in sa:
                init += bool(edge(x, True)); final += bool(edge(x, False))
    return dict(words=len(a), dropped=dropped, garbled=garbled, init_c=init, final_c=final, detail=detail)

if __name__ == "__main__":
    src = open("passage.txt").read()
    for f in sys.argv[1:]:
        r = score(src, open(f).read())
        print(f"{f}: words={r['words']} dropped={r['dropped']} garbled={r['garbled']} init_c={r['init_c']} final_c={r['final_c']}")
        for d in r["detail"]:
            print("   ", *d)
