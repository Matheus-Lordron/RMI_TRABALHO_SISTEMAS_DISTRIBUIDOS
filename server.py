# server.py (ATUALIZADO)
import Pyro5.server
import Pyro5.api
import threading
import time

# Lista de nicknames de administradores
ADMINS = ["admin", "root", "dev"] 

# Mapa para usuários banidos (nickname: True)
BANNED_USERS = {}

# Mapa para usuários que precisam de aprovação (nickname: proxy)
PENDING_APPROVAL = {}

@Pyro5.server.expose
class ChatServer:
    def __init__(self):
        self.clients = {} # {nickname: client_proxy}
        print("[Servidor] ChatServer inicializado.")

    def is_admin(self, nickname):
        return nickname in ADMINS

    def register(self, nickname, client_proxy):
        """Registra um novo cliente no chat."""
        if nickname in self.clients:
            raise ValueError(f"Nickname '{nickname}' já está em uso.")
        
        if nickname in BANNED_USERS:
            raise PermissionError(f"Nickname '{nickname}' foi banido.")

        if nickname not in ADMINS and len(self.clients) >= 0: # Para testar aprovação: >=0
            # Se não é admin e já há usuários, exige aprovação
            PENDING_APPROVAL[nickname] = client_proxy
            print(f"[Servidor] Cliente '{nickname}' aguardando aprovação.")
            # Notifica os admins
            self.broadcast("Servidor", f"Novo cliente '{nickname}' aguardando aprovação.", only_admins=True)
            # Notifica o cliente que ele está pendente
            try:
                client_proxy.receive_message(f"[Servidor] Seu nickname '{nickname}' aguarda aprovação de um administrador.")
            except Exception:
                pass # Cliente pode ter caído antes de receber
            return False # Sinaliza que o registro não foi completo
        
        # Se for admin ou não precisar de aprovação
        self._add_client(nickname, client_proxy)
        return True # Registro bem-sucedido

    def _add_client(self, nickname, client_proxy):
        """Adiciona o cliente à lista de clientes ativos."""
        self.clients[nickname] = client_proxy
        if nickname in PENDING_APPROVAL:
            del PENDING_APPROVAL[nickname] # Remove da lista de pendentes
        
        print(f"[Servidor] {nickname} entrou no chat.")
        self.broadcast("Servidor", f"{nickname} entrou no chat.", exclude=[nickname])

        # Notifica o cliente que a aprovação foi bem-sucedida (se aplicável)
        try:
            client_proxy.receive_message(f"[Servidor] Seu acesso foi aprovado. Bem-vindo!")
        except Exception:
            pass
            
    def unregister(self, nickname):
        """Remove um cliente do chat."""
        if nickname in self.clients:
            del self.clients[nickname]
            print(f"[Servidor] {nickname} saiu do chat.")
            self.broadcast("Servidor", f"{nickname} saiu do chat.", exclude=[])
        elif nickname in PENDING_APPROVAL: # Também remove se estava pendente e saiu
            del PENDING_APPROVAL[nickname]
            print(f"[Servidor] Cliente '{nickname}' (pendente) saiu.")
            self.broadcast("Servidor", f"Cliente '{nickname}' (pendente) desconectou.", only_admins=True)
            
    def get_users(self):
        """Retorna a lista de usuários online."""
        return list(self.clients.keys())

    def get_pending_users(self):
        """Retorna a lista de usuários aguardando aprovação."""
        return list(PENDING_APPROVAL.keys())
            
    def broadcast(self, sender_nickname, message, exclude=None, only_admins=False):
        """Envia uma mensagem para todos os clientes conectados (chat coletivo)."""
        if exclude is None:
            exclude = []
            
        full_message = f"[{sender_nickname} (Coletivo)] {message}"
        print(f"Transmitindo: {full_message}")
        
        for nick, client in list(self.clients.items()): # Usa list() para iterar sobre uma cópia
            if only_admins and nick not in ADMINS:
                continue # Pula não-admins se for only_admins
            if nick not in exclude:
                try:
                    client.receive_message(full_message)
                except Pyro5.errors.CommunicationError:
                    print(f"Erro de comunicação com {nick}. Removendo.")
                    self.unregister(nick)
                except Exception as e:
                    print(f"Erro inesperado ao enviar para {nick}: {e}. Removendo.")
                    self.unregister(nick)

    def private_message(self, sender_nickname, recipient_nickname, message):
        """Envia uma mensagem privada para um usuário específico (chat individual)."""
        sender_proxy = self.clients.get(sender_nickname)
        if not sender_proxy: return False # Remetente não está online

        if recipient_nickname not in self.clients:
            try:
                sender_proxy.receive_message(f"[Servidor] Usuário '{recipient_nickname}' não encontrado ou offline.")
            except Exception: pass
            return False
        
        if sender_nickname == recipient_nickname:
             try:
                sender_proxy.receive_message(f"[Servidor] Você não pode enviar mensagem privada para si mesmo.")
             except Exception: pass
             return False

        try:
            recipient_proxy = self.clients[recipient_nickname]
            recipient_proxy.receive_message(f"[{sender_nickname} (Privado)] {message}")
            
            sender_proxy.receive_message(f"[Para {recipient_nickname} (Privado)] {message}")
            return True
            
        except Pyro5.errors.CommunicationError:
            print(f"Erro de comunicação com {recipient_nickname} ao enviar PM. Removendo.")
            self.unregister(recipient_nickname)
            try: sender_proxy.receive_message(f"[Servidor] Erro ao enviar PM para {recipient_nickname}. Usuário desconectou.")
            except Exception: pass
            return False
        except Exception as e:
            print(f"Erro inesperado ao enviar PM de {sender_nickname} para {recipient_nickname}: {e}")
            try: sender_proxy.receive_message(f"[Servidor] Erro desconhecido ao enviar PM para {recipient_nickname}.")
            except Exception: pass
            return False

    # Métodos de Admin
    def approve_client(self, admin_nickname, client_to_approve):
        """Aprova um cliente que estava aguardando."""
        if not self.is_admin(admin_nickname):
            raise PermissionError("Apenas administradores podem aprovar clientes.")
        
        if client_to_approve in PENDING_APPROVAL:
            client_proxy = PENDING_APPROVAL[client_to_approve]
            self._add_client(client_to_approve, client_proxy) # Move para clientes ativos
            self.broadcast("Servidor", f"Administrador {admin_nickname} aprovou '{client_to_approve}'.")
            return True
        else:
            print(f"[Servidor] Cliente '{client_to_approve}' não encontrado ou não está pendente de aprovação.")
            return False

    def ban_client(self, admin_nickname, client_to_ban):
        """Bane um cliente."""
        if not self.is_admin(admin_nickname):
            raise PermissionError("Apenas administradores podem banir clientes.")
        
        if client_to_ban in self.clients:
            self.clients[client_to_ban].receive_message(f"[Servidor] Você foi banido por {admin_nickname}.")
            self.clients[client_to_ban]._pyroRelease() # Libera o proxy
            del self.clients[client_to_ban]
        elif client_to_ban in PENDING_APPROVAL:
            del PENDING_APPROVAL[client_to_ban]

        BANNED_USERS[client_to_ban] = True # Adiciona à lista de banidos
        self.broadcast("Servidor", f"Administrador {admin_nickname} baniu '{client_to_ban}'.")
        print(f"[Servidor] Cliente '{client_to_ban}' foi banido e desconectado.")
        return True
    
    def is_client_banned(self, nickname):
        """Verifica se um nickname está banido."""
        return nickname in BANNED_USERS


def main():
    daemon = Pyro5.server.Daemon()
    ns = Pyro5.api.locate_ns()
    
    chat_server = ChatServer()
    uri = daemon.register(chat_server)
    ns.register("chat.server", uri)
    
    print("Servidor de Chat está pronto e registrado como 'chat.server'.")
    print(f"Admins configurados: {', '.join(ADMINS)}")
    daemon.requestLoop()

if __name__ == "__main__":
    main()