import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
from streamlit_extras.grid import grid
import openai
import plotly.express as px
import toml

# Carrega o arquivo config.toml
secrets = toml.load(".streamlit/secrets.toml")

# Define a página para usar a largura total
st.set_page_config(layout="wide")

# Configurações do banco de dados a partir do arquivo .streamlit/secrets.toml
user = st.secrets["database"]["DB_USER"]
password = st.secrets["database"]["DB_PASSWORD"]
host = st.secrets["database"]["DB_HOST"]
database = st.secrets["database"]["DB_DATABASE"]
schema = st.secrets["database"]["DB_SCHEMA"]
table_name = st.secrets["database"]["DB_TABLE"]

# Criação da string de conexão
connection_string = f"mysql+mysqlconnector://{user}:{password}@{host}/{database}"

engine = create_engine(connection_string)

# Consulta para obter dados de campeões e anos
df = pd.read_sql_query(
    """
    SELECT b.*, vc.campeao
    FROM dataplace.brasileirao b
    LEFT JOIN dataplace.vw_campeoes vc ON b.ano_campeonato = vc.ano_campeonato;
    """, engine
)

# Consulta para obter dados de média de público por ano
df_publico = pd.read_sql_query("SELECT ano_campeonato, media_de_publico FROM dataplace.vw_media_publico;", engine)

# Consulta para obter os anos disponíveis
edicao = pd.read_sql_query(f"SELECT DISTINCT ano_campeonato FROM {schema}.{table_name};", engine)

def media_de_publico(df, ano):
    # Filtra o DataFrame para o ano específico
    df_filtrado = df[df['ano_campeonato'] == ano]
    
    # Agrupa os dados pelo time mandante e calcula a média de público
    media_publico = df_filtrado.groupby('time_mandante')['publico'].mean().reset_index()
    
    # Adiciona o ano ao DataFrame resultante
    media_publico['ano_campeonato'] = ano
    
    # Reorganiza as colunas
    media_publico = media_publico[['ano_campeonato', 'time_mandante', 'publico']]
    
    # Seleciona a maior média
    maior_media = media_publico.loc[media_publico['publico'].idxmax()]

    return media_publico, maior_media





def media_de_valor_equipe(df, ano):
    # Filtra o DataFrame para o ano específico
    df_filtrado = df[df['ano_campeonato'] == ano]
    
    # Calcula o maior valor das equipes mandantes e visitantes
    maior_valor_mandante = df_filtrado.groupby('time_mandante')['valor_equipe_titular_mandante'].max().reset_index()
    maior_valor_visitante = df_filtrado.groupby('time_visitante')['valor_equipe_titular_visitante'].max().reset_index()
    
    # Renomeia as colunas para facilitar a junção
    maior_valor_mandante.columns = ['time_mandante', 'maior_valor_mandante']
    maior_valor_visitante.columns = ['time_visitante', 'maior_valor_visitante']
    
    # Junta os DataFrames
    media = pd.merge(maior_valor_mandante, maior_valor_visitante, left_on='time_mandante', right_on='time_visitante', how='outer')
    
    # Calcula a média total
    media['media_total'] = (media['maior_valor_mandante'].fillna(0) + media['maior_valor_visitante'].fillna(0)) / 14
    
    # Adiciona o ano ao DataFrame resultante
    media['ano_campeonato'] = ano
    
    # Seleciona a maior média
    maior_media = media.loc[media['media_total'].idxmax()]

    # Reorganiza as colunas
    return media[['ano_campeonato', 'time_mandante', 'media_total']], maior_media




def build_sidebar():
    st.image(f"./image/logo.png", width=250)
    ano = st.multiselect(label="Edição", options=edicao['ano_campeonato'], placeholder="Edição")
    return ano

# Estilo de fonte
st.markdown(
    """
    <style>
    .small-font {
        font-size: 18px; /* Ajuste o tamanho da fonte aqui */
    }
    </style>
    """,
    unsafe_allow_html=True
)
# Função para plotar o gráfico de barras com Plotly


def plotar_grafico_media_publico():
    # Preparar os dados
    df_publico['media_de_publico'] = df_publico['media_de_publico'].astype(int)
    
    # Define o título
    st.subheader("Média de Público por Ano")
    
    # Cria o gráfico de barras com Plotly
    fig = px.bar(
        df_publico, 
        x='ano_campeonato', 
        y='media_de_publico', 
        title="Média de Público por Ano", 
        labels={'ano_campeonato': 'Ano do Campeonato', 'media_de_publico': 'Média de Público'},
        text='media_de_publico',  # Adiciona os rótulos de dados
        height= 450
    )
    
    # Ajusta a cor das barras para dourado
    fig.update_traces(marker_color='gold')
    
    # Ajusta o layout para uma visualização melhor
    fig.update_layout(
        yaxis_title='Média de Público',
        xaxis_title='Ano do Campeonato',
        template='plotly_white'
    )

    # Exibe o gráfico no Streamlit
    st.plotly_chart(fig)


# Configura sua chave da API
openai.api_key = st.secrets["database"]['OPENAI_API_KEY']

def consultar_openai(prompt):
    try:
        # Faz a solicitação à API com limite de tokens
        resposta = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # ou outro modelo que você deseja usar
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500  # Limita a resposta a 200 tokens
        )

        # Extrai o texto da resposta
        texto_resposta = resposta['choices'][0]['message']['content']
        return texto_resposta

    except Exception as e:
        return f"Ocorreu um erro: {str(e)}"


def exibir_valores_selecionados(ano):
    mygrid = grid(3, vertical_align="top")

    for e in ano:
           
        # Filtra o campeão para o ano selecionado
        dataset = df[df['ano_campeonato'] == e]
        
        # Verifica se existe um registro para o ano selecionado
        if not dataset.empty:
            nome_campeao = dataset['campeao'].values[0]
        else:
            nome_campeao = "Não disponível"

        # Cria o container e insere os dados
        c = mygrid.container(border=True)
        c.subheader(f"Campeão {e}", divider='grey')
        colA, colB = c.columns(2)
        
        # Exibe a imagem e o nome do campeão com tamanho de fonte menor
        colA.image(f'./image/{nome_campeao}.png', width=50)
        colB.markdown(f"<p class='small-font'>Equipe: {nome_campeao}</p>", unsafe_allow_html=True)

        media_publico, maior_media = media_de_publico(df,e)
        media_publico_ano = maior_media['publico'].astype(int).astype(str)
        time_media_publico_ano = maior_media['time_mandante']

        # Cria o container e insere os dados
        c = mygrid.container(border=True)
        c.subheader(f"Maior Média de Público", divider='grey')
        colC, colD = c.columns(2)
        
        # Exibe a imagem e o nome do campeão com tamanho de fonte menor
        colC.image(f'./image/{time_media_publico_ano}.png', width=50)
        colD.markdown(f"<p class='small-font'>{time_media_publico_ano}: {media_publico_ano}</p>", unsafe_allow_html=True)

        # Chama a função para obter as médias
        media_valor_equipe, time_mais_valioso = media_de_valor_equipe(df, e)

        media_valor_equipe_final = round(time_mais_valioso['media_total'],2)
        
        # Obtém o nome do time mais valioso
        nome_time_mais_valioso = time_mais_valioso['time_mandante']

        # Cria o container e insere os dados
        c = mygrid.container(border=True)
        c.subheader(f"Time mais valioso", divider='grey')
        colE, colF = c.columns(2)
        
        # Exibe a imagem e o nome do campeão com tamanho de fonte menor
        colE.image(f'./image/{nome_time_mais_valioso}.png', width=50)
        colF.markdown(f"<p class='small-font'>{nome_time_mais_valioso}: {media_valor_equipe_final}</p>", unsafe_allow_html=True)

        st.subheader(f"Edição : {e}",divider='grey')
        # Exibe o gráfico de média de público


        # Prompt embutido no código para engenharia de prompts
        prompt = f'''Estou fornecendo um dataset que contem dados do campeonato brasileiro de futebol. 
        <dataset>
            {{dataset}}
        </dataset>
        Vamos iniciar formatando os dados como Markdown.
        
        Considere os dados contidos no dataset {dataset} retorne a seguinte lista de solicitações.
        1 - Retorne Qual time foi campeão, considere os dados do dataset {dataset['campeao']}
        2 - Considere a coluna {dataset['gols_mandante']} e informe Qual o time que fez mais gols como mandante ao longo do ano. Informe o número de gols.
        3 - Qual time possui a maior media de publico como mandante ao longo do ano (cite o nome do estadio e a média). 
        4 - Qual foi o maior placar e em qual confronto.
        5 - Qual foi o percentual de empates.
        Por fim retorne alguma curiosidade sobre os dados contidos no dataset.
        Retorne apenas as respostas completas.'''

        resposta = consultar_openai(prompt)

        st.markdown(f"### Insights gerados usando a API da OpenAI:\n\n{resposta}")  


plotar_grafico_media_publico()

with st.sidebar:
    ano = build_sidebar()
    

if ano:
    exibir_valores_selecionados(ano)