import os

d = r'D:\Open_code_project\injection_mold_flow\validation_test\0'
os.makedirs(d, exist_ok=True)
print(f'Created directory: {d}')
print(f'Exists check: {os.path.isdir(d)}')

# Create U file
with open(os.path.join(d,'U'), 'w', encoding='ascii') as f:
    f.write('FoamFile { version 2.0; format ascii; class volVectorField; object U; }\n')
    f.write('dimensions [0 1 -1 0 0 0 0];\n')
    f.write('internalField uniform (0 0 0);\n')
    f.write('boundaryField\n')
    f.write('{\n')
    f.write('    gate_inlet { type fixedValue; value uniform (0.25 0 0); }\n')
    f.write('    outlet     { type zeroGradient; }\n')
    f.write('    walls      { type noSlip; }\n')
    f.write('}\n')

# Create p file
with open(os.path.join(d,'p'), 'w', encoding='ascii') as f:
    f.write('FoamFile { version 2.0; format ascii; class volScalarField; object p; }\n')
    f.write('dimensions [0 2 -2 0 0 0 0];\n')
    f.write('internalField uniform 1e5;\n')
    f.write('boundaryField\n')
    f.write('{\n')
    f.write('    gate_inlet { type zeroGradient; }\n')
    f.write('    outlet     { type fixedValue; value uniform 1e5; }\n')
    f.write('    walls      { type zeroGradient; }\n')
    f.write('}\n')

# Create alpha file
with open(os.path.join(d,'alpha'), 'w', encoding='ascii') as f:
    f.write('FoamFile { version 2.0; format ascii; class volScalarField; object alpha; }\n')
    f.write('dimensions [0 0 0 0 0 0 0];\n')
    f.write('internalField uniform 0;\n')
    f.write('boundaryField\n')
    f.write('{\n')
    f.write('    gate_inlet { type fixedValue; value uniform 1; }\n')
    f.write('    outlet     { type inletOutlet; inletValue uniform 0; value uniform 0; }\n')
    f.write('    walls      { type zeroGradient; }\n')
    f.write('}\n')

# Create T file
with open(os.path.join(d,'T'), 'w', encoding='ascii') as f:
    f.write('FoamFile { version 2.0; format ascii; class volScalarField; object T; }\n')
    f.write('dimensions [0 0 0 1 0 0 0];\n')
    f.write('internalField uniform 503.15;\n')
    f.write('boundaryField\n')
    f.write('{\n')
    f.write('    gate_inlet { type fixedValue; value uniform 503.15; }\n')
    f.write('    outlet     { type zeroGradient; }\n')
    f.write('    walls      { type fixedValue; value uniform 323.15; }\n')
    f.write('}\n')

print('All 4 field files created successfully')
for fn in ['U','p','alpha','T']:
    fp = os.path.join(d,fn)
    with open(fp,'rb') as f:
        raw = f.read()
    print(f'  {fn}: {len(raw)} bytes, first bytes={raw[:20]}')
