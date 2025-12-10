# server/server.py
import Pyro5.api
import Pyro5.server
import Pyro5.errors
import time
from database import Database
from crypto_utils import hash_password, verify_password

@Pyro5.server.expose
class WhatsUTServer(object):
    def __init__(self):
        self.db = Database()
        self._last_seen = {}
        self._ttl = 90
        self._callbacks = {}

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
            cb = self._callbacks.get(receiver_username)
            if cb:
                try:
                    cb.notify_private(sender_username, receiver_username)
                except Exception as e:
                    print(f"[SEND] callback receiver erro: {e}")
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

    def list_groups(self):
        return self.db.list_groups()

    def list_groups_with_status(self, username):
        user = self.db.get_user(username)
        if not user:
            return []
        uid = user[0]
        res = []
        for gid, name, admin_uname in self.db.list_groups():
            if admin_uname == username:
                status = "aprovado"
            else:
                st = self.db.membership_status(uid, gid)
                if st is None:
                    status = "fora"
                elif st == 0:
                    status = "pendente"
                else:
                    status = "aprovado"
            res.append((name, admin_uname, status))
        return res

    def request_join_group(self, username, group_name):
        user = self.db.get_user(username)
        grp = self.db.get_group(group_name)
        if not user or not grp:
            return False
        return self.db.request_join_group(user[0], grp[0])

    def list_pending_requests(self, admin_username, group_name):
        admin = self.db.get_user(admin_username)
        grp = self.db.get_group(group_name)
        if not admin or not grp:
            return []
        if grp[2] != admin[0]:
            return []
        return [u for (u,) in self.db.list_pending_requests(grp[0])]

    def approve_member(self, admin_username, group_name, member_username):
        admin = self.db.get_user(admin_username)
        grp = self.db.get_group(group_name)
        mem = self.db.get_user(member_username)
        if not admin or not grp or not mem:
            return False
        if grp[2] != admin[0]:
            return False
        return self.db.approve_member(mem[0], grp[0])

    def create_group(self, admin_username, group_name):
        admin = self.db.get_user(admin_username)
        if not admin:
            return False
        return self.db.create_group(group_name, admin[0])

    def add_member_direct(self, admin_username, group_name, member_username):
        admin = self.db.get_user(admin_username)
        grp = self.db.get_group(group_name)
        mem = self.db.get_user(member_username)
        if not admin or not grp or not mem:
            return False
        if grp[2] != admin[0]:
            return False
        return self.db.add_member_approved(mem[0], grp[0])

    def delete_group(self, admin_username, group_name):
        admin = self.db.get_user(admin_username)
        grp = self.db.get_group(group_name)
        if not admin or not grp:
            return False
        if grp[2] != admin[0]:
            return False
        return self.db.delete_group(grp[0])

    def send_group_message(self, sender_username, group_name, content):
        grp = self.db.get_group(group_name)
        snd = self.db.get_user(sender_username)
        if not grp or not snd:
            return False
        st = self.db.membership_status(snd[0], grp[0])
        if st != 1:
            return False
        try:
            self.db.save_group_message(grp[0], snd[0], content)
            return True
        except Exception:
            return False

    def get_group_conversation(self, group_name):
        grp = self.db.get_group(group_name)
        if not grp:
            return []
        return self.db.get_group_messages(grp[0])

    def register_callback(self, username, cb_uri):
        try:
            proxy = Pyro5.api.Proxy(cb_uri)
            try:
                proxy._pyroOneway.add("notify_private")
            except Exception:
                pass
            self._callbacks[username] = proxy
            return True
        except Exception:
            return False

    def unregister_callback(self, username):
        try:
            self._callbacks.pop(username, None)
            return True
        except Exception:
            return False


def start_server():
    daemon = Pyro5.server.Daemon()

    try:
        ns = Pyro5.api.locate_ns()
    except Exception as e:
        print("❌ NÃO FOI POSSÍVEL ENCONTRAR O NAMESERVER! ----------------")
        print("Execute no terminal: pyro5-ns")
        print("Detalhe:", e)
        return

    obj = WhatsUTServer()
    uri = daemon.register(obj)
    try:
        ns.register("whatsut.server", uri)
    except Pyro5.errors.NamingError:
        try:
            ns.remove("whatsut.server")
        except Exception:
            pass
        ns.register("whatsut.server", uri)

    print("🚀 Servidor WhatsUT rodando! URI:", uri)
    daemon.requestLoop()


if __name__ == "__main__":
    start_server()
