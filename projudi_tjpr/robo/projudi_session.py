from pyjudi_tjpr import Authenticator
import logging

def make_session(usr: str, pwd: str, token: str):
    authenticator = Authenticator(
        username=usr,
        password=pwd,
        twofactor_secret=token,
    )

    session = authenticator.get_logged_session()

    session.headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64"
    }

    logging.getLogger().info("Sessão no projudi iniciada com sucesso.")

    return session 