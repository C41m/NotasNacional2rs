from io import BytesIO
from datetime import datetime
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter


# Estilos reutilizáveis
HEADER_FONT = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
HEADER_FILL = PatternFill(start_color='1F3A5F', end_color='1F3A5F', fill_type='solid')
SUBHEADER_FILL = PatternFill(start_color='2E5C8A', end_color='2E5C8A', fill_type='solid')
TOTAL_FILL = PatternFill(start_color='DCE6F0', end_color='DCE6F0', fill_type='solid')
ALT_ROW_FILL = PatternFill(start_color='F2F5F9', end_color='F2F5F9', fill_type='solid')
WHITE_FILL = PatternFill(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')

TITLE_FONT = Font(name='Calibri', bold=True, size=16, color='1F3A5F')
SUBTITLE_FONT = Font(name='Calibri', bold=True, size=12, color='2E5C8A')
NORMAL_FONT = Font(name='Calibri', size=10)
BOLD_FONT = Font(name='Calibri', bold=True, size=10)
CARD_VALUE_FONT = Font(name='Calibri', bold=True, size=14, color='1F3A5F')
CARD_LABEL_FONT = Font(name='Calibri', size=9, color='555555')

THIN_BORDER = Border(
    left=Side(style='thin', color='CCCCCC'),
    right=Side(style='thin', color='CCCCCC'),
    top=Side(style='thin', color='CCCCCC'),
    bottom=Side(style='thin', color='CCCCCC'),
)

HEADER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
CENTER_ALIGN = Alignment(horizontal='center', vertical='center')
RIGHT_ALIGN = Alignment(horizontal='right', vertical='center')
LEFT_ALIGN = Alignment(horizontal='left', vertical='center')


def _valor_brl(valor) -> str:
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        v = 0
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _role_label(role: str | None) -> str:
    if not role:
        return "—"
    role = role.lower()
    if role == "prestado":
        return "Prestado (Saída)"
    if role == "tomado":
        return "Tomado (Entrada)"
    if role == "intermediario":
        return "Intermediário"
    return role.capitalize()


def _tipo_evento_label(tipo_evento: str | None) -> str:
    if not tipo_evento:
        return "Normal"
    return tipo_evento


def _apply_header_style(ws, row: int, max_col: int):
    for col in range(1, max_col + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER


def _apply_subheader_style(ws, row: int, max_col: int):
    for col in range(1, max_col + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = SUBHEADER_FILL
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER


def _apply_total_style(ws, row: int, max_col: int):
    for col in range(1, max_col + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = BOLD_FONT
        cell.fill = TOTAL_FILL
        cell.border = THIN_BORDER


def _apply_cell_style(ws, row: int, col: int, bold: bool = False, align: Alignment = LEFT_ALIGN, number_format: str = None):
    cell = ws.cell(row=row, column=col)
    cell.font = BOLD_FONT if bold else NORMAL_FONT
    cell.alignment = align
    cell.border = THIN_BORDER
    if number_format:
        cell.number_format = number_format
    if row % 2 == 0:
        cell.fill = ALT_ROW_FILL
    else:
        cell.fill = WHITE_FILL


def _auto_width(ws, min_width: int = 10, max_width: int = 55):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        adjusted = min(max(max_len + 2, min_width), max_width)
        ws.column_dimensions[col_letter].width = adjusted


def gerar_xlsx_nfse_download(
    periodo: str,
    empresas_data: list[dict],
) -> bytes:
    """
    Gera planilha XLSX do download de NFSe com duas abas:
    1. RESUMO - KPIs por empresa + totais por tipo (Prestado/Tomado/Cancelado)
    2. DETALHAMENTO - Todas as notas fiscais detalhadas
    """
    wb = Workbook()

    # ==================== ABA 1: RESUMO ====================
    ws1 = wb.active
    ws1.title = "RESUMO"

    row = 1
    # Título
    ws1.merge_cells('A1:J1')
    cell = ws1.cell(row=1, column=1, value="2RS Notas - Relatório de Download NFSe")
    cell.font = TITLE_FONT
    cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 1

    ws1.merge_cells(f'A{row}:J{row}')
    cell = ws1.cell(row=row, column=1, value=f"Competência: {periodo}")
    cell.font = SUBTITLE_FONT
    cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 1

    ws1.merge_cells(f'A{row}:J{row}')
    cell = ws1.cell(row=row, column=1, value=f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    cell.font = NORMAL_FONT
    cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 2

    # Totais globais
    total_empresas = len(empresas_data)
    total_notas = sum(e.get("total_notas", 0) for e in empresas_data)
    total_prestado = sum(e.get("notas_prestado", 0) for e in empresas_data)
    total_tomado = sum(e.get("notas_tomado", 0) for e in empresas_data)
    total_cancelado = sum(e.get("notas_cancelado", 0) for e in empresas_data)
    total_valor_servico = sum(e.get("valor_servico_total", 0.0) for e in empresas_data)
    total_valor_iss = sum(e.get("valor_iss_total", 0.0) for e in empresas_data)

    kpi_headers = [
        "Empresas", "Total Notas", "Prestados", "Tomados", "Cancelados",
        "Valor Serviço", "Valor ISS", "Valor Total (Serv+ISS)"
    ]
    kpi_values = [
        total_empresas, total_notas, total_prestado, total_tomado, total_cancelado,
        _valor_brl(total_valor_servico), _valor_brl(total_valor_iss),
        _valor_brl(total_valor_servico + total_valor_iss)
    ]

    for col, (header, value) in enumerate(zip(kpi_headers, kpi_values), 1):
        ws1.cell(row=row, column=col, value=header).font = CARD_LABEL_FONT
        ws1.cell(row=row, column=col).alignment = CENTER_ALIGN
        cell = ws1.cell(row=row + 1, column=col, value=value)
        cell.font = CARD_VALUE_FONT
        cell.alignment = CENTER_ALIGN
    row += 3

    # Tabela: Resumo por Empresa
    ws1.merge_cells(f'A{row}:J{row}')
    cell = ws1.cell(row=row, column=1, value="Resumo por Empresa")
    cell.font = SUBTITLE_FONT
    row += 1

    empresa_headers = [
        "Empresa", "CNPJ", "Total Notas", "Prestados", "Tomados", "Cancelados",
        "Valor Serviço (R$)", "Valor ISS (R$)", "Valor Total (R$)"
    ]
    for col, header in enumerate(empresa_headers, 1):
        ws1.cell(row=row, column=col, value=header)
    _apply_header_style(ws1, row, len(empresa_headers))
    row += 1

    for emp in empresas_data:
        ws1.cell(row=row, column=1, value=emp.get("razao_social", "-"))
        ws1.cell(row=row, column=2, value=emp.get("cnpj", "-"))
        ws1.cell(row=row, column=3, value=emp.get("total_notas", 0))
        ws1.cell(row=row, column=4, value=emp.get("notas_prestado", 0))
        ws1.cell(row=row, column=5, value=emp.get("notas_tomado", 0))
        ws1.cell(row=row, column=6, value=emp.get("notas_cancelado", 0))
        ws1.cell(row=row, column=7, value=emp.get("valor_servico_total", 0.0))
        ws1.cell(row=row, column=7).number_format = '#,##0.00'
        ws1.cell(row=row, column=8, value=emp.get("valor_iss_total", 0.0))
        ws1.cell(row=row, column=8).number_format = '#,##0.00'
        ws1.cell(row=row, column=9, value=emp.get("valor_servico_total", 0.0) + emp.get("valor_iss_total", 0.0))
        ws1.cell(row=row, column=9).number_format = '#,##0.00'

        for col in range(1, len(empresa_headers) + 1):
            _apply_cell_style(ws1, row, col)
        row += 1

    # Linha TOTAL
    ws1.cell(row=row, column=1, value="TOTAL GERAL")
    ws1.cell(row=row, column=3, value=total_notas)
    ws1.cell(row=row, column=4, value=total_prestado)
    ws1.cell(row=row, column=5, value=total_tomado)
    ws1.cell(row=row, column=6, value=total_cancelado)
    ws1.cell(row=row, column=7, value=total_valor_servico)
    ws1.cell(row=row, column=7).number_format = '#,##0.00'
    ws1.cell(row=row, column=8, value=total_valor_iss)
    ws1.cell(row=row, column=8).number_format = '#,##0.00'
    ws1.cell(row=row, column=9, value=total_valor_servico + total_valor_iss)
    ws1.cell(row=row, column=9).number_format = '#,##0.00'
    _apply_total_style(ws1, row, len(empresa_headers))
    row += 2

    # Ajustar larguras da aba RESUMO
    widths_resumo = [40, 18, 12, 12, 12, 12, 18, 18, 18]
    for i, w in enumerate(widths_resumo, 1):
        ws1.column_dimensions[get_column_letter(i)].width = w

    # ==================== ABA 2: DETALHAMENTO ====================
    ws2 = wb.create_sheet("DETALHAMENTO")

    row = 1
    ws2.merge_cells('A1:R1')
    cell = ws2.cell(row=1, column=1, value="2RS Notas - Detalhamento de Notas Fiscais NFSe")
    cell.font = TITLE_FONT
    cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 1

    ws2.merge_cells(f'A{row}:R{row}')
    cell = ws2.cell(row=row, column=1, value=f"Competência: {periodo}")
    cell.font = SUBTITLE_FONT
    cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 1

    ws2.merge_cells(f'A{row}:R{row}')
    cell = ws2.cell(row=row, column=1, value=f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    cell.font = NORMAL_FONT
    cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 2

    detalhe_headers = [
        "Empresa", "CNPJ", "Chave de Acesso", "Número NFSe", "Competência",
        "Data Emissão", "Tipo", "Prestador (CNPJ)", "Prestador (Nome)",
        "Tomador (CNPJ)", "Tomador (Nome)", "Código Serviço",
        "Descrição Serviço", "Valor Serviço (R$)", "Base Cálculo ISS (R$)",
        "Alíquota ISS (%)", "Valor ISS (R$)", "ISS Retido"
    ]
    for col, header in enumerate(detalhe_headers, 1):
        ws2.cell(row=row, column=col, value=header)
    _apply_header_style(ws2, row, len(detalhe_headers))
    row += 1

    for emp in empresas_data:
        notas = emp.get("notas", [])
        if not notas:
            ws2.cell(row=row, column=1, value=emp.get("razao_social", "-"))
            ws2.cell(row=row, column=2, value=emp.get("cnpj", "-"))
            ws2.merge_cells(start_row=row, start_column=3, end_row=row, end_column=len(detalhe_headers))
            cell = ws2.cell(row=row, column=3, value="Nenhuma nota encontrada")
            cell.font = Font(name='Calibri', size=10, italic=True, color='888888')
            cell.alignment = Alignment(horizontal='center', vertical='center')
            for col in range(1, len(detalhe_headers) + 1):
                _apply_cell_style(ws2, row, col)
            row += 1
            continue

        for n in notas:
            ws2.cell(row=row, column=1, value=emp.get("razao_social", "-"))
            ws2.cell(row=row, column=2, value=emp.get("cnpj", "-"))
            ws2.cell(row=row, column=3, value=n.get("chave_acesso", "-") or "-")
            ws2.cell(row=row, column=4, value=n.get("numero_nfse", "-") or "-")
            ws2.cell(row=row, column=5, value=n.get("competencia", "-") or "-")
            ws2.cell(row=row, column=6, value=n.get("data_emissao", "-") or "-")
            ws2.cell(row=row, column=7, value=_role_label(n.get("role")))
            ws2.cell(row=row, column=8, value=n.get("cnpj_prestador", "-") or "-")
            ws2.cell(row=row, column=9, value=n.get("razao_social_prestador", "-") or "-")
            ws2.cell(row=row, column=10, value=n.get("cnpj_tomador", "-") or "-")
            ws2.cell(row=row, column=11, value=n.get("razao_social_tomador", "-") or "-")
            ws2.cell(row=row, column=12, value=n.get("codigo_servico", "-") or "-")
            ws2.cell(row=row, column=13, value=n.get("descricao_servico", "-") or "-")
            ws2.cell(row=row, column=14, value=n.get("valor_servico", 0.0) or 0.0)
            ws2.cell(row=row, column=14).number_format = '#,##0.00'
            ws2.cell(row=row, column=15, value=n.get("base_calculo_iss", 0.0) or 0.0)
            ws2.cell(row=row, column=15).number_format = '#,##0.00'
            ws2.cell(row=row, column=16, value=n.get("aliquota_iss", 0.0) or 0.0)
            ws2.cell(row=row, column=16).number_format = '0.00"%"'
            ws2.cell(row=row, column=17, value=n.get("valor_iss", 0.0) or 0.0)
            ws2.cell(row=row, column=17).number_format = '#,##0.00'
            ws2.cell(row=row, column=18, value="Sim" if n.get("iss_retido") == "1" else "Não")

            for col in range(1, len(detalhe_headers) + 1):
                _apply_cell_style(ws2, row, col)
            row += 1

    # Ajustar larguras da aba DETALHAMENTO
    widths_detalhe = [35, 18, 30, 14, 12, 18, 14, 18, 30, 18, 30, 14, 35, 16, 16, 12, 16, 10]
    for i, w in enumerate(widths_detalhe, 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # Congelar painéis (cabeçalho fixo)
    ws1.freeze_panes = 'A6'
    ws2.freeze_panes = 'A5'

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()