# Sistema de Monitoramento de Tempo de Resposta com Axiom

## Overview
Esta implementação atende ao **Requisito Não-Funcional 3 (RNF3)** do sistema: **"Implementar monitoramento de tempo de resposta do suporte, medindo SLAs e gerando alertas para desvios."**

O sistema de monitoramento de tempo de resposta é integrado ao chatbot e **não precisa ser executado separadamente**. Ele funciona automaticamente junto com o chatbot, registrando tempos de resposta e verificando a conformidade com o SLA estabelecido.

## Estrutura de Integração

### Camadas do Sistema
1. **Apresentação**
   - Interface CLI para alertas
   - Dashboards Axiom

2. **Aplicação**
   - Módulo ResponseTime
   - Módulo AxiomLogger

3. **Persistência**
   - Axiom Cloud (principal)
   - JSON local (backup)

4. **Infraestrutura**
   - Sistema de logging
   - Configuração (.env)

### Componentes Principais
1. **ResponseTime**
   - Gerenciamento de métricas
   - Validação de SLAs
   - Geração de alertas

2. **AxiomLogger**
   - Integração com Axiom
   - Circuit breaker
   - Fallback local

## Controle de Qualidade

### 1. Versionamento e Protocolos
- SDK Axiom: v0.3.0+
- API: v1
- Protocolo: HTTPS/TLS 1.2+
- Formato de dados: JSON estruturado

### 2. Métricas de Tempo
- Timeout de conexão: 5s
- Retry delay: Exponencial (1s, 2s, 4s, 8s)
- Máximo de retentativas: 3

### 3. Tratamento de Exceções
- Níveis de severidade (CRÍTICO, ERRO, AVISO, INFO)
- Circuit breaker automático
- Fallback para armazenamento local
- Rotação automática de logs

## Funcionalidades

### 1. **Monitoramento de Tempo de Resposta**
- Medição por canal de atendimento
- Métricas em tempo real
- Backup local redundante
- Rotação automática de arquivos

### 2. **Monitoramento de SLA**
- Threshold configurável
- Alertas automáticos
- Tracking de violações
- Dashboards em tempo real

### 3. **Análise de Métricas**
- Tempo médio por canal
- Mínimo/Máximo/Média
- Total de registros
- Violações de SLA

## Configuração

### Variáveis de Ambiente
Crie um arquivo `.env` baseado no `.env.example`:
```
AXIOM_TOKEN=seu_token_aqui
AXIOM_ORG_ID=seu_org_id_aqui
AXIOM_DATASET=chatbot-monitoring
```

### Dependências
Instale as dependências com:
```bash
pip install -r requirements.txt
```

## Arquivos Gerados
- **response_times.json**: Backup local principal
- **response_times_fallback_YYYYMMDD.json**: Fallback com rotação
- **chatbot_alerts.log**: Log de alertas de SLA
- **axiom_integration.log**: Log de integração

## Integração Axiom

### Recursos
- Monitoramento em tempo real
- Tracking de violações de SLA
- Dashboards analíticos
- Armazenamento de longo prazo

### Resiliência
- Circuit breaker automático
- Retry com backoff exponencial
- Fallback local em caso de falha
- Sincronização automática

### Monitoramento de Saúde
- Health checks periódicos
- Métricas de latência
- Taxa de sucesso
- Tempo de recuperação

## Testes
O sistema inclui testes automatizados para:
- Inicialização e configuração
- Registro de tempos
- Validação de SLA
- Integração com Axiom
- Fallback e recuperação
- Métricas e cálculos

Execute os testes com:
```bash
pytest test_response_time.py -v
```

