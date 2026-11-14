import re, sys

path = sys.argv[1] if len(sys.argv) > 1 else 'xnu/patches/0180-athens-spi-nt36672c-touch.patch'
lines = open(path, encoding='utf-8', errors='replace').read().split('\n')

hunks = []
cur = None
curfile = '?'
for l in lines:
    if l.startswith('+++ '):
        curfile = l[4:].strip()
        continue
    m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', l)
    if m:
        if cur:
            hunks.append((curfile, cur))
        cur = {'hdr': l, 'os': int(m.group(1)),
               'oc': int(m.group(2)) if m.group(2) else 1,
               'ns': int(m.group(3)),
               'nc': int(m.group(4)) if m.group(4) else 1,
               'body': []}
        continue
    if cur is not None:
        # hunk body lines start with ' ', '+', '-', or '\' (no newline marker)
        if l.startswith('\\'):
            continue
        if l == '':
            # bare empty line: not valid diff body, treat as hunk terminator
            hunks.append((curfile, cur))
            cur = None
            continue
        if l[0] in ' +-':
            cur['body'].append(l)
        else:
            hunks.append((curfile, cur))
            cur = None
if cur:
    hunks.append((curfile, cur))

bad = 0
for fname, h in hunks:
    plus = sum(1 for b in h['body'] if b.startswith('+'))
    minus = sum(1 for b in h['body'] if b.startswith('-'))
    ctx = sum(1 for b in h['body'] if b.startswith(' ') or b == '')
    if h['os'] == 0 and h['oc'] == 0:
        aoc, anc = 0, plus
    else:
        aoc, anc = ctx + minus, ctx + plus
    ok = (aoc == h['oc'] and anc == h['nc'])
    if not ok:
        bad += 1
    print(('OK ' if ok else 'BAD'), h['hdr'], 'decl', h['oc'], h['nc'],
          'actual', aoc, anc, '|', fname)
print('BAD COUNT:', bad)
