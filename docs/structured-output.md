# Structured Output

NAAS can parse raw command output into typed data structures (`list[dict]`)
on the server side, eliminating ad-hoc parsing in client applications. Two
parsers are supported on the `/v2/send-command-structured` endpoint:

- **TextFSM** (the default and most commonly used) — regex-based templates
  with the large [ntc-templates](https://github.com/networktocode/ntc-templates)
  community library covering 1000+ vendor commands.
- **TTP** (Template Text Parser) — Jinja2-style templates, useful when you'd
  rather write that style than regex or when ntc-templates doesn't cover
  your command.

Pass either `textfsm_template` or `ttp_template` (mutually exclusive). With
neither, NAAS uses TextFSM with ntc-templates.

## Quick Start

```bash
curl -k -u "username:password" https://localhost:8443/v2/send-command-structured \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version", "show ip interface brief"]
  }'
```

By default this picks up matching ntc-templates and parses each command's
output into `list[dict]`.

## How it works

1. **Automatic template lookup** (TextFSM only) — Netmiko matches
   `(platform, command)` against ntc-templates and applies the template
   automatically.
2. **Custom template** — supply `textfsm_template` or `ttp_template` to override
   the lookup or to parse a command ntc-templates doesn't cover.
3. **Structured output** — returns `list[dict]` per command when a template
   matches, raw `str` when none does (TextFSM falls back gracefully).
4. **Endpoint** — `/v2/send-command-structured` for the structured path;
   `/v2/send-command` is the raw-output equivalent.

## Return type

Results are `list[dict]` when a template matched, `str` when none did. **Client
code must handle both.**

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

```python
result = response["results"]["show version"]
if isinstance(result, list):
    # Parsed output
    for item in result:
        print(item["hostname"])
else:
    # Raw string (no template matched)
    print(result)
```

## Choosing TextFSM or TTP

| | TextFSM | TTP |
| --- | --- | --- |
| Community templates | [ntc-templates](https://github.com/networktocode/ntc-templates) — large, active, 1000+ commands | [ttp-templates](https://github.com/dmulyalin/ttp_templates) — smaller |
| Template syntax | Regex + state machine | Jinja2-like placeholders |
| Default behavior | Auto-lookup via ntc-templates if no template provided | Must supply `ttp_template` explicitly |
| Best for | Standard show commands covered by ntc-templates | Custom or complex parsing where regex is painful |

Most NAAS users want TextFSM with ntc-templates — that's the default for a
reason. Reach for TTP when ntc-templates doesn't cover a command and you'd
rather write a TTP template than a TextFSM one, or when you have an existing
TTP-templates investment.

## TextFSM

### Custom TextFSM templates

Supply your own template for commands not covered by ntc-templates:

```json
{
  "host": "192.168.1.1",
  "platform": "cisco_ios",
  "commands": ["show custom output"],
  "textfsm_template": "Value FIELD1 (\\S+)\\nValue FIELD2 (\\S+)\\n\\nStart\\n  ^${FIELD1}\\s+${FIELD2} -> Record"
}
```

### Template syntax

TextFSM templates define:

- **Value** lines: field names and regex capture groups
- **States**: parsing state machine (`Start`, `Record`, etc.)
- **Rules**: regex patterns that match lines and extract values

Example template for `show ip interface brief`:

```text
Value INTERFACE (\S+)
Value IP_ADDRESS (\S+)
Value STATUS (up|down|administratively down)

Start
  ^${INTERFACE}\s+${IP_ADDRESS}.*${STATUS} -> Record
```

See the [TextFSM documentation](https://github.com/google/textfsm/blob/master/README.md)
for full syntax.

## TTP

### Using TTP templates

Pass `ttp_template` (mutually exclusive with `textfsm_template`):

```bash
curl -k -u "username:password" https://localhost:8443/v2/send-command-structured \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show interfaces"],
    "ttp_template": "interface {{ interface }}\n ip address {{ ip }} {{ mask }}"
  }'
```

### Community templates

Reference templates from the
[`ttp-templates`](https://github.com/dmulyalin/ttp_templates) library with the
`ttp://` prefix:

```json
{
  "ttp_template": "ttp://platform/cisco_ios/show_interfaces.txt"
}
```

### Template syntax

TTP templates use `{{ variable }}` placeholders:

```text
interface {{ interface }}
 ip address {{ ip }} {{ mask }}
 description {{ description | ORPHRASE }}
```

See the [TTP documentation](https://ttp.readthedocs.io/) for full syntax.

## When to use structured vs raw output

**Use `/v2/send-command-structured` when:**

- You need typed data for programmatic processing
- The command is covered by ntc-templates (check the [template index](https://github.com/networktocode/ntc-templates/tree/master/ntc_templates/templates)) or you have a template ready
- Your code can handle mixed return types (`list[dict]` vs `str`)

**Use `/v2/send-command` when:**

- You need raw output for logging, display, or human review
- The command has no template and you don't want to write one
- You want a consistent return type (always `str`)

## Limitations

- **No connection pooling.** Both TextFSM and TTP keep parsing state on the
  Netmiko connection that makes pooling unreliable. Structured requests always
  open a fresh SSH session.
- **Template availability** (TextFSM auto-lookup). Not every command has an
  ntc-template — check coverage before relying on auto-parsing.
- **Mixed return types.** A single response can mix `list[dict]` and `str`
  results (one command parsed, another fell back to raw).
- **Parsing overhead.** Adds roughly 10–50ms per command depending on output
  size.

## Examples

### Inventory collection

```python
import requests

response = requests.post(
    "https://naas.local/v2/send-command-structured",
    auth=("user", "pass"),
    json={
        "host": "192.168.1.1",
        "platform": "cisco_ios",
        "commands": ["show version", "show inventory"]
    },
    verify=False
)

job_id = response.json()["job_id"]

# Poll for results
result = requests.get(
    f"https://naas.local/v2/send-command-structured/{job_id}",
    auth=("user", "pass"),
    verify=False
).json()

for device in result["results"]["show version"]:
    print(f"{device['hostname']}: {device['version']}")
```

### Custom TextFSM template

```python
template = """
Value VLAN_ID (\\d+)
Value VLAN_NAME (\\S+)
Value STATUS (active|suspended)

Start
  ^${VLAN_ID}\\s+${VLAN_NAME}\\s+${STATUS} -> Record
"""

response = requests.post(
    "https://naas.local/v2/send-command-structured",
    auth=("user", "pass"),
    json={
        "host": "192.168.1.1",
        "platform": "cisco_ios",
        "commands": ["show vlan brief"],
        "textfsm_template": template
    },
    verify=False
)
```

## See also

- [Platform Autodetect](platform-autodetect.md) — fingerprint unknown devices
  before running structured commands
