from pathlib import Path

path = Path('.github/scripts/profile_v3.py')
text = path.read_text(encoding='utf-8')


def rep(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected profile pattern not found: {old[:120]!r}')
    text = text.replace(old, new, 1)


rep("W,H=1440,12000", "W,H=1440,9400")
rep(".rule{stroke:#fff;stroke-opacity:.075;stroke-width:1.35}.term{fill:none;stroke:#454545;stroke-width:1.6}", ".rule{stroke:#fff;stroke-opacity:.095;stroke-width:1.6}.term{fill:none;stroke:#5A5A5A;stroke-width:2.8}")
rep('y="{y-31}" width="0" height="43"', 'y="{y-82 if \'hero\' in cl else y-31}" width="0" height="{110 if \'hero\' in cl else 43}"')
rep("('Strecker',340,220,'sans fg hero',2.45,1.05,420)", "('Strecker',340,220,'sans fg hero',2.45,1.05,460)")

rep("y=840;t=shell(y,1080,11.55)", "y=840;t=shell(y,840,11.55)")
rep("y=2110;t=shell(y,1280,t1)", "y=1830;t=shell(y,1020,t1)")
rep("y=3570;t=shell(y,1160,t2)", "y=3030;t=shell(y,980,t2)")
rep("y=4910;t=shell(y,1020,t3)", "y=4160;t=shell(y,850,t3)")
rep("y=6110;t=shell(y,1500,t4)", "y=5170;t=shell(y,1235,t4)")

rep("ay=7830;ab=t5+.7;q=opclip(ay,1650,ab,.8)", "ay=6570;ab=t5+.7;q=opclip(ay,1530,ab,.8)")
rep('width="1216" height="1650" rx="18" fill="#020202" stroke="#343434"', 'width="1216" height="1530" rx="18" fill="#020202" stroke="#5B5B5B" stroke-width="3"')
rep('width="1216" height="72" rx="18" fill="#0B0B0B"', 'width="1216" height="72" rx="18" fill="#0B0B0B" stroke="#3F3F3F" stroke-width="2"')
rep('width="1168" height="62" rx="12" fill="#080808" stroke="#292929"', 'width="1168" height="62" rx="12" fill="#080808" stroke="#3A3A3A" stroke-width="1.9"')
rep('width="500" height="176" rx="16" fill="#060606" stroke="#2B2B2B"', 'width="500" height="176" rx="16" fill="#060606" stroke="#3A3A3A" stroke-width="1.9"')
rep('width="1168" height="108" rx="16" fill="#060606" stroke="#2B2B2B"', 'width="1168" height="108" rx="16" fill="#060606" stroke="#3A3A3A" stroke-width="1.9"')
rep('width="1168" height="930" rx="16" fill="#010101" stroke="#2B2B2B"', 'width="1168" height="860" rx="16" fill="#010101" stroke="#454545" stroke-width="2.3"')
rep('stroke-width="3" stroke-dasharray="16 14"', 'stroke-width="3.4" stroke-dasharray="16 14"')
rep('fill="none" stroke="#76B900" stroke-width="4" pathLength="1"', 'fill="none" stroke="#76B900" stroke-width="4.4" pathLength="1"')

rep("fy=9690;fs=shell(fy,1350,ab+8.4)", "fy=8280;fs=shell(fy,500,ab+8.4)")
rep('y1="11320" x2="1328" y2="11320"', 'y1="8980" x2="1328" y2="8980"')
rep('y="11392" class="mono dim foot"', 'y="9052" class="mono dim foot"')
rep('y="11392" class="mono dim foot" text-anchor="end"', 'y="9052" class="mono dim foot" text-anchor="end"')

path.write_text(text, encoding='utf-8')
print('Applied compact profile layout tuning')
