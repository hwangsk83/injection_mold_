import os, sys

sys.stdout = open(1, 'w', encoding='ascii', closefd=False)

d = r'D:\Open_code_project\injection_mold_flow\dummy_mold_case\0'
for f in ['U', 'p', 'alpha', 'T']:
    fp = os.path.join(d, f)
    if not os.path.isfile(fp):
        print(f'MISSING: {fp}')
        continue
    with open(fp, 'rb') as fh:
        raw = fh.read()
    print(f'--- {f} ({len(raw)} bytes) ---')
    print(raw.decode('ascii', errors='replace'))
    print()

print('=== DECOMP LOG CHECK ===')
decomp = r'D:\Open_code_project\injection_mold_flow\validation_test\log.decomposePar'
if os.path.isfile(decomp):
    with open(decomp, 'r') as fh:
        for line in fh:
            if 'FV fields' in line or 'no FV' in line or 'Decomposing' in line:
                print(f'DECOMP: {line.strip()}')

print('=== PROCESSOR 0 POLYDIR ===')
p0 = r'D:\Open_code_project\injection_mold_flow\validation_test\processor0'
if os.path.isdir(p0):
    for root, dirs, files in os.walk(p0):
        for fn in files:
            fp = os.path.join(root, fn)
            print(f'  {os.path.relpath(fp, p0)} ({os.path.getsize(fp)}B)')
else:
    print('  processor0 NOT FOUND')
