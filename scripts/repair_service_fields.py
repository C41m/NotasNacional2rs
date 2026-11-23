# scripts/repair_service_fields.py
"""Backfill de campos de atividade a partir do xml_original.

Por que existe: o parser original lia `<cServ>` como se fosse folha (o texto
dentro dele está vazio — os dados ficam em filhos). Por isso quase todas as
notas têm esses campos vazios no banco.

Fecha cinco colunas, todas derivadas do XML armazenado — nada é criado do
zero e nada é sobrescrito se já tiver valor:

    codigo_servico       ← cTribNac (serv/cServ)
    descricao_servico    ← xDescServ (serv/cServ)
    tributo_nacional     ← xTribNac (infNFSe)
    tributo_municipal    ← xTribMun (infNFSe)
    codigo_nbs           ← xNBS     (infNFSe)

Idempotente. Preenche só o que está vazio.

Uso:
    .\\.venv-dev\\Scripts\\python.exe scripts/repair_service_fields.py --sample   # 20 linhas
    .\\.venv-dev\\Scripts\\python.exe scripts/repair_service_fields.py           # todas
"""

import argparse
import re
import sys
from pathlib import Path

import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.models.nfse import Nfse  # noqa: E402
from sqlalchemy import or_  # noqa: E402


def local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def extract(xml_text: str):
    """Extrai (codigo_servico, descricao_servico, tributo_nacional, tributo_municipal, codigo_nbs)."""
    codigo_servico = descricao_servico = tributo_nacional = tributo_municipal = codigo_nbs = None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None, None, None, None, None

    for el in root.iter():
        name = local_name(el.tag)
        text = (el.text or '').strip()
        if not text:
            continue
        if name == 'cTribNac':
            codigo_servico = codigo_servico or text
        elif name == 'xDescServ':
            descricao_servico = descricao_servico or text
        elif name == 'xTribNac':
            tributo_nacional = tributo_nacional or text
        elif name == 'xTribMun':
            tributo_municipal = tributo_municipal or text
        elif name == 'xNBS':
            codigo_nbs = codigo_nbs or text

    return codigo_servico, descricao_servico, tributo_nacional, tributo_municipal, codigo_nbs


def or_empty(column):
    return or_(column.is_(None), column == '')


def or_empty_val(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == '')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', action='store_true', help='Só primeiro lote de 20 (validação)')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        q = db.query(Nfse).filter(
            Nfse.xml_original.isnot(None),
            Nfse.xml_original != '',
            or_(
                or_empty(Nfse.codigo_servico),
                or_empty(Nfse.descricao_servico),
                or_empty(Nfse.tributo_nacional),
                or_empty(Nfse.tributo_municipal),
                or_empty(Nfse.codigo_nbs),
            ),
        ).order_by(Nfse.id)
        if args.sample:
            q = q.limit(20)

        total = q.count() if not args.sample else min(20, q.count())
        print(f'Notas a revisar: {total}')

        atualizadas = 0
        sem_extraido = 0
        processadas = 0
        campos = ('codigo_servico', 'descricao_servico', 'tributo_nacional', 'tributo_municipal', 'codigo_nbs')
        fill = {k: 0 for k in campos}

        for nota in q.yield_per(500):
            processadas += 1
            if processadas % 1000 == 0:
                print(f'  ... {processadas}/{total} processadas · {atualizadas} atualizadas · {fill}')

            codigo_servico, descricao_servico, tributo_nacional, tributo_municipal, codigo_nbs = extract(nota.xml_original or '')
            values = {
                'codigo_servico': codigo_servico,
                'descricao_servico': descricao_servico,
                'tributo_nacional': tributo_nacional,
                'tributo_municipal': tributo_municipal,
                'codigo_nbs': codigo_nbs,
            }
            if not any(values.values()):
                sem_extraido += 1
                continue

            changed = False
            for campo, valor in values.items():
                if valor and or_empty_val(getattr(nota, campo)):
                    setattr(nota, campo, valor)
                    fill[campo] += 1
                    changed = True

            if changed:
                atualizadas += 1

        db.commit()
        print(f'\nPronto: {processadas} revisadas · {atualizadas} notas preenchidas · {sem_extraido} sem extração (XML atípico/vazio)')
        print(f'Por campo: {fill}')
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
