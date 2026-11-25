# Serviço DANFSe (sidecar)

O FastAPI não gera o DANFSe: ele faz proxy para o serviço Go da Receita Federal,
que deve estar ouvindo em `http://localhost:8080/api/danfse`.

- Código-fonte / build: https://github.com/ReceitaFederal/calculadora-rtc-gerador-danfse
- Binário usado: `tools/danfse-service.exe` (não versionado; `.gitignore`)
- SHA-256 esperado: `9D7839E2EDD64B103D68EF7756F442F21AB16B28FC0DABF0720EBE5378BDCC98`
- Subida local: execute `tools\danfse-service.exe`; a porta 8080 deve ficar em LISTEN.
- Verificação: `GET /nfse/notas/{id}/danfse` (com `X-API-Key`) devolve um `%PDF`.

O frontend baixa esse PDF pelo botão "Baixar DANFSe (PDF)" no detalhe da nota
e pelo ícone de PDF na coluna Ações da tela `/notas`.
