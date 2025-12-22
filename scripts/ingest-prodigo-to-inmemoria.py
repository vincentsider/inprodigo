#!/usr/bin/env python3
"""
Ingest Prodigo output into In-Memoria database.

Maps:
- rules.jsonl → semantic_concepts (each rule as a searchable concept)
- edges.jsonl → feature_map (flows as features with their dependencies)
- nodes.jsonl → project_metadata + entry_points

Usage:
    python ingest-prodigo-to-inmemoria.py /path/to/prodigo-output/manifests/AppName::Version

The script expects:
    - manifests_dir/rules.jsonl
    - manifests_dir/pipeline-summary.json
    - manifests_dir/../graph/AppName::Version/edges.jsonl
    - manifests_dir/../graph/AppName::Version/nodes.jsonl
"""

import json
import sqlite3
import uuid
import sys
import argparse
from pathlib import Path
from collections import defaultdict


def load_jsonl(path: Path) -> list:
    """Load a JSONL file into a list of dicts."""
    items = []
    with open(path, 'r') as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def populate_project_metadata(conn, manifests_dir: Path):
    """Insert project metadata."""
    cursor = conn.cursor()

    # Load pipeline summary for metadata
    with open(manifests_dir / "pipeline-summary.json") as f:
        summary = json.load(f)

    app_name = summary.get('applicationId', manifests_dir.name)

    cursor.execute("""
        INSERT OR REPLACE INTO project_metadata
        (project_id, project_path, project_name, language_primary, languages_detected, framework_detected, intelligence_version, last_full_scan)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        app_name,
        str(manifests_dir),
        app_name,
        "Pega",
        json.dumps(["Pega", "XML", "JSONL"]),
        "Pega Platform",
        "1.0.0"
    ))

    print(f"✓ Inserted project metadata for {app_name}")
    conn.commit()


def populate_semantic_concepts(conn, manifests_dir: Path):
    """Map rules to semantic concepts for searchability."""
    cursor = conn.cursor()
    rules = load_jsonl(manifests_dir / "rules.jsonl")

    # Map Pega rule types to concept types
    type_mapping = {
        'Rule-Obj-Flow': 'workflow',
        'Rule-Obj-FlowAction': 'action',
        'Rule-Obj-Property': 'property',
        'Rule-Obj-Model': 'data_transform',
        'Rule-HTML-Section': 'ui_component',
        'Rule-HTML-Harness': 'ui_component',
        'Rule-Portal': 'portal',
        'Rule-Declare-Pages': 'data_page',
        'Rule-Obj-Report-Definition': 'report',
        'Rule-Declare-DecisionTable': 'decision',
        'Rule-Declare-Expressions': 'expression',
        'Rule-Obj-When': 'condition',
        'Rule-Access-When': 'condition',
        'Rule-Obj-Activity': 'activity',
        'Rule-Obj-Corr': 'correspondence',
        'Rule-Notification': 'notification',
        'Rule-Connect-SQL': 'connector',
    }

    count = 0
    for rule in rules:
        concept_type = type_mapping.get(rule['ruleType'], 'rule')

        # Build relationships from references
        relationships = []
        for ref in rule.get('references', []):
            relationships.append({
                'type': ref.get('type'),
                'name': ref.get('name'),
                'class': ref.get('class')
            })

        cursor.execute("""
            INSERT OR REPLACE INTO semantic_concepts
            (id, concept_name, concept_type, confidence_score, relationships, file_path, line_range)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            rule['rule_id'],
            rule['ruleName'],
            concept_type,
            1.0,  # High confidence - these are actual rules
            json.dumps(relationships),
            f"xml/{manifests_dir.name}/{rule['ruleType']}/{rule['ruleName']}.xml",
            json.dumps({'appliesTo': rule['appliesTo'], 'ruleset': rule['ruleset']})
        ))
        count += 1

    print(f"✓ Inserted {count} semantic concepts from rules")
    conn.commit()


def populate_feature_map(conn, manifests_dir: Path, graph_dir: Path):
    """Build feature map from flows and their dependencies."""
    cursor = conn.cursor()

    edges = load_jsonl(graph_dir / "edges.jsonl")
    nodes = load_jsonl(graph_dir / "nodes.jsonl")

    # Build node lookup
    node_lookup = {n['id']: n for n in nodes}

    # Group edges by source (flows as features)
    flow_deps = defaultdict(list)
    for edge in edges:
        src = edge['src']
        if 'Rule-Obj-Flow' in src:
            flow_deps[src].append({
                'dst': edge['dst'],
                'type': edge['type'],
                'confidence': edge.get('confidence', 'Unknown')
            })

    # Also find what each flow is called by
    flow_callers = defaultdict(list)
    for edge in edges:
        dst = edge['dst']
        if 'Rule-Obj-Flow' in dst:
            flow_callers[dst].append(edge['src'])

    count = 0
    for flow_id, deps in flow_deps.items():
        node = node_lookup.get(flow_id, {})
        flow_name = node.get('ruleName', flow_id.split('.')[-1])

        # Primary files = the flow itself
        primary_files = [f"xml/{manifests_dir.name}/Rule-Obj-Flow/{flow_name}.xml"]

        # Related files = all dependencies
        related_files = list(set(d['dst'] for d in deps))

        # Dependencies as structured data
        dependencies = deps

        cursor.execute("""
            INSERT OR REPLACE INTO feature_map
            (id, project_path, feature_name, primary_files, related_files, dependencies, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            flow_id,
            str(manifests_dir),
            flow_name,
            json.dumps(primary_files),
            json.dumps(related_files),
            json.dumps(dependencies),
            'active'
        ))
        count += 1

    print(f"✓ Inserted {count} features from flows")
    conn.commit()


def populate_entry_points(conn, manifests_dir: Path):
    """Identify entry points (portals, main flows)."""
    cursor = conn.cursor()
    rules = load_jsonl(manifests_dir / "rules.jsonl")

    count = 0
    for rule in rules:
        entry_type = None
        if rule['ruleType'] == 'Rule-Portal':
            entry_type = 'web'
        elif rule['ruleType'] == 'Rule-Obj-Flow' and 'main' in rule['ruleName'].lower():
            entry_type = 'workflow'

        if entry_type:
            cursor.execute("""
                INSERT OR REPLACE INTO entry_points
                (id, project_path, entry_type, file_path, description, framework)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                rule['rule_id'],
                str(manifests_dir),
                entry_type,
                f"xml/{manifests_dir.name}/{rule['ruleType']}/{rule['ruleName']}.xml",
                f"{rule['ruleType']}: {rule['ruleName']} ({rule['appliesTo']})",
                'Pega'
            ))
            count += 1

    print(f"✓ Inserted {count} entry points")
    conn.commit()


def populate_key_directories(conn, manifests_dir: Path):
    """Add key directories for navigation."""
    cursor = conn.cursor()

    # Count files in each directory
    rules = load_jsonl(manifests_dir / "rules.jsonl")

    directories = [
        ('xml', 'Raw Pega rule XML exports', 'source', len(rules)),
        ('manifests', 'Processed rule metadata and summaries', 'config', 10),
        ('graph', 'Dependency graph data', 'data', 5),
    ]

    for dir_name, desc, dir_type, file_count in directories:
        cursor.execute("""
            INSERT OR REPLACE INTO key_directories
            (id, project_path, directory_path, directory_type, file_count, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            str(manifests_dir),
            f"prodigo-output/{dir_name}/{manifests_dir.name}",
            dir_type,
            file_count,
            desc
        ))

    print(f"✓ Inserted {len(directories)} key directories")
    conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description='Ingest Prodigo output into In-Memoria database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python ingest-prodigo-to-inmemoria.py ./prodigo-output/manifests/WRBank::01.01.01

The script will:
    1. Read rules.jsonl and populate semantic_concepts table
    2. Read edges.jsonl and populate feature_map table
    3. Identify entry points (portals, main flows)
    4. Create project metadata

After running, you can query with:
    get_semantic_insights(query="approval", path="./prodigo-output/manifests/WRBank::01.01.01")
        """
    )
    parser.add_argument(
        'manifests_dir',
        type=Path,
        help='Path to the Prodigo manifests directory (e.g., prodigo-output/manifests/AppName::Version)'
    )
    parser.add_argument(
        '--graph-dir',
        type=Path,
        help='Path to the graph directory (defaults to ../graph/AppName::Version relative to manifests)'
    )

    args = parser.parse_args()

    manifests_dir = args.manifests_dir.resolve()

    # Determine graph directory
    if args.graph_dir:
        graph_dir = args.graph_dir.resolve()
    else:
        # Default: assume parallel structure prodigo-output/graph/AppName::Version
        graph_dir = manifests_dir.parent.parent / "graph" / manifests_dir.name

    # Validate paths
    if not manifests_dir.exists():
        print(f"Error: Manifests directory not found: {manifests_dir}")
        sys.exit(1)

    if not (manifests_dir / "rules.jsonl").exists():
        print(f"Error: rules.jsonl not found in {manifests_dir}")
        sys.exit(1)

    if not graph_dir.exists():
        print(f"Warning: Graph directory not found: {graph_dir}")
        print("Feature map will not be populated.")

    db_path = manifests_dir / "in-memoria.db"
    print(f"Connecting to: {db_path}")
    conn = sqlite3.connect(db_path)

    try:
        populate_project_metadata(conn, manifests_dir)
        populate_semantic_concepts(conn, manifests_dir)

        if graph_dir.exists():
            populate_feature_map(conn, manifests_dir, graph_dir)

        populate_entry_points(conn, manifests_dir)
        populate_key_directories(conn, manifests_dir)

        # Summary
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM semantic_concepts")
        concepts = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM feature_map")
        features = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM entry_points")
        entries = cursor.fetchone()[0]

        print(f"\n✅ Ingestion complete!")
        print(f"   - {concepts} semantic concepts")
        print(f"   - {features} features mapped")
        print(f"   - {entries} entry points")
        print(f"\nDatabase: {db_path}")
        print(f"\nNow use with In-Memoria:")
        print(f'   get_semantic_insights(query="...", path="{manifests_dir}")')

    finally:
        conn.close()


if __name__ == "__main__":
    main()
