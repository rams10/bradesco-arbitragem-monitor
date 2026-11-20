# Bradesco Arbitragem Monitor — iPhone + hospedagem gratuita

Este projeto usa GitHub Actions para consultar a brapi a cada 30 minutos em dias úteis, enviar alertas ao Telegram e atualizar um painel web estático no GitHub Pages. Não depende de deixar o iPhone ligado.

## Importante
- A brapi informa atraso aproximado de 30 minutos no plano gratuito e limite de um ticker por chamada nesse plano; o monitor faz duas chamadas por coleta (uma para cada ação), cerca de 1.000 chamadas/mês se executado 16 vezes por dia útil.
- O agendamento do GitHub Actions não é garantido no minuto exato; pode atrasar.
- Os sinais são cruzamentos da relação BBDC4/BBDC3: 1,07 para baixo e 1,13 para cima.
- O painel é público se publicado no GitHub Pages gratuito. Não coloque informações pessoais nele.
- As chaves ficam em GitHub Actions Secrets, nunca no código.
- O monitor não envia ordens e não substitui a conferência de preço, spread, custos, impostos, proventos e datas-com.

## Configuração pelo iPhone
1. Entre em https://github.com/ pelo Safari e crie/acesse sua conta.
2. Crie um repositório chamado `bradesco-arbitragem-monitor`. Para usar GitHub Free + Pages, ele precisa ser público. O código deste projeto não contém tokens.
3. Baixe e descompacte o ZIP no app Arquivos do iPhone.
4. No repositório, use Add file → Upload files e envie os arquivos mantendo os caminhos/pastas. Se o Safari não permitir enviar as pastas, use Add file → Create new file e crie os arquivos com os caminhos abaixo, colando o conteúdo correspondente.
5. Em Settings → Secrets and variables → Actions → New repository secret, crie:
   - `BRAPI_TOKEN`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   Cole cada valor diretamente no GitHub. Não compartilhe os tokens comigo, nem em Issues, comentários ou prints.
6. Em Settings → Actions → General → Workflow permissions, selecione `Read and write permissions` e salve. Isso permite que o workflow atualize o histórico no painel.
7. Abra Actions → `BBDC3/BBDC4 monitor` → Run workflow para testar manualmente.
8. Para publicar o site: Settings → Pages → Deploy from a branch → Branch `main` → folder `/docs` → Save.
9. Quando o GitHub mostrar a URL do Pages, abra no Safari e escolha Compartilhar → Adicionar à Tela de Início.

## Arquivos
- `.github/workflows/monitor.yml`
- `monitor.py`
- `docs/index.html`
- `docs/data.json`

## Segurança
O repositório é público para permitir GitHub Pages no plano gratuito, mas GitHub Actions Secrets não são expostos no código ou no site. Não habilite workflows de terceiros desconhecidos. Se uma chave for exposta, revogue-a e gere outra.
