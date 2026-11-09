"""Minimal static check: undefined names and unused imports (no third-party linter needed)."""
import ast, builtins, sys
from pathlib import Path

problems = 0
for path in sorted(Path(".").rglob("*.py")):
    if ".venv" in path.parts or "build" in path.parts:
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    defined, imported, used = set(dir(builtins)), {}, set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                n = (a.asname or a.name).split(".")[0]
                defined.add(n); imported[n] = node.lineno
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
            if not isinstance(node, ast.ClassDef):
                for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                    defined.add(a.arg)
                if node.args.vararg: defined.add(node.args.vararg.arg)
                if node.args.kwarg: defined.add(node.args.kwarg.arg)
        elif isinstance(node, ast.Lambda):
            for a in node.args.args + node.args.kwonlyargs:
                defined.add(a.arg)
            if node.args.vararg: defined.add(node.args.vararg.arg)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, (ast.Store, ast.Del)): defined.add(node.id)
            else: used.add((node.id, node.lineno))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
    names_used = {n for n, _ in used}
    for name, line in sorted(used, key=lambda x: x[1]):
        if name not in defined:
            print(f"{path}:{line}: undefined name '{name}'"); problems += 1
    for name, line in imported.items():
        if name not in names_used and path.name != "__init__.py" and name != "annotations":
            # attribute access like `os.name` counts as Name usage already
            print(f"{path}:{line}: unused import '{name}'"); problems += 1
print("problems:", problems)
sys.exit(1 if problems else 0)
