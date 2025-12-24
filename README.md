# InProdigo (Memory for Pega/Prodigo)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Gives AI coding assistants persistent memory for Pega applications processed by Prodigo.

---

## Quick Start

### Installation

```bash
# Install globally from GitHub
npm install -g github:vincentsider/inprodigo

# Or use directly with npx
npx github:vincentsider/inprodigo --help
```

### Connect to Your AI Tool

**Claude Desktop** - Add to your config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "in-memoria": {
      "command": "npx",
      "args": ["github:vincentsider/inprodigo", "server"]
    }
  }
}
```

**Claude Code CLI**:

```bash
claude mcp add in-memoria -- npx github:vincentsider/inprodigo server
```

**GitHub Copilot (VS Code)** - Add to your VS Code `settings.json`:

```json
{
  "github.copilot.chat.experimental.mcpServers": {
    "in-memoria": {
      "command": "npx",
      "args": ["github:vincentsider/inprodigo", "server"]
    }
  }
}
```

Then restart VS Code and use Copilot Chat (`Cmd+Shift+I`).

> **Note**: MCP support in Copilot is experimental. Requires latest VS Code and Copilot extension.

---

## Prodigo / Pega Support

This fork adds support for **Prodigo output** - processed Pega application exports. Since Pega rules are XML-based (not traditional code), In-Memoria's tree-sitter parsing doesn't work directly. Instead, we provide an ingestion script that populates In-Memoria's database from Prodigo's pre-processed JSONL manifests.

### What the Ingestion Script Does

The script (`scripts/ingest-prodigo-to-inmemoria.py`) reads Prodigo output and populates In-Memoria's SQLite database:

| Prodigo Source | In-Memoria Table | What It Contains |
|----------------|------------------|------------------|
| `rules.jsonl` | `semantic_concepts` | All Pega rules as searchable concepts |
| `edges.jsonl` | `feature_map` | Flows mapped to their dependencies |
| `nodes.jsonl` | `entry_points` | Portals and main flows as entry points |
| `pipeline-summary.json` | `project_metadata` | Application info and tech stack |

### Setup for Pega Projects

**1. Clone this repo to get the ingestion script:**

```bash
git clone https://github.com/vincentsider/inprodigo
```

**2. Run the ingestion script on your Prodigo output:**

```bash
python inprodigo/scripts/ingest-prodigo-to-inmemoria.py ./prodigo-output/manifests/AppName::Version
```

The script expects this structure:
```
prodigo-output/
├── manifests/AppName::Version/
│   ├── rules.jsonl          # Parsed rule metadata
│   ├── in-memoria.db        # Database will be populated here
│   └── pipeline-summary.json
└── graph/AppName::Version/
    ├── edges.jsonl           # Rule dependencies
    └── nodes.jsonl           # Graph nodes
```

**3. Query your Pega application in Claude/Copilot:**

Just talk naturally:

```
You: "Find all approval-related rules in my Pega app"

Claude: "I found 43 approval-related concepts including:
         - approvalrejection_flow_2 (workflow)
         - emailapproval-9 (correspondence)
         - approvalstatus (property)
         ..."

You: "What workflows handle credit proposals?"

Claude: "Based on the feature map, I found these credit-related workflows:
         - createcreditproposal (18 dependencies)
         - creditbusinessanalysis_flow (25 dependencies)
         - creditriskanalysis_flow (20 dependencies)
         ..."
```

Claude automatically uses the In-Memoria MCP tools behind the scenes.

### What About the XML Files?

The ingestion script reads **JSONL manifests** (pre-processed by Prodigo), not the raw XMLs:

```
prodigo-output/
├── xml/AppName::Version/        ← Raw Pega XMLs (NOT read by ingestion)
│   └── Rule-Obj-Flow/...            Contains full rule definitions
├── manifests/AppName::Version/  ← JSONL metadata (READ by ingestion)
│   ├── rules.jsonl                  Rule names, types, references
│   └── in-memoria.db                Populated by our script
└── graph/AppName::Version/      ← Dependency data (READ by ingestion)
    └── edges.jsonl                  Rule-to-rule relationships
```

**When are XMLs needed?**
- Searching/finding rules → No (JSONL has metadata)
- Understanding dependencies → No (JSONL has relationships)
- **Implementing new features** → Yes (XMLs have full rule logic)
- **Generating new rules** → Yes (need XML format)

When you ask Claude to help implement a Pega feature, it will:
1. Search via In-Memoria (fast, uses database)
2. Read relevant XMLs (for actual rule content)
3. Generate new/modified XMLs (for implementation)

### Key Differences from Standard In-Memoria

| Feature | Standard | With Prodigo |
|---------|----------|--------------|
| Learning | `auto_learn_if_needed` parses code | Run ingestion script manually |
| File types | JS, TS, Python, etc. | XML rules via JSONL manifests |
| Concepts | Functions, classes, variables | Pega rules (flows, properties, sections) |
| Path parameter | Optional | Required (points to manifest directory) |

---

## Standard Codebases (Non-Pega)

For regular codebases (JavaScript, TypeScript, Python, etc.), this fork works the same as the original In-Memoria:

```bash
# Analyze and learn from your project
npx github:vincentsider/inprodigo learn ./my-project

# Or let AI agents trigger learning automatically
npx github:vincentsider/inprodigo server
```

### Language Support

Native AST parsing via tree-sitter for:

- TypeScript & JavaScript (including JSX/TSX)
- Python
- PHP
- Rust
- Go
- Java
- C & C++
- C#
- Svelte
- SQL

---

## How It Works

In Memoria is built on Rust + TypeScript, using the Model Context Protocol to connect AI tools to persistent codebase intelligence.

### Architecture

```
┌─────────────────────┐    MCP     ┌──────────────────────┐    napi-rs    ┌─────────────────────┐
│  AI Tool (Claude)   │◄──────────►│  TypeScript Server   │◄─────────────►│   Rust Core         │
└─────────────────────┘            └──────────┬───────────┘               │  • AST Parser       │
                                              │                           │  • Pattern Learner  │
                                              │                           │  • Semantic Engine  │
                                              ▼                           │  • Blueprint System │
                                   ┌──────────────────────┐               └─────────────────────┘
                                   │ SQLite (persistent)  │
                                   │ SurrealDB (in-mem)   │
                                   └──────────────────────┘
```

### MCP Tools for AI Assistants

In Memoria provides **13 specialized tools** that AI assistants can call via MCP:

**Core Analysis:**
- `analyze_codebase` - Analyze files/directories with concepts, patterns, complexity
- `search_codebase` - Multi-mode search (semantic/text/pattern)

**Intelligence:**
- `learn_codebase_intelligence` - Deep learning to extract patterns and architecture
- `get_project_blueprint` - Instant project context with tech stack and entry points
- `get_semantic_insights` - Query learned concepts and relationships (supports `path` parameter for Prodigo)
- `get_pattern_recommendations` - Get patterns with related files for consistency
- `predict_coding_approach` - Implementation guidance with file routing
- `get_developer_profile` - Access coding style and work context
- `contribute_insights` - Record architectural decisions

**Automation:**
- `auto_learn_if_needed` - Smart auto-learning with staleness detection

**Monitoring:**
- `get_system_status` - Health check
- `get_intelligence_metrics` - Analytics on learned patterns
- `get_performance_status` - Performance diagnostics

---

## Build from Source

```bash
git clone https://github.com/vincentsider/inprodigo
cd inprodigo
npm install
npm run build:ts   # TypeScript only (no Rust required)
npm run build      # Full build (requires Rust 1.70+)
```

**Requirements:**
- Node.js 18+
- Rust 1.70+ (only for full build)

---

## Credits

This is a fork of [In-Memoria](https://github.com/pi22by7/In-Memoria) by [@pi22by7](https://github.com/pi22by7).

**Changes in this fork:**
- Added `path` parameter to `get_semantic_insights` for project-specific databases
- Added Prodigo ingestion script (`scripts/ingest-prodigo-to-inmemoria.py`)
- Updated documentation for Pega/Prodigo workflows

## License

MIT - see [LICENSE](LICENSE)

---

**Try it**: `npx github:vincentsider/inprodigo server`

_In memoria: in memory. Because your AI assistant should remember._
