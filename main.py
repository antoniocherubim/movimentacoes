from projudi_tjpr.projudi_client import ProjudiClient
from eproc.eproc_client import EprocClient
import configparser
import logging
import os
import re
import sys
import datetime
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import traceback
from functools import wraps
import gc
import psutil
import weakref

EPROC_SC_BASE_URL = "https://eproc1g.tjsc.jus.br/eproc"
EPROC_RS_BASE_URL = "https://eproc1g.tjrs.jus.br/eproc"

# Configuração do timeout (em segundos)
REQUEST_TIMEOUT = 300  # 5 minutos
SAVE_INTERVAL = 10  # Salvar a cada 10 processos processados

class TimeoutError(Exception):
    pass

def timeout_handler(func, args, kwargs, result, error):
    try:
        result.append(func(*args, **kwargs))
    except Exception as e:
        error.append(e)

def with_timeout(timeout):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = []
            error = []
            
            # Cria uma thread para executar a função
            thread = threading.Thread(
                target=timeout_handler,
                args=(func, args, kwargs, result, error)
            )
            thread.daemon = True
            thread.start()
            
            # Espera pelo resultado ou timeout
            thread.join(timeout)
            
            if thread.is_alive():
                logging.error(f"Timeout na função {func.__name__} após {timeout} segundos")
                raise TimeoutError(f"A operação excedeu o tempo limite de {timeout} segundos")
            
            if error:
                raise error[0]
                
            return result[0]
        return wrapper
    return decorator

class MovimentacoesApp:
    def __init__(self):
        self._setup_logs()
        logging.info("Iniciando aplicação MovimentacoesApp")
        config = self._read_config()
        
        # Inicializa o Tkinter
        root = tk.Tk()
        root.withdraw()
        
        # Abre diálogo de seleção de arquivo
        logging.info("Abrindo diálogo para seleção de arquivo")
        self.planilha_dir = filedialog.askopenfilename(
            title="Selecione a planilha de processos",
            filetypes=[
                ("Arquivos Excel", "*.xlsx"),
                ("Todos os arquivos", "*.*")
            ],
            initialdir=os.path.expanduser("~/Downloads")
        )
        
        if not self.planilha_dir:
            logging.error("Nenhum arquivo foi selecionado")
            messagebox.showerror("Erro", "Nenhum arquivo foi selecionado!")
            sys.exit(1)
            
        if not os.path.exists(self.planilha_dir):
            logging.error(f"Arquivo não encontrado: {self.planilha_dir}")
            messagebox.showerror("Erro", f"O arquivo {self.planilha_dir} não existe!")
            sys.exit(1)

        logging.info("Inicializando clientes dos tribunais")
        self.projudi_client = ProjudiClient(
            username=config["projudi_username"],
            password=config["projudi_password"],
            token=config["projudi_token"],
        )

        self.eproc_rs_client = EprocClient(
            username=config["eproc_rs_user"],
            password=config["eproc_rs_senha"],
            base_url=EPROC_RS_BASE_URL,
            token=config["eproc_rs_token"],
            api_key=config["eproc_api_key_captcha_resolver"],
        )

        self.eproc_sc_client = EprocClient(
            username=config["eproc_sc_user"],
            password=config["eproc_sc_senha"],
            base_url=EPROC_SC_BASE_URL,
            token=config["eproc_sc_token"],
            api_key=config["eproc_api_key_captcha_resolver"],
        )
        logging.info("Clientes dos tribunais inicializados com sucesso")

        # Inicializa os nomes dos arquivos parciais
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.partial_mov_file = f"movimentacoes_parcial_{timestamp}.xlsx"
        self.partial_err_file = f"erros_parcial_{timestamp}.xlsx"
        
        # Inicializa contadores e listas
        self.todas_movimentacoes = []
        self.processos_com_erro = []
        self.ultimo_save = 0
        self.processados = 0

    def _setup_logs(self):
        logs_path = os.path.join(os.path.abspath(os.getcwd()), "logs")
        if not os.path.exists(logs_path):
            os.makedirs(logs_path)

        date = str(datetime.datetime.now()).split(".")[0]
        logfile = re.sub("[^0-9]", "", date)
        log_file = os.path.join(logs_path, f"{logfile}.log")
        
        logging.basicConfig(
            filename=log_file,
            filemode="a",
            format="%(asctime)s %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
            level=logging.INFO,
        )
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
        logging.info("Configuração de logs concluída")

    def _monitor_memory(self):
        """Monitora o uso de memória e força coleta de lixo se necessário"""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        if memory_percent > 80:
            logging.warning(f"Uso de memória alto: {memory_percent:.2f}%")
            gc.collect()
            
        return memory_percent

    def _save_partial_results(self, todas_movimentacoes, processos_com_erro):
        """Salva resultados parciais em arquivos Excel"""
        try:
            if todas_movimentacoes:
                df = pd.DataFrame(todas_movimentacoes)
                colunas = ['processo', 'BRADESCO'] + [col for col in df.columns if col not in ['processo', 'BRADESCO']]
                df = df[colunas]
                
                # Se o arquivo já existe, lê e concatena com os novos dados
                if os.path.exists(self.partial_mov_file):
                    df_existente = pd.read_excel(self.partial_mov_file)
                    df = pd.concat([df_existente, df], ignore_index=True)
                
                df.to_excel(self.partial_mov_file, index=False)
                logging.info(f"Arquivo parcial de movimentações atualizado: {self.partial_mov_file}")
                # Limpa a lista após salvar
                todas_movimentacoes.clear()

            if processos_com_erro:
                df_erros = pd.DataFrame(processos_com_erro, columns=['Processo', 'Erro'])
                
                # Se o arquivo já existe, lê e concatena com os novos dados
                if os.path.exists(self.partial_err_file):
                    df_erros_existente = pd.read_excel(self.partial_err_file)
                    df_erros = pd.concat([df_erros_existente, df_erros], ignore_index=True)
                
                df_erros.to_excel(self.partial_err_file, index=False)
                logging.info(f"Arquivo parcial de erros atualizado: {self.partial_err_file}")
                # Limpa a lista após salvar
                processos_com_erro.clear()
                
            # Força coleta de lixo após salvar
            gc.collect()
            
        except Exception as e:
            logging.error(f"Erro ao salvar resultados parciais: {str(e)}")
            logging.error(traceback.format_exc())

    @with_timeout(REQUEST_TIMEOUT)
    def _execute_with_timeout(self, client, num_processo):
        return client.execute(num_processo)

    def _read_config(self):
        config = configparser.ConfigParser()
        config.read("config.ini")

        return {
            "projudi_username": config["CREDENCIAIS.PROJUDI"]["usuario"],
            "projudi_password": config["CREDENCIAIS.PROJUDI"]["senha"],
            "projudi_token": config["CREDENCIAIS.PROJUDI"]["token_2fa"],
            "eproc_sc_user": config["CREDENCIAIS.EPROC_SC"]["usuario"],
            "eproc_sc_senha": config["CREDENCIAIS.EPROC_SC"]["senha"],
            "eproc_sc_token": config["CREDENCIAIS.EPROC_SC"]["token"],
            "eproc_rs_user": config["CREDENCIAIS.EPROC_RS"]["usuario"],
            "eproc_rs_senha": config["CREDENCIAIS.EPROC_RS"]["senha"],
            "eproc_rs_token": config["CREDENCIAIS.EPROC_RS"]["token"],
            "eproc_api_key_captcha_resolver": config["CONFIGURACOES"]["api_key_captcha_resolver"],
        }

    def _is_projudi(self, processo):
        processo = re.sub("[^0-9]", "", str(processo))
        return len(processo) == 20 and processo[13:16] == "816"

    def _is_eproc_rs(self, processo):
        processo = re.sub("[^0-9]", "", str(processo))
        return len(processo) == 20 and processo[13:16] == "821"

    def _is_eproc_sc(self, processo):
        processo = re.sub("[^0-9]", "", str(processo))
        return len(processo) == 20 and processo[13:16] == "824"

    def adjust_process_length(self, process):
        return re.sub("[^0-9]", "", str(process)).rjust(20, "0")

    def get_processos(self):
        df = pd.read_excel(self.planilha_dir)
        return df[["PROCESSO", "BRADESCO"]].values.tolist()

    def run(self):
        try:
            logging.info("Iniciando processamento dos processos")
            processos = self.get_processos()
            total_processos = len(processos)
            logging.info(f"Total de processos a serem processados: {total_processos}")
            
            # Inicializa contadores
            self.processados = 0
            self.ultimo_save = 0
            
            for idx, (processo, bradesco) in enumerate(processos, 1):
                try:
                    # Monitora memória a cada 10 processos
                    if idx % 10 == 0:
                        self._monitor_memory()
                        
                    num_processo = self.adjust_process_length(processo)
                    logging.info(f"Processando processo {idx}/{total_processos}: {num_processo}")

                    start_time = time.time()
                    movs = None

                    if self._is_projudi(num_processo):
                        logging.info(f"Processo {num_processo} identificado como Projudi")
                        movs = self._execute_with_timeout(self.projudi_client, num_processo)
                    elif self._is_eproc_sc(num_processo):
                        logging.info(f"Processo {num_processo} identificado como Eproc SC")
                        movs = self._execute_with_timeout(self.eproc_sc_client, num_processo)
                    elif self._is_eproc_rs(num_processo):
                        logging.info(f"Processo {num_processo} identificado como Eproc RS")
                        movs = self._execute_with_timeout(self.eproc_rs_client, num_processo)
                    else:
                        logging.warning(f"Processo {num_processo} não pertence a nenhum tribunal suportado")
                        self.processos_com_erro.append((num_processo, "Tribunal não suportado"))
                        continue

                    if movs:
                        for mov in movs:
                            mov['BRADESCO'] = bradesco
                        self.todas_movimentacoes.extend(movs)
                        logging.info(f"Processo {num_processo} processado com sucesso em {time.time() - start_time:.2f} segundos")
                    else:
                        logging.warning(f"Nenhuma movimentação encontrada para o processo {num_processo}")
                        self.processos_com_erro.append((num_processo, "Nenhuma movimentação encontrada"))

                except TimeoutError:
                    logging.error(f"Timeout ao processar processo {num_processo}")
                    self.processos_com_erro.append((num_processo, "Timeout"))
                except Exception as e:
                    logging.error(f"Erro ao processar processo {num_processo}: {str(e)}")
                    logging.error(traceback.format_exc())
                    self.processos_com_erro.append((num_processo, str(e)))

                # Salva resultados parciais a cada SAVE_INTERVAL processos
                if idx - self.ultimo_save >= SAVE_INTERVAL:
                    self._save_partial_results(self.todas_movimentacoes, self.processos_com_erro)
                    self.ultimo_save = idx
                    self.processados = idx
                    logging.info(f"Progresso: {idx}/{total_processos} processos processados")

            # Salva resultados finais
            self._save_partial_results(self.todas_movimentacoes, self.processos_com_erro)
            
            # Renomeia os arquivos parciais para finais
            final_mov_file = f"movimentacoes_final_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            final_err_file = f"erros_final_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            if os.path.exists(self.partial_mov_file):
                os.rename(self.partial_mov_file, final_mov_file)
                logging.info(f"Arquivo final de movimentações salvo como: {final_mov_file}")
            
            if os.path.exists(self.partial_err_file):
                os.rename(self.partial_err_file, final_err_file)
                logging.info(f"Arquivo final de erros salvo como: {final_err_file}")

            logging.info(f"Processamento concluído. Total de processos processados: {self.processados}/{total_processos}")

        except Exception as e:
            logging.error(f"Erro fatal durante a execução: {str(e)}")
            logging.error(traceback.format_exc())
            # Tenta salvar resultados parciais mesmo em caso de erro fatal
            self._save_partial_results(self.todas_movimentacoes, self.processos_com_erro)
            raise
        finally:
            # Limpa recursos
            self.todas_movimentacoes.clear()
            self.processos_com_erro.clear()
            gc.collect()

if __name__ == "__main__":
    app = MovimentacoesApp()
    try:
        app.run()
    except KeyboardInterrupt:
        logging.info("Processo interrompido pelo usuário")
        sys.exit(0)
    except Exception as error:
        logging.error(f"Erro fatal: {str(error)}")
        logging.error(traceback.format_exc())
        sys.exit(1) 
