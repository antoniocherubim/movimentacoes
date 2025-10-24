from bs4 import BeautifulSoup
import base64
from PIL import Image
import re
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

CAPTCHA_DIR = "."

class SalvarImagemCaptchaException(Exception):
    pass

class Liminares:
    def __init__(self, tipo_arquivo, titulo, endpoint):
        self.tipo_arquivo = tipo_arquivo
        self.titulo = titulo
        self.endpoint = endpoint

class HTMLParser:
    def requires_2fa(self, html: str) -> bool:
        return "Informe o código de 6 dígitos gerado" in html

    def requires_captcha(self, html: str) -> bool:
        bs = BeautifulSoup(html, features="html.parser")
        return bool(bs.find("div", attrs={"id": "divInfraCaptcha"})) or self.is_cloudflare_captcha(html)

    def is_cloudflare_captcha(self, html: str) -> bool:
        bs = BeautifulSoup(html, features="html.parser")
        return bool(bs.find("div", attrs={"id": "challenge-stage"})) or "cloudflare" in html.lower()

    def get_captcha_form(self, html: str) -> dict:
        if self.is_cloudflare_captcha(html):
            return {}
            
        bs = BeautifulSoup(html, features="html.parser")
        form = bs.find("form")
        return {i.get("id"): i.get("value", None) for i in form.find_all("input")}

    def get_endpoint_form_catpcha(self, html: str) -> str:
        bs = BeautifulSoup(html, features="html.parser")
        form = bs.find("form")
        return form.attrs["action"] if form else None

    def salva_imagem_captcha(self, html: str) -> str:
        try:
            if self.is_cloudflare_captcha(html):
                return None

            bs = BeautifulSoup(html, features="html.parser")
            div_captcha = bs.find("div", attrs={"id": "divInfraCaptcha"})
            
            if div_captcha:
                label = div_captcha.find("label")
                
                if label:
                    img = label.find("img")
                    
                    if img and "src" in img.attrs:
                        image_text = img.attrs["src"]
                        
                        filename = os.path.join(CAPTCHA_DIR, "image.png")
                        new_filename = os.path.join(CAPTCHA_DIR, "new_image.jpg")
                        
                        with open(filename, "wb") as arq:
                            if "data:image" in image_text:
                                image_text = image_text.split(",")[1]
                            arq.write(base64.b64decode(image_text))
                        
                        im = Image.open(filename)
                        rgb_im = im.convert("RGB")
                        rgb_im.save(new_filename)
                        return new_filename
                    else:
                        logger.error("[DEBUG] Atributo 'src' não encontrado na imagem")
                else:
                    logger.error("[DEBUG] Tag 'label' não encontrada dentro da div do captcha")
            else:
                logger.error("[DEBUG] Div do captcha não encontrada no HTML")
                
            raise SalvarImagemCaptchaException("Não foi possível encontrar a imagem do captcha no HTML")
        except Exception as e:
            logger.error(f"[DEBUG] Erro ao salvar imagem do captcha: {str(e)}")
            raise SalvarImagemCaptchaException(str(e))

    def get_id_usuario(self, html: str, username: str) -> str:
        if "usuário logado como" in html.lower():
            return None
        else:
            bs = BeautifulSoup(html, features="html.parser")
            button = bs.find("button", attrs={"data-descricao": f"{username} / ADVOGADO"})
            return re.findall("[0-9]+", button.attrs["onclick"])[0]
    
    def get_menu_links(self, html: str) -> dict:
        """retorna todos os links do menu lateral após logado"""
        bs = BeautifulSoup(html, features="html.parser")
        ul = bs.find("ul")

        links = {}
        for anchor in ul.find_all("a"):
            links[anchor.find("span").text] = anchor.attrs["href"]
        return links

    def get_2fa_form(self, html: str) -> dict:
        bs = BeautifulSoup(html, features="html.parser")
        form = bs.find("form")
        return {i.get("id"): i.get("value", None) for i in form.find_all("input")}

    def get_endpoint_consulta_processo(self, html: str) -> str:
        """busca pelo endpoint da consulta de processo no formulario da consulta processual"""
        endpoint = re.findall(
            r"controlador_ajax.php\?acao_ajax=processos_consulta_por_numprocesso&hash=[a-z0-9]+",
            html,
        )[0]
        return endpoint

    def processo_nao_encontrado(self, html: str) -> bool:
        return "Processo não encontrado" in html

    def get_endpoint_processo_consultado(self, html: str) -> str:
        return json.loads(html)["resultados"][0]["linkProcessoAssinado"]

    def precisa_acessar_integra_do_processo(self, html: str) -> bool:
        return "Acesso íntegra do processo" in html

    def get_endpoint_integra_processo(self, html: str) -> str:
        return re.findall(
            r"controlador.php\?acao=processo_vista_sem_procuracao&txtNumProcesso=[0-9a-z]+&hash=[0-9a-z]+",
            html,
        )[0]
    
    def validate_integra_access(self, html: str) -> bool:
        """verifica se o acesso à íntegra foi liberado após resolver o captcha"""
        return "ACESSO LIBERADO" in html.upper()
    
    def validate_captcha_response(self, html: str) -> bool:
        return "ACESSO LIBERADO" in html.upper()
    
    def get_dados_das_liminares(self, html: str) -> list[Liminares]:
        bs = BeautifulSoup(html, features="html.parser")
        tr = bs.find("tr", attrs={"id": "trEvento1"})
        liminares = []
        for anchor in tr.find_all("a"):
            liminares.append(
                Liminares(
                    tipo_arquivo=anchor.attrs["data-mimetype"],
                    titulo=anchor.attrs["title"],
                    endpoint=anchor.attrs["href"],
                )
            )
        return liminares

    def get_endpoint_arquivo(self, html: str) -> str:
        bs = BeautifulSoup(html, features="html.parser")
        return bs.find("iframe").attrs["src"]

    def get_movimentacoes(self, html: str) -> list:
        soup = BeautifulSoup(html, 'html.parser')
        num_processo = (
            soup.find("span", id="txtNumProcesso").get_text(strip=True)
            if soup.find("span", id="txtNumProcesso")
            else None
        )
        
        tabela = soup.find('table', {'id': 'tblEventos'})
        movimentacoes = []
        palavras_chave = ["TRANSITADO EM JULGADO", "TRANSITO", "BAIXA", "DEFINITIVAMENTE", "SENTENÇA", "JULGAD", "DESISTÊNCIA", "HOMOL"]
        
        if tabela:
            linhas = tabela.find_all('tr')
            for linha in linhas[1:]: 
                colunas = linha.find_all('td')
                if len(colunas) >= 5:
                    evento = colunas[0].get_text(strip=True)
                    data_hora = colunas[1].get_text(strip=True)
                    data_obj = datetime.strptime(data_hora, "%d/%m/%Y %H:%M:%S")
                    data_formatada = data_obj.strftime("%d-%m-%Y")
                    descricao = colunas[2].get_text(strip=True)
                    elemento_info_user = colunas[3].find('span', class_='sr-only')
                    if elemento_info_user:
                        info_user = elemento_info_user.get_text(separator='\n').split('\n')
                    else:
                        label = colunas[3].find('label', class_='infraEventoUsuario')
                        if label and 'onmouseover' in label.attrs:
                            texto = label['onmouseover']
                            match = re.search(r"carregarInfoUsuarioOutroGrau\('(.+?)'\)", texto)
                            info_user = match.group(1).split('<br/>') if match else None
                        else:
                            texto = None
                    if info_user:
                        usuario = info_user[0]
                        tipo = info_user[1] if len(info_user) >= 2 else ""
                    else:
                        usuario = ""
                        tipo = ""

                    #FILTRO AQUI
                    movimentacao = {
                        'processo': self.__format_processo(num_processo),
                        'evento': evento,
                        'data': data_formatada,
                        'descricao': descricao,
                        'usuario': usuario,
                        'tipo': tipo,
                    }
                    movimentacoes.append(movimentacao)
            if movimentacoes == []:
                movimentacao = {
                    'processo': self.__format_processo(num_processo),
                    'evento': '',
                    'data': '',
                    'descricao': '',
                    'usuario': '',
                    'tipo': '',
                    'ARQUIVOS': "Nenhuma movimentação correspondeu aos parâmetros de busca."
                }
                movimentacoes.append(movimentacao)
            
            return movimentacoes


    def get_endpoint_download_arquivo(self, html: str) -> str:
        """
        Extrai o endpoint para download do arquivo a partir do HTML.
        Primeiro tenta extrair pelos inputs, depois busca no JavaScript.
        Se falhar, tenta encontrar dentro de um iframe.
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Tenta encontrar os parâmetros nos inputs do HTML
            params = {}
            for param in ['doc', 'evento', 'key', 'nome_documento', 'hash']:
                value = soup.find('input', {'name': param})
                if value:
                    params[param] = value.get('value', '')

            if params:
                endpoint_download = (
                    f"controlador.php?acao=acessar_documento_implementacao"
                    f"&acao_origem=acessar_documento"
                    f"&doc={params.get('doc', '')}"
                    f"&evento={params.get('evento', '')}"
                    f"&key={params.get('key', '')}"
                    f"&mesmoGrau=S"
                    f"&nome_documento={params.get('nome_documento', '')}"
                    f"&termosPesquisados="
                    f"&hash={params.get('hash', '')}"
                )
                return endpoint_download

            # Se não encontrar diretamente, busca dentro do JavaScript
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    match = re.search(r'controlador\.php\?acao=acessar_documento_implementacao[^"\']+', script.string)
                    if match:
                        return match.group(0)  # Retorna a URL encontrada

            # Se não encontrou nos inputs nem no JavaScript, tenta no iframe
            return self.get_endpoint_arquivo(html)

        except Exception as e:
            logger.warning(f"Erro ao tentar nova abordagem de download: {str(e)}")
            return self.get_endpoint_arquivo(html)

    def __format_processo(self, nbr: str) -> str:
        nbr = re.sub("[^0-9]", "", nbr)
        nbr = nbr.rjust(20, "0")
        regex = re.compile(
            r"([0-9]{7})([0-9]{2})([0-9]{4})([0-9]{1})([0-9]{2})([0-9]{4})"
        )
        groups = regex.search(nbr)
        return f"{groups.group(1)}-{groups.group(2)}.{groups.group(3)}.{groups.group(4)}.{groups.group(5)}.{groups.group(6)}"

    def get_cloudflare_captcha_data(self, html: str):
        bs = BeautifulSoup(html, features="html.parser")
        turnstile_div = bs.find('div', {'class': 'cf-turnstile'})
        if not turnstile_div:
            raise SalvarImagemCaptchaException("Não foi possível encontrar o elemento do Turnstile")
        sitekey = turnstile_div.get('data-sitekey')
        if not sitekey:
            raise SalvarImagemCaptchaException("Não foi possível encontrar o sitekey do Turnstile")
        return sitekey
