
import streamlit as st
import pandas as pd
from io import BytesIO


# --------------------------------------------------
# CONFIGURAÇÃO DA APLICAÇÃO
# --------------------------------------------------

st.set_page_config(
    page_title="Planilha Express",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Planilha Express")
st.subheader("Organize seus dados sem complicação")

st.write(
    "Envie duas planilhas CSV, combine os registros, "
    "identifique duplicados e baixe o resultado tratado."
)


# --------------------------------------------------
# FUNÇÕES
# --------------------------------------------------


MAX_CSV_SIZE_BYTES = 10 * 1024 * 1024
MAX_CSV_ROWS = 100_000
MAX_CSV_COLUMNS = 100


def ler_csv(arquivo):
    """Valida e lê um arquivo CSV dentro dos limites definidos."""

    conteudo = arquivo.getvalue()

    if not conteudo:
        raise ValueError("O arquivo enviado está vazio.")

    if len(conteudo) > MAX_CSV_SIZE_BYTES:
        raise ValueError(
            "O arquivo ultrapassa o limite de 10 MB."
        )

    if b"\x00" in conteudo:
        raise ValueError(
            "O arquivo contém bytes nulos e não foi aceito como CSV."
        )

    ultimo_erro = None

    for encoding in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(
                BytesIO(conteudo),
                sep=None,
                engine="python",
                encoding=encoding,
                dtype=str,
                keep_default_na=False,
                on_bad_lines="error",
            )

            if len(df.columns) > MAX_CSV_COLUMNS:
                raise ValueError(
                    f"O arquivo excede o limite de "
                    f"{MAX_CSV_COLUMNS} colunas."
                )

            if len(df) > MAX_CSV_ROWS:
                raise ValueError(
                    f"O arquivo excede o limite de "
                    f"{MAX_CSV_ROWS:,} registros."
                )

            return df

        except UnicodeDecodeError as erro:
            ultimo_erro = erro

        except pd.errors.ParserError as erro:
            raise ValueError(
                "O CSV possui uma estrutura inválida."
            ) from erro

        except pd.errors.EmptyDataError as erro:
            raise ValueError(
                "O arquivo não contém um CSV válido."
            ) from erro

    raise ValueError(
        f"Não foi possível interpretar o arquivo: {ultimo_erro}"
    )




#FINAL
def normalizar_para_comparacao(df):
    """Cria uma cópia normalizada sem alterar os dados exportados."""
    comparacao = df.copy()

    for coluna in comparacao.columns:
        comparacao[coluna] = (
            comparacao[coluna]
            .astype("string")
            .str.strip()
            .str.casefold()
        )

    return comparacao


def tratar_planilhas(df_a, df_b, coluna_identificadora=None):
    """Combina as planilhas e remove duplicados."""
    if list(df_a.columns) != list(df_b.columns):
        raise ValueError(
            "As planilhas precisam ter as mesmas colunas, "
            "na mesma ordem."
        )

    combinado = pd.concat(
        [df_a, df_b],
        ignore_index=True,
    )

    total_original = len(combinado)
    comparacao = normalizar_para_comparacao(combinado)

    if coluna_identificadora is None:
        mascara_unicos = ~comparacao.duplicated()
    else:
        if coluna_identificadora not in comparacao.columns:
            raise ValueError("A coluna identificadora selecionada não existe.")

        mascara_unicos = ~comparacao.duplicated(
            subset=[coluna_identificadora]
        )

    resultado = combinado.loc[mascara_unicos].reset_index(drop=True)

    return resultado, total_original, total_original - len(resultado)


def proteger_valor_csv(valor):
    """Reduz o risco de valores serem interpretados como fórmulas."""
    texto = str(valor)

    # Considera também espaços antes do primeiro caractere.
    inicio = texto.lstrip(" \t\r\n")

    if inicio.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + texto

    return texto


def gerar_csv(df):
    """Exporta CSV aplicando proteção contra fórmulas perigosas."""
    exportacao = df.copy()

    for coluna in exportacao.columns:
        exportacao[coluna] = exportacao[coluna].map(
            proteger_valor_csv
        )

    return exportacao.to_csv(index=False).encode("utf-8-sig")



# --------------------------------------------------
# ENTRADA DOS ARQUIVOS
# --------------------------------------------------

st.divider()

coluna1, coluna2 = st.columns(2)

with coluna1:
    arquivo_a = st.file_uploader(
        "1. Envie a primeira planilha",
        type=["csv"],
        key="arquivo_a",
    )

with coluna2:
    arquivo_b = st.file_uploader(
        "2. Envie a segunda planilha",
        type=["csv"],
        key="arquivo_b",
    )


# --------------------------------------------------
# LEITURA E PRÉ-VISUALIZAÇÃO
# --------------------------------------------------

if arquivo_a is None or arquivo_b is None:
    st.info("Envie as duas planilhas CSV para começar.")
    st.session_state.pop("resultado_tratamento", None)

else:
    try:
        df_a = ler_csv(arquivo_a)
        df_b = ler_csv(arquivo_b)

        # Limpa espaços nos nomes das colunas.
        df_a.columns = df_a.columns.str.strip()
        df_b.columns = df_b.columns.str.strip()

        if len(df_a.columns) == 0 or len(df_b.columns) == 0:
            raise ValueError("Um dos arquivos não possui colunas válidas.")

        if not df_a.columns.is_unique or not df_b.columns.is_unique:
            raise ValueError(
                "Existem nomes de colunas repetidos em um dos arquivos."
            )

        st.subheader("Conferência das planilhas")

        col_a, col_b = st.columns(2)

        with col_a:
            st.write("**Primeira planilha**")
            st.caption(f"{len(df_a)} registros")
            st.dataframe(df_a.head(5), use_container_width=True)

        with col_b:
            st.write("**Segunda planilha**")
            st.caption(f"{len(df_b)} registros")
            st.dataframe(df_b.head(5), use_container_width=True)

        if list(df_a.columns) != list(df_b.columns):
            st.error(
                "As colunas não correspondem. "
                "Verifique os nomes e a ordem das colunas nos dois CSVs."
            )
            st.session_state.pop("resultado_tratamento", None)

        else:
            st.divider()
            st.subheader("Configurar tratamento")

            criterio = st.radio(
                "Como deseja identificar registros duplicados?",
                options=[
                    "Todas as colunas",
                    "Uma coluna identificadora",
                ],
                horizontal=True,
                key="criterio_duplicidade",
            )

            coluna_identificadora = None

            if criterio == "Uma coluna identificadora":
                coluna_identificadora = st.selectbox(
                    "Selecione a coluna identificadora",
                    options=list(df_a.columns),
                    key="coluna_identificadora",
                )

            # O formulário agrupa as opções e evita processamentos
            # inesperados enquanto o usuário altera a configuração.
            with st.form("form_tratamento"):
                confirmar = st.form_submit_button(
                    "Combinar e tratar planilhas",
                    type="primary",
                    use_container_width=True,
                )

            if confirmar:
                try:
                    resultado, total, removidos = tratar_planilhas(
                        df_a,
                        df_b,
                        coluna_identificadora=coluna_identificadora,
                    )

                    st.session_state["resultado_tratamento"] = {
                        "df": resultado,
                        "total": total,
                        "removidos": removidos,
                    }

                except Exception as erro:
                    st.error(f"Falha durante o tratamento: {erro}")
                    st.session_state.pop("resultado_tratamento", None)

    except (ValueError, pd.errors.EmptyDataError) as erro:
        st.error(f"Não foi possível processar os arquivos: {erro}")
        st.session_state.pop("resultado_tratamento", None)

    except Exception as erro:
        st.error(
            "Ocorreu um erro inesperado ao ler os arquivos. "
            f"Detalhes: {type(erro).__name__}: {erro}"
        )
        st.session_state.pop("resultado_tratamento", None)


# --------------------------------------------------
# RESULTADO
# --------------------------------------------------

dados = st.session_state.get("resultado_tratamento")

if dados is not None:
    resultado = dados["df"]

    st.divider()
    st.subheader("✅ Tratamento concluído")

    metrica1, metrica2, metrica3 = st.columns(3)

    metrica1.metric("Registros recebidos", dados["total"])
    metrica2.metric("Duplicados removidos", dados["removidos"])
    metrica3.metric("Registros finais", len(resultado))

    st.subheader("Resultado final")
    st.dataframe(resultado, use_container_width=True)

    st.download_button(
        label="📥 Baixar CSV tratado",
        data=gerar_csv(resultado),
        file_name="planilha_tratada.csv",
        mime="text/csv",
        key="download_csv",
    )
