# Consulta de Processos Judiciais

Sistema para consulta automatizada de processos judiciais nos sistemas EPROC e PROJUDI do TJPR.

## Funcionalidades

- Consulta automatizada de processos
- Download automático de documentos
- Suporte para autenticação 2FA
- Resolução automática de CAPTCHA (requer API key do 2captcha)
- Exportação de movimentações

## Requisitos

- Python 3.8 ou superior
- Conta de acesso aos sistemas EPROC e PROJUDI
- API key do serviço 2captcha

## Instalação

1. Clone o repositório:
```bash
git clone <seu-repositorio>
cd <seu-diretorio>
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure o arquivo `config.ini`:
```ini
[EPROC]
username = seu_usuario
password = sua_senha
base_url = https://eproc.url.base
api_key = sua_api_key_2captcha
token = seu_token_2fa

[PROJUDI]
username = seu_usuario
password = sua_senha
base_url = https://projudi.url.base
api_key = sua_api_key_2captcha
```

## Uso

### Como executável
1. Gere o executável:
```bash
python build.py
```

2. Execute o programa:
```bash
./dist/consulta_processos
```

### Como script Python
```bash
python main.py
```

## Estrutura do Projeto

```
.
├── eproc/
│   ├── __init__.py
│   ├── client.py
│   ├── eproc_client.py
│   └── html_parser.py
├── projudi_tjpr/
│   ├── __init__.py
│   ├── client.py
│   ├── projudi_client.py
│   └── html_parser.py
├── main.py
├── config.ini
├── requirements.txt
└── build.py
```

## Notas

- Os arquivos baixados serão salvos no diretório `MEDIA/`
- É necessário ter uma API key válida do 2captcha para resolução automática de captchas
- Configure corretamente o token 2FA se estiver habilitado em sua conta

## Suporte

Para problemas e sugestões, por favor abra uma issue no repositório. 