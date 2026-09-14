import json
import sys
import urllib.request

url = sys.argv[1] if len(sys.argv) > 1 else ""
if not url:
    print("ERROR: pass the service URL as an argument")
    sys.exit(1)

endpoint = f"{url.rstrip('/')}/api/opportunities"

print(f"=== GET {endpoint} ===")
with urllib.request.urlopen(endpoint, timeout=60) as resp:
    data = json.loads(resp.read().decode())

print(f"Total opportunities returned: {len(data)}")
print()

found = False
for o in data:
    if o.get('id') == 'CLI101':
        found = True
        print("client  :", o.get('name'))
        print("RM      :", o.get('rm_name'))
        print()
        print("why_now :", (o.get('why_now') or '')[:300])
        print()
        print("action  :", (o.get('action') or '')[:350])
        break

if not found:
    print("CLI101 not found in the response")
