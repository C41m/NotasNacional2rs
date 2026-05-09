import base64
from cryptography.hazmat.primitives.serialization import pkcs12

# O base64 que você enviou (primeiros 100 chars)
pfx_base64 = "TUlBQ0FRTXdnQVlKS29aSWh2Y05BUWNCb0lBRWdpUGJNSUlqMXpDQ0hmTUdDU3FHU0liM0RRRUhCcUNDSGVRd2doM2dBZ0VBTUlJZDJRWUpLb1pJaHZjTkFRY0JNQ2dHQ2lxR1NJYjNEUUVNQVFZd0dnUVVvOFZCU0duNVRTOG9IUFFaY04wSXZiMWkwZThDQWdRQWdJSWRvSHRaRWZzbklodFpibmVWMzY0UHdobE1pUGp3RUhVMTdXNEorSlVMY2VpYnM2RHF1bVBYd0p4aTFkMWtCUElJZDJRWUpLb1pJaHZjTkFRY0JNQ2dHQ2lxR1NJYjNEUUVNQVFZd0dnUVVvOFZCU0duNVRTOG9IUFFaY04wSXZiMWkwZThDQWdRQWdJSWRvSHRaRWZzbklodFpibmVWMzY0UHdobE1pUGp3RUhVMTdXNEorSlVMY2VpYnM2RHF1bVBYd0p4aTFkMWtCUElJZDJRWUpLb1pJaHZjTkFRY0JNQ2dHQ2lxR1NJYjNEUUVNQVFZd0dnUVVvOFZCU0duNVRTOG9IUFFaY04wSXZiMWkwZThDQWdRQWdJSWRvSHRaRWZzbklodFpibmVWMzY0UHdobE1pUGp3RUhVMTdXNEorSlVMY2VpYnM2RHF1bVBYd0p4aTFkMWtCUElJZDJRWUpLb1pJaHZjTkFRY0JNQ2dHQ2lxR1NJYjNEUUVNQVFZd0dnUVVvOFZCU0duNVRTOG9IUFFaY04wSXZiMWkwZThDQWdRQWdJSWRvSHRaRWZzbklodFpibmVWMzY0UHdobE1pUGp3RUhVMTdXNEorSlVMY2VpYnM2RHF1bVBYd0p4aTFkMWtC"
password = "ads2u"

try:
    pfx_data = base64.b64decode(pfx_base64)
    print(f"Base64 válido! Tamanho: {len(pfx_data)} bytes")
    
    private_key, cert, chain = pkcs12.load_key_and_certificates(pfx_data, password.encode())
    print("SUCESSO! Certificado PFX válido!")
    print(f"Certificado válido até: {cert.not_valid_after_utc}")
except Exception as e:
    print(f"ERRO: {e}")
