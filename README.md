# Claude Code Token Benchmark

Reproducible A/B token-cost measurement for any Claude Code install. Backs the
public claim from [Loadout](https://loadout.hellomilo.app): a routed Claude
Code architecture loads ~83% fewer always-loaded tokens per turn than a
monolithic CLAUDE.md preserving the same captured knowledge.

The script is standalone. No Loadout install required. Run it against your own
`~/.claude/` and see the numbers from your own setup.

**Status:** live and runnable. Reference numbers measured 2026-05-25.

## What this measures

Two architectures, same accumulated knowledge:

| Architecture | Always-loaded tokens / turn | Notes |
|---|---:|---|
| **Routed (Loadout shape)** | CLAUDE.md + MEMORY.md index only | Rules and memory entries load on demand via routing |
| **Monolithic** | The same files concatenated into one CLAUDE.md | Everything paid for on every turn |

The script measures both surfaces against AJ's actual install (1 CLAUDE.md, 6
rules files, 85 memory entries) using Anthropic's `count_tokens` API.
Headline reference numbers from that run:

- Routed: **15,083 tokens / turn**
- Monolithic equivalent: **91,252 tokens / turn**
- Delta: **76,169 fewer tokens, 83.5% reduction, 6.05x smaller**

(Measured 2026-05-25 against AJ's `~/.claude/`. Your numbers will differ based
on the size of your accumulated knowledge surface. The architectural gap
widens with use.)

## Reproduce

Requires Python 3.10+ and an Anthropic API key.

```bash
git clone https://github.com/ajeenkya/loadout-benchmark.git
cd loadout-benchmark
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 ab-token-test.py
```

The script:

1. Reads your `~/.claude/CLAUDE.md` and `~/.claude/projects/*/memory/MEMORY.md`
   (the routed always-loaded surface).
2. Walks `~/.claude/rules/*.md` and `~/.claude/projects/*/memory/*.md` (the
   captured knowledge that would have to be inlined to drop routing).
3. Counts tokens for both configurations via
   `anthropic.messages.count_tokens`.
4. Writes `ab_results.json` with the full breakdown.

If your `~/.claude/` is empty or close to default, the gap will look small.
Run it again after a few months of accumulated memory entries. The routed
surface stays roughly flat (routing pointers are ~30 tokens each) while the
monolithic equivalent grows linearly with every captured lesson.

## What this doesn't measure

End-to-end conversation token cost. That's dominated by the model's own system
prompt, tool schemas, MCP server instructions, and the conversation itself.
None of which Loadout touches. The claim is bounded to the user-controllable
context layer (CLAUDE.md + memory + rules), and the benchmark measures
exactly that.

Anthropic's prompt cache applies to both architectures equally during active
sessions. The benchmark measures pre-cache token count because cache hit rate
is workload-dependent. Cold starts, edits to CLAUDE.md, model switches, and
long idle gaps all invalidate cache. The smaller your always-loaded surface,
the lower the cost floor when cache misses.

## Tech

Python 3.10+, `anthropic` SDK, `count_tokens` API. ~150 lines, no other
dependencies.

## License

MIT. Fork it, run it, share it. If you publish numbers from your own install,
link back and we'll be happy to compare notes.

## More

The full architecture this script measures (memory, rules, hooks, focus,
voice, the doc-cascade routing pattern) is documented at
[loadout.hellomilo.app](https://loadout.hellomilo.app). The benchmark script
is enough to verify the headline claim. The guide is for installing the
architecture in your own stack.

---

Built by [Ajeenkya Bhatalkar](https://ajeenkya.github.io).
