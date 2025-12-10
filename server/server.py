# server/server.py
import Pyro5.api
import Pyro5.server
import time
from database import Database
from crypto_utils import hash_password, verify_password

@Pyro5.server.expose
class WhatsUTServer(object):
    def __init__(self):
        self.db = Database()
        self._last_seen = {}
        self._ttl = 90

        # Mostrar usuários no startup (debug)
        print("\n===== Usuários registrados no banco =====")
        for u in self.db.list_users():
            print(f"ID: {u[0]} | Username: {u[1]} | Banido: {u[2]}")
        print("=========================================\n")

    def ping(self):
        return "Servidor WhatsUT Online!"

    # --------- LOGIN / REGISTRO -----------
    def register(self, username, password):
        """
        Servidor recebe senha em texto e faz o hash aqui antes de salvar.
        """
        hashed = hash_password(password)
        success = self.db.add_user(username, hashed)
        if success:
            print(f"[REGISTER] novo usuário: {username}")
        else:
            print(f"[REGISTER] falha: usuário '{username}' já existe")
        return success

    def login(self, username, password):
        """
        Valida credenciais usando verify_password.
        Retorna (bool, mensagem).
        """
        user = self.db.get_user(username)
        if not user:
            return (False, "Usuário não encontrado.")

        user_id, user_name, db_hash, banned = user

        if banned:
            return (False, "Usuário banido.")

        try:
            ok = verify_password(password, db_hash)
        except Exception as e:
            # caso db_hash esteja em bytes/text diferente, capture e falhe graciosamente
            print(f"[LOGIN] erro verify_password: {e}")
            return (False, "Erro ao validar senha.")

        if ok:
            print(f"[LOGIN] usuário '{username}' autenticado.")
            return (True, "Login autorizado!")
        else:
            print(f"[LOGIN] senha incorreta para '{username}'.")
            return (False, "Senha incorreta.")

    # --------- LISTA DE USUÁRIOS -----------
    def list_users(self):
        """
        Retorna lista de tuplas (id, username, banned)
        """
        return self.db.list_users()

    # --------- MENSAGENS PRIVADAS (ENVIAR / CONVERSA) -----------
    def send_message(self, sender_username, receiver_username, content):
        """
        Recebe nomes (strings). Valida existência e salva mensagem no DB.
        Retorna True se salvo, False caso algum usuário não exista.
        """
        sender = self.db.get_user(sender_username)
        receiver = self.db.get_user(receiver_username)
        if not sender or not receiver:
            print(f"[SEND] falha: sender or receiver not found ({sender_username}, {receiver_username})")
            return False

        sender_id = sender[0]
        receiver_id = receiver[0]
        try:
            self.db.save_message(sender_id, receiver_id, content)
            print(f"[SEND] {sender_username} -> {receiver_username}: {content}")
            return True
        except Exception as e:
            print(f"[SEND] erro ao salvar mensagem: {e}")
            return False

    def get_conversation(self, user_a, user_b):
        """
        Retorna lista de tuplas (sender_name, receiver_name, content, timestamp)
        entre user_a e user_b, ordenadas por timestamp asc.
        Se algum usuário não existir, retorna lista vazia.
        """
        ua = self.db.get_user(user_a)
        ub = self.db.get_user(user_b)
        if not ua or not ub:
            return []

        ua_id = ua[0]
        ub_id = ub[0]
        rows = self.db.get_messages_between(ua_id, ub_id)
        # rows já têm o formato (sender_name, receiver_name, content, timestamp)
        return rows

    def heartbeat(self, username):
        self._last_seen[username] = time.time()
        return True

    def is_online(self, username):
        ts = self._last_seen.get(username)
        if not ts:
            return False
        return (time.time() - ts) <= self._ttl

    def set_offline(self, username):
        if username in self._last_seen:
            del self._last_seen[username]
        return True

    def get_status_map(self):
        now = time.time()
        res = []
        for uid, uname, banned in self.db.list_users():
            online = (now - self._last_seen.get(uname, 0) <= self._ttl) and not banned
            res.append((uname, online))
        return res


def start_server():
    daemon = Pyro5.server.Daemon()

    try:
        ns = Pyro5.api.locate_ns()
    except Exception as e:
        print("❌ NÃO FOI POSSÍVEL ENCONTRAR O NAMESERVER! ----------------")
        print("Execute no terminal: pyro5-ns")
        print("Detalhe:", e)
        return

    uri = daemon.register(WhatsUTServer)
    ns.register("whatsut.server", uri)

    print("🚀 Servidor WhatsUT rodando! URI:", uri)
    daemon.requestLoop()


if __name__ == "__main__":
    start_server()
