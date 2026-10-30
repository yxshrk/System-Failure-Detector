#!/usr/bin/env bash
# Assemble the full report from its sections and export it to Word (pandoc; no LaTeX needed).
set -euo pipefail
cd "$(dirname "$0")"
(cd .. && .venv/bin/python -m experiments.encodings > report/encodings.md)   # Appendix B, generated from the code
sed '/<!-- RESULTS -->/d' report.md > full.md
for part in results.md discussion.md tail.md references.md appendix.md encodings.md; do
  printf '\n\n' >> full.md
  cat "$part" >> full.md
done
pandoc full.md -o report.docx --resource-path=.:..
# PDF: standalone HTML (MathML equations, embedded images) printed by headless Chrome
pandoc full.md -s --mathml --embed-resources --resource-path=.:.. --css print.css \
  --metadata pagetitle="AI Pre-Mortems" -o report.html
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ -x "$CHROME" ]; then
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$PWD/report.pdf" "file://$PWD/report.html" 2>/dev/null
  echo "wrote report/report.pdf"
fi
echo "wrote report/full.md and report/report.docx ($(wc -w < full.md) words incl. tables)"
