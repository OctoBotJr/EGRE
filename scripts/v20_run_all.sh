#!/bin/sh
# V-20: run R1-R4 against the local model. Detached (nohup) so it survives
# a Claude Code session restart -- check progress via runs/v2-r*/ and this
# script's own log, not by assuming the launching session stays alive.
set -eu
cd "$(dirname "$0")/.."
source .venv/bin/activate

export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
PROGRAMS="crc32_clean,fnv1a_clean,adler32_clean,djb2_clean,fnv1a_crcdecoy,crc32_obfpoly,djb2_fnvdecoy,fnv1_clean,jamcrc_clean,crc32c_clean,sdbm_execdecoy"

echo "=== R1 (hypotheses) $(date) ==="
python -m egre.cli.run --llm openai --model qwen3.5:4b --repeats 1 --programs "$PROGRAMS" \
  --hypotheses --out runs/v2-r1

echo "=== R2 (hypotheses + query_graph) $(date) ==="
python -m egre.cli.run --llm openai --model qwen3.5:4b --repeats 1 --programs "$PROGRAMS" \
  --hypotheses --query-graph --out runs/v2-r2

echo "=== R3 (hypotheses + query_graph + revision) $(date) ==="
python -m egre.cli.run --llm openai --model qwen3.5:4b --repeats 1 --programs "$PROGRAMS" \
  --hypotheses --query-graph --revision --out runs/v2-r3

echo "=== R4 (hypotheses + query_graph + knowledge, open world) $(date) ==="
python -m egre.cli.run --llm openai --model qwen3.5:4b --repeats 1 --programs "$PROGRAMS" \
  --hypotheses --query-graph --knowledge --out runs/v2-r4

echo "=== ALL DONE $(date) ==="
