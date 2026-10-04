from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
web = ROOT / "web"
files = [p for p in web.rglob("*") if p.is_file() and "vendor" not in p.parts and "fonts" not in p.parts]
required_fonts = {
    "IBMPlexSans-Regular.woff2",
    "IBMPlexSans-SemiBold.woff2",
    "IBMPlexMono-Regular.woff2",
    "SourceSerif4-Regular.woff2",
}
errors = []
font_dir = web / "fonts"
for fname in sorted(required_fonts):
    if not (font_dir / fname).exists():
        errors.append(f"web/fonts/{fname}: declared font file is missing")

declared_fonts = set()
for p in files:
    text = p.read_text(encoding="utf-8", errors="ignore")
    checks = [
        (r"(?:linear|radial|conic)-gradient\s*\(", "gradient"),
        (r"backdrop-filter", "backdrop filter"),
        (r"filter\s*:\s*[^;]*blur\s*\(", "blur filter"),
        (r"box-shadow\s*:", "box shadow"),
        (r"text-transform\s*:\s*uppercase", "uppercase transform"),
        (r"letter-spacing\s*:\s*[0-9.]+em", "wide letter spacing"),
        (r"border-radius\s*:\s*(?:[5-9]|[1-9]\d+)px", "large radius"),
        (r"@(?:import|font-face)[^{]*(?:https?:)?//", "remote font/import"),
        (r"@keyframes", "keyframes"),
        (r"transition\s*:[^;]*\b(?:160|[2-9]\d{2}|\d{4,})ms", "long transition"),
        (r"(?:\u2014|--\s)", "em dash"),
        (r"[\U0001F300-\U0001FAFF]", "emoji"),
    ]
    for pat, name in checks:
        if re.search(pat, text, flags=re.I):
            errors.append(f"{p.relative_to(ROOT)}: {name}")
    for m in re.finditer(r"font-family\s*:\s*[\"']?([^;,{\"']+)", text, flags=re.I):
        declared_fonts.add(m.group(1).strip())

allowed_families = {"IBM Plex Sans", "IBM Plex Mono", "Source Serif 4", "sans-serif", "monospace", "serif"}
for fam in declared_fonts:
    if fam not in allowed_families:
        errors.append(f"font family {fam}")

css = (web / "app.css").read_text(encoding="utf-8")
for fname in required_fonts:
    if fname not in css:
        errors.append(f"web/app.css: missing @font-face reference to {fname}")

if errors:
    print("SLOP SCAN FAILED")
    for e in errors:
        print("-", e)
    sys.exit(1)
print("SLOP SCAN PASSED")
