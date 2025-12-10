# server/server.py
import Pyro5.api
import Pyro5.server
import Pyro5.errors
import time
import base64
from database import Database
from crypto_utils import hash_password, verify_password

@Pyro5.server.expose
class WhatsUTServer(object):
    def __init__(self):
        self.db = Database()
        self._last_seen = {}
        self._ttl = 90
        self._callbacks = {}
        
        print("\n===== Usuários registrados no banco =====")
        for u in self.db.list_users():
            print(f"ID: {u[0]} | Username: {u[1]} | Banido: {u[2]}")
        print("=========================================\n")

    def ping(self):
        return "Servidor WhatsUT Online!"

    # ========== AUTENTICAÇÃO ==========
    def register(self, username, password):
        hashed = hash_password(password)
        success = self.db.add_user(username, hashed)
        if success:
            print(f"[REGISTER] novo usuário: {username}")
        else:
            print(f"[REGISTER] falha: usuário '{username}' já existe")
        return success

    def login(self, username, password):
        user = self.db.get_user(username)
        if not user:
            return (False, "Usuário não encontrado.")
        
        user_id, user_name, db_hash, banned = user
        
        if banned:
            return (False, "Usuário banido.")
        
        try:
            ok = verify_password(password, db_hash)
        except Exception as e:
            print(f"[LOGIN] erro verify_password: {e}")
            return (False, "Erro ao validar senha.")
        
        if ok:
            print(f"[LOGIN] usuário '{username}' autenticado.")
            return (True, "Login autorizado!")
        else:
            print(f"[LOGIN] senha incorreta para '{username}'.")
            return (False, "Senha incorreta.")

    # ========== LISTA DE USUÁRIOS ==========
    def list_users(self):
        return self.db.list_users()

    # ========== MENSAGENS PRIVADAS ==========
    def send_message(self, sender_username, receiver_username, content):
        sender = self.db.get_user(sender_username)
        receiver = self.db.get_user(receiver_username)
        if not sender or not receiver:
            return False
        
        sender_id = sender[0]
        receiver_id = receiver[0]
        
        try:
            self.db.save_message(sender_id, receiver_id, content)
            print(f"[MSG] {sender_username} -> {receiver_username}: {content[:50]}")
            
            # Notifica callback
            cb = self._callbacks.get(receiver_username)
            if cb:
                try:
                    cb.notify_private(sender_username, receiver_username)
                except Exception as e:
                    print(f"[CALLBACK] erro: {e}")
            return True
        except Exception as e:
            print(f"[MSG] erro: {e}")
            return False

    def get_conversation(self, user_a, user_b):
        ua = self.db.get_user(user_a)
        ub = self.db.get_user(user_b)
        if not ua or not ub:
            return []
        return self.db.get_messages_between(ua[0], ub[0])

    # ========== ENVIO DE ARQUIVOS ==========
    def send_file(self, sender_username, receiver_username, filename, file_data_b64):
        """
        file_data_b64: string base64 do arquivo
        Retorna: (bool, mensagem)
        """
        sender = self.db.get_user(sender_username)
        receiver = self.db.get_user(receiver_username)
        
        if not sender or not receiver:
            return (False, "Usuário não encontrado")
        
        try:
            # Decodifica base64
            file_data = base64.b64decode(file_data_b64)
            file_id = self.db.save_file(sender[0], receiver[0], filename, file_data)
            print(f"[FILE] {sender_username} -> {receiver_username}: {filename} ({len(file_data)} bytes)")
            
            # Notifica callback
            cb = self._callbacks.get(receiver_username)
            if cb:
                try:
                    cb.notify_file(sender_username, receiver_username, filename)
                except Exception:
                    pass
            
            return (True, f"Arquivo enviado com ID: {file_id}")
        except Exception as e:
            print(f"[FILE] erro: {e}")
            return (False, f"Erro ao enviar arquivo: {e}")

    def get_files_list(self, user_a, user_b):
        """Retorna lista de arquivos trocados entre dois usuários"""
        ua = self.db.get_user(user_a)
        ub = self.db.get_user(user_b)
        if not ua or not ub:
            return []
        return self.db.get_files_between(ua[0], ub[0])

    def download_file(self, file_id):
        """
        Retorna: (filename, file_data_b64) ou (None, None) se não encontrado
        """
        try:
            result = self.db.get_file_data(file_id)
            if result:
                filename, file_data = result
                file_data_b64 = base64.b64encode(file_data).decode()
                return (filename, file_data_b64)
            return (None, None)
        except Exception as e:
            print(f"[DOWNLOAD] erro: {e}")
            return (None, None)

    # ========== PRESENÇA ONLINE ==========
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

    # ========== GRUPOS ==========
    def create_group(self, admin_username, group_name, admin_on_leave='transfer'):
        """
        admin_on_leave: 'transfer' (transfere para próximo membro) ou 'delete' (deleta o grupo)
        """
        admin = self.db.get_user(admin_username)
        if not admin:
            return False
        return self.db.create_group(group_name, admin[0], admin_on_leave)

    def list_groups(self):
        return self.db.list_groups()

    def list_groups_with_status(self, username):
        user = self.db.get_user(username)
        if not user:
            return []
        uid = user[0]
        res = []
        for gid, name, admin_uname, admin_on_leave in self.db.list_groups():
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
        if grp[2] != admin[0]:  # Verifica se é admin
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

    def add_member_direct(self, admin_username, group_name, member_username):
        admin = self.db.get_user(admin_username)
        grp = self.db.get_group(group_name)
        mem = self.db.get_user(member_username)
        if not admin or not grp or not mem:
            return False
        if grp[2] != admin[0]:
            return False
        return self.db.add_member_approved(mem[0], grp[0])

    def leave_group(self, username, group_name):
        """Usuário sai do grupo. Se for admin, transfere ou deleta conforme configuração"""
        user = self.db.get_user(username)
        grp = self.db.get_group(group_name)
        if not user or not grp:
            return False
        
        gid, name, admin_id, admin_on_leave = grp
        user_id = user[0]
        
        # Se não é admin, apenas remove
        if admin_id != user_id:
            self.db.remove_member(user_id, gid)
            print(f"[GROUP] {username} saiu do grupo {group_name}")
            return True
        
        # Admin está saindo
        if admin_on_leave == 'delete':
            # Deleta o grupo
            self.db.delete_group(gid)
            print(f"[GROUP] Admin {username} saiu. Grupo {group_name} deletado.")
            return True
        else:
            # Transfere para próximo membro (por ordem de entrada)
            members = self.db.list_group_members(gid, approved_only=True)
            next_admin = None
            for mid, mname in members:
                if mid != user_id:
                    next_admin = mid
                    break
            
            if next_admin:
                self.db.update_group_admin(gid, next_admin)
                self.db.remove_member(user_id, gid)
                print(f"[GROUP] Admin {username} saiu. Novo admin: ID {next_admin}")
                return True
            else:
                # Não há outros membros, deleta o grupo
                self.db.delete_group(gid)
                print(f"[GROUP] Admin {username} saiu e não há outros membros. Grupo deletado.")
                return True

    def delete_group(self, admin_username, group_name):
        admin = self.db.get_user(admin_username)
        grp = self.db.get_group(group_name)
        if not admin or not grp:
            return False
        if grp[2] != admin[0]:
            return False
        return self.db.delete_group(grp[0])

    def kick_member(self, admin_username, group_name, member_username):
        """Admin expulsa um membro do grupo"""
        admin = self.db.get_user(admin_username)
        grp = self.db.get_group(group_name)
        mem = self.db.get_user(member_username)
        if not admin or not grp or not mem:
            return False
        if grp[2] != admin[0]:  # Verifica se é admin
            return False
        self.db.remove_member(mem[0], grp[0])
        print(f"[GROUP] {admin_username} expulsou {member_username} do grupo {group_name}")
        return True

    # ========== MENSAGENS DE GRUPO ==========
    def send_group_message(self, sender_username, group_name, content):
        grp = self.db.get_group(group_name)
        snd = self.db.get_user(sender_username)
        if not grp or not snd:
            return False
        st = self.db.membership_status(snd[0], grp[0])
        if st != 1:  # Precisa estar aprovado
            return False
        try:
            self.db.save_group_message(grp[0], snd[0], content)
            print(f"[GROUP MSG] {sender_username} em {group_name}: {content[:50]}")
            return True
        except Exception as e:
            print(f"[GROUP MSG] erro: {e}")
            return False

    def get_group_conversation(self, group_name):
        grp = self.db.get_group(group_name)
        if not grp:
            return []
        return self.db.get_group_messages(grp[0])

    # ========== BANIMENTO ==========
    def request_ban_user(self, requester_username, target_username, reason=""):
        """Usuário solicita banimento de outro usuário"""
        req = self.db.get_user(requester_username)
        tar = self.db.get_user(target_username)
        if not req or not tar:
            return (False, "Usuário não encontrado")
        
        request_id = self.db.create_ban_request(req[0], tar[0], reason)
        print(f"[BAN REQUEST] {requester_username} solicitou ban de {target_username}")
        return (True, f"Solicitação criada com ID: {request_id}")

    def list_ban_requests(self):
        """Lista todas as solicitações de banimento pendentes"""
        return self.db.list_ban_requests('pending')

    def approve_ban(self, request_id):
        """Aprova uma solicitação de banimento (simulando um admin do servidor)"""
        try:
            self.db.approve_ban_request(request_id)
            # Busca o target da solicitação e bane
            requests = self.db.list_ban_requests('approved')
            for rid, req_name, tar_name, reason, ts in requests:
                if rid == request_id:
                    self.db.ban_user(tar_name)
                    print(f"[BAN] Usuário {tar_name} foi banido")
                    return True
            return False
        except Exception as e:
            print(f"[BAN] erro: {e}")
            return False

    def reject_ban(self, request_id):
        """Rejeita uma solicitação de banimento"""
        try:
            self.db.reject_ban_request(request_id)
            print(f"[BAN] Solicitação {request_id} rejeitada")
            return True
        except Exception:
            return False

    # ========== CALLBACKS ==========
    def register_callback(self, username, cb_uri):
        try:
            proxy = Pyro5.api.Proxy(cb_uri)
            try:
                proxy._pyroOneway.add("notify_private")
                proxy._pyroOneway.add("notify_file")
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
        print("❌ NÃO FOI POSSÍVEL ENCONTRAR O NAMESERVER!")
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