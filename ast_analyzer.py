import ast
import os
import sys
from pathlib import Path

def get_type_hint(annotation):
    if annotation is None:
        return "Any"
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Subscript):
        # A simple approximation for Subscript (e.g. List[str])
        value = get_type_hint(annotation.value)
        slice_hint = get_type_hint(annotation.slice)
        return f"{value}[{slice_hint}]"
    elif isinstance(annotation, ast.Constant):
        return repr(annotation.value)
    elif isinstance(annotation, ast.Tuple):
        return "Tuple[" + ", ".join(get_type_hint(elt) for elt in annotation.elts) + "]"
    elif isinstance(annotation, ast.Attribute):
        return f"{get_type_hint(annotation.value)}.{annotation.attr}"
    return "Any"

def has_node_decorator(node):
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == 'node':
            return True
        elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == 'node':
            return True
    return False

def extract_function_details(func_node):
    inputs = []
    for arg in func_node.args.args:
        if arg.arg == 'self':
            continue
        arg_type = get_type_hint(arg.annotation)
        inputs.append(f"{arg.arg}: {arg_type}")
    
    # Handle kwargs / varargs if needed
    if func_node.args.vararg:
        inputs.append(f"*{func_node.args.vararg.arg}")
    if func_node.args.kwarg:
        inputs.append(f"**{func_node.args.kwarg.arg}")
        
    outputs = get_type_hint(func_node.returns) if func_node.returns else "Any"
    is_node = has_node_decorator(func_node)
    
    return {
        "name": func_node.name,
        "inputs": ", ".join(inputs),
        "outputs": outputs,
        "is_node": is_node
    }

def analyze_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
    except Exception as e:
        return {"error": str(e)}

    classes = []
    functions = []
    
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            class_methods = []
            is_node_class = has_node_decorator(node)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef) or isinstance(child, ast.AsyncFunctionDef):
                    # We might only care about public methods
                    if not child.name.startswith('_') or child.name == '__init__':
                        class_methods.append(extract_function_details(child))
            
            classes.append({
                "name": node.name,
                "is_node": is_node_class,
                "methods": class_methods
            })
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if not node.name.startswith('_'):
                functions.append(extract_function_details(node))
                
    return {"classes": classes, "functions": functions}

def main():
    repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo")
    search_dirs = [
        repo_root / "Backend Monorepo" / "Python Libs" / "common_lib" / "src" / "common_lib" / "modules"
    ]
    
    output_file = repo_root / "FUNCTIONALITY_AUDIT.md"
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("# Platform Functionality Audit\n\n")
        out.write("This document lists all classes and functions across the platform modules, highlighting their inputs/outputs and whether they are exposed as `@node`.\n\n")
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                print(f"Warning: Directory {search_dir} does not exist.")
                continue
                
            out.write(f"## Directory: `{search_dir.relative_to(repo_root)}`\n\n")
            
            # Walk directory
            for root, _, files in os.walk(search_dir):
                for file in files:
                    if file.endswith('.py') and file != '__init__.py':
                        filepath = Path(root) / file
                        rel_path = filepath.relative_to(search_dir)
                        
                        analysis = analyze_file(filepath)
                        if "error" in analysis:
                            continue
                            
                        if not analysis["classes"] and not analysis["functions"]:
                            continue
                            
                        out.write(f"### {rel_path}\n\n")
                        
                        # 1. @node Functions/Classes
                        node_items = []
                        non_node_items = []
                        
                        for c in analysis["classes"]:
                            if c["is_node"]:
                                node_items.append(f"**Class:** `{c['name']}`")
                                for m in c["methods"]:
                                    node_items.append(f"  - `{m['name']}({m['inputs']}) -> {m['outputs']}`" + (" [@node]" if m["is_node"] else ""))
                            else:
                                non_node_items.append(f"**Class:** `{c['name']}`")
                                for m in c["methods"]:
                                    if m["is_node"]:
                                        node_items.append(f"**Method:** `{c['name']}.{m['name']}({m['inputs']}) -> {m['outputs']}` [@node]")
                                    else:
                                        non_node_items.append(f"  - `{m['name']}({m['inputs']}) -> {m['outputs']}`")
                                        
                        for f in analysis["functions"]:
                            if f["is_node"]:
                                node_items.append(f"**Function:** `{f['name']}({f['inputs']}) -> {f['outputs']}` [@node]")
                            else:
                                non_node_items.append(f"**Function:** `{f['name']}({f['inputs']}) -> {f['outputs']}`")
                                
                        if node_items:
                            out.write("#### Exposed as `@node`\n")
                            for item in node_items:
                                out.write(f"- {item}\n")
                            out.write("\n")
                            
                        if non_node_items:
                            out.write("#### Non-`@node` Functionality (Gaps)\n")
                            for item in non_node_items:
                                out.write(f"- {item}\n")
                            out.write("\n")
                            
    print(f"Generated {output_file}")

if __name__ == "__main__":
    main()
