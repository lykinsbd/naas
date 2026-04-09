# naas-client

Python client library for [NAAS](https://github.com/lykinsbd/naas) (Netmiko As A Service).

## Installation

```bash
pip install naas-client
```

## Quick Start

```python
from naas_client import NaasClient

# Basic auth
client = NaasClient("https://naas.example.com", username="admin", password="secret")

# Or API key auth
client = NaasClient("https://naas.example.com", api_key="your-api-key")

# Submit a command and wait for results
job = client.send_command(
    host="192.168.1.1",
    platform="cisco_ios",
    commands=["show version", "show interfaces"],
)
result = job.wait(timeout=30)
print(result.output["show version"])
```

## License

MIT
