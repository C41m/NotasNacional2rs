#!/usr/bin/env python3
"""
PoC: como se DECLARA (transmite) o PGDAS-D via API oficial do SERPRO
Integra Contador — SEM browser.

Mecanismo (e o que o sistema do video faz por baixo):
  1. Client MONTA a declaracao com os numeros da empresa (receitas por
     atividade, receitas 12m anteriores, folha, isencoes/reducoes).
     O cliente NAO calcula imposto.
  2. Envia JSON no servico PGDASD/TRANSDECLARACAO11.
  3. A Receita CALCULA o DAS (RBT12, Fator R, aliquota efetiva, tributos)
     e devolve valoresDevidos + numero da declaracao + XML da
     declaracao transmitida.

Ou seja: nenhum scraping, nenhum ViewState, nenhum Chromium. E o calculo
tributario fica com a Receita -- o cliente so envia a apuracao bruta.

ATENCAO: este PoC roda contra a API TRIAL (sandbox, CNPJ ficticio).
Para producao exige contrato SERPRO + e-CNPJ do escritorio + procuracao
eletronica 00146 ativa no e-CAC de cada empresa.

Uso:
  python scripts/poc_transmitir_declaracao.py
  python scripts/poc_transmitir_declaracao.py --simular   # so o calculo, nao transmite
"""
import argparse
import asyncio
import json

import httpx

TRIAL_DECLARAR = "https://gateway.apiserpro.serpro.gov.br/integra-contador-trial/v1/Declarar"
PROD_DECLARAR = "https://gateway.apiserpro.serpro.gov.br/integra-contador/v1/Declarar"
TRIAL_BEARER = "06aef429-a981-3ec5-a1f8-71d38d86481e"

# Exemplo da documentacao oficial, reduzido para os numeros da empresa real.
# Troque pelos valores apurados da empresa antes de usar em producao.
DECLARACAO_EXEMPLO = {
    "cnpjCompleto": "00000000000100",
    "pa": 202101,
    "indicadorTransmissao": True,
    "indicadorComparacao": True,
    "declaracao": {
        "tipoDeclaracao": 1,
        "receitaPaCompetenciaInterno": 10000.00,
        "receitaPaCompetenciaExterno": 0.00,
        "receitaPaCaixaInterno": None,
        "receitaPaCaixaExterno": None,
        "valorFixoIcms": 100.00,
        "valorFixoIss": None,
        "receitasBrutasAnteriores": [
            {"pa": 202001, "valorInterno": 100.00, "valorExterno": 200.00},
            {"pa": 202002, "valorInterno": 300.00, "valorExterno": 0.00},
            {"pa": 202003, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202004, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202005, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202006, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202007, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202008, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202009, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202010, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202011, "valorInterno": 0.00, "valorExterno": 0.00},
            {"pa": 202012, "valorInterno": 0.00, "valorExterno": 0.00},
        ],
        "folhasSalario": [
            {"pa": 202001, "valor": 2000.00},
            {"pa": 202002, "valor": 2000.00},
            {"pa": 202003, "valor": 2000.00},
            {"pa": 202004, "valor": 2000.00},
            {"pa": 202005, "valor": 0.00},
            {"pa": 202006, "valor": 0.00},
            {"pa": 202007, "valor": 0.00},
            {"pa": 202008, "valor": 0.00},
            {"pa": 202009, "valor": 0.00},
            {"pa": 202010, "valor": 0.00},
            {"pa": 202011, "valor": 0.00},
            {"pa": 202012, "valor": 0.00},
        ],
        "naoOptante": None,
        "estabelecimentos": [
            {
                "cnpjCompleto": "00000000000100",
                "atividades": [
                    {
                        "idAtividade": 1,
                        "valorAtividade": 4000.00,
                        "receitasAtividade": [
                            {
                                "valor": 4000.00,
                                "codigoOutroMunicipio": None,
                                "outraUf": None,
                                "isencoes": [
                                    {"codTributo": 1007, "valor": 100.00, "identificador": 1}
                                ],
                                "reducoes": [
                                    {
                                        "codTributo": 1007,
                                        "valor": 1500.00,
                                        "percentualReducao": 50.00,
                                        "identificador": 1,
                                    }
                                ],
                                "qualificacoesTributarias": [],
                                "exigibilidadesSuspensas": None,
                            }
                        ],
                    },
                    {
                        "idAtividade": 10,
                        "valorAtividade": 6000.00,
                        "receitasAtividade": [
                            {
                                "valor": 6000.00,
                                "codigoOutroMunicipio": 9701,
                                "outraUf": "DF",
                                "isencoes": None,
                                "reducoes": None,
                                "qualificacoesTributarias": None,
                                "exigibilidadesSuspensas": None,
                            }
                        ],
                    },
                ],
            }
        ],
        "valoresParaComparacao": [
            {"codigoTributo": 1001, "valor": 23.20},
            {"codigoTributo": 1002, "valor": 18.20},
            {"codigoTributo": 1004, "valor": 66.53},
            {"codigoTributo": 1005, "valor": 14.43},
            {"codigoTributo": 1006, "valor": 222.64},
            {"codigoTributo": 1007, "valor": 100.00},
            {"codigoTributo": 1010, "valor": 120.60},
        ],
    },
}

TRIBUTOS = {
    1001: "IRPJ", 1002: "CSLL", 1004: "COFINS", 1005: "PIS",
    1006: "CPP (INSS)", 1007: "ICMS", 1010: "ISS", 1011: "IPI",
}


def montar_payload(declaracao: dict, cnpj: str, transmitir: bool):
    declaracao = dict(declaracao)
    declaracao["indicadorTransmissao"] = transmitir
    return {
        "contratante": {"numero": cnpj, "tipo": 2},
        "autorPedidoDados": {"numero": cnpj, "tipo": 2},
        "contribuinte": {"numero": cnpj, "tipo": 2},
        "pedidoDados": {
            "idSistema": "PGDASD",
            "idServico": "TRANSDECLARACAO11",
            "versaoSistema": "1.0",
            "dados": json.dumps(declaracao),
        },
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnpj", default="00000000000100")
    ap.add_argument("--simular", action="store_true",
                    help="indicadorTransmissao=false: so calcula, nao transmite")
    ap.add_argument("--ver-tributos", action="store_true")
    a = ap.parse_args()

    payload = montar_payload(DECLARACAO_EXEMPLO, a.cnpj, transmitir=not a.simular)

    print(f"=== PGDASD / TRANSDECLARACAO11 — modo: "
          f"{'SIMULACAO (nao transmite)' if a.simular else 'TRANSMISSAO'} ===")
    print(f"CNPJ: {a.cnpj}")
    print("\nPayload 'dados' (o que o cliente envia — sem nenhum tributo calculado):")
    print(json.dumps(json.loads(payload["pedidoDados"]["dados"]),
                     indent=2, ensure_ascii=False)[:1800])

    async with httpx.AsyncClient(timeout=180.0) as c:
        r = await c.post(
            TRIAL_DECLARAR,
            json=payload,
            headers={
                "Authorization": f"Bearer {TRIAL_BEARER}",
                "Content-Type": "application/json",
                "accept": "application/json",
            },
        )

    print(f"\n--- resposta: HTTP {r.status_code} ---")
    try:
        data = r.json()
    except Exception:
        print(r.text[:2000])
        return

    print(f"status: {data.get('status')}")
    for m in data.get("mensagens", []):
        print(f"  [{m.get('codigo')}] {m.get('texto')}")

    raw = data.get("dados")
    if not raw:
        print("\n(sem 'dados' na resposta)")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:1200])
        return

    inner = json.loads(raw) if isinstance(raw, str) else raw
    print(f"\nidDeclaracao:        {inner.get('idDeclaracao')}")
    print(f"dataHoraTransmissao: {inner.get('dataHoraTransmissao')}")

    devidos = inner.get("valoresDevidos", [])
    print(f"\n=== TRIBUTOS CALCULADOS PELA RECEITA ({len(devidos)}) ===")
    total = 0.0
    for t in devidos:
        nome = TRIBUTOS.get(t.get("codigoTributo"), "?")
        print(f"  {t.get('codigoTributo')}  {nome:<12} R$ {t.get('valor'):>12,.2f}")
        total += float(t.get("valor") or 0)
    print(f"  {'':>4}  {'TOTAL':<12} R$ {total:>12,.2f}")

    decl_xml = inner.get("declaracao")
    if decl_xml:
        import base64
        pdf_bytes = base64.b64decode(decl_xml)
        print(f"\ndeclaracao: base64 -> {len(pdf_bytes)} bytes "
              f"(PDF da declaração transmitida)")


if __name__ == "__main__":
    asyncio.run(main())