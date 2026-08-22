from pathlib import Path

path = Path('.github/scripts/profile_v3.py')
text = path.read_text(encoding='utf-8')

replacements = [
    ('W,H=1440,8750;', 'W,H=1440,8120;'),
    ('q=opclip(ay,880,ab,.8)', 'q=opclip(ay,780,ab,.8)'),
    ('width="1216" height="880" rx="18"', 'width="1216" height="780" rx="18"'),
    ('width="1168" height="300" rx="16"', 'width="1168" height="220" rx="16"'),
    ('y1="{gy+58+i*24}" x2="{gx+1130}" y2="{gy+58+i*24}"', 'y1="{gy+48+i*16}" x2="{gx+1130}" y2="{gy+48+i*16}"'),
    ('y1="{gy+70}" x2="{gx+56+i*84}" y2="{gy+280}"', 'y1="{gy+54}" x2="{gx+56+i*84}" y2="{gy+205}"'),
    ('y1="{gy+165}" x2="{gx+1130}" y2="{gy+165}"', 'y1="{gy+130}" x2="{gx+1130}" y2="{gy+130}"'),
    ("p=f'M{gx+56},{gy+105} L{gx+100},{gy+130} L{gx+150},{gy+115} L{gx+210},{gy+170} L{gx+270},{gy+145} L{gx+330},{gy+205} L{gx+390},{gy+135} L{gx+450},{gy+180} L{gx+510},{gy+120} L{gx+570},{gy+165} L{gx+630},{gy+195} L{gx+690},{gy+105} L{gx+750},{gy+205} L{gx+810},{gy+170} L{gx+870},{gy+190} L{gx+930},{gy+160} L{gx+990},{gy+220} L{gx+1050},{gy+150} L{gx+1130},{gy+180}'", "p=f'M{gx+56},{gy+84} L{gx+100},{gy+102} L{gx+150},{gy+92} L{gx+210},{gy+136} L{gx+270},{gy+116} L{gx+330},{gy+165} L{gx+390},{gy+108} L{gx+450},{gy+144} L{gx+510},{gy+96} L{gx+570},{gy+132} L{gx+630},{gy+157} L{gx+690},{gy+84} L{gx+750},{gy+165} L{gx+810},{gy+136} L{gx+870},{gy+152} L{gx+930},{gy+128} L{gx+990},{gy+176} L{gx+1050},{gy+120} L{gx+1130},{gy+144}'"),
    ('fy=7650;', 'fy=7420;'),
    ('y1="8320" x2="1328" y2="8320"', 'y1="7990" x2="1328" y2="7990"'),
    ('x="112" y="8392"', 'x="112" y="8055"'),
    ('x="1328" y="8392"', 'x="1328" y="8055"'),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Expected exactly one match for {old!r}, found {count}')
    text = text.replace(old, new)

path.write_text(text, encoding='utf-8')
print('Applied compact FrameView panel v2 tuning.')
