from pathlib import Path

path = Path('.github/scripts/profile_v3.py')
s = path.read_text(encoding='utf-8')

replacements = {
    "W,H=1440,9400": "W,H=1440,8750",
    "ay=6570;ab=t5+.7;q=opclip(ay,1530,ab,.8)": "ay=6570;ab=t5+.7;q=opclip(ay,880,ab,.8)",
    "height=\"1530\" rx=\"18\"": "height=\"880\" rx=\"18\"",
    "height=\"860\" rx=\"16\"": "height=\"300\" rx=\"16\"",
    "gy+70+i*76": "gy+58+i*24",
    "gy+840": "gy+280",
    "gy+360": "gy+165",
    "M{gx+56},{gy+250} L{gx+100},{gy+290} L{gx+150},{gy+265} L{gx+210},{gy+355} L{gx+270},{gy+315} L{gx+330},{gy+410} L{gx+390},{gy+300} L{gx+450},{gy+370} L{gx+510},{gy+275} L{gx+570},{gy+350} L{gx+630},{gy+395} L{gx+690},{gy+250} L{gx+750},{gy+410} L{gx+810},{gy+355} L{gx+870},{gy+390} L{gx+930},{gy+340} L{gx+990},{gy+430} L{gx+1050},{gy+320} L{gx+1130},{gy+370}": "M{gx+56},{gy+105} L{gx+100},{gy+130} L{gx+150},{gy+115} L{gx+210},{gy+170} L{gx+270},{gy+145} L{gx+330},{gy+205} L{gx+390},{gy+135} L{gx+450},{gy+180} L{gx+510},{gy+120} L{gx+570},{gy+165} L{gx+630},{gy+195} L{gx+690},{gy+105} L{gx+750},{gy+205} L{gx+810},{gy+170} L{gx+870},{gy+190} L{gx+930},{gy+160} L{gx+990},{gy+220} L{gx+1050},{gy+150} L{gx+1130},{gy+180}",
    "fy=8280": "fy=7650",
    "y1=\"8980\" x2=\"1328\" y2=\"8980\"": "y1=\"8320\" x2=\"1328\" y2=\"8320\"",
    "y=\"9052\"": "y=\"8392\""
}

missing = []
for old, new in replacements.items():
    if old not in s:
        missing.append(old)
    else:
        s = s.replace(old, new)

if missing:
    raise SystemExit('Expected patterns not found:\n' + '\n'.join(missing))

path.write_text(s, encoding='utf-8')
print('Compacted FrameView panel in profile_v3.py')
