# Structured Output with TextFSM

NAAS supports structured output parsing via TextFSM, converting raw command output into
typed data structures (list of dicts). This eliminates custom parsing logic in client applications.

## Quick Start

Use the `/v1/send_command_structured` endpoint:

```bash
curl -k -u "username:password" https://localhost:8443/v1/send_command_structured \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version", "show ip interface brief"]
  }'
```

## How It Works

1. **Automatic template lookup** — Uses [ntc-templates](https://github.com/networktocode/ntc-templates),
   a community library with 1000+ TextFSM templates for common vendor commands
2. **Template matching** — Netmiko matches `(platform, command)` to a template automatically
3. **Structured output** — Returns `list[dict]` per command instead of raw strings
4. **Fallback** — If no template exists, returns raw string (same as `/v1/send_command`)

## Return Type

Results are `list[dict]` when a template is found, `str` when no template exists:

```json
{
  "job_id": "...",
  "status": "finished",
  "results": {
    "show version": [
      {
        "hostname": "router1",
        "version": "15.0(2)SE",
        "uptime": "1 week, 2 days"
      }
    ],
    "show ip interface brief": [
      {"interface": "Gi0/1", "ip_address": "192.168.1.1", "status": "up"},
      {"interface": "Gi0/2", "ip_address": "192.168.1.2", "status": "down"}
    ]
  }
}
```

**Client code must handle both types:**

```python
result = response["results"]["show version"]
if isinstance(result, list):
    # Parsed output
    for item in result:
        print(item["hostname"])
else:
    # Raw string (no template found)
    print(result)
```

## Custom Templates

Supply your own TextFSM template for commands not covered by ntc-templates:

```json
{
  "ip": "192.168.1.1",
  "platform": "cisco_ios",
  "commands": ["show custom output"],
  "textfsm_template": "Value FIELD1 (\\S+)\\nValue FIELD2 (\\S+)\\n\\nStart\\n  ^${FIELD1}\\s+${FIELD2} -> Record"
}
```

### Template Syntax

TextFSM templates define:

- **Value** lines: field names and regex capture groups
- **States**: parsing state machine (Start, Record, etc.)
- **Rules**: regex patterns that match lines and extract values

Example template for `show ip interface brief`:

```text
Value INTERFACE (\S+)
Value IP_ADDRESS (\S+)
Value STATUS (up|down|administratively down)

Start
  ^${INTERFACE}\s+${IP_ADDRESS}.*${STATUS} -> Record
```

See [TextFSM documentation](https://github.com/google/textfsm/wiki) for full syntax.

## Platform Autodetect

Use `platform: "autodetect"` to fingerprint unknown devices:

```json
{
  "ip": "192.168.1.1",
  "platform": "autodetect",
  "commands": ["show version"]
}
```

The detected platform is returned in the response:

```json
{
  "job_id": "...",
  "status": "finished",
  "detected_platform": "cisco_nxos",
  "results": { ... }
}
```

**Note:** Autodetect adds a second SSH connection overhead and is not compatible with
connection pooling. Best for discovery workflows, not production automation.

## When to Use Structured Output

**Use `/v1/send_command_structured` when:**

- You need typed data for programmatic processing
- The command is covered by ntc-templates (check [the template index](https://github.com/networktocode/ntc-templates/tree/master/ntc_templates/templates))
- You're willing to handle mixed return types (list vs string)

**Use `/v1/send_command` when:**

- You need raw output for logging/display
- The command has no ntc-template and you don't want to write one
- You want consistent return types (always string)

## Limitations

- **No connection pooling** — TextFSM parsing state makes pooling unreliable
- **Template availability** — not all commands have templates; check ntc-templates coverage
- **Return type variance** — client code must handle both `list[dict]` and `str`
- **Performance** — parsing adds ~10-50ms per command depending on output size

## Examples

### Inventory Collection

```python
import requests

response = requests.post(
    "https://naas.local/v1/send_command_structured",
    auth=("user", "pass"),
    json={
        "ip": "192.168.1.1",
        "platform": "cisco_ios",
        "commands": ["show version", "show inventory"]
    },
    verify=False
)

job_id = response.json()["job_id"]

# Poll for results
result = requests.get(
    f"https://naas.local/v1/send_command_structured/{job_id}",
    auth=("user", "pass"),
    verify=False
).json()

for device in result["results"]["show version"]:
    print(f"{device['hostname']}: {device['version']}")
```

### Discovery with Autodetect

```python
response = requests.post(
    "https://naas.local/v1/send_command_structured",
    auth=("user", "pass"),
    json={
        "ip": "192.168.1.1",
        "platform": "autodetect",
        "commands": ["show version"]
    },
    verify=False
)

# ... poll for results ...

print(f"Detected platform: {result['detected_platform']}")
```

### Custom Template

```python
# Custom template for a non-standard command
template = """
Value VLAN_ID (\d+)
Value VLAN_NAME (\S+)
Value STATUS (active|suspended)

Start
  ^${VLAN_ID}\s+${VLAN_NAME}\s+${STATUS} -> Record
"""

response = requests.post(
    "https://naas.local/v1/send_command_structured",
    auth=("user", "pass"),
    json={
        "ip": "192.168.1.1",
        "platform": "cisco_ios",
        "commands": ["show vlan brief"],
        "textfsm_template": template
    },
    verify=False
)
```

## TTP (Template Text Parser)

[TTP](https://ttp.readthedocs.io/) is an alternative parser with Jinja2-like syntax. Use it when you prefer TTP's template style or need features not available in TextFSM.

Pass a `ttp_template` instead of `textfsm_template` — the two are mutually exclusive:

```bash
curl -k -u "username:password" https://localhost:8443/v1/send_command_structured \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show interfaces"],
    "ttp_template": "interface {{ interface }}\n ip address {{ ip }} {{ mask }}"
  }'
```

### TTP Template Syntax

TTP templates use `{{ variable }}` placeholders:

```text
interface {{ interface }}
 ip address {{ ip }} {{ mask }}
 description {{ description | ORPHRASE }}
```

See [TTP documentation](https://ttp.readthedocs.io/) for full syntax.

### Community Templates

The [`ttp-templates`](https://github.com/dmulyalin/ttp_templates) library provides community-maintained templates. Reference them with `ttp://` prefix:

```json
{
  "ttp_template": "ttp://platform/cisco_ios/show_interfaces.txt"
}
```

### When to Use TTP vs TextFSM

| | TextFSM | TTP |
| --- | --- | --- |
| Community templates | ntc-templates (large, active) | ttp-templates (small) |
| Template syntax | Regex-based | Jinja2-like |
| Best for | Standard commands with ntc-templates coverage | Custom parsing, complex structures |
