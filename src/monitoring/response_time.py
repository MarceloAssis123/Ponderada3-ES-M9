import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from .axiom_logger import AxiomLogger, AxiomIntegrationError, SeverityLevel

# Configuração de logging
logging.basicConfig(
    filename="chatbot_alerts.log",
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ResponseTime")

SLA_THRESHOLD = 5
VERSION = "1.0.0"

class ResponseTime:
    def __init__(self):
        """
        Inicializa o monitoramento de tempos de resposta e métricas.
        """
        self.metrics = {
            "chat": [],
            "voz": [],
            "email": []
        }
        self.axiom_logger = AxiomLogger()
        self._verify_integration()

    def _verify_integration(self) -> None:
        """
        Verifica a saúde da integração com Axiom durante a inicialização.
        """
        try:
            health_status = self.axiom_logger.health_check()
            if health_status["status"] == "healthy":
                logger.info(
                    f"Integração com Axiom OK (Latência: {health_status['latency']:.2f}s, "
                    f"Versão: {health_status['version']})"
                )
            else:
                logger.warning(
                    f"Integração com Axiom com problemas: {health_status.get('error', 'Erro desconhecido')}"
                )
        except Exception as e:
            logger.error(f"Erro ao verificar integração com Axiom: {str(e)}")

    def registrar_tempo(self, canal: str, tempo_resposta: float) -> None:
        """
        Registra o tempo de resposta para um canal específico e salva no arquivo JSON.
        
        Args:
            canal (str): Canal de atendimento (chat, voz, email)
            tempo_resposta (float): Tempo de resposta em segundos
        """
        start_time = time.time()
        
        try:
            if canal not in self.metrics:
                logger.warning(f"⚠️ Canal '{canal}' não reconhecido. Registrando como 'outro'.")
                canal = "outro"
                if "outro" not in self.metrics:
                    self.metrics["outro"] = []

            self.metrics[canal].append(tempo_resposta)
            self._salvar_dados(canal, tempo_resposta)
            self._verificar_sla(canal, tempo_resposta)

            processing_time = time.time() - start_time
            logger.info(f"Tempo de processamento: {processing_time:.2f}s")

        except Exception as e:
            logger.error(f"Erro ao registrar tempo: {str(e)}")
            raise

    def _salvar_dados(self, canal: str, tempo_resposta: float) -> None:
        """
        Armazena as métricas na Axiom e em um arquivo JSON para análises futuras.
        
        Args:
            canal (str): Canal de atendimento
            tempo_resposta (float): Tempo de resposta em segundos
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "canal": canal,
            "tempo_resposta": tempo_resposta,
            "acima_sla": tempo_resposta > SLA_THRESHOLD,
            "version": VERSION,
            "metricas_canal": self._calcular_metricas_canal(canal)
        }
        
        try:
            # Envia para Axiom
            self.axiom_logger.log_response_time(data)
        except AxiomIntegrationError as e:
            logger.error(f"Erro na integração com Axiom: {str(e)}")
            if e.severity == SeverityLevel.CRITICAL:
                # Notificação adicional para erros críticos
                self._notificar_erro_critico(e)
        
        # Mantém o arquivo local como backup
        try:
            with open("response_times.json", "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            logger.error(f"Erro ao salvar backup local: {str(e)}")

    def _verificar_sla(self, canal: str, tempo_resposta: float) -> None:
        """
        Verifica se o tempo de resposta ultrapassa o SLA único e gera um alerta.
        
        Args:
            canal (str): Canal de atendimento
            tempo_resposta (float): Tempo de resposta em segundos
        """
        if tempo_resposta > SLA_THRESHOLD:
            alert_msg = (
                f"⚠️ ALERTA: Tempo de resposta de {tempo_resposta:.2f}s no canal '{canal}', "
                f"acima do SLA de {SLA_THRESHOLD}s!"
            )
            logger.warning(alert_msg)
            print(alert_msg)

    def _calcular_metricas_canal(self, canal: str) -> Dict[str, Any]:
        """
        Calcula métricas específicas para um canal.
        
        Args:
            canal (str): Canal de atendimento
            
        Returns:
            Dict contendo métricas do canal
        """
        tempos = self.metrics.get(canal, [])
        if not tempos:
            return {
                "media": 0,
                "min": 0,
                "max": 0,
                "total_registros": 0,
                "violacoes_sla": 0
            }
        
        return {
            "media": sum(tempos) / len(tempos),
            "min": min(tempos),
            "max": max(tempos),
            "total_registros": len(tempos),
            "violacoes_sla": sum(1 for t in tempos if t > SLA_THRESHOLD)
        }

    def calcular_metricas(self) -> Dict[str, float]:
        """
        Retorna métricas do chatbot, incluindo tempo médio de resposta por canal.
        
        Returns:
            Dict contendo médias de tempo por canal
        """
        return {
            canal: round(sum(tempos) / len(tempos), 2) if tempos else 0
            for canal, tempos in self.metrics.items()
        }

    def _notificar_erro_critico(self, erro: AxiomIntegrationError) -> None:
        """
        Registra e notifica sobre erros críticos no sistema.
        
        Args:
            erro (AxiomIntegrationError): Erro ocorrido
        """
        msg = f"ERRO CRÍTICO NO SISTEMA DE MONITORAMENTO: {str(erro)}"
        logger.critical(msg)
        # Aqui poderia ser adicionada integração com sistema de notificação
        # como Slack, Email, etc.

