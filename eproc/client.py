import requests


class HTTPClient:
    def __init__(self, session: requests.Session) -> None:
        self.session = session

    def get(self, **kwargs) -> requests.Response:
        r = self.session.get(**kwargs)
        return r

    def post(self, **kwargs) -> requests.Response:
        r = self.session.post(**kwargs)
        return r

class Client:
    def __init__(self, base_url):
        self.base_url = base_url
        self.http_client = HTTPClient(requests.Session())

    def login(self, username: str, password: str) -> requests.Response:
        """faz a request de login"""
        url = f"{self.base_url}/index.php"
        data = {
            "txtUsuario": username,
            "pwdSenha": password,
            "hdnAcao": "login",
            "hdnDebug": "",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        r = self.http_client.post(url=url, data=data, headers=headers)
        return r

    def acessa_perfil(self, id_usuario: str) -> requests.Response:
        """Faz a request de selecao do perfil do usuario"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        url = f"{self.base_url}/controlador.php?acao=pessoa_usuario_logar&acao_origem=entrar&id_usuario={id_usuario}"
        data = "lista_processos="
        r = self.http_client.post(url=url, data=data, headers=headers)
        return r

    def resolve_catpcha(self, data: dict, endpoint) -> requests.Response:
        """faz a request para submeter o captcha. Recebe como parametro o payload que será enviado na request e o endpoint"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        r = self.http_client.post(
            url=f"{self.base_url}/{endpoint}", data=data, headers=headers
        )
        return r

    def resolve_2fa(self, data: dict) -> requests.Response:
        """faz a request para resolver o 2fa. Recebe como parametro o payload que será enviado na request"""
        endpoint = "/index.php"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        r = self.http_client.post(
            url=f"{self.base_url}{endpoint}", data=data, headers=headers
        )
        return r
    
    def acessa_link(self, link) -> requests.Response:
        """acessa um dado link. util para acessar algum link do menu"""
        return self.http_client.get(url=link)

    def consulta_processo(self, endpoint, num_processo) -> requests.Response:
        """faz a request de consultar o processo. como o endpoint possui uma hash que muda conforme o login é necessario passa-lo como parametro"""
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "hdnInfraTipoPagina": "1",
            "acao_origem": "consultar",
            "acao_retorno": "",
            "acao": "processo_consultar",
            "hdnNumPaginaAtual": "1",
            "hdnNumSentidoNavegacao": "1",
            "hdnNumIdProcessoCursorInicio": "",
            "hdnNumIdProcessoCursorFim": "",
            "hdnNumIdProcessoCursorIniciosAnteriores": "",
            "tipoPesquisa": "NU",
            "numNrProcesso": num_processo,
            "selIdClasseSelecionados": "",
            "strChave": "",
        }
        r = self.http_client.post(url=url, headers=headers, data=data)
        return r

    def acessa_endpoint(self, endpoint) -> requests.Response:
        """faz um get para acessar um endpoint"""
        url = f"{self.base_url}/{endpoint}"
        r = self.http_client.get(url=url)
        return r
