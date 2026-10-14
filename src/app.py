
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

st.title("Planilha Express")
st.subheader("Organize seus dados sem complicação")

st.write(
    "Envie duas planilhas CSV, combine os registros, "
    "identifique duplicados e baixe o resultado tratado."
)


# --------------------------------------------------
# LIMITES E FUNÇÕES DE PROCESSAMENTO
# --------------------------------------------------

MAX_CSV_SIZE_BYTES = 10 * 1024 * 1024
MAX_CSV_ROWS = 100_000
MAX_CSV_COLUMNS = 100


def limpar_resultado():
    """Remove o resultado mantido no estado da sessão."""
    st.session_state.pop("resultado_tratamento", None)


def reiniciar_aplicacao():
    """
    Limpa o resultado e os controles relacionados aos arquivos.
    O Streamlit executará novamente o script após a interação.
    """
    for chave in (
        "resultado_tratamento",
        "arquivo_a",
        "arquivo_b",
        "criterio_duplicidade",
        "coluna_identificadora",
        "mostrar_previa",
    ):
        st.session_state.pop(chave, None)

    st.rerun()


def ler_csv(arquivo):
    """Valida e lê um arquivo CSV dentro dos limites definidos."""

    conteudo = arquivo.getvalue()

    if not conteudo:
        raise ValueError("O arquivo enviado está vazio.")

    if len(conteudo) > MAX_CSV_SIZE_BYTES:
        raise ValueError("O arquivo ultrapassa o limite de 10 MB.")

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
                nrows=MAX_CSV_ROWS + 1,
            )

            if len(df.columns) > MAX_CSV_COLUMNS:
                raise ValueError("O arquivo excede o limite de colunas.")

            if len(df) > MAX_CSV_ROWS:
                raise ValueError("O arquivo excede o limite de registros.")

            return df

        except UnicodeDecodeError as erro:
            ultimo_erro = erro

        except pd.errors.ParserError as erro:
            raise ValueError("A estrutura do CSV é inválida.") from erro

        except pd.errors.EmptyDataError as erro:
            raise ValueError("O arquivo não contém um CSV válido.") from erro

    raise ValueError(
        "Não foi possível interpretar o arquivo com os formatos aceitos."
    ) from ultimo_erro


def normalizar_para_comparacao(df):
    """Cria uma cópia normalizada sem alterar os dados originais."""
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
    """Combina planilhas e remove registros duplicados."""

    if list(df_a.columns) != list(df_b.columns):
        raise ValueError(
            "As planilhas precisam ter as mesmas colunas, "
            "na mesma ordem."
        )

    combinado = pd.concat([df_a, df_b], ignore_index=True)

    total_original = len(combinado)
    comparacao = normalizar_para_comparacao(combinado)

    if coluna_identificadora is None:
        mascara_unicos = ~comparacao.duplicated()
    else:
        if coluna_identificadora not in comparacao.columns:
            raise ValueError("A coluna identificadora não existe.")

        mascara_unicos = ~comparacao.duplicated(
            subset=[coluna_identificadora]
        )

    resultado = combinado.loc[mascara_unicos].reset_index(drop=True)

    return resultado, total_original, total_original - len(resultado)


def proteger_valor_csv(valor):
    """Reduz o risco de interpretação de valores como fórmulas CSV."""
    texto = str(valor)
    inicio = texto.lstrip(" \t\r\n")

    if inicio.startswith(("=", "+", "-", "@")):
        return "'" + texto

    return texto


def gerar_csv(df):
    """Gera um CSV protegido contra fórmulas perigosas."""
    exportacao = df.copy()

    for coluna in exportacao.columns:
        exportacao[coluna] = exportacao[coluna].map(proteger_valor_csv)

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
# LEITURA E CONFERÊNCIA
# --------------------------------------------------

if arquivo_a is None or arquivo_b is None:
    st.info("Envie as duas planilhas CSV para começar.")
    limpar_resultado()

else:
    try:
        df_a = ler_csv(arquivo_a)
        df_b = ler_csv(arquivo_b)

        df_a.columns = df_a.columns.str.strip()
        df_b.columns = df_b.columns.str.strip()

        if len(df_a.columns) == 0 or len(df_b.columns) == 0:
            raise ValueError("Um dos arquivos não possui colunas válidas.")

        if not df_a.columns.is_unique or not df_b.columns.is_unique:
            raise ValueError("Existem nomes de colunas repetidos.")

        st.subheader("Conferência das planilhas")

        st.caption(
            f"Primeira planilha: {len(df_a)} registros. "
            f"Segunda planilha: {len(df_b)} registros."
        )

        mostrar_previa = st.checkbox(
            "Exibir os primeiros cinco registros de cada arquivo",
            value=False,
            key="mostrar_previa",
            help=(
                "Ative somente se precisar conferir os registros. "
                "A pré-visualização pode expor dados pessoais."
            ),
        )

        if mostrar_previa:
            col_a, col_b = st.columns(2)

            with col_a:
                st.write("Primeira planilha")
                st.dataframe(df_a.head(5), use_container_width=True)

            with col_b:
                st.write("Segunda planilha")
                st.dataframe(df_b.head(5), use_container_width=True)

        if list(df_a.columns) != list(df_b.columns):
            limpar_resultado()

            st.error(
                "As colunas não correspondem. "
                "Confira os nomes e a ordem nos dois arquivos."
            )

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

                except ValueError:
                    limpar_resultado()

                    st.error(
                        "Não foi possível tratar os arquivos. "
                        "Confira a estrutura e os critérios selecionados."
                    )

                except Exception:
                    limpar_resultado()

                    st.error(
                        "Não foi possível concluir o tratamento. "
                        "Tente novamente."
                    )

    except ValueError:
        limpar_resultado()

        st.error(
            "Não foi possível ler os arquivos. "
            "Verifique se os CSVs estão válidos e dentro dos limites aceitos."
        )

    except Exception:
        limpar_resultado()

        st.error(
            "Ocorreu um erro inesperado ao processar os arquivos. "
            "Tente novamente. Se o problema persistir, "
            "entre em contato com o responsável pela aplicação."
        )


# --------------------------------------------------
# RESULTADO
# --------------------------------------------------

dados = st.session_state.get("resultado_tratamento")

if dados is not None:
    resultado = dados["df"]

    st.divider()
    st.subheader("Tratamento concluído")

    metrica1, metrica2, metrica3 = st.columns(3)

    metrica1.metric("Registros recebidos", dados["total"])
    metrica2.metric("Duplicados removidos", dados["removidos"])
    metrica3.metric("Registros finais", len(resultado))

    st.subheader("Resultado final")
    st.dataframe(resultado, use_container_width=True)

    st.download_button(
        label="Baixar CSV tratado",
        data=gerar_csv(resultado),
        file_name="planilha_tratada.csv",
        mime="text/csv",
        key="download_csv",
    )

    st.button(
        "Limpar dados e reiniciar",
        on_click=reiniciar_aplicacao,
        help=(
            "Remove o resultado da sessão e limpa os controles "
            "de upload para iniciar um novo processamento."
        ),
    )
