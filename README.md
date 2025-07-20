<a href="https://github.com/FelipePizetta/telegram-video-downloader/blob/main/README-EN.md">Don't speak Portuguese? Click here to view the english version!</a>

# 📹 Downloader de Vídeos do Telegram

Uma ferramenta robusta em Python para baixar vídeos com segurança de grupos e canais do Telegram, com reconexão automática e acompanhamento de progresso.

🔥 **Recursos**

## Download à Prova de Falhas

- Reconexão automática em caso de queda de conexão  
- Lógica de re-tentativa configurável com backoff exponencial  
- Controle de tempo limite por arquivo (evita travamentos infinitos)

## Gerenciamento Inteligente de Mídia

- Filtros por data/tamanho (ignora vídeos pequenos/de baixa qualidade)  
- Armazenamento organizado com nomes de arquivo baseados na data  
- Suporte a downloads paralelos (configurável)

## Log de Nível Empresarial

- Logs compatíveis com UTF-8 (suporta emojis)  
- Registros detalhados de sucesso/falha  
- Rotação diária de logs

## Segurança em Primeiro Lugar

- Credenciais armazenadas em `.env` (nunca no código)  
- Sessão com criptografia  
- Configuração segura para uso com Git

# ⚙️ Stack Técnica
![Screenshot](https://github.com/felipepizetta/telegram-video-downloader/blob/50afe79423e9c45bade44feb43a527225e1790b0/assets/img/stack.png)
