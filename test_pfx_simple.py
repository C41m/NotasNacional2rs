from cryptography.hazmat.primitives.serialization import pkcs12
import sys

# Testa o primeir certificado
pfx_path = r"F:\Projetos\2RSNotas\crt\ADS2U GESTAO DE TRAFEGO LTDA46940238000106.pfx"
password = "ads2u"

try:
    with open(pfx_path, "rb") as f:
        pfx_data = f.read()
    print(f"PFX lido: {len(pfx_data)} bytes")
    private_key, cert, chain = pkcs12.load_key_and_certificates(pfx_data, password.encode())
    print(f"SUCESSO! Certificado válido até: {cert.not_valid_after_utc}")
except Exception as e:
    print(f"ERRO: {e}")
    sys.exit(1)
