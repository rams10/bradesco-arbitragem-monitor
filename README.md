# Monitor de alternância entre classes — BBDC, Sanepar e Klabin

Este projeto usa GitHub Actions para consultar a brapi aproximadamente a cada 30 minutos em dias úteis, enviar alertas ao Telegram e atualizar um painel web estático no GitHub Pages. Não depende de deixar o iPhone ligado.

## Pares monitorados

- **BBDC3 / BBDC4**: relação BBDC4/BBDC3; limites originais 1,07 e 1,13.
- **SAPR3 / SAPR4**: relação SAPR4/SAPR3; limites iniciais 0,88 e 1,05. Esses limites são provisórios e foram definidos aproximadamente pelo 1º e 3º quartis de dez fechamentos anuais (2017–2026). Ainda não foram validados por backtest diário.\n- **KLBN3 / KLBN4**: relação KLBN3/KLBN4; limites 0,95 e 1,05, equivalentes a desconto/prêmio relativo de 5% em qualquer direção. O painel começa com 13 observações semanais sincronizadas e passa a acrescentar observações a cada coleta de meia em meia hora.

Quando a relação cruza o limite inferior, o papel final 4 está relativamente mais barato e o painel sinaliza avaliar a troca da classe 3 para a 4. Quando cruza o limite superior, sinaliza avaliar a troca da classe 4 para a 3. O monitor não envia ordens.

## Consumo e atualização

- A brapi informa atraso aproximado de 30 minutos no plano gratuito e limite de um ticker por chamada.
- São seis chamadas por coleta (BBDC3, BBDC4, SAPR3, SAPR4, KLBN3 e KLBN4). Com 16 coletas por dia útil, isso representa cerca de 2.100 chamadas por mês, abaixo da cota gratuita informada pela brapi de 15.000 chamadas por ciclo mensal.\n- A fonte informa atraso aproximado de 30 minutos para cotações no plano gratuito; por isso, consultar a cada 30 minutos acompanha a recência oferecida, mas não produz cotações em tempo real.
- O agendamento do GitHub Actions não é garantido no minuto exato; pode atrasar.
- O monitor suspende o sinal de cada par se a cotação estiver velha ou se os horários dos dois papéis forem muito diferentes.
- Se um par falhar, os outros ainda podem ser atualizados; a falha fica registrada em `pair_status`.\n- O Telegram envia apenas alertas de cruzamento de limite, não uma mensagem a cada consulta. Os alertas abrangem os três pares.

## Configuração pelo iPhone

1. Entre em https://github.com/ pelo Safari e crie/acesse sua conta.
2. Use o repositório `bradesco-arbitragem-monitor`.
3. Em Settings → Secrets and variables → Actions, mantenha os secrets:
   - `BRAPI_TOKEN`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   Cole cada valor diretamente no GitHub. Não compartilhe os tokens comigo, nem em Issues, comentários ou prints.
4. Em Settings → Actions → General → Workflow permissions, selecione `Read and write permissions`.
5. Abra Actions → `BBDC3/BBDC4 monitor` → Run workflow para testar manualmente.
6. O Pages usa a pasta `/docs` da branch `main`.

## Arquivos

- `.github/workflows/monitor.yml`
- `monitor.py`
- `docs/index.html`
- `docs/data.json`

## Segurança e limitações

O repositório é público para permitir GitHub Pages gratuito, mas os tokens ficam em GitHub Actions Secrets, nunca no código ou no site. Não coloque informações pessoais no painel. Cotações atrasadas e diferenças de liquidez podem impedir uma execução real nos preços indicados. Confira spread, custos, impostos, proventos e datas-com antes de qualquer alternância.
