import ast
import os
import sys
from pathlib import Path

def check_file(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    try:
        tree = ast.parse(code, filename=str(path))
    except Exception as e:
        return [f"SyntaxError in {path}: {e}"]
        
    errors = []
    # Collect all imported names AND top-level class/function definitions
    known_names = set(dir(__builtins__))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                known_names.add(n.asname or n.name)
        elif isinstance(node, ast.ImportFrom):
            for n in node.names:
                known_names.add(n.asname or n.name)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            known_names.add(node.name)
                
    # Check annotations
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # check arg annotations
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.annotation:
                    errors.extend(_check_annotation(arg.annotation, known_names, path, node.name))
            if node.returns:
                errors.extend(_check_annotation(node.returns, known_names, path, node.name))
        elif isinstance(node, ast.AnnAssign):
            if node.annotation:
                errors.extend(_check_annotation(node.annotation, known_names, path, "variable"))
                
    return errors

def _check_annotation(node, known_names, path, context):
    errors = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            if sub.id not in known_names:
                errors.append(f"Undefined annotation '{sub.id}' in {path} (context: {context})")
    return errors

def main():
    root = Path(__file__).resolve().parent.parent
    all_errors = []
    
    for folder in ["src", "api", "config"]:
        folder_path = root / folder
        if not folder_path.exists():
            continue
        for p in folder_path.rglob("*.py"):
            errs = check_file(p)
            all_errors.extend(errs)
            
    print(f"AST & Annotation Scan Complete. Found {len(all_errors)} errors.")
    for err in all_errors:
        print("  -", err)
        
    if all_errors:
        sys.exit(1)
    else:
        print("ALL TYPE ANNOTATIONS AND IMPORTS ARE VALID!")

if __name__ == "__main__":
    main()
