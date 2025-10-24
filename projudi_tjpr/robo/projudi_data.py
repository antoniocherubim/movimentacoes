from bs4 import BeautifulSoup
import re
from datetime import datetime
from robobrowser import RoboBrowser
from .projudi_session import make_session
import os

MEDIA_DIR = "MEDIA"

# Cria o diretório MEDIA se não existir
os.makedirs(MEDIA_DIR, exist_ok=True)

class ProjudiData:
    def __init__(self, user: str, pwd: str, token: str) -> None:
        self.BASE_URL = "https://projudi.tjpr.jus.br"
        self.URL_PESQUISA = f"{self.BASE_URL}/projudi/processo/buscaProcessosQualquerInstancia.do?actionType=pesquisar"
        self.session = make_session(user, pwd, token)
        self.browser = RoboBrowser(session=self.session, parser="html.parser")

    def _open_home(self) -> bool:
        self.browser.open(url=f"{self.BASE_URL}/projudi/home.do")
        lis = self.browser.find_all("li", {"class": "externo"})

        for li in lis:
            html = BeautifulSoup(str(li), "html.parser")
            link = html.select("li", limit=1)[0].attrs.get("onclick")

            if link and link.startswith(
                "document.location.href='/projudi/autenticacao.do"
            ):
                link = link.split("href='")[1].split("';")[0]
                link = f"{self.BASE_URL}{link}"
                self.browser.open(link)
                return True
        return False

    def open_process(self, number: str):
        if self._open_home():
            html = BeautifulSoup(str(self.browser.response.content), "html.parser")
            link = html.select_one('a[title^="Busca por processos de 1"]').attrs["href"]

            self.browser.open(f"{self.BASE_URL}{link}")
            pesq_form = self.browser.get_form()
            pesq_form["numeroProcesso"] = number
            self.browser.submit_form(pesq_form)

            html = BeautifulSoup(str(self.browser.response.content), "html.parser")
            link_processo = html.select_one('a[href^="/projudi/processo.do?_tj="]')

            if link_processo:
                link_processo = link_processo.attrs["href"]
                self.browser.open(f"{self.BASE_URL}{link_processo}")
                return True
        return False

    def _open_tab(self, tab: str):
        form = self.browser.get_form()
        form["selectedIcon"] = tab
        self.browser.submit_form(form)

    def extract_tabela_movimentacoes(self, processo):
        resultado = []
        palavras_chave = ["TRANSITADO EM JULGADO", "TRANSITO", "BAIXA", "DEFINITIVAMENTE", "SENTENÇA", "JULGAD", "DESISTÊNCIA", "HOMOL",]
        self._open_tab("tabMovimentacoesProcesso")
        soup = BeautifulSoup(str(self.browser.parsed), "html.parser")
        tabela = soup.find("table", attrs={"class": "resultTable"})
        linhas = tabela.find_all("tr")
        for linha in linhas:
            colunas = linha.find_all("td")
            if len(colunas) < 5:
                continue
            texto_linha = linha.get_text(strip=True)
            evento = colunas[1].get_text(strip=True)
            data_str = colunas[2].get_text(strip=True).split("\n")[0].strip()
            data_obj = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S.%f")
            data_formatada = data_obj.strftime("%d-%m-%Y")
            descricao = colunas[3].text.strip().replace("\t", "").replace("\n", "").replace("\r", "")
            descricao = re.sub(r'\s+', ' ', descricao)
            movimentado_por = colunas[4].text.strip().replace("\t", "").replace("\r", "").replace("\n", " ").split("  ", maxsplit=1)
            usuario = movimentado_por[0]
            tipo = movimentado_por[1] if len(movimentado_por) >= 2 else ""
            #FILTRO AQUI
            evento_dict = {
                "processo": self.__format_processo(processo),
                "evento": evento,
                "data": data_formatada,
                "descricao": descricao,
                "usuario": usuario,
                "tipo": tipo.upper(),
                "ARQUIVOS": "", 
                "tipo_arquivo": "",
            }
            resultado.append(evento_dict)

               # url_arquivos_regex = r"/projudi/processo/movimentacaoArquivoDocumento\.do\?_tj=[a-zA-Z0-9]+"
              #       url_arquivos_regex, str(linha.find_all("td")[0])
              #  )[0]
              #  self.browser.open(f"{self.BASE_URL}{arquivos_url}")

    #            arquivos_salvos = []  
    #            tipos_arquivos = []  
    #            for arquivo in self._get_arquivos_urls(processo, evento):
    #                extensao = arquivo['filename'].split('.')[-1]
    #                descricao_resume = " ".join(re.findall(r'\b[A-ZÀ-Ú]+\b', descricao))
    #                nome_arquivo = f"{processo}-{descricao_resume}-{data_formatada}.{extensao}"

    #                with open(f"{MEDIA_DIR}/{nome_arquivo}", "wb") as arq:
    #                    self.browser.follow_link({"href": arquivo["url"]}, method="GET")
    #                    arq.write(self.browser.response.content)

    #                arquivos_salvos.append(nome_arquivo)
    #                tipos_arquivos.append(arquivo["tipo_arquivo"])

                    # Atualiza o dicionário existente na lista `resultado`
    #            evento_dict["ARQUIVOS"] = ", ".join(arquivos_salvos)
    #            evento_dict["tipo_arquivo"] = ", ".join(tipos_arquivos)

        if resultado == []:
            resultado.append({
                "processo": self.__format_processo(processo),
                "ARQUIVOS": "Nenhuma movimentação correspondeu aos parâmetros de busca."
            })

        return resultado

    
    def __format_processo(self, nbr: str) -> str:
        nbr = re.sub("[^0-9]", "", nbr)
        nbr = nbr.rjust(20, "0")
        regex = re.compile(
            r"([0-9]{7})([0-9]{2})([0-9]{4})([0-9]{1})([0-9]{2})([0-9]{4})"
        )
        groups = regex.search(nbr)
        return f"{groups.group(1)}-{groups.group(2)}.{groups.group(3)}.{groups.group(4)}.{groups.group(5)}.{groups.group(6)}" 

    def _get_arquivos_urls(self, num_processo, num_movimentacao):
        result = []
        for tr in self.browser.find_all("tr"):
            if not len(tr.find_all("td")) == 9:
                continue
            tipo_arquivo = re.sub(r"[(\n+)(\t+)(\r+)]+", " ", tr.find_all("td")[0].text)
            link = tr.find("a")
            url = link.attrs["href"]
            filename = f"{num_processo}_{num_movimentacao}_{link.text.strip()}"
            result.append(
                {"tipo_arquivo": tipo_arquivo, "url": url, "filename": filename}
            )
        return result
