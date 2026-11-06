import json, re, sys
from app.importer import _get
B = 'https://olympiads.bc-pf.org'
def links(path):
    t = _get(B + path).text.replace('\\"', '"')
    kids = sorted(set(re.findall(r'href="(' + re.escape(path) + r'/[^"#?]+)"', t)))
    files = re.findall(r'"link":"(https://cdn\.bc-pf\.org/[^"]+)","label":"([^"]*)"', t)
    return kids, files
out = []
def walk(path, depth=0):
    kids, files = links(path)
    for f in dict.fromkeys(files): out.append((path, *f))
    if depth < 3:
        for k in kids:
            if k.count('/') > path.count('/'): walk(k, depth + 1)
for p in sys.argv[1:]:
    walk(p)
json.dump(out, sys.stdout, ensure_ascii=False, indent=0)
