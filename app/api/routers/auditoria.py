from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.api_key import verify_api_key, api_key_dep
from app.models.auditoria import Auditoria, AuditoriaPendencia
from app.schemas.auditoria import (
    AuditoriaIngestRequest,
    AuditoriaOut,
    AuditoriaResumoOut,
    AuditoriaPendenciaOut,
)
from typing import List

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.post("/ingest", response_model=AuditoriaOut)
async def ingest_auditoria(
    payload: AuditoriaIngestRequest,
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Recebe um relatório de auditoria do Deepseek e faz upsert."""
    cnpj = payload.cnpj
    periodo = payload.periodo

    # Buscar auditoria existente pelo cnpj + periodo
    existing = db.execute(
        select(Auditoria).where(Auditoria.cnpj == cnpj, Auditoria.periodo == periodo)
    ).scalar_one_or_none()

    if existing:
        # Update existing
        existing.razao_social = payload.razao_social
        existing.status_geral = payload.status_geral
        existing.conformidade_pct = payload.conformidade_pct
        existing.observacao_geral = payload.observacao_geral
        existing.documentos_esperados = payload.documentos_esperados
        existing.documentos_encontrados = payload.documentos_encontrados
        # Novos campos
        existing.fator_r = payload.fator_r
        existing.aliquota_efetiva = payload.aliquota_efetiva
        existing.receita_pa = payload.receita_pa
        existing.rbt12 = payload.rbt12
        existing.folha_12m = payload.folha_12m
        existing.pro_labore = payload.pro_labore
        existing.inss = payload.inss
        existing.irrf = payload.irrf
        existing.fgts = payload.fgts
        existing.num_funcionarios = payload.num_funcionarios
        existing.media_mensal_folha = payload.media_mensal_folha
        existing.classificacao_anexo = payload.classificacao_anexo
        existing.analise_completa = payload.analise_completa

        # Deletar pendências antigas com SQL cru (evita problemas de flush/commit)
        db.execute(
            text('DELETE FROM auditoria_pendencias WHERE auditoria_id = :id'),
            {'id': existing.id}
        )

        # Inserir novas pendências
        for p_data in payload.pendencias:
            pendencia = AuditoriaPendencia(
                auditoria_id=existing.id,
                tipo_documento=p_data.tipo_documento,
                gravidade=p_data.gravidade,
                status=p_data.status,
                observacao=p_data.observacao,
                crf=p_data.crf,
                crt=p_data.crt,
                base_calculo=p_data.base_calculo,
                receita_declarada=p_data.receita_declarada,
            )
            db.add(pendencia)
        db.commit()
    else:
        # Create new
        auditoria = Auditoria(
            cnpj=cnpj,
            razao_social=payload.razao_social,
            periodo=periodo,
            status_geral=payload.status_geral,
            conformidade_pct=payload.conformidade_pct,
            observacao_geral=payload.observacao_geral,
            documentos_esperados=payload.documentos_esperados,
            documentos_encontrados=payload.documentos_encontrados,
            fator_r=payload.fator_r,
            aliquota_efetiva=payload.aliquota_efetiva,
            receita_pa=payload.receita_pa,
            rbt12=payload.rbt12,
            folha_12m=payload.folha_12m,
            pro_labore=payload.pro_labore,
            inss=payload.inss,
            irrf=payload.irrf,
            fgts=payload.fgts,
            num_funcionarios=payload.num_funcionarios,
            media_mensal_folha=payload.media_mensal_folha,
            classificacao_anexo=payload.classificacao_anexo,
            analise_completa=payload.analise_completa,
        )
        db.add(auditoria)
        db.commit()
        db.refresh(auditoria)

        for p_data in payload.pendencias:
            pendencia = AuditoriaPendencia(
                auditoria_id=auditoria.id,
                tipo_documento=p_data.tipo_documento,
                gravidade=p_data.gravidade,
                status=p_data.status,
                observacao=p_data.observacao,
                crf=p_data.crf,
                crt=p_data.crt,
                base_calculo=p_data.base_calculo,
                receita_declarada=p_data.receita_declarada,
            )
            db.add(pendencia)
        db.commit()

    # Determine which auditoria object to use
    result_obj = auditoria if 'auditoria' in dir() else existing

    # Reload with pendencias
    result = db.execute(
        select(Auditoria)
        .where(Auditoria.id == result_obj.id)
        .options(selectinload(Auditoria.pendencias))
    )
    auditoria = result.scalar_one()

    return _auditoria_to_out(auditoria)


@router.get("/visao-geral", response_model=dict)
async def visao_geral(
    periodo: str = Query(..., description="Período no formato YYYY-MM"),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    """KPIs consolidados + lista de empresas ordenadas por pendências críticas."""
    total_empresas = db.execute(
        select(func.count(Auditoria.id)).where(Auditoria.periodo == periodo)
    ).scalar() or 0

    conformes = db.execute(
        select(func.count(Auditoria.id)).where(
            Auditoria.periodo == periodo, Auditoria.status_geral == "CONFORME"
        )
    ).scalar() or 0

    criticas = db.execute(
        select(func.count(Auditoria.id)).where(
            Auditoria.periodo == periodo, Auditoria.status_geral == "CRITICO"
        )
    ).scalar() or 0

    total_faltantes = db.execute(
        select(func.sum(Auditoria.documentos_esperados - Auditoria.documentos_encontrados)).where(
            Auditoria.periodo == periodo
        )
    ).scalar() or 0

    empresas_result = db.execute(
        select(Auditoria).where(Auditoria.periodo == periodo).order_by(Auditoria.id)
    ).scalars().all()

    empresas = []
    for emp in empresas_result:
        criticas_count = db.execute(
            select(func.count(AuditoriaPendencia.id)).where(
                AuditoriaPendencia.auditoria_id == emp.id,
                AuditoriaPendencia.gravidade == "ALTA",
            )
        ).scalar() or 0
        empresas.append({
            "id": emp.id,
            "cnpj": emp.cnpj,
            "razao_social": emp.razao_social,
            "periodo": emp.periodo,
            "status_geral": emp.status_geral,
            "conformidade_pct": emp.conformidade_pct,
            "fator_r": emp.fator_r,
            "aliquota_efetiva": emp.aliquota_efetiva,
            "classificacao_anexo": emp.classificacao_anexo,
            "pendencias_criticas_count": criticas_count,
        })

    empresas.sort(key=lambda x: x["pendencias_criticas_count"], reverse=True)

    return {
        "kpis": {
            "total_empresas": total_empresas,
            "conformes": conformes,
            "criticas": criticas,
            "total_documentos_faltantes": total_faltantes,
        },
        "empresas": empresas,
    }


@router.get("/empresa/{cnpj}", response_model=AuditoriaOut)
async def get_auditoria_empresa(
    cnpj: str,
    periodo: str = Query(..., description="Período no formato YYYY-MM"),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    """Detalhes da auditoria de uma empresa + lista de pendências."""
    result = db.execute(
        select(Auditoria)
        .where(Auditoria.cnpj == cnpj, Auditoria.periodo == periodo)
        .options(selectinload(Auditoria.pendencias))
    )
    auditoria = result.scalar_one_or_none()

    if not auditoria:
        raise HTTPException(status_code=404, detail="Auditoria não encontrada")

    return _auditoria_to_out(auditoria)


@router.get("/periodos", response_model=List[str])
async def get_periodos(db: Session = Depends(get_db), api_key: str = Depends(api_key_dep)):
    """Lista de períodos distintos."""
    result = db.execute(
        select(Auditoria.periodo).distinct().order_by(Auditoria.periodo.desc())
    )
    return [row[0] for row in result.all()]


@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db), api_key: str = Depends(api_key_dep)):
    """KPIs agregados do dashboard."""
    # Contagens por status
    total_result = db.execute(select(func.count(Auditoria.id)))
    total_empresas = total_result.scalar() or 0

    conformes_result = db.execute(
        select(func.count(Auditoria.id)).where(Auditoria.status_geral == "CONFORME")
    )
    conformes = conformes_result.scalar() or 0

    criticas_result = db.execute(
        select(func.count(Auditoria.id)).where(Auditoria.status_geral == "CRITICO")
    )
    criticas = criticas_result.scalar() or 0

    total_doc_faltantes_result = db.execute(
        select(func.sum(Auditoria.documentos_esperados - Auditoria.documentos_encontrados))
    )
    total_doc_faltantes = total_doc_faltantes_result.scalar() or 0

    return {
        "kpis": {
            "total_empresas": total_empresas,
            "conformes": conformes,
            "criticas": criticas,
            "total_documentos_faltantes": total_doc_faltantes,
        }
    }


@router.get("/dashboard/fator-r")
async def get_fator_r_ranking(db: Session = Depends(get_db), api_key: str = Depends(api_key_dep)):
    """Ranking de empresas por Fator R."""
    result = db.execute(
        select(Auditoria)
        .where(Auditoria.fator_r.isnot(None))
        .order_by(Auditoria.fator_r.desc())
    )
    empresas = result.scalars().all()
    return [
        {
            "cnpj": emp.cnpj,
            "razao_social": emp.razao_social,
            "fator_r": emp.fator_r,
            "aliquota_efetiva": emp.aliquota_efetiva,
            "periodo": emp.periodo,
            "classificacao_anexo": emp.classificacao_anexo,
        }
        for emp in empresas
    ]


def _auditoria_to_out(auditoria: Auditoria) -> AuditoriaOut:
    """Converte modelo Auditoria para AuditoriaOut com pendências."""
    pendencias = [
        AuditoriaPendenciaOut(
            id=p.id,
            auditoria_id=p.auditoria_id,
            tipo_documento=p.tipo_documento,
            gravidade=p.gravidade,
            status=p.status,
            observacao=p.observacao,
            crf=p.crf,
            crt=p.crt,
            base_calculo=p.base_calculo,
            receita_declarada=p.receita_declarada,
        )
        for p in auditoria.pendencias
    ]
    return AuditoriaOut(
        id=auditoria.id,
        cnpj=auditoria.cnpj,
        razao_social=auditoria.razao_social,
        periodo=auditoria.periodo,
        status_geral=auditoria.status_geral,
        conformidade_pct=auditoria.conformidade_pct,
        observacao_geral=auditoria.observacao_geral,
        documentos_esperados=auditoria.documentos_esperados,
        documentos_encontrados=auditoria.documentos_encontrados,
        fator_r=auditoria.fator_r,
        aliquota_efetiva=auditoria.aliquota_efetiva,
        receita_pa=auditoria.receita_pa,
        rbt12=auditoria.rbt12,
        folha_12m=auditoria.folha_12m,
        pro_labore=auditoria.pro_labore,
        inss=auditoria.inss,
        irrf=auditoria.irrf,
        fgts=auditoria.fgts,
        num_funcionarios=auditoria.num_funcionarios,
        media_mensal_folha=auditoria.media_mensal_folha,
        classificacao_anexo=auditoria.classificacao_anexo,
        analise_completa=auditoria.analise_completa,
        created_at=auditoria.created_at,
        updated_at=auditoria.updated_at,
        pendencias=pendencias,
    )
