"""
Convert seed.py connector data to a JSON resource file.
Uses text processing to bypass Python's nested parentheses limit.
"""
import json
import re
import os

def py_to_json_text(text: str) -> str:
    """Convert a Python dict literal string to valid JSON string."""
    text = re.sub(r'(?<!")\bTrue\b(?!")', 'true', text)
    text = re.sub(r'(?<!")\bFalse\b(?!")', 'false', text)
    text = re.sub(r'(?<!")\bNone\b(?!")', 'null', text)
    
    result = []
    in_single = False
    in_double = False
    escaped = False
    
    for ch in text:
        if escaped:
            result.append(ch)
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            result.append(ch)
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            result.append('"')
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            result.append('"')
            continue
        result.append(ch)
    
    text = ''.join(result)
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    return text


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    seed_path = os.path.join(script_dir, 'seed.py')
    
    # Output to app/resources/ directory
    app_resources = os.path.join(os.path.dirname(script_dir), 'resources')
    os.makedirs(app_resources, exist_ok=True)
    output_path = os.path.join(app_resources, 'connector_seeds.json')
    
    print(f"Reading {seed_path}...")
    with open(seed_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print(f"File size: {len(text):,} chars")
    
    # Find the return statement
    idx = text.find('def get_connector_seeds()')
    returns_idx = text.find('return [', idx)
    start = returns_idx + len('return [')
    
    # Find matching closing bracket using str.find for efficiency
    depth = 1
    pos = start
    while depth > 0 and pos < len(text):
        ob = text.find('[', pos)
        cb = text.find(']', pos)
        if cb == -1:
            print("ERROR: no closing bracket found")
            return
        if ob != -1 and ob < cb:
            depth += 1
            pos = ob + 1
        else:
            depth -= 1
            pos = cb + 1
    
    content = text[start:pos - 1]  # Exclude the closing ]
    print(f"Content: {len(content):,} chars")
    
    # Extract all connectors by tracking brace depth
    connectors = []
    depth = 0
    current = []
    in_connector = False
    
    for ch in content:
        if ch == '{':
            depth += 1
            in_connector = True
            current.append(ch)
        elif ch == '}':
            depth -= 1
            current.append(ch)
            if depth == 0 and in_connector:
                connectors.append(''.join(current))
                current = []
                in_connector = False
        elif in_connector:
            current.append(ch)
    
    print(f"Extracted {len(connectors)} connectors")
    
    json_connectors = []
    for i, conn_text in enumerate(connectors):
        try:
            json_text = py_to_json_text(conn_text)
            parsed = json.loads(json_text)
            conn_id = parsed.get('id', f'connector_{i}')
            tool_count = len(parsed.get('tools', []))
            services = parsed.get('metadata_json', {}).get('services', [])
            svc_tools = sum(len(s.get('tools', [])) for s in services)
            print(f"  [{i}] {conn_id}: {tool_count} tools + {svc_tools} service tools = {tool_count + svc_tools}")
            json_connectors.append(parsed)
        except json.JSONDecodeError as e:
            print(f"  [{i}] ERROR: {e}")
            debug_path = os.path.join(script_dir, f'connector_{i}_debug.py')
            with open(debug_path, 'w', encoding='utf-8') as df:
                df.write(conn_text[:5000])
            print(f"       Saved first 5k chars to {debug_path}")
    
    # Write JSON output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_connectors, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Wrote {len(json_connectors)} connectors to {output_path}")
    print(f"   File size: {os.path.getsize(output_path):,} bytes")
    
    # Summary
    total_tools = 0
    total_svc_tools = 0
    for conn in json_connectors:
        t = len(conn.get('tools', []))
        s = conn.get('metadata_json', {}).get('services', [])
        st = sum(len(svc.get('tools', [])) for svc in s)
        total_tools += t
        total_svc_tools += st
    print(f"\n📊 Total: {total_tools} top-level tools + {total_svc_tools} service tools = {total_tools + total_svc_tools}")


if __name__ == '__main__':
    main()
