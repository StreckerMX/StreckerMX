from pathlib import Path
import re

path = Path("assets/profile-hero.svg")
text = path.read_text(encoding="utf-8")

pattern = re.compile(
    r'<rect y="-620" width="1440" height="620" fill="url\(#scan\)">'
    r'<animate attributeName="y" from="-620" to="(?P<end>\d+)" dur="42s" repeatCount="indefinite"/>'
    r'</rect>'
)

match = pattern.search(text)
if not match:
    raise SystemExit("Could not find the generated profile scan animation")

end = match.group("end")
replacement = (
    '<g id="profile-scans">'
    f'<rect y="-620" width="1440" height="620" fill="url(#scan)"><animate attributeName="y" from="-620" to="{end}" dur="24s" begin="0s" repeatCount="indefinite"/></rect>'
    f'<rect y="-620" width="1440" height="620" fill="url(#scan)"><animate attributeName="y" from="-620" to="{end}" dur="24s" begin="-12s" repeatCount="indefinite"/></rect>'
    '</g>'
)

path.write_text(pattern.sub(replacement, text, count=1), encoding="utf-8")
print("Enhanced profile scan cadence: 2 bands, 24 s cycle, 12 s stagger")
