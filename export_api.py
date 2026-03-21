import requests

schema = requests.get("http://localhost:8081/openapi.json").json()

md = ["# API\n"]

for path, methods in schema["paths"].items():
    md.append(f"## {path}")
    for method, details in methods.items():
        md.append(f"### {method.upper()}")
        md.append(details.get("summary", ""))

open("API.md", "w").write("\n\n".join(md))