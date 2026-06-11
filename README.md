# 📣 Marketing Automation System v6

Sistema completo de automação de marketing com **26 funcionalidades**, 9 plataformas, Gemini Flash (gratuito), painel web PWA instalável e 151 testes automatizados.

---

## 🆕 Novidades da v6

| # | Funcionalidade | Descrição |
|---|---|---|
| 1 | **PWA instalável** | App instalável no celular e desktop, ícone na tela inicial, suporte offline |
| 2 | **Voz da marca** | Tom, keywords e exemplos injetados em todo conteúdo gerado pelo Gemini |
| 3 | **RSS auto-posting** | Monitora feeds e cria posts automaticamente a partir de novos artigos |
| 4 | **Webhooks de eventos** | Notifica Zapier, Make, N8N etc. com HMAC-SHA256 em cada evento |
| 5 | **Notificações Slack** | Alertas em tempo real no canal do time para aprovações e publicações |
| 6 | **Upload direto de imagens** | Upload de arquivos PNG/JPG/WebP com suporte a Cloudinary ou armazenamento local |
| 7 | **Rate limiting** | Flask-Limiter: 300 req/hora global, 60/min na API, 10/min nas integrações |
| 8 | **Export CSV + HTML** | Exporta histórico de posts como CSV e relatório visual pronto para PDF |
| 9 | **Score de performance** | Gemini avalia engajamento previsto (1-10) com pontos fortes e sugestões |
| 10 | **Reciclagem de conteúdo** | Repostar top posts com variações geradas pelo Gemini |

---

## 🏗️ Estrutura

```
marketing_automation/
├── web_app.py                  ← Ponto de entrada
├── app.py                      ← Factory Flask + Rate Limiting
├── auth.py                     ← Multi-usuário + 2FA
├── config.py                   ← Todas as variáveis de ambiente
├── render.yaml / Procfile      ← Deploy no Render
│
├── core/
│   ├── models.py               ← User, Post, Template, BrandVoice, RssFeed, Webhook, AuditLog
│   ├── ai_processor.py         ← Gemini Flash + Brand Voice
│   ├── scheduler.py            ← APScheduler + PostgreSQL
│   ├── brand_voice.py          ← Identidade de marca + Score de performance
│   ├── rss_monitor.py          ← Monitoramento de feeds RSS
│   ├── webhooks.py             ← Dispatch HTTP + Slack
│   ├── recycler.py             ← Reciclagem de conteúdo
│   ├── exporter.py             ← Export CSV e HTML
│   ├── email_service.py        ← Notificações SMTP
│   ├── image_gen.py            ← DALL-E 3
│   ├── audit.py                ← Auditoria, sentimento, A/B, melhor horário
│   └── publishers/             ← 9 plataformas
│       ├── twitter.py
│       ├── instagram.py
│       ├── linkedin.py
│       ├── facebook.py
│       ├── youtube.py
│       ├── tiktok.py
│       ├── pinterest.py
│       ├── whatsapp.py
│       └── gmb.py
│
├── routes/
│   ├── api.py                  ← Stats, jobs, preview, publish
│   ├── api_posts.py            ← CRUD + fluxo aprovação + webhooks
│   ├── api_tools.py            ← Templates, 2FA, CSV import, sentimento, A/B
│   ├── api_integrations.py     ← Brand Voice, RSS, Webhooks, Upload, Export, Score, Recycling
│   ├── views.py
│   └── youtube_auth.py
│
├── static/
│   ├── manifest.json           ← PWA manifest
│   └── sw.js                   ← Service Worker (offline)
│
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── verify_2fa.html
│   └── index.html              ← Painel com 14 abas
│
└── tests/                      ← 151 testes
    ├── conftest.py
    ├── test_auth.py
    ├── test_posts.py
    ├── test_tools.py
    ├── test_api.py
    ├── test_integrations.py    ← Testes das 10 novas melhorias
    ├── test_ai_processor.py
    └── test_publishers.py
```

---

## 🚀 Funcionalidades completas (26)

### Publicação
- Adaptação automática com Gemini Flash para 9 plataformas
- Preview em tempo real antes de publicar
- Score de engajamento previsto (1-10) por IA
- Geração de imagens com DALL-E 3
- Upload direto de arquivos PNG/JPG/WebP
- A/B testing automático com duas variantes
- Agendamento com APScheduler + PostgreSQL
- Importação em massa via CSV

### Fluxo de trabalho
- Roles: admin / revisor / editor
- Fluxo de aprovação: draft → pending → approved → published
- Notificações por e-mail (SMTP)
- Notificações no Slack
- Webhooks HTTP (Zapier, Make, N8N) com HMAC-SHA256
- Log de auditoria completo

### Automação
- RSS: monitora feeds e cria posts automaticamente
- Reciclagem: repostar top posts com variações do Gemini
- Voz da marca: identidade consistente em todo conteúdo

### Analytics
- Dashboard com estatísticas e histórico
- Análise de sentimento de comentários
- Sugestão de melhor horário por plataforma
- Export CSV e relatório HTML para PDF
- Engajamento por plataforma

### Segurança & UX
- Autenticação 2FA (TOTP - Google Authenticator)
- Rate limiting por IP e por endpoint
- PWA instalável no celular e desktop
- Calendário visual de posts agendados
- Biblioteca de templates reutilizáveis

---

## ⚙️ Instalação

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edite o .env com suas credenciais
python web_app.py   # http://localhost:5000
```

---

## 📲 Instalar como app (PWA)

No Chrome/Edge/Safari:
- Acesse o painel no navegador
- Clique no ícone de instalação na barra de endereço
- O app aparece na tela inicial como qualquer app nativo

---

## 🔗 Webhooks

Ao criar um webhook, você recebe um `secret` para validar as requisições:

```python
import hmac, hashlib

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

Eventos disponíveis: `post.published`, `post.approved`, `post.rejected`, `post.failed`, `post.pending`

---

## 📡 RSS Auto-posting

1. Acesse **RSS Feeds → Adicionar feed**
2. Cole a URL do feed RSS do blog ou site
3. Selecione as plataformas de destino
4. O sistema verifica automaticamente no intervalo configurado
5. Novos artigos viram posts em rascunho para revisão

---

## 🧪 Testes

```bash
pytest tests/ --ignore=tests/test_scheduler.py -v
# 151 testes
```
