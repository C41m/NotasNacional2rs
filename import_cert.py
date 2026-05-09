import base64
import requests
import json

# Read PFX file
pfx_path = r"F:\Projetos\2RSNotas\crt\LACERDA E CANGUSSU SERVICOS MEDICOS LTDA21581770000145.pfx"
with open(pfx_path, "rb") as f:
    pfx_data = f.read()
    pfx_base64 = base64.b64encode(pfx_data).decode()

# Prepare payload
payload = {
    "nome": "ESPACO TERAPEUTICO DE SERVICOS PSICOLOGICOS LTDA",
    "cnpj": "21581770000145",
    "pfx_base64": pfx_base64,
    "password": "123456"
}

# Call API
try:
    response = requests.post(
        "http://localhost:8000/companies/",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
