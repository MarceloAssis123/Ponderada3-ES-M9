import json
import logging
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from response_time import ResponseTime, SLA_THRESHOLD, VERSION
from axiom_logger import AxiomIntegrationError, SeverityLevel

# Dummy para simular o open() sem escrever em disco.
class DummyFile:
    def __init__(self):
        self.content = ""
    def write(self, data):
        self.content += data
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        pass

# Fixture que substitui o open() pelo dummy.
@pytest.fixture
def dummy_open(monkeypatch):
    dummy_file = DummyFile()
    def fake_open(*args, **kwargs):
        return dummy_file
    monkeypatch.setattr("builtins.open", fake_open)
    return dummy_file

# Fixture para mock do AxiomLogger
@pytest.fixture
def mock_axiom_logger(monkeypatch):
    mock_logger = Mock()
    mock_logger.health_check.return_value = {
        "status": "healthy",
        "latency": 0.1,
        "version": VERSION,
        "api_version": "v1",
        "protocol": "TLS 1.2"
    }
    def fake_init(self):
        self.axiom_logger = mock_logger
        self.metrics = {"chat": [], "voz": [], "email": []}
    monkeypatch.setattr(ResponseTime, "__init__", fake_init)
    return mock_logger

# Testa a inicialização, garantindo que os canais corretos estejam na métrica.
def test_inicializacao(mock_axiom_logger):
    rt = ResponseTime()
    assert rt.metrics == {"chat": [], "voz": [], "email": []}
    mock_axiom_logger.health_check.assert_called_once()

# Testa verificação de saúde da integração
def test_verify_integration_healthy(mock_axiom_logger, caplog):
    rt = ResponseTime()
    assert any("Integração com Axiom OK" in record.message for record in caplog.records)

def test_verify_integration_unhealthy(mock_axiom_logger, caplog):
    mock_axiom_logger.health_check.return_value = {
        "status": "unhealthy",
        "error": "Conexão falhou"
    }
    rt = ResponseTime()
    assert any("Integração com Axiom com problemas" in record.message for record in caplog.records)

# Testa o registro de tempo para um canal conhecido (ex.: "chat")
def test_registrar_tempo_canal_conhecido(dummy_open, mock_axiom_logger, capsys):
    rt = ResponseTime()
    rt.registrar_tempo("chat", 3.2)
    
    # Verifica se o tempo foi adicionado corretamente
    assert rt.metrics["chat"] == [3.2]
    
    # Verifica se os dados foram salvos em formato JSON
    linhas = dummy_open.content.strip().split("\n")
    assert len(linhas) == 1
    dados = json.loads(linhas[0])
    assert dados["canal"] == "chat"
    assert dados["tempo_resposta"] == 3.2
    assert dados["acima_sla"] == False
    assert dados["version"] == VERSION
    assert "metricas_canal" in dados

    # Verifica se os dados foram enviados para Axiom
    mock_axiom_logger.log_response_time.assert_called_once()
    axiom_data = mock_axiom_logger.log_response_time.call_args[0][0]
    assert axiom_data["canal"] == "chat"
    assert axiom_data["tempo_resposta"] == 3.2
    assert axiom_data["acima_sla"] == False
    assert axiom_data["version"] == VERSION

    # Como o tempo está abaixo do SLA, nenhuma mensagem de alerta deve ser impressa
    saida = capsys.readouterr().out
    assert "ALERTA" not in saida

# Testa o fluxo quando o tempo de resposta ultrapassa o SLA
def test_registrar_tempo_acima_sla(dummy_open, mock_axiom_logger, capsys, caplog):
    rt = ResponseTime()
    tempo = SLA_THRESHOLD + 1  # acima do limite
    rt.registrar_tempo("chat", tempo)
    
    # Verifica se o tempo foi adicionado
    assert rt.metrics["chat"] == [tempo]
    
    # Verifica a escrita dos dados no "arquivo"
    linhas = dummy_open.content.strip().split("\n")
    dados = json.loads(linhas[-1])
    assert dados["canal"] == "chat"
    assert dados["tempo_resposta"] == tempo
    assert dados["acima_sla"] == True
    assert dados["version"] == VERSION

    # Verifica se os dados foram enviados para Axiom
    mock_axiom_logger.log_response_time.assert_called_once()
    axiom_data = mock_axiom_logger.log_response_time.call_args[0][0]
    assert axiom_data["canal"] == "chat"
    assert axiom_data["tempo_resposta"] == tempo
    assert axiom_data["acima_sla"] == True
    assert axiom_data["version"] == VERSION

    # Captura a saída impressa e verifica a mensagem de alerta
    saida = capsys.readouterr().out
    assert "ALERTA" in saida

    # Verifica se o alerta foi registrado no log
    assert any("ALERTA" in record.message for record in caplog.records)

# Testa o comportamento para um canal desconhecido quando a chave "outro" não existe
def test_registrar_tempo_canal_desconhecido_erro(dummy_open, mock_axiom_logger, capsys):
    rt = ResponseTime()
    with pytest.raises(KeyError):
        rt.registrar_tempo("sms", 4.0)
    
    # Verifica se foi impressa a mensagem de aviso para canal desconhecido
    saida = capsys.readouterr().out
    assert "Canal 'sms' não reconhecido" in saida

# Testa o registro para canal desconhecido, mas com a chave "outro" previamente adicionada
def test_registrar_tempo_canal_desconhecido_corrigido(dummy_open, mock_axiom_logger, capsys):
    rt = ResponseTime()
    # Adiciona o canal "outro" para tratar os casos de canais não reconhecidos
    rt.metrics["outro"] = []
    rt.registrar_tempo("sms", 4.0)
    
    # Verifica se o tempo foi registrado em "outro"
    assert rt.metrics["outro"] == [4.0]
    
    # Verifica se os dados foram enviados para Axiom
    mock_axiom_logger.log_response_time.assert_called_once()
    axiom_data = mock_axiom_logger.log_response_time.call_args[0][0]
    assert axiom_data["canal"] == "outro"
    assert axiom_data["tempo_resposta"] == 4.0
    assert axiom_data["version"] == VERSION
    
    saida = capsys.readouterr().out
    assert "Canal 'sms' não reconhecido" in saida

# Testa o cálculo das métricas (média dos tempos de resposta)
def test_calcular_metricas(mock_axiom_logger):
    rt = ResponseTime()
    rt.metrics["chat"] = [2, 4, 6]
    rt.metrics["voz"] = [5, 7]
    rt.metrics["email"] = []  # Sem registros deve retornar 0
    
    metricas = rt.calcular_metricas()
    assert metricas["chat"] == 4.0   # (2+4+6)/3
    assert metricas["voz"] == 6.0    # (5+7)/2
    assert metricas["email"] == 0

# Testa o cálculo de métricas específicas do canal
def test_calcular_metricas_canal(mock_axiom_logger):
    rt = ResponseTime()
    rt.metrics["chat"] = [2, 4, 6, 8]  # 8 > SLA_THRESHOLD
    
    metricas = rt._calcular_metricas_canal("chat")
    assert metricas["media"] == 5.0
    assert metricas["min"] == 2
    assert metricas["max"] == 8
    assert metricas["total_registros"] == 4
    assert metricas["violacoes_sla"] == 1

# Testa o tratamento de erros críticos
def test_tratamento_erro_critico(mock_axiom_logger, caplog):
    rt = ResponseTime()
    mock_axiom_logger.log_response_time.side_effect = AxiomIntegrationError(
        "Erro crítico de teste",
        SeverityLevel.CRITICAL
    )
    
    rt.registrar_tempo("chat", 3.0)
    
    # Verifica se o erro crítico foi registrado
    assert any("ERRO CRÍTICO" in record.message for record in caplog.records)

# Testa falha no backup local
def test_falha_backup_local(mock_axiom_logger, monkeypatch, caplog):
    rt = ResponseTime()
    
    def fake_open(*args, **kwargs):
        raise IOError("Erro ao abrir arquivo")
    
    monkeypatch.setattr("builtins.open", fake_open)
    rt.registrar_tempo("chat", 3.0)
    
    # Verifica se o erro foi registrado
    assert any("Erro ao salvar backup local" in record.message for record in caplog.records)
