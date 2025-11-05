# client.py
import Pyro5.api
import threading
import sys

# Esta classe será instanciada no cliente, mas exposta ao Pyro
# para que o SERVIDOR possa chamar o método 'receive_message'.
@Pyro5.server.expose
@Pyro5.server.behavior(instance_mode="single")
class ChatClient:
    def receive_message(self, message):
        """Este é o método de CALLBACK que o servidor chama."""
        # Usamos \r para limpar a linha atual e reimprimir o prompt '>'
        # Isso evita que a mensagem recebida bagunce o que o usuário está digitando.
        print(f"\r{message}\n> ", end="")

def start_client_daemon(client_obj):
    """Inicia o daemon do cliente em uma thread separada."""
    # Precisamos de um daemon para que o objeto 'client_obj'
    # possa receber chamadas do servidor.
    with Pyro5.server.Daemon() as daemon:
        daemon.register(client_obj)
        # O requestLoop bloqueia, por isso roda em uma thread
        daemon.requestLoop()

def main():
    try:
        # 1. Encontrar o Servidor de Nomes
        ns = Pyro5.api.locate_ns()
        # 2. Procurar pelo nosso servidor de chat
        server_uri = ns.lookup("chat.server")
        # 3. Criar um proxy para o servidor
        server = Pyro5.api.Proxy(server_uri)
    except Pyro5.errors.NamingError:
        print("Erro: Não foi possível encontrar o servidor de chat.")
        print("Verifique se o Servidor de Nomes (pyro5-ns) e o server.py estão rodando.")
        sys.exit(1)

    nickname = input("Digite seu nickname: ").strip()
    if not nickname:
        print("Nickname não pode ser vazio.")
        sys.exit(1)

    # 4. Criar a instância do cliente (para callbacks)
    client_obj = ChatClient()

    # 5. Iniciar o daemon do cliente em uma thread
    #    Isso permite que o cliente ouça por mensagens *enquanto*
    #    o usuário digita na thread principal.
    daemon_thread = threading.Thread(
        target=start_client_daemon,
        args=(client_obj,),
        daemon=True  # Define como daemon para sair quando a thread principal sair
    )
    daemon_thread.start()

    # 6. Registrar este cliente no servidor
    try:
        # Passamos nosso nickname e o objeto cliente (que o servidor usará para callback)
        server.register(nickname, client_obj)
    except ValueError as e:
        print(f"Erro ao registrar: {e}")
        sys.exit(1)

    print(f"Bem-vindo, {nickname}! Chat conectado.")
    print("Comandos:")
    print("  /pm <nickname> <mensagem>  - Envia mensagem privada")
    print("  /list                      - Lista usuários online")
    print("  /quit                      - Sai do chat")
    print("Qualquer outra coisa é uma mensagem coletiva.")
    print("> ", end="")

    try:
        while True:
            # Thread principal fica bloqueada aqui, esperando input
            message = input()
            
            if message.startswith("/quit"):
                break
            elif message.startswith("/list"):
                users = server.get_users()
                print(f"[Usuários online: {', '.join(users)}]\n> ", end="")
            elif message.startswith("/pm "):
                try:
                    # Divide: /pm, nickname, mensagem
                    _, recipient, msg_body = message.split(" ", 2)
                    server.private_message(nickname, recipient, msg_body)
                except ValueError:
                    print("[Sistema] Formato inválido. Use: /pm <nickname> <mensagem>\n> ", end="")
            elif message: # Se não for comando e não for vazio
                # Envia como mensagem coletiva (broadcast)
                server.broadcast(nickname, message, exclude=[nickname])
            else:
                # Apenas reimprime o prompt se o usuário der Enter
                print("> ", end="")

    except KeyboardInterrupt:
        print("\nDesconectando...")
    finally:
        # 7. Sempre cancelar o registro ao sair
        server.unregister(nickname)
        print("Você saiu do chat.")

if __name__ == "__main__":
    main()