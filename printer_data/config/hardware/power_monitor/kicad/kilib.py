"""Minimal KiCad 8 symbol-library helper: extract + flatten symbols, list pins."""
import re, os
LIBDIR = os.environ.get('KICAD_LIBSRC', os.path.expanduser('~/kicad_libsrc_8.0.8'))  # KiCad 8.0.8 symbol libs (not in git)
_cache = {}

def _lib(name):
    if name not in _cache:
        _cache[name] = open(os.path.join(LIBDIR, name + '.kicad_sym')).read()
    return _cache[name]

def _block(text, start):
    d = 0
    for j in range(start, len(text)):
        c = text[j]
        if c == '(':
            d += 1
        elif c == ')':
            d -= 1
            if d == 0:
                return text[start:j + 1]
    raise ValueError('unbalanced')

def raw_symbol(lib, name):
    t = _lib(lib)
    i = t.index('\t(symbol "%s"' % name)
    return _block(t, t.index('(symbol', i))

def flat_symbol(lib, name):
    """Return the symbol block, with 'extends' resolved, top renamed to lib:name."""
    b = raw_symbol(lib, name)
    m = re.search(r'\(extends "([^"]+)"\)', b)
    if m:
        parent = flat_symbol(lib, m.group(1))
        pname = m.group(1)
        # child properties replace parent properties
        props = {}
        for pm in re.finditer(r'\(property "([^"]+)"', b):
            props[pm.group(1)] = _block(b, pm.start())
        out = parent.replace('(symbol "%s:%s"' % (lib, pname), '(symbol "%s:%s"' % (lib, name), 1)
        out = out.replace('(symbol "%s_' % pname, '(symbol "%s_' % name)
        for k, v in props.items():
            pm = re.search(r'\(property "%s"' % re.escape(k), out)
            if pm:
                old = _block(out, pm.start())
                out = out.replace(old, v, 1)
        return out
    return b.replace('(symbol "%s"' % name, '(symbol "%s:%s"' % (lib, name), 1)

PIN_RE = re.compile(r'\(pin (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+)(?: (\d+))?\)', re.S)

def pins(block):
    """{number: (name, x, y, angle, etype)} in library coordinates (y up)."""
    res = {}
    for m in PIN_RE.finditer(block):
        pb = _block(block, m.start())
        name = re.search(r'\(name "([^"]*)"', pb).group(1)
        num = re.search(r'\(number "([^"]*)"', pb).group(1)
        res[num] = (name, float(m.group(3)), float(m.group(4)), int(m.group(5) or 0), m.group(1))
    return res
