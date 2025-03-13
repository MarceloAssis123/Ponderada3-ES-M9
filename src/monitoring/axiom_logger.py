import os
import time
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
from axiom.client import Client
from dotenv import load_dotenv

# Configuração de logging
logging.basicConfig(
    filename="axiom_integration.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AxiomLogger")

class SeverityLevel(Enum):
    CRITICAL = "CRÍTICO"
    ERROR = "ERRO"
    WARNING = "AVISO"
    INFO = "INFO"

class AxiomIntegrationError(Exception):
    """Exceção base para erros de integração com Axiom."""
    def __init__(self, message: str, severity: SeverityLevel):
        self.severity = severity
        super().__init__(f"{severity.value}: {message}")

class AxiomConnectionError(AxiomIntegrationError):
    """Erro de conexão com Axiom."""
    def __init__(self, message: str):
        super().__init__(message, SeverityLevel.ERROR)

class AxiomLogger:
    VERSION = "1.0.0"
    API_VERSION = "v1"
    PROTOCOL_VERSION = "TLS 1.2"
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # segundos
    CONNECTION_TIMEOUT = 5  # segundos

    def __init__(self):
        """
        Inicializa o logger da Axiom usando credenciais do ambiente.
        Implementa circuit breaker e retry com backoff exponencial.
        """
        load_dotenv()
        self.client = Client(
            token=os.getenv('AXIOM_TOKEN'),
            org_id=os.getenv('AXIOM_ORG_ID')
        )
        self.dataset = os.getenv('AXIOM_DATASET', 'chatbot-monitoring')
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure = None
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60  # segundos
        logger.info(f"AxiomLogger inicializado (v{self.VERSION}, API {self.API_VERSION})")

    def _check_circuit_breaker(self) -> bool:
        """
        Verifica se o circuit breaker permite novas tentativas.
        """
        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            if self.circuit_breaker_last_failure:
                time_since_last_failure = time.time() - self.circuit_breaker_last_failure
                if time_since_last_failure < self.circuit_breaker_timeout:
                    logger.warning("Circuit breaker aberto, usando fallback local")
                    return False
                self.circuit_breaker_failures = 0
        return True

    def _exponential_backoff(self, attempt: int) -> None:
        """
        Implementa delay exponencial entre tentativas.
        """
        delay = self.INITIAL_RETRY_DELAY * (2 ** attempt)
        time.sleep(delay)

    def log_response_time(self, data: Dict[str, Any]) -> bool:
        """
        Envia os dados de tempo de resposta para a Axiom com retry e circuit breaker.
        
        Args:
            data (dict): Dicionário contendo os dados a serem enviados
            
        Returns:
            bool: True se o envio foi bem-sucedido, False caso contrário
        """
        if not self._check_circuit_breaker():
            self._save_to_file(data)
            return False

        start_time = time.time()
        data["_metadata"] = {
            "version": self.VERSION,
            "api_version": self.API_VERSION,
            "protocol": self.PROTOCOL_VERSION,
            "timestamp": datetime.now().isoformat()
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                self.client.ingest(self.dataset, [data])
                latency = time.time() - start_time
                logger.info(f"Dados enviados com sucesso. Latência: {latency:.2f}s")
                self.circuit_breaker_failures = 0
                return True
            except Exception as e:
                self.circuit_breaker_failures += 1
                self.circuit_breaker_last_failure = time.time()
                logger.error(f"Tentativa {attempt + 1}/{self.MAX_RETRIES} falhou: {str(e)}")
                
                if attempt < self.MAX_RETRIES - 1:
                    self._exponential_backoff(attempt)
                else:
                    logger.error("Todas as tentativas falharam, usando fallback local")
                    self._save_to_file(data)
                    raise AxiomConnectionError(f"Falha ao enviar dados após {self.MAX_RETRIES} tentativas")
        
        return False

    def _save_to_file(self, data: Dict[str, Any]) -> None:
        """
        Salva os dados em um arquivo local como fallback.
        Implementa rotação automática de arquivos.
        
        Args:
            data (dict): Dicionário contendo os dados a serem salvos
        """
        try:
            current_date = datetime.now().strftime("%Y%m%d")
            fallback_file = f"response_times_fallback_{current_date}.json"
            
            data["_fallback_metadata"] = {
                "saved_at": datetime.now().isoformat(),
                "reason": "axiom_connection_failure"
            }
            
            with open(fallback_file, "a") as f:
                f.write(json.dumps(data) + "\n")
            
            logger.info(f"Dados salvos com sucesso no arquivo de fallback: {fallback_file}")
            
            # Limpa arquivos antigos (mantém últimos 7 dias)
            self._cleanup_old_fallback_files()
        except Exception as e:
            logger.critical(f"Erro ao salvar no arquivo de fallback: {str(e)}")
            raise AxiomIntegrationError("Falha no sistema de fallback", SeverityLevel.CRITICAL)

    def _cleanup_old_fallback_files(self, days_to_keep: int = 7) -> None:
        """
        Remove arquivos de fallback mais antigos que o número especificado de dias.
        """
        try:
            current_time = time.time()
            for file in os.listdir():
                if file.startswith("response_times_fallback_") and file.endswith(".json"):
                    file_time = os.path.getmtime(file)
                    if (current_time - file_time) > (days_to_keep * 24 * 60 * 60):
                        os.remove(file)
                        logger.info(f"Arquivo antigo removido: {file}")
        except Exception as e:
            logger.error(f"Erro ao limpar arquivos antigos: {str(e)}")

    def health_check(self) -> Dict[str, Any]:
        """
        Realiza verificação de saúde da integração.
        
        Returns:
            Dict contendo status e métricas da integração
        """
        try:
            start_time = time.time()
            self.client.ingest(self.dataset, [{"health_check": True}])
            latency = time.time() - start_time
            
            return {
                "status": "healthy",
                "latency": latency,
                "circuit_breaker_failures": self.circuit_breaker_failures,
                "version": self.VERSION,
                "api_version": self.API_VERSION,
                "protocol": self.PROTOCOL_VERSION
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "circuit_breaker_failures": self.circuit_breaker_failures,
                "version": self.VERSION,
                "api_version": self.API_VERSION,
                "protocol": self.PROTOCOL_VERSION
            } 