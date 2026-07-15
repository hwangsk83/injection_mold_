import os
path = 'system_auditor.py'
with open(path, 'r', encoding='utf-8') as f:
    data = f.read()
# Remove ALL lines containing REPLACE
import re
cleaned = re.sub(r'^.*REPLACE.*\n?', '', data, flags=re.MULTILINE)
with open(path, 'w', encoding='utf-8') as f:
    f.write(cleaned)
print('Fixed. Removed all REPLACE lines.')