from .html_parser import HTMLParser, SalvarImagemCaptchaException
from .client import Client
from twocaptcha import TwoCaptcha
import logging
import requests
import onetimepass as otp
import os

logger = logging.getLogger()

TENTATIVAS_RESOLUCAO_CAPTCHA = 5
MEDIA_DIR = "MEDIA"

# Cria o diretório MEDIA se não existir
os.makedirs(MEDIA_DIR, exist_ok=True)

class ResolucaoCaptchaException(Exception):
    pass

class ProcessoNaoEncontradoException(Exception):
    pass

class EprocClient:
    def __init__(self, username: str, password: str, base_url: str, api_key: str, token: str) -> None:
        self.username = username
        self.password = password
        self.base_url = base_url
        self.api_key = api_key
        self.token = token
        self.html_parser = HTMLParser()
        self.captcha = TwoCaptcha(api_key)
        self.client = Client(base_url)

    def __get_text_from_catpcha_image(self, image_filename: str) -> str:
        try:
            result = self.captcha.normal(image_filename)
            return result["code"]
        except Exception as e:
            logger.error("Erro ao resolver captcha: %s", e)
            raise ResolucaoCaptchaException(f"{e}")

    def __resolve_captcha_cloudflare(self, html: str) -> requests.Response:
        logger.info("Detectado captcha da Cloudflare (Standalone). Iniciando resolução...")    

        sitekey = self.html_parser.get_cloudflare_captcha_data(html)
        if not sitekey:
            raise ResolucaoCaptchaException("Não foi possível encontrar o sitekey do Turnstile")

        for attempt in range(1, TENTATIVAS_RESOLUCAO_CAPTCHA + 1):
            try:
                logger.info(f"Tentativa {attempt} de {TENTATIVAS_RESOLUCAO_CAPTCHA} para resolver o captcha.")

                result = self.captcha.turnstile(
                    sitekey=sitekey,
                    url=self.base_url
                )

                data = self.html_parser.get_captcha_form(html)
                data["cf-turnstile-response"] = result['code']

                endpoint = self.html_parser.get_endpoint_form_catpcha(html)
                r = self.client.resolve_catpcha(data, endpoint)

                if self.html_parser.validate_captcha_response(r.text):
                    logger.info("Captcha resolvido com sucesso.")
                    return r 

                logger.warning(f"Falha na validação do captcha (tentativa {attempt}/{TENTATIVAS_RESOLUCAO_CAPTCHA}).")

            except ResolucaoCaptchaException as e:
                logger.warning(f"Tentativa {attempt} falhou: {str(e)}")

        raise ResolucaoCaptchaException("Todas as tentativas para resolver o captcha falharam.")

    def __resolve_captcha_infra(self, html: str) -> requests.Response:
        tentativas = 1
        while self.html_parser.requires_captcha(html) and tentativas < TENTATIVAS_RESOLUCAO_CAPTCHA:
            data = self.html_parser.get_captcha_form(html)
            filename = self.html_parser.salva_imagem_captcha(html)
            result = self.__get_text_from_catpcha_image(filename)
            data["txtInfraCaptcha"] = result
            endpoint = self.html_parser.get_endpoint_form_catpcha(html)
            r = self.client.resolve_catpcha(data, endpoint)
            tentativas += 1
            html = r.text
        if tentativas == TENTATIVAS_RESOLUCAO_CAPTCHA:
            raise ResolucaoCaptchaException("Erro ao resolver o captcha. Excedido o num max de tentativas")
        return r

    def login(self) -> requests.Response:
        logger.info("Iniciando login para o usuário: %s", self.username)
        r = self.client.login(self.username, self.password)
        while self.html_parser.requires_captcha(r.text) or self.html_parser.requires_2fa(r.text):
            if self.html_parser.requires_captcha(r.text):
                logger.info("Captcha detectado. Iniciando tentativa de resolução.")
                if self.html_parser.is_cloudflare_captcha(r.text):
                    r = self.__resolve_captcha_cloudflare(r.text)
                else:
                    r = self.__resolve_captcha_infra(r.text)
            if self.html_parser.requires_2fa(r.text):
                logger.info("2FA requerido. Iniciando validação.")
                r = self.__resolve_2fa(r.text)
        id_usuario = self.html_parser.get_id_usuario(r.text, self.username)
        if id_usuario:
            r = self.client.acessa_perfil(id_usuario)
            self.links = self.html_parser.get_menu_links(r.text)
            logger.info("Login concluído com sucesso para o usuário: %s", self.username)
            return r
        else:
            return r

    def consulta_processo(self, nprocesso: str) -> requests.Response:
        logger.info(f"[EPROC] Consultando processo {nprocesso}...")
        consulta_processual = "Consultar Processos"
        url_consulta_processual = f"{self.base_url}/{self.links[consulta_processual]}"
        r = self.client.acessa_link(url_consulta_processual)
        r = self.client.consulta_processo(self.html_parser.get_endpoint_consulta_processo(r.text), nprocesso)
        if self.html_parser.processo_nao_encontrado(r.text):
            raise ProcessoNaoEncontradoException(f"Processo {nprocesso} não encontrado")
        endpoint = self.html_parser.get_endpoint_processo_consultado(r.text)
        r = self.client.acessa_endpoint(endpoint)
        if self.html_parser.precisa_acessar_integra_do_processo(r.text):
            endpoint = self.html_parser.get_endpoint_integra_processo(r.text)
            r = self.client.acessa_endpoint(endpoint)
            if self.html_parser.requires_2fa(r.text):
                r = self.__resolve_2fa(r.text)
            if self.html_parser.requires_captcha(r.text):
                if self.html_parser.is_cloudflare_captcha(r.text):
                    r = self.__resolve_captcha_cloudflare(r.text)
                else:
                    r = self.__resolve_captcha_infra(r.text)
        return r

    def baixar_arquivos(self, r: requests.Response, movimentacoes: list) -> list:
        for movimentacao in movimentacoes:
            if movimentacao.get('liminares'):
                for liminar in movimentacao['liminares']:
                    if liminar.tipo_arquivo != "Nenhum arquivo disponível":
                        try:
                            # Primeiro acessa o endpoint da liminar
                            r = self.client.acessa_endpoint(liminar.endpoint)
                            
                            # Obtém o endpoint de download do arquivo
                            endpoint_download = self.html_parser.get_endpoint_download_arquivo(r.text)
                            
                            # Faz o download do arquivo
                            r = self.client.acessa_endpoint(endpoint_download)
                            
                            # Salva o arquivo
                            filename = f"{movimentacao['processo']} - {movimentacao['descricao']} - {movimentacao['data']}.{liminar.tipo_arquivo}"
                            filepath = os.path.join(MEDIA_DIR, filename)
                            with open(filepath, "wb") as arq:
                                arq.write(r.content)
                            
                            # Atualiza o nome do arquivo na movimentação
                            movimentacao['ARQUIVOS'] = filename
                        except Exception as e:
                            logger.error(f"Erro ao baixar arquivo: {str(e)}")
                            movimentacao['ARQUIVOS'] = "Erro ao baixar arquivo"
                    else:
                        movimentacao['ARQUIVOS'] = "Nenhum arquivo disponível"
            else:
                movimentacao['ARQUIVOS'] = "Nenhum arquivo disponível"
        return movimentacoes

    def execute(self, nprocesso: str):
        try:
            r = self.login()
            r = self.consulta_processo(nprocesso)
            movimentacoes = self.html_parser.get_movimentacoes(r.text)
            if "Nenhuma movimentação" in movimentacoes:
                return movimentacoes
            #movimentacoes = self.baixar_arquivos(r, movimentacoes)
            return movimentacoes

        except ProcessoNaoEncontradoException as e:
            logger.info(f"[EPROC] {str(e)}")
            return []
        except Exception as e:
            logger.error(f"[EPROC] Erro ao consultar processo {nprocesso}")
            logger.exception(e)
            return []

    def __resolve_2fa(self, html: str) -> requests.Response:
        data = self.html_parser.get_2fa_form(html)
        secret_code = otp.get_totp(self.token)
        data["txtAcessoCodigo"] = secret_code
        return self.client.resolve_2fa(data)
    

    
    