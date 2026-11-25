from io import BytesIO
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


MESES = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]

HEADER_FONT = Font(name='Calibri', bold=True, size=10, color='FFFFFF')
TITLE_FONT = Font(name='Calibri', bold=True, size=14, color='1F3A5F')
SUBTITLE_FONT = Font(name='Calibri', bold=True, size=11, color='1F3A5F')
NORMAL_FONT = Font(name='Calibri', size=10)
BOLD_FONT = Font(name='Calibri', bold=True, size=10)
SECTION_FONT = Font(name='Calibri', bold=True, size=11, color='FFFFFF')

HEADER_FILL = PatternFill('solid', start_color='1F3A5F', end_color='1F3A5F')
SECTION_FILL = PatternFill('solid', start_color='2E5C8A', end_color='2E5C8A')
TOTAL_FILL = PatternFill('solid', start_color='DCE6F0', end_color='DCE6F0')
ALT_FILL = PatternFill('solid', start_color='F2F5F9', end_color='F2F5F9')
THIN = Side(style='thin', color='CCCCCC')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
LEFT = Alignment(horizontal='left', vertical='center')
RIGHT = Alignment(horizontal='right', vertical='center')
NUM = '#,##0.00'


def _mes_extenso(periodo: str) -> str:
    if not periodo or len(periodo) < 7:
        return periodo or ''
    try:
        ano, mes = periodo[:4], int(periodo[5:7])
        if 1 <= mes <= 12:
            nome = MESES[mes - 1]
            return f'{nome[0].upper() + nome[1:]} de {ano}'
    except (ValueError, TypeError):
        pass
    return periodo


def _v(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _deducao(n: dict) -> float:
    return _v(n.get('valor_desconto_condicionado')) + _v(n.get('valor_desconto_incondicionado'))


def _base(n: dict) -> float:
    base = _v(n.get('base_calculo_iss'))
    return base if base else max(_v(n.get('valor_servico')) - _deducao(n), 0)


def _retido(n: dict) -> bool:
    return (n.get('iss_retido') or '') == '2'


def _totais(notas: list[dict]) -> dict:
    return {
        'qtd': len(notas),
        'servico': sum(_v(n.get('valor_servico')) for n in notas),
        'deducao': sum(_deducao(n) for n in notas),
        'base': sum(_base(n) for n in notas),
        'iss': sum(_v(n.get('valor_iss')) for n in notas),
    }


def _linha_totais(ws, row: int, rotulo: str, t: dict):
    valores = [rotulo, t['qtd'], t['servico'], t['deducao'], t['base'], t['iss']]
    for col, valor in enumerate(valores, 1):
        cell = ws.cell(row=row, column=col, value=valor)
        cell.font = BOLD_FONT
        cell.fill = TOTAL_FILL
        cell.border = BORDER
        cell.alignment = LEFT if col == 1 else (CENTER if col == 2 else RIGHT)
        if col >= 3:
            cell.number_format = NUM


def _bloco(ws, row: int, titulo: str, linhas: list[tuple[str, dict]]):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    cell = ws.cell(row=row, column=1, value=titulo)
    cell.font = SECTION_FONT
    cell.fill = SECTION_FILL
    cell.alignment = LEFT
    row += 1
    for col, header in enumerate(['', 'Quantidade', 'Valor dos Serviços', 'Deduções', 'Base de Cálculo', 'ISS Devido'], 1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = BORDER
    row += 1
    for rotulo, t in linhas:
        vals = [rotulo, t['qtd'], t['servico'], t['deducao'], t['base'], t['iss']]
        for col, valor in enumerate(vals, 1):
            cell = ws.cell(row=row, column=col, value=valor)
            cell.font = NORMAL_FONT
            cell.border = BORDER
            cell.alignment = LEFT if col == 1 else (CENTER if col == 2 else RIGHT)
            if col >= 3:
                cell.number_format = NUM
            if row % 2 == 0:
                cell.fill = ALT_FILL
        row += 1
    return row + 1


def _aba_resumo(wb, periodo: str, empresas_data: list[dict]):
    ws = wb.active
    ws.title = 'Resumo Escrituração'

    prestadas = [n for emp in empresas_data for n in emp.get('notas', []) if (n.get('role') or '').lower() == 'prestado']
    tomadas = [n for emp in empresas_data for n in emp.get('notas', []) if (n.get('role') or '').lower() == 'tomado']
    prest_proprio = [n for n in prestadas if not _retido(n)]
    prest_retido = [n for n in prestadas if _retido(n)]
    tom_proprio = [n for n in tomadas if not _retido(n)]
    tom_retido = [n for n in tomadas if _retido(n)]
    canceladas_p = [n for n in prestadas if n.get('tipo_evento')]
    canceladas_t = [n for n in tomadas if n.get('tipo_evento')]

    ws.merge_cells('A1:F1')
    ws['A1'] = '2RS Notas — Escrituração de NFS-e (formato ISS Fortaleza)'
    ws['A1'].font = TITLE_FONT
    ws['A1'].alignment = CENTER
    ws.merge_cells('A2:F2')
    ws['A2'] = f'Competência: {_mes_extenso(periodo)}'
    ws['A2'].font = SUBTITLE_FONT
    ws['A2'].alignment = CENTER
    if len(empresas_data) == 1:
        emp = empresas_data[0]
        for row, texto in [(3, f"CNPJ: {emp.get('cnpj', '-')}"), (4, f"Razão Social: {emp.get('razao_social', '-')}")]:
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
            ws.cell(row=row, column=1, value=texto).font = NORMAL_FONT
    else:
        ws.merge_cells('A3:F3')
        ws['A3'] = f'Empresas incluídas: {len(empresas_data)}'
        ws['A3'].font = NORMAL_FONT

    row = 6
    row = _bloco(ws, row, 'Serviços Prestados', [
        ('ISS Próprio — NFS-e Não Recusada pelo Tomador', _totais(prest_proprio)),
        ('ISS Retido Pelo Tomador — NFS-e Recusada ou Documento Digitado pelo Tomador', _totais(prest_retido)),
        ('Somátório', _totais(prestadas)),
    ])
    row = _bloco(ws, row, 'Serviços Tomados', [
        ('ISS Responsabilidade Prestador', _totais(tom_proprio)),
        ('ISS Retido (Responsabilidade / Substituição)', _totais(tom_retido)),
        ('Somátório', _totais(tomadas)),
    ])
    recolher_proprio = _totais(prest_proprio)
    row = _bloco(ws, row, 'Imposto sobre Serviços', [
        ('A Recolher no Município — ISS Próprio', recolher_proprio),
        ('A Recolher no Município — ISS Retido', _totais([])),
        ('Somátório', recolher_proprio),
    ])
    vazio = _totais([])
    row = _bloco(ws, row, 'Informações Complementares', [
        ('Serviços Prestados — NFS-e Cancelada', {**vazio, 'qtd': len(canceladas_p)}),
        ('Serviços Tomados — NFS-e Cancelada', {**vazio, 'qtd': len(canceladas_t)}),
    ])

    for col, width in enumerate([62, 12, 18, 14, 18, 16], 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = 'A6'


def _aba_detalhe(wb, nome: str, periodo: str, empresas_data: list[dict], role: str, parte: str):
    ws = wb.create_sheet(nome)
    ws.merge_cells('A1:O1')
    ws['A1'] = f'2RS Notas — Detalhamento de Serviços {nome}'
    ws['A1'].font = TITLE_FONT
    ws['A1'].alignment = CENTER
    ws.merge_cells('A2:O2')
    ws['A2'] = f'Competência: {_mes_extenso(periodo)}'
    ws['A2'].font = SUBTITLE_FONT
    ws['A2'].alignment = CENTER

    headers = [
        'Empresa', 'CNPJ Empresa', 'Número NFSe', 'Competência', 'Data Emissão',
        f'{parte} (CNPJ)', f'{parte} (Nome)', 'Código Serviço', 'Descrição Serviço',
        'Valor Serviço', 'Deduções', 'Base Cálculo', 'Alíquota (%)', 'ISS Devido', 'Classificação',
    ]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = BORDER

    row = 5
    notas = []
    for emp in empresas_data:
        for n in emp.get('notas', []):
            if (n.get('role') or '').lower() != role:
                continue
            notas.append(n)
            retido = _retido(n)
            if role == 'prestado':
                classificacao = 'ISS Retido pelo Tomador' if retido else 'ISS Próprio'
                parte_cnpj, parte_nome = n.get('cnpj_tomador'), n.get('razao_social_tomador')
            else:
                classificacao = 'ISS Retido (Substituição)' if retido else 'Responsabilidade do Prestador'
                parte_cnpj, parte_nome = n.get('cnpj_prestador'), n.get('razao_social_prestador')
            vals = [
                emp.get('razao_social'), emp.get('cnpj'), n.get('numero_nfse'), n.get('competencia'),
                n.get('data_emissao'), parte_cnpj, parte_nome, n.get('codigo_servico'),
                n.get('descricao_servico'), _v(n.get('valor_servico')), _deducao(n), _base(n),
                _v(n.get('aliquota_iss')), _v(n.get('valor_iss')), classificacao,
            ]
            for col, valor in enumerate(vals, 1):
                cell = ws.cell(row=row, column=col, value=valor)
                cell.font = NORMAL_FONT
                cell.border = BORDER
                cell.alignment = LEFT if col in (1, 7, 9, 15) else (RIGHT if col in (10, 11, 12, 13, 14) else CENTER)
                if col in (10, 11, 12, 14):
                    cell.number_format = NUM
                if col == 13:
                    cell.number_format = '0.00"%"'
                if row % 2 == 0:
                    cell.fill = ALT_FILL
            row += 1

    t = _totais(notas)
    totais = ['TOTAL', '', t['qtd'], '', '', '', '', '', '', t['servico'], t['deducao'], t['base'], '', t['iss'], '']
    for col, valor in enumerate(totais, 1):
        cell = ws.cell(row=row, column=col, value=valor)
        cell.font = BOLD_FONT
        cell.fill = TOTAL_FILL
        cell.border = BORDER
        cell.alignment = LEFT if col == 1 else (RIGHT if col in (10, 11, 12, 14) else CENTER)
        if col in (10, 11, 12, 14):
            cell.number_format = NUM

    widths = [32, 18, 14, 12, 14, 18, 30, 14, 38, 16, 14, 16, 12, 16, 26]
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = 'A5'


def gerar_xlsx_nfse_download(periodo: str, empresas_data: list[dict]) -> bytes:
    """Planilha no formato do certificado do ISS Fortaleza: resumo + prestados + tomados."""
    wb = Workbook()
    _aba_resumo(wb, periodo, empresas_data)
    _aba_detalhe(wb, 'Serviços Prestados', periodo, empresas_data, 'prestado', 'Tomador')
    _aba_detalhe(wb, 'Serviços Tomados', periodo, empresas_data, 'tomado', 'Prestador')

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
