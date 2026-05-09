from cryptography.hazmat.primitives.serialization import pkcs12
import sys

# Testando o primeiro certificado
pfx_path = r"F:\Projetos\2RSNotas\crt\ESPACO TERAPEUTICO DE SERVICOS PSICOLOGICOS LTDA31690578000140.pfx"
password = "123456"

try:
    with open(pfx_path, "rb") as f:
        pfx_data = f.read()
    print(f"PFX lido. Tamanho: {len(pfx_data)} bytes")
    
    private_key, cert, chain = pkcs12.load_key_and_certificates(pfx_data, password.encode())
    print("SUCESSO! Certificado validado.")
    print(f"Certificado válido até: {cert.not_valid_after_utc}")
except Exception as e:
    print(f"ERRO: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
