"""A/B token test: Loadout architecture vs naive monolithic CLAUDE.md.

Uses Anthropic's count_tokens endpoint for exact token counts (no estimates).

Two comparisons:
  (1) Always-loaded surface: what Claude reads on every single turn.
  (2) Modeled week: 20 realistic prompt scenarios across mixed work.

Both scenarios compare:
  - Loadout: CLAUDE.md + MEMORY.md index always loaded, rules + memory entries
    loaded only when a routing condition fires.
  - Monolithic: everything concatenated into one always-loaded CLAUDE.md.

Reproduces the headline number from Loadout's marketing copy against your own
~/.claude/ install. If your captured knowledge is small, your delta is small.
The gap scales with what you've written down.

USAGE:
    export ANTHROPIC_API_KEY=...
    python3 ab-token-test.py

OPTIONAL OVERRIDES (env vars):
    CLAUDE_HOME    Path to your Claude home dir. Default: ~/.claude
    MEMORY_DIR     Path to the memory dir holding MEMORY.md and entry files.
                   Default: auto-discovered (most-recently-modified memory dir
                   under $CLAUDE_HOME/projects/*/memory/).
    MODEL          Anthropic model id for token counting. Default: claude-opus-4-5
    OUT            Path to write JSON summary. Default: ./ab_results.json
"""
from __future__ import annotations
import os
import sys
import json
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.stderr.write(
        "missing dependency: anthropic\n"
        "  install with: pip install anthropic   (or: uv pip install anthropic)\n"
    )
    sys.exit(1)


CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude")))
MODEL = os.environ.get("MODEL", "claude-opus-4-5")
OUT = Path(os.environ.get("OUT", "ab_results.json"))


def discover_memory_dir() -> Path:
    """Find the memory dir for the active project under $CLAUDE_HOME/projects/.

    Claude Code stores per-project memory at
    ~/.claude/projects/<encoded-cwd>/memory/. Pick the one with MEMORY.md whose
    parent was modified most recently.
    """
    explicit = os.environ.get("MEMORY_DIR")
    if explicit:
        return Path(explicit)

    candidates = sorted(
        (p for p in (CLAUDE_HOME / "projects").glob("*/memory") if (p / "MEMORY.md").is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        sys.stderr.write(
            f"no memory dir found under {CLAUDE_HOME}/projects/*/memory/ with MEMORY.md\n"
            f"set MEMORY_DIR=... to point at one explicitly\n"
        )
        sys.exit(1)
    return candidates[0]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def count(client, text: str) -> int:
    resp = client.messages.count_tokens(
        model=MODEL,
        system=text,
        messages=[{"role": "user", "content": "x"}],
    )
    return resp.input_tokens


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write("ANTHROPIC_API_KEY is required\n")
        sys.exit(1)

    claude_md_path = CLAUDE_HOME / "CLAUDE.md"
    rules_dir = CLAUDE_HOME / "rules"
    memory_dir = discover_memory_dir()
    memory_index = memory_dir / "MEMORY.md"

    if not claude_md_path.is_file():
        sys.stderr.write(f"missing: {claude_md_path}\n")
        sys.exit(1)

    client = anthropic.Anthropic()

    claude_md = read(claude_md_path)
    mem_index = read(memory_index)
    rules_files = sorted(rules_dir.glob("*.md")) if rules_dir.is_dir() else []
    memory_files = sorted(p for p in memory_dir.glob("*.md") if p.name != "MEMORY.md")

    print("Inventory:")
    print(f"  CLAUDE_HOME         : {CLAUDE_HOME}")
    print(f"  memory dir          : {memory_dir}")
    print(f"  CLAUDE.md           : {len(claude_md):>7,} chars")
    print(f"  MEMORY.md (index)   : {len(mem_index):>7,} chars")
    print(f"  rules files         : {len(rules_files):>3} files")
    print(f"  memory entry files  : {len(memory_files):>3} files")
    print()

    loadout_always = claude_md + "\n\n" + mem_index
    monolithic_parts = [claude_md, mem_index]
    for rf in rules_files:
        monolithic_parts.append(read(rf))
    for mf in memory_files:
        monolithic_parts.append(read(mf))
    monolithic_always = "\n\n".join(monolithic_parts)

    print(f"Counting tokens (Anthropic count_tokens, model={MODEL})...")
    loadout_tokens = count(client, loadout_always)
    monolithic_tokens = count(client, monolithic_always)

    print()
    print("=" * 70)
    print("ALWAYS-LOADED SURFACE")
    print("=" * 70)
    print(f"  Loadout    (CLAUDE.md + MEMORY.md index): {loadout_tokens:>7,} tokens")
    print(f"  Monolithic (everything in CLAUDE.md)    : {monolithic_tokens:>7,} tokens")
    delta = monolithic_tokens - loadout_tokens
    pct = (delta / monolithic_tokens) * 100 if monolithic_tokens else 0
    print(f"  Delta                                   : {delta:>+7,} tokens "
          f"({pct:.1f}% reduction)")
    if loadout_tokens:
        print(f"  Monolithic is {monolithic_tokens / loadout_tokens:.2f}x larger")
    print()

    rules_tokens = {rf.stem: count(client, read(rf)) for rf in rules_files}
    memory_tokens = {mf.stem: count(client, read(mf)) for mf in memory_files}

    if rules_tokens:
        print("Per-rules-file token costs:")
        for name, tok in sorted(rules_tokens.items(), key=lambda x: -x[1]):
            print(f"  rules/{name+'.md':<28} {tok:>5,} tokens")
    if memory_tokens:
        print(f"  memory entries (mean per file)     : "
              f"{sum(memory_tokens.values()) / len(memory_tokens):.0f} tokens")
        print(f"  memory entries (total all {len(memory_tokens)} files): "
              f"{sum(memory_tokens.values()):,} tokens")
    print()

    mean_memory_per_turn = 2
    mean_memory_tok = (
        (sum(memory_tokens.values()) / len(memory_tokens) * mean_memory_per_turn)
        if memory_tokens else 0
    )

    week = [
        ("Python script work",        []),
        ("Python script work",        []),
        ("Python: pandas/data",       []),
        ("iOS Swift debugging",       ["ios"]),
        ("iOS Swift debugging",       ["ios"]),
        ("iOS XcodeGen change",       ["ios"]),
        ("gstack skill misfire",      ["gstack"]),
        ("Video prompt writing",      ["video-gen-prompting"]),
        ("Video prompt writing",      ["video-gen-prompting"]),
        ("Generic chat / Q&A",        []),
        ("Generic chat / Q&A",        []),
        ("Generic chat / Q&A",        []),
        ("Session-end /context-save", ["doc-cascade", "lesson-routing"]),
        ("Tricky collab moment",      ["collaboration"]),
        ("Tricky collab moment",      ["collaboration"]),
        ("Lesson routing decision",   ["lesson-routing"]),
        ("Bash/CLI work",             []),
        ("Reading docs",              []),
        ("Reading docs",              []),
        ("Multi-stack debug",         ["ios", "gstack"]),
    ]

    loadout_week_total = 0
    monolithic_week_total = 0
    print("Modeled week (20 mixed turns, ~2 memory entries pulled per turn):")
    print(f"  {'Turn scenario':<32} {'Loadout':>10} {'Monolithic':>11}")
    for label, rules_loaded in week:
        loaded = loadout_tokens + sum(rules_tokens.get(r, 0) for r in rules_loaded) + mean_memory_tok
        loadout_week_total += loaded
        monolithic_week_total += monolithic_tokens
        print(f"  {label:<32} {loaded:>10,.0f} {monolithic_tokens:>11,}")
    print()
    print(f"  Week totals:")
    print(f"    Loadout    : {loadout_week_total:>10,.0f} tokens")
    print(f"    Monolithic : {monolithic_week_total:>10,} tokens")
    week_delta = monolithic_week_total - loadout_week_total
    week_pct = (week_delta / monolithic_week_total) * 100 if monolithic_week_total else 0
    print(f"    Reduction  : {week_delta:>10,.0f} tokens ({week_pct:.1f}%)")
    if loadout_week_total:
        print(f"    Monolithic is {monolithic_week_total / loadout_week_total:.2f}x larger")
    print()

    summary = {
        "always_loaded": {
            "loadout_tokens": loadout_tokens,
            "monolithic_tokens": monolithic_tokens,
            "reduction_tokens": delta,
            "reduction_pct": round(pct, 1),
            "monolithic_multiple": round(monolithic_tokens / loadout_tokens, 2) if loadout_tokens else None,
        },
        "modeled_week_20_turns": {
            "loadout_total": round(loadout_week_total),
            "monolithic_total": monolithic_week_total,
            "reduction_tokens": round(week_delta),
            "reduction_pct": round(week_pct, 1),
            "monolithic_multiple": round(monolithic_week_total / loadout_week_total, 2) if loadout_week_total else None,
        },
        "components": {
            "claude_md_tokens": count(client, claude_md),
            "memory_index_tokens": count(client, mem_index),
            "rules_total_tokens": sum(rules_tokens.values()),
            "memory_entries_total_tokens": sum(memory_tokens.values()),
            "memory_entry_count": len(memory_files),
            "rules_file_count": len(rules_files),
        },
        "paths": {
            "claude_home": str(CLAUDE_HOME),
            "memory_dir": str(memory_dir),
        },
        "model": MODEL,
    }
    OUT.write_text(json.dumps(summary, indent=2))
    print(f"Summary JSON: {OUT}")


if __name__ == "__main__":
    main()
