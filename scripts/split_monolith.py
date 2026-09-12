"""
Mechanical, verifiable extraction of top-level functions/constants out of a
monolith module into sub-modules that LATE-BIND back to it.

Used for the 2026-09 split of app.py (-> api/*.py blueprints) and scraper.py
(-> scrapers/*.py providers). Re-runnable: it always starts from the monolith
text you give it, so re-splitting after a merge is a matter of re-running.

Design (why late binding):
  * Tests and the fixture harness monkeypatch names ON THE MONOLITH
    (`patch('app.load_config')`, `setattr(scraper, '_get_usd_to_ils', ...)`).
    A moved function must still see those patches, so every reference it
    makes to a name that stays in (or is re-exported by) the monolith is
    rewritten to `core.<name>`, where `core` is `import app as core`.
  * The monolith imports the sub-modules at its BOTTOM (after all helpers are
    defined, before any `if __name__ == "__main__":` block) and re-exports
    every moved name, so `app.run_mobile_reminders_job` / `scraper.scrape_saily_global`
    keep working for scripts, tests and the scheduler.
  * `python app.py` makes the monolith `__main__`; a `sys.modules['app']` alias
    inserted at the top prevents `import app` from executing the file twice.

Plan file (JSON):
  {
    "monolith": "app.py", "core": "app", "package": "api",
    "kind": "flask" | "plain",
    "modules": {"mobile": {"ranges": [[2200, 2598]], "names": ["..."], "doc": "..."}, ...},
    "local_aliases": ["logger"]        # emitted as `logger = core.logger`, not rewritten
  }
A node (function/assignment) is moved if its name is listed OR it lies inside
one of the line ranges. Nodes containing a `global` statement are never moved.

    python scripts/split_monolith.py plan.json            # write modules + rewrite monolith
    python scripts/split_monolith.py plan.json --dry-run  # report only
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── scope analysis ───────────────────────────────────────────────────────────
class _Scope:
    def __init__(self, bound, parent=None):
        self.bound = set(bound)
        self.parent = parent

    def is_bound(self, name):
        s = self
        while s is not None:
            if name in s.bound:
                return True
            s = s.parent
        return False


def _bound_in_scope(node):
    """Names bound directly in this function/lambda/class scope (no descent
    into nested function bodies, but nested def/class NAMES count)."""
    bound = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = node.args
        for arg in a.posonlyargs + a.args + a.kwonlyargs:
            bound.add(arg.arg)
        if a.vararg: bound.add(a.vararg.arg)
        if a.kwarg: bound.add(a.kwarg.arg)
    body = node.body if isinstance(node.body, list) else [node.body]

    def visit(child):
        # examine the statement/expression ITSELF first (a bare `import x as y`
        # or `global z` body statement binds names), then its children
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(child.name)
            return             # nested scope handled separately
        if isinstance(child, ast.Lambda):
            return
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            bound.add(child.id)
        elif isinstance(child, (ast.Global, ast.Nonlocal)):
            bound.update(child.names)
        elif isinstance(child, ast.ExceptHandler) and child.name:
            bound.add(child.name)
        elif isinstance(child, (ast.Import, ast.ImportFrom)):
            for al in child.names:
                bound.add((al.asname or al.name).split(".")[0])
        elif isinstance(child, ast.arg):
            bound.add(child.arg)
        elif isinstance(child, ast.MatchAs) and child.name:
            bound.add(child.name)
        for sub in ast.iter_child_nodes(child):
            visit(sub)
    for b in body:
        visit(b)
    return bound


def _collect_name_refs(node, rewrite_set, scope=None, out=None):
    """Yield (lineno, col, end_col, id) for every Load-context Name in `node`
    whose id is in rewrite_set and is NOT locally bound in any enclosing scope."""
    if out is None:
        out = []
    if scope is None:
        scope = _Scope(set())
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # decorators + defaults + annotations are evaluated in the ENCLOSING scope
            if not isinstance(child, ast.Lambda):
                for d in child.decorator_list:
                    _collect_name_refs(_Wrap(d), rewrite_set, scope, out)
                if child.returns:
                    _collect_name_refs(_Wrap(child.returns), rewrite_set, scope, out)
            a = child.args
            for d in a.defaults + [x for x in a.kw_defaults if x is not None]:
                _collect_name_refs(_Wrap(d), rewrite_set, scope, out)
            for arg in a.posonlyargs + a.args + a.kwonlyargs + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else []):
                if arg.annotation:
                    _collect_name_refs(_Wrap(arg.annotation), rewrite_set, scope, out)
            inner = _Scope(_bound_in_scope(child), scope)
            body = child.body if isinstance(child.body, list) else [child.body]
            for b in body:
                _collect_name_refs(_Wrap(b), rewrite_set, inner, out)
            continue
        if isinstance(child, ast.ClassDef):
            for d in child.decorator_list + child.bases:
                _collect_name_refs(_Wrap(d), rewrite_set, scope, out)
            inner = _Scope(_bound_in_scope(child), scope)
            for b in child.body:
                _collect_name_refs(_Wrap(b), rewrite_set, inner, out)
            continue
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            if child.id in rewrite_set and not scope.is_bound(child.id):
                out.append((child.lineno, child.col_offset, child.end_col_offset, child.id))
        _collect_name_refs(child, rewrite_set, scope, out)
    return out


class _Wrap:
    """Tiny adapter so _collect_name_refs can recurse into a single node."""
    def __init__(self, node):
        self._node = node
    def __getattr__(self, k):
        return getattr(self._node, k)


# make ast.iter_child_nodes work on _Wrap
_orig_iter = ast.iter_child_nodes
def _iter_child_nodes(node):
    if isinstance(node, _Wrap):
        yield node._node
        return
    yield from _orig_iter(node)
ast.iter_child_nodes = _iter_child_nodes


def _has_global(node):
    return any(isinstance(n, ast.Global) for n in ast.walk(node))


# ── monolith model ───────────────────────────────────────────────────────────
class Node:
    def __init__(self, n, lines):
        self.n = n
        self.start = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
        self.end = n.end_lineno
        # pull in directly-attached leading comment lines
        s = self.start
        while s - 2 >= 0 and lines[s - 2].lstrip().startswith("#") and not lines[s - 2].startswith("# ──"):
            s -= 1
        self.start = s
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self.names = [n.name]
            self.kind = "def"
        elif isinstance(n, ast.Assign):
            self.names = [t.id for t in n.targets if isinstance(t, ast.Name)]
            self.kind = "assign"
            if not self.names and isinstance(n.targets[0], ast.Subscript) and isinstance(n.targets[0].value, ast.Name):
                # `SOME_DICT["k"] = ...` patch statement: travels with SOME_DICT's module
                self.kind = "patch"
                self.anchor = n.targets[0].value.id
        elif isinstance(n, (ast.AnnAssign,)) and isinstance(n.target, ast.Name):
            self.names = [n.target.id]
            self.kind = "assign"
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            self.names = [(al.asname or al.name).split(".")[0] for al in n.names]
            self.kind = "import"
        else:
            self.names = []
            self.kind = "other"

    @property
    def name(self):
        return self.names[0] if self.names else f"<{self.kind}@{self.start}>"


def load_monolith(path):
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    tree = ast.parse(src)
    nodes = [Node(n, lines) for n in tree.body]
    # module-level bound names, including those bound inside top-level if/try blocks
    bound = set()
    for n in tree.body:
        if isinstance(n, (ast.If, ast.Try, ast.With)):
            for sub in ast.walk(n):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    bound.add(sub.name)
                elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    bound.add(sub.id)
                elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                    for al in sub.names:
                        bound.add((al.asname or al.name).split(".")[0])
    for nd in nodes:
        bound.update(nd.names)
    imports = OrderedDict()   # alias -> source line(s)
    for nd in nodes:
        if nd.kind == "import":
            for al in nd.names:
                imports[al] = "\n".join(lines[nd.n.lineno - 1: nd.n.end_lineno])
    return src, lines, tree, nodes, bound, imports


# ── the split ────────────────────────────────────────────────────────────────
def run(plan, dry_run=False):
    mono_path = os.path.join(ROOT, plan["monolith"])
    core = plan["core"]
    pkg = plan["package"]
    kind = plan.get("kind", "plain")
    local_aliases = set(plan.get("local_aliases", ["logger"]))
    src, lines, tree, nodes, bound, imports = load_monolith(mono_path)

    # 1. assignment of nodes to target modules
    target = {}           # node index -> module name
    for mod, spec in plan["modules"].items():
        names = set(spec.get("names", []))
        ranges = spec.get("ranges", [])
        for i, nd in enumerate(nodes):
            if nd.kind in ("import", "other"):
                continue
            hit = bool(names & set(nd.names)) or any(a <= nd.n.lineno <= b for a, b in ranges)
            if not hit:
                continue
            if _has_global(nd.n):
                print(f"  keep (global stmt): {nd.name}")
                continue
            if i in target and target[i] != mod:
                raise SystemExit(f"node {nd.name} claimed by both {target[i]} and {mod}")
            target[i] = mod
    moved_names = {}      # name -> module
    for i, mod in target.items():
        for nm in nodes[i].names:
            moved_names[nm] = mod
    # `SOME_DICT["k"] = ...` top-level patch statements follow SOME_DICT
    for i, nd in enumerate(nodes):
        if nd.kind == "patch" and i not in target and nd.anchor in moved_names:
            target[i] = moved_names[nd.anchor]

    # Imports of PROJECT modules (db, notifier, scraper, ...) are late-bound too:
    # tests patch e.g. `app.get_workspace_invite` (a `from db import` alias), so a
    # sub-module must resolve it through core at call time. Stdlib / third-party
    # imports are replicated verbatim in each sub-module header.
    def _is_project_import(alias):
        src_line = imports[alias]
        m = re.match(r"\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", src_line)
        root = ((m.group(1) or m.group(2)) if m else "").split(".")[0]
        return (os.path.exists(os.path.join(ROOT, root + ".py")) or
                (os.path.isdir(os.path.join(ROOT, root)) and
                 os.path.exists(os.path.join(ROOT, root, "__init__.py"))))
    forced = set(plan.get("latebind_imports", []))
    latebind_imports = {a for a in imports if a in forced or _is_project_import(a)}
    import_names = set(imports) - latebind_imports
    core_defs = (bound - import_names)   # names to late-bind through core (unless same module)

    # 2. build each module
    outputs = {}
    per_mod_imports = defaultdict(set)
    for mod, spec in plan["modules"].items():
        idxs = sorted(i for i, m in target.items() if m == mod)
        if not idxs:
            print(f"  {mod}: nothing matched")
            continue
        same = {nm for i in idxs for nm in nodes[i].names}
        chunks = []
        for i in idxs:
            nd = nodes[i]
            seg = lines[nd.start - 1: nd.end]
            seg_src = "\n".join(seg)
            # names referenced: rewrite core defs (not same-module, not local aliases) + collect imports
            rewrite_set = (core_defs - same - local_aliases) | import_names | local_aliases
            refs = _collect_name_refs(_Wrap(nd.n), rewrite_set)
            edits = []
            for ln, c0, c1, ident in refs:
                if ident in import_names and ident not in core_defs:
                    per_mod_imports[mod].add(ident)
                    continue
                if ident in local_aliases:
                    per_mod_imports[mod].add(ident)
                    continue
                if ident in same:
                    continue
                edits.append((ln, c0, c1, ident))
            # apply edits right-to-left per line (offsets are in the original file's columns)
            seg_lines = seg[:]
            for ln, c0, c1, ident in sorted(edits, key=lambda e: (e[0], -e[1])):
                li = ln - nd.start
                line = seg_lines[li]
                # ast col offsets are in UTF-8 bytes
                b = line.encode("utf-8")
                assert b[c0:c1].decode("utf-8") == ident, (nd.name, ln, ident, b[c0:c1])
                seg_lines[li] = (b[:c0] + f"core.{ident}".encode("utf-8") + b[c1:]).decode("utf-8")
            seg_src = "\n".join(seg_lines)
            # paths built from __file__ must keep pointing at the project root
            seg_src = re.sub(r"(?<![\w.])__file__\b", "core.__file__", seg_src)
            if kind == "flask":
                seg_src = re.sub(r"^(\s*)@core\.app\.route\(", r"\1@bp.route(", seg_src, flags=re.M)
                if re.search(r"@core\.app\.(before|after|errorhandler|teardown)", seg_src):
                    raise SystemExit(f"{nd.name}: app-level hook decorator can't move to a blueprint")
            chunks.append(seg_src)
        outputs[mod] = (idxs, chunks, spec)

    # 2b. import order: a module whose MODULE-LEVEL code (constants, decorators,
    # defaults) references a name moved to another module needs that module
    # imported (and re-exported through core) first. Topologically sort; a cycle
    # is a hard error (merge those modules in the plan).
    def _import_time_refs(nd):
        n = nd.n
        subs = []
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            subs += n.decorator_list + n.args.defaults + [d for d in n.args.kw_defaults if d is not None]
        elif isinstance(n, ast.ClassDef):
            subs += n.decorator_list + n.bases + n.body
        else:
            subs.append(n)
        refs = set()
        for s in subs:
            refs.update(r[3] for r in _collect_name_refs(_Wrap(s), set(moved_names)))
        return refs
    deps = {mod: set() for mod in outputs}
    for mod, (idxs, chunks, spec) in outputs.items():
        for i in idxs:
            for ref in _import_time_refs(nodes[i]):
                other = moved_names.get(ref)
                if other and other != mod:
                    deps[mod].add(other)
    ordered, pending = [], OrderedDict((m, set(d)) for m, d in deps.items())
    while pending:
        ready = [m for m, d in pending.items() if not d]
        if not ready:
            raise SystemExit(f"import-time dependency cycle between modules: "
                             f"{ {m: sorted(d) for m, d in pending.items()} }")
        for m in ready:
            ordered.append(m)
            del pending[m]
        for d in pending.values():
            d.difference_update(ready)
    outputs = OrderedDict((m, outputs[m]) for m in ordered)

    # 2c. anything left in the monolith that runs at import time and touches a
    # moved name would NameError (the re-export block sits at the bottom).
    for i, nd in enumerate(nodes):
        if i in target or nd.kind in ("import",):
            continue
        if nd.kind == "def":
            refs = _import_time_refs(nd)
        else:
            refs = {r[3] for r in _collect_name_refs(_Wrap(nd.n), set(moved_names))}
        if refs:
            print(f"  WARNING: {plan['monolith']}:{nd.start} {nd.name} references moved name(s) at import time: {sorted(refs)}")

    # 3. emit modules
    os.makedirs(os.path.join(ROOT, pkg), exist_ok=True)
    init_path = os.path.join(ROOT, pkg, "__init__.py")
    written = []
    for mod, (idxs, chunks, spec) in outputs.items():
        hdr = [f'"""{spec.get("doc", mod)}\n\nExtracted from {plan["monolith"]} by scripts/split_monolith.py (2026-09).\n'
               f'Names defined in {plan["monolith"]} are referenced as `core.<name>` (late-bound) so\n'
               f'monkeypatching `{core}.<name>` in tests keeps working; {plan["monolith"]} re-exports\n'
               f'everything defined here.\n"""']
        hdr.append(f"import {core} as core  # noqa: E402  (the monolith; imported at its bottom)")
        needed = per_mod_imports[mod]
        seen = set()
        for alias in imports:
            if alias in needed and imports[alias] not in seen:
                seen.add(imports[alias])
                hdr.append(imports[alias])
        for la in sorted(local_aliases):
            if la in needed:
                hdr.append(f"{la} = core.{la}")
        if kind == "flask":
            hdr.append("from flask import Blueprint")
            hdr.append(f'bp = Blueprint("{mod}", __name__)')
        body = "\n".join(hdr) + "\n\n\n" + "\n\n\n".join(chunks) + "\n"
        path = os.path.join(ROOT, pkg, f"{mod}.py")
        written.append((mod, path, len(chunks), sum(c.count("\n") + 1 for c in chunks)))
        if not dry_run:
            open(path, "w", encoding="utf-8", newline="\n").write(body)

    # 4. rewrite the monolith: drop moved ranges, add bottom import/re-export block
    drop = set()
    for i in target:
        nd = nodes[i]
        for ln in range(nd.start, nd.end + 1):
            drop.add(ln)
    kept = [l for i, l in enumerate(lines, 1) if i not in drop]
    new_src = "\n".join(kept)
    # collapse 3+ blank lines left by removals
    new_src = re.sub(r"\n{4,}", "\n\n\n", new_src)

    block = ["", "", f"# ── sub-modules ({pkg}/) - extracted 2026-09, see scripts/split_monolith.py ──",
             "# Imported here (after every helper above is defined) so they can late-bind",
             f"# `core.<name>` back to this module; their public + private names are re-exported",
             f"# so `{core}.<name>` keeps working for tests, scripts and the scheduler."]
    for mod, (idxs, chunks, spec) in outputs.items():
        names = [nm for i in idxs for nm in nodes[i].names]
        block.append(f"from {pkg}.{mod} import (  # noqa: E402,F401")
        for nm in names:
            block.append(f"    {nm},")
        block.append(")")
        if kind == "flask":
            block.append(f"import {pkg}.{mod} as _{mod}_bp_mod  # noqa: E402")
            block.append(f"app.register_blueprint(_{mod}_bp_mod.bp)")
    block.append("")
    block_src = "\n".join(block)

    m = re.search(r'^if __name__ == ["\']__main__["\']:', new_src, flags=re.M)
    if m:
        new_src = new_src[:m.start()] + block_src + "\n\n" + new_src[m.start():]
    else:
        new_src = new_src.rstrip("\n") + "\n" + block_src

    alias = (f"import sys as _sys\n"
             f"if __name__ == \"__main__\":\n"
             f"    # `python {plan['monolith']}` makes this module __main__; the {pkg}/ sub-modules do\n"
             f"    # `import {core} as core`, which would otherwise execute this file a second time.\n"
             f"    _sys.modules.setdefault(\"{core}\", _sys.modules[__name__])\n")
    if f'_sys.modules.setdefault("{core}"' not in new_src:
        # insert after the module docstring / first import block start
        first_import = re.search(r"^(import |from )", new_src, flags=re.M)
        pos = first_import.start() if first_import else 0
        new_src = new_src[:pos] + alias + new_src[pos:]

    print(f"\n{plan['monolith']}: {len(lines)} -> {new_src.count(chr(10)) + 1} lines; moved {len(target)} nodes")
    for mod, path, n, ln in written:
        print(f"  {pkg}/{mod}.py  nodes={n:3d} lines={ln:5d}")
    if not dry_run:
        open(mono_path, "w", encoding="utf-8", newline="\n").write(new_src)
        if not os.path.exists(init_path):
            open(init_path, "w", encoding="utf-8", newline="\n").write(
                f'"""{pkg}/ - sub-modules extracted from {plan["monolith"]} (see scripts/split_monolith.py)."""\n')
    return written


if __name__ == "__main__":
    plan_path = sys.argv[1]
    plan = json.load(open(plan_path, encoding="utf-8"))
    run(plan, dry_run="--dry-run" in sys.argv)
