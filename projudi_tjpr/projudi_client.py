from .robo.projudi_data import ProjudiData
import logging
import time
import os
import re

MEDIA_DIR = "MEDIA"

# Cria o diretório MEDIA se não existir
os.makedirs(MEDIA_DIR, exist_ok=True)

class ProjudiClient:
    def __init__(self, username: str, password: str, token: str) -> None:
        max_retries = 5
        retry_delay = 30
        
        for attempt in range(max_retries):
            try:
                self.projudi_data = ProjudiData(user=username, pwd=password, token=token)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.getLogger().error(f"[PROJUDI] Falha ao efetuar login após {max_retries} tentativas")
                    raise Exception("Falha ao efetuar login")
                
                logging.getLogger().warning(f"[PROJUDI] Tentativa {attempt + 1} de login falhou. Aguardando {retry_delay} segundos...")
                time.sleep(retry_delay)

    def execute(self, nprocesso: str):
        try:
            if self.projudi_data.open_process(nprocesso):
                movimentacoes = self.projudi_data.extract_tabela_movimentacoes(nprocesso)
                return movimentacoes
            return []
        except Exception as e:
            logging.getLogger().error(
                f"[PROJUDI] Ocorreu um erro ao buscar movimentações do processo: {nprocesso}"
            )
            logging.getLogger().exception(e)
            return []

        