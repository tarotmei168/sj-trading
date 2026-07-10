import ast

def analyze(filepath, label):
    with open(filepath, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    classes = []
    toplevel_funcs = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            funcs = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append({'name': node.name, 'methods': funcs})
        elif isinstance(node, ast.FunctionDef) and isinstance(node.parent, ast.Module):
            toplevel_funcs.append(node.name)
    
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    
    for c in classes:
        print(f"\n  📦 {c['name']}")
        for m in c['methods']:
            print(f"    ├─ {m}()")
    
    if toplevel_funcs:
        print(f"\n  📦 頂層函式")
        for f in toplevel_funcs:
            print(f"    ├─ {f}()")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f"\n  📊 總行數: {len(lines)} 行")

# Monkey-patch parent references
for node in ast.walk(ast.parse(open('src/sj_trading/triple_engine_v2.py', encoding='utf-8').read())):
    for child in ast.walk(node):
        pass
