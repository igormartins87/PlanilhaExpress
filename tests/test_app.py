
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd

# Localiza a raiz do projeto e adiciona src ao caminho de importação.
RAIZ_PROJETO = Path(__file__).resolve().parents[1]
PASTA_SRC = RAIZ_PROJETO / "src"

sys.path.insert(0, str(PASTA_SRC))

from app import tratar_planilhas, gerar_csv


def test_remove_registros_exatamente_iguais():
    """Remove linhas completamente repetidas."""
    df_a = pd.DataFrame({
        "nome": ["Ana", "Bruno"],
        "email": ["ana@email.com", "bruno@email.com"],
    })

    df_b = pd.DataFrame({
        "nome": ["Bruno", "Carlos"],
        "email": ["bruno@email.com", "carlos@email.com"],
    })

    resultado, total, removidos = tratar_planilhas(df_a, df_b)

    assert total == 4
    assert removidos == 1
    assert len(resultado) == 3


def test_normaliza_espacos_e_maiusculas():
    """Reconhece duplicados com espaços ou diferenças de caixa."""
    df_a = pd.DataFrame({
        "nome": ["Ana", "Bruno"],
        "email": ["ana@email.com", "bruno@email.com"],
    })

    df_b = pd.DataFrame({
        "nome": [" ANA ", "BRUNO"],
        "email": ["ana@email.com", "bruno@email.com"],
    })

    resultado, total, removidos = tratar_planilhas(df_a, df_b)

    assert total == 4
    assert removidos == 2
    assert len(resultado) == 2

    # Preserva os valores originais da primeira ocorrência.
    assert resultado.iloc[0]["nome"] == "Ana"
    assert resultado.iloc[1]["nome"] == "Bruno"


def test_remove_duplicados_por_coluna_identificadora():
    """Identifica duplicados usando uma coluna específica."""
    df_a = pd.DataFrame({
        "nome": ["Ana"],
        "email": ["ana@email.com"],
    })

    df_b = pd.DataFrame({
        "nome": ["Ana Silva"],
        "email": [" ANA@EMAIL.COM "],
    })

    resultado, total, removidos = tratar_planilhas(
        df_a,
        df_b,
        coluna_identificadora="email",
    )

    assert total == 2
    assert removidos == 1
    assert len(resultado) == 1
    assert resultado.iloc[0]["nome"] == "Ana"


def test_rejeita_colunas_diferentes():
    """Rejeita planilhas com estruturas incompatíveis."""
    df_a = pd.DataFrame({
        "nome": ["Ana"],
        "email": ["ana@email.com"],
    })

    df_b = pd.DataFrame({
        "nome": ["Bruno"],
        "telefone": ["21999999999"],
    })

    try:
        tratar_planilhas(df_a, df_b)
        assert False, "Era esperado um ValueError."
    except ValueError as erro:
        assert "mesmas colunas" in str(erro)


def test_exportacao_protege_valores_que_parecem_formulas():
    """Verifica a proteção dos valores potencialmente perigosos."""
    df = pd.DataFrame({
        "valor": [
            "=1+1",
            "+SUM(A1:A2)",
            "-1+2",
            "@SUM(A1:A2)",
            "  =1+1",
            "Nome comum",
        ]
    })

    conteudo = gerar_csv(df)

    exportado = pd.read_csv(
        BytesIO(conteudo),
        dtype=str,
        keep_default_na=False,
    )

    valores = exportado["valor"].tolist()

    assert valores[0] == "'=1+1"
    assert valores[1] == "'+SUM(A1:A2)"
    assert valores[2] == "'-1+2"
    assert valores[3] == "'@SUM(A1:A2)"
    assert valores[4] == "'  =1+1"
    assert valores[5] == "Nome comum"


def test_exportacao_nao_modifica_dataframe_original():
    """Garante que exportar não altere os dados originais."""
    df = pd.DataFrame({
        "nome": ["=1+1", "Ana"],
    })

    original = df.copy(deep=True)

    gerar_csv(df)

    pd.testing.assert_frame_equal(df, original)
