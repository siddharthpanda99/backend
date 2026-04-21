import sys
import os
import json

# Setup path
sys.path.append(os.getcwd())

from app.modules.plugins.routes.router import _load_kb_graph

def analyze_graph():
    print("Fetching graph data...")
    data = _load_kb_graph()
    
    nodes = data['nodes']
    edges = data['edges']
    
    node_ids = {n['id'] for n in nodes}
    print(f"Total Nodes: {len(nodes)}")
    print(f"Unique Node IDs: {len(node_ids)}")
    
    if len(nodes) != len(node_ids):
        print("!!! WARNING: Duplicate Node IDs detected !!!")
        seen = set()
        for n in nodes:
            if n['id'] in seen:
                print(f"Duplicate ID: {n['id']} (Name: {n['label']})")
            seen.add(n['id'])

    orphan_edges = 0
    missing_targets = set()
    for e in edges:
        if e['from'] not in node_ids:
            orphan_edges += 1
            missing_targets.add(e['from'])
        if e['to'] not in node_ids:
            orphan_edges += 1
            missing_targets.add(e['to'])
            
    print(f"Total Edges: {len(edges)}")
    print(f"Orphan Ends (not in node list): {orphan_edges}")
    if missing_targets:
        print(f"Sample missing IDs: {list(missing_targets)[:10]}")

if __name__ == "__main__":
    analyze_graph()
