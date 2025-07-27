# Telegram Video Downloader

Um aplicativo em Python com interface gráfica (GUI) para baixar vídeos de grupos do Telegram, com suporte a filtros de tamanho mínimo e seleção de pasta de destino.

## Funcionalidades

- **Download de Vídeos**: Baixe vídeos de grupos do Telegram com base em um tamanho mínimo (e.g., "10MB").
- **Seleção de Grupos**: Escolha múltiplos grupos para download a partir de uma lista.
- **Gerenciamento de Grupos**: Adicione ou remova grupos diretamente na interface, salvando em `config/groups.txt`.
- **Seleção de Pasta**: Escolha a pasta de destino para os vídeos baixados.
- **Progresso Visual**: Exibe barras de progresso para cada download em andamento.
- **Log de Atividades**: Registra mensagens de status e erros em uma área de log na interface e em `logs/debug.log`.
- **Interface Minimalista**: Design limpo e compacto com cores planas, sem bordas e botões de maximizar desativados.

## Pré-requisitos

- **Python 3.8+**: Certifique-se de ter o Python instalado.
- **Dependências**:
  - PyQt6 (interface gráfica)
  - Telethon (interação com a API do Telegram)
  - python-dotenv (gerenciamento de variáveis de ambiente)

## Instalação

1. **Clone o Repositório**:
   - Execute: `git clone <URL_DO_REPOSITORIO>`
   - Navegue até o diretório: `cd telegram-video-downloader`

2. **Crie um Ambiente Virtual (opcional, mas recomendado)**:
   - Execute: `python -m venv venv`
   - Ative o ambiente virtual:
     - Para Linux/Mac: `source venv/bin/activate`
     - Para Windows: `venv\Scripts\activate`

3. **Instale as Dependências**:
   - Execute: `pip install PyQt6 telethon python-dotenv`

4. **Configure as Credenciais do Telegram**:
   - Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:
     ```
     API_ID=seu_api_id
     API_HASH=seu_api_hash
     SINCE_DATE=YYYY-MM-DD  # Opcional: data inicial para baixar vídeos
     MAX_TOTAL_SIZE=10GB    # Opcional: tamanho máximo total dos downloads
     ```
   - Obtenha `API_ID` e `API_HASH` em [my.telegram.org](https://my.telegram.org).

5. **Crie os Diretórios Necessários**:
   - O programa cria automaticamente os diretórios `config/`, `logs/` e `downloads/` se não existirem.
   - Opcionalmente, crie um arquivo `config/groups.txt` vazio ou adicione nomes de grupos (e.g., `@nome_do_grupo` ou IDs numéricos).

## Uso

1. **Execute o Programa**:
   - Execute: `python main.py`

2. **Interface Gráfica**:
   - **Pasta de Destino**: Clique em "Escolher" para selecionar a pasta onde os vídeos serão salvos.
   - **Tamanho Mínimo**: Insira o tamanho mínimo dos vídeos (e.g., "10MB") no campo "Tamanho".
   - **Adicionar Grupos**: Digite o nome ou ID de um grupo (e.g., `@nome_do_grupo`) no campo "Adicionar Grupo" e clique em "Adicionar".
   - **Remover Grupos**: Selecione um ou mais grupos na lista e clique em "Remover" para excluí-los.
   - **Selecionar Grupos**: Selecione os grupos desejados na lista para download.
   - **Iniciar Download**: Clique em "Iniciar" para começar o download dos vídeos.
   - **Limpar Log**: Clique em "Limpar" para esvaziar a área de log.

3. **Logs**: Acompanhe o progresso e erros na área de log e no arquivo `logs/debug.log`.

## Observações

- Os vídeos são salvos em `downloads/` com nomes no formato `YYYY-MM-DD_ID.ext`.
- A janela é compacta (550x450) e não pode ser maximizada, mas pode ser redimensionada.

# ⚙️ Stack Técnica
![Screenshot](https://github.com/felipepizetta/telegram-video-downloader/blob/50afe79423e9c45bade44feb43a527225e1790b0/assets/img/stack.png)
