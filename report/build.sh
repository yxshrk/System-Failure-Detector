#!/usr/bin/env bash
# Assemble the full report from its sections and export it to Word (pandoc; no LaTeX needed).
set -euo pipefail
cd "$(dirname "$0")"
sed '/<!-- RESULTS -->/d' report.md > full.md
for part in results.md discussion.md tail.md references.md appendix.md; do
  printf '\n\n' >> full.md
  cat "$part" >> full.md
done
pandoc full.md -o report.docx --resource-path=.:..
echo "wrote report/full.md and report/report.docx ($(wc -w < full.md) words incl. tables)"
