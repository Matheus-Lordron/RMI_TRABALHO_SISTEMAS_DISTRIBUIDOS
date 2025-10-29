# client_gui_full.py
"""
Chat RMI (Pyro5) - Cliente GUI completo com:
 - Aba "Geral" (broadcast)
 - Aba "Grupo" (broadcast com etiqueta de grupo)
 - Aba "Admin" (listagem pendentes + banir/aprovar) [visível apenas para admins]
 - Lista lateral de usuários online (selecionável para PM)
 - Callbacks via Pyro5 Daemon em thread (criação manual do daemon)
 - Fila de mensagens para comunicação segura com a thread da GUI
"""

import Pyro5.api
import Pyro5.server
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import time

# --------------------------
# Callback exposto ao servidor
# --------------------------
@Pyro5.server.expose
@Pyro5.server.behavior(instance_mode="single")
class ChatCallback:
    def __init__(self):
        self.message_queue = None

    def set_queue(self, q: queue.Queue):
        self.message_queue = q

    def receive_message(self, message):
        # Recebe mensagens do servidor e as coloca na fila
        if self.message_queue:
            # Diferencia tipos simples: se for string, envia tipo 'message'
            # mensagens contendo certas palavras podem disparar atualização de listas
            self.message_queue.put(("message", message))
            msg_lower = message.lower()
            if "entrou no chat" in msg_lower or "saiu do chat" in msg_lower or "aprovou" in msg_lower or "baniu" in msg_lower or "aguardando aprovação" in msg_lower:
                # pede atualização de listas
                self.message_queue.put(("update_users", None))
                self.message_queue.put(("update_pending", None))
        else:
            print("[Callback] receive_message chamado antes de set_queue().")

# --------------------------
# Thread que roda o Pyro Daemon
# --------------------------
class PyroDaemonThread(threading.Thread):
    def __init__(self, callback_obj: ChatCallback):
        super().__init__()
        # Manter a thread como não-daemon (padrão) para controlar o ciclo de vida manualmente.
        self.callback_obj = callback_obj
        self.daemon_obj = None  # Objeto Pyro5.server.Daemon
        self.uri = None
        self.ready_event = threading.Event()
        self._stop_event = threading.Event()

    def run(self):
        try:
            # Criação manual do daemon (não usar 'with')
            self.daemon_obj = Pyro5.server.Daemon()
            self.uri = self.daemon_obj.register(self.callback_obj)
            print(f"[Thread Pyro] Daemon iniciado: {self.uri}")
            # Sinaliza que o daemon e URI estão prontos
            self.ready_event.set()
            # Request loop bloqueante; será encerrado por shutdown()
            self.daemon_obj.requestLoop()
        except Exception as e:
            print(f"[Thread Pyro] Erro no loop do daemon: {e}")
            self.ready_event.set()

    def shutdown(self):
        if self.daemon_obj:
            try:
                self.daemon_obj.shutdown()
                print("[Thread Pyro] Daemon shutdown solicitado.")
            except Exception as e:
                print(f"[Thread Pyro] Erro no shutdown do daemon: {e}")

# --------------------------
# GUI Principal
# --------------------------
class ChatGUI:
    USER_REFRESH_MS = 3000  # intervalo para atualizar lista de usuários e pendentes

    def __init__(self, root):
        self.root = root
        self.root.title("Chat RMI - Cliente")
        self.root.geometry("900x520")

        # Estado
        self.nickname = None
        self.server = None
        self.is_admin = False
        self.server_uri_str = None

        # Pyro callback/daemon
        self.message_queue = queue.Queue()
        self.callback_obj = None
        self.pyro_thread = None

        # Widgets e variáveis
        self.tab_control = None
        self.chat_text = None
        self.chat_group_text = None
        self.entry_var = tk.StringVar()
        self.user_listbox = None
        self.pending_listbox = None  # only for admin
        self.current_tab = tk.StringVar(value="Geral")
        self.selected_recipient = tk.StringVar(value="")  # nickname selecionado para PM

        # Inicialização procedural
        self.build_layout()
        self.connect_to_server()

    # --------------------------
    # Layout / widgets
    # --------------------------
    def build_layout(self):
        # Frame principal contém painel de chat (esquerda) e painel lateral (direita)
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Chat area (esquerda)
        left = tk.Frame(main_frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Tabs: Geral, Grupo, Admin (Admin só mostrado se is_admin=True)
        self.tab_control = ttk.Notebook(left)
        # Tab Geral
        tab_general = ttk.Frame(self.tab_control)
        self.chat_text = tk.Text(tab_general, state="disabled", wrap=tk.WORD)
        self.chat_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.tab_control.add(tab_general, text="Geral")

        # Tab Grupo
        tab_group = ttk.Frame(self.tab_control)
        self.chat_group_text = tk.Text(tab_group, state="disabled", wrap=tk.WORD)
        self.chat_group_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.tab_control.add(tab_group, text="Grupo")

        # Admin tab placeholder (adicionado pós-conexão quando necessário)
        self.admin_tab = ttk.Frame(self.tab_control)  # será adicionado somente se admin

        self.tab_control.pack(fill=tk.BOTH, expand=True)

        # Entry + send
        bottom_frame = tk.Frame(left)
        bottom_frame.pack(fill=tk.X, padx=4, pady=(0,6))
        entry = tk.Entry(bottom_frame, textvariable=self.entry_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.bind("<Return>", lambda e: self.on_send_clicked())
        send_btn = tk.Button(bottom_frame, text="Enviar", command=self.on_send_clicked)
        send_btn.pack(side=tk.RIGHT, padx=(6,0))

        # Right panel: users + admin controls
        right = tk.Frame(main_frame, width=260)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,6), pady=6)
        right.pack_propagate(False)

        tk.Label(right, text="Usuários Online:").pack(anchor="nw")
        self.user_listbox = tk.Listbox(right, height=16)
        self.user_listbox.pack(fill=tk.X, padx=4, pady=(0,8))
        self.user_listbox.bind("<<ListboxSelect>>", self.on_user_select)

        # Controls for PM and mode
        tk.Label(right, text="Destinatário selecionado:").pack(anchor="nw")
        tk.Label(right, textvariable=self.selected_recipient, relief="sunken").pack(fill=tk.X, padx=4, pady=(0,8))

        # Admin controls area (inside admin tab)
        # But also keep quick ban button on side for convenience
        ban_btn = tk.Button(right, text="Banir selecionado", command=self.ban_selected_quick)
        ban_btn.pack(fill=tk.X, padx=4, pady=(4,0))

        # Info label
        self.status_label = tk.Label(right, text="Desconectado", anchor="w")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=(6,0))

        # --- prepare admin area widgets but not packed yet ---
        # pending listbox and approve/ban buttons live in admin_tab; created in setup_admin_tab()

    # --------------------------
    # Conexão com servidor / registro
    # --------------------------
    def connect_to_server(self):
        try:
            print("[connect] Localizando Servidor de Nomes...")
            ns = Pyro5.api.locate_ns()
            print(f"[connect] NS em: {ns._pyroUri}")
            server_uri = ns.lookup("chat.server")
            print(f"[connect] chat.server em: {server_uri}")

            self.server_uri_str = str(server_uri)
            self.server = Pyro5.api.Proxy(self.server_uri_str)

            # Pedir nickname ao usuário
            self.nickname = simpledialog.askstring("Nickname", "Digite seu nickname:", parent=self.root)
            if not self.nickname:
                messagebox.showinfo("Fechar", "Nickname não informado. Encerrando cliente.")
                self.root.after(10, self.root.destroy)
                return

            self.root.title(f"Chat RMI - {self.nickname}")
            self.status_label.config(text="Conectando...")

            # Consultar se é admin (para preparar a GUI)
            try:
                self.is_admin = self.server.is_admin(self.nickname)
            except Exception:
                self.is_admin = False

            # Criar objeto callback e daemon thread
            self.callback_obj = ChatCallback()
            self.callback_obj.set_queue(self.message_queue)

            self.pyro_thread = PyroDaemonThread(self.callback_obj)
            self.pyro_thread.start()

            # Esperar URI ficar pronto (timeout razoável)
            self.pyro_thread.ready_event.wait(timeout=5)
            if not self.pyro_thread.uri:
                raise Exception("Falha ao iniciar o daemon do cliente. URI não foi criado.")

            callback_uri = self.pyro_thread.uri
            print(f"[connect] Callback URI: {callback_uri}")

            # Registrar no servidor: enviamos o proxy do callback, que o servidor usará para callbacks
            # criamos um Proxy para o callback_uri para enviar (ou enviar a string uri também funciona)
            callback_proxy = Pyro5.api.Proxy(callback_uri)
            registered = self.server.register(self.nickname, callback_proxy)

            if registered:
                self.append_message("[Servidor] Conectado com sucesso ao chat.")
            else:
                self.append_message(f"[Servidor] Aguardando aprovação para '{self.nickname}'.")

            # Se for admin, ativa a aba admin
            if self.is_admin:
                self.setup_admin_tab()
                self.tab_control.add(self.admin_tab, text="Admin")

            # marca conectado e inicia processos periódicos
            self.status_label.config(text=f"Conectado como {self.nickname}" + (" (admin)" if self.is_admin else ""))
            self.root.after(100, self.process_queue)
            # solicita listas imediatamente
            self.request_user_list()
            if self.is_admin:
                self.request_pending_list()
            # requests periódicos
            self.root.after(self.USER_REFRESH_MS, self.periodic_refresh)

        except Pyro5.errors.NamingError as e:
            messagebox.showerror("Erro NS", f"Não foi possível localizar o Name Server: {e}")
            self.root.after(10, self.root.destroy)
        except Exception as e:
            messagebox.showerror("Erro Conexão", f"Erro ao conectar ao servidor: {e}")
            print("Detalhe:", e)
            self.root.after(10, self.root.destroy)

    # --------------------------
    # Admin tab setup
    # --------------------------
    def setup_admin_tab(self):
        # Build content inside self.admin_tab
        frame = self.admin_tab
        # Top: pendentes
        tk.Label(frame, text="Usuários Aguardando Aprovação").pack(anchor="nw", padx=6, pady=(6,0))
        self.pending_listbox = tk.Listbox(frame, height=8)
        self.pending_listbox.pack(fill=tk.X, padx=6, pady=(0,6))

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=6, pady=(0,6))
        approve_btn = tk.Button(btn_frame, text="Aprovar Selecionado", command=self.approve_selected)
        approve_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,4))
        ban_btn = tk.Button(btn_frame, text="Banir Selecionado", command=self.ban_selected_from_admin)
        ban_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4,0))

        # Abaixo, lista de online (reutilizamos a listbox principal para simplicidade)
        tk.Label(frame, text="Usuários Online (Admin)").pack(anchor="nw", padx=6, pady=(6,0))
        # cria outra listbox para admin view of online users
        self.admin_online_listbox = tk.Listbox(frame, height=8)
        self.admin_online_listbox.pack(fill=tk.X, padx=6, pady=(0,6))

    # --------------------------
    # Processamento da fila de mensagens (GUI thread)
    # --------------------------
    def process_queue(self):
        if not self.root.winfo_exists():
            return
        try:
            while not self.message_queue.empty():
                kind, payload = self.message_queue.get_nowait()
                if kind == "message":
                    self.handle_incoming_message(payload)
                elif kind == "update_users":
                    self.request_user_list()
                elif kind == "update_pending":
                    if self.is_admin:
                        self.request_pending_list()
                elif kind == "user_list":
                    self.update_user_list_display(payload)
                elif kind == "pending_list":
                    self.update_pending_list_display(payload)
        except queue.Empty:
            pass
        finally:
            # re-agenda
            self.root.after(100, self.process_queue)

    def handle_incoming_message(self, message: str):
        # Decide se a mensagem vai para Geral ou Grupo (simples heurística: se contém '(Grupo)' vai pro grupo)
        if "(Grupo)" in message:
            self.append_message_to_widget(self.chat_group_text, message)
        else:
            self.append_message(message)
        # Atualiza listas se necessário (algumas mensagens já disparam update_users via callback)

    # --------------------------
    # UI helpers
    # --------------------------
    def append_message(self, text: str):
        self.append_message_to_widget(self.chat_text, text)

    def append_message_to_widget(self, widget: tk.Text, text: str):
        widget.config(state="normal")
        widget.insert(tk.END, text + "\n")
        widget.config(state="disabled")
        widget.see(tk.END)

    # --------------------------
    # Envio de mensagens
    # --------------------------
    def on_send_clicked(self):
        msg = self.entry_var.get().strip()
        if not msg:
            return
        self.entry_var.set("")

        # Se existe um destinatário selecionado (e não é "Todos"), envia PM
        recipient = self.selected_recipient.get()
        if recipient:
            # envia como private message
            t = threading.Thread(target=self._thread_private_message, args=(recipient, msg))
            t.daemon = True
            t.start()
            self.append_message(f"[Para {recipient} (Privado)] {msg}")
            return

        # Se a aba atual for Grupo, manda como "(Grupo)"
        current = self.tab_control.tab(self.tab_control.select(), "text")
        if current == "Grupo":
            t = threading.Thread(target=self._thread_broadcast_group, args=(msg,))
            t.daemon = True
            t.start()
            self.append_message_to_widget(self.chat_group_text, f"[Você (Grupo)] {msg}")
        else:
            t = threading.Thread(target=self._thread_broadcast_general, args=(msg,))
            t.daemon = True
            t.start()
            self.append_message(f"[Você] {msg}")

    def _thread_broadcast_general(self, msg):
        proxy = None
        try:
            proxy = Pyro5.api.Proxy(self.server_uri_str)
            proxy.broadcast(self.nickname, msg, exclude=[self.nickname])
        except Exception as e:
            print("[send] Erro broadcast:", e)
            self.append_message(f"[Sistema] Erro ao enviar broadcast: {e}")
        finally:
            if proxy:
                proxy._pyroRelease()

    def _thread_broadcast_group(self, msg):
        # Implementa broadcast mas com etiqueta (Grupo). O servidor continua recebendo 'broadcast' — etiqueta é só visual aqui.
        proxy = None
        try:
            proxy = Pyro5.api.Proxy(self.server_uri_str)
            proxy.broadcast(self.nickname, f"(Grupo) {msg}", exclude=[self.nickname])
        except Exception as e:
            print("[send group] Erro:", e)
            self.append_message(f"[Sistema] Erro ao enviar mensagem ao grupo: {e}")
        finally:
            if proxy:
                proxy._pyroRelease()

    def _thread_private_message(self, recipient, msg):
        proxy = None
        try:
            proxy = Pyro5.api.Proxy(self.server_uri_str)
            proxy.private_message(self.nickname, recipient, msg)
        except Exception as e:
            print("[pm] Erro:", e)
            self.append_message(f"[Sistema] Erro ao enviar PM para {recipient}: {e}")
        finally:
            if proxy:
                proxy._pyroRelease()

    # --------------------------
    # Lista de usuários / pendentes
    # --------------------------
    def request_user_list(self):
        t = threading.Thread(target=self._thread_get_users)
        t.daemon = True
        t.start()

    def _thread_get_users(self):
        proxy = None
        try:
            proxy = Pyro5.api.Proxy(self.server_uri_str)
            users = proxy.get_users()
            self.message_queue.put(("user_list", users))
        except Exception as e:
            print("[request_user_list] Erro:", e)
        finally:
            if proxy:
                proxy._pyroRelease()

    def update_user_list_display(self, users):
        # atualiza listbox principal e admin online listbox
        self.user_listbox.delete(0, tk.END)
        for u in sorted(users):
            self.user_listbox.insert(tk.END, u)
        if self.is_admin and hasattr(self, "admin_online_listbox"):
            self.admin_online_listbox.delete(0, tk.END)
            for u in sorted(users):
                self.admin_online_listbox.insert(tk.END, u)

    def request_pending_list(self):
        if not self.is_admin:
            return
        t = threading.Thread(target=self._thread_get_pending)
        t.daemon = True
        t.start()

    def _thread_get_pending(self):
        proxy = None
        try:
            proxy = Pyro5.api.Proxy(self.server_uri_str)
            pending = proxy.get_pending_users()
            self.message_queue.put(("pending_list", pending))
        except Exception as e:
            print("[request_pending_list] Erro:", e)
        finally:
            if proxy:
                proxy._pyroRelease()

    def update_pending_list_display(self, pending):
        if not self.is_admin:
            return
        self.pending_listbox.delete(0, tk.END)
        for u in sorted(pending):
            self.pending_listbox.insert(tk.END, u)

    # --------------------------
    # Ações admin: aprovar / banir
    # --------------------------
    def approve_selected(self):
        selected = self.pending_listbox.curselection()
        if not selected:
            messagebox.showinfo("Aprovar", "Selecione um usuário pendente para aprovar.")
            return
        user = self.pending_listbox.get(selected[0])
        if messagebox.askyesno("Aprovar", f"Deseja aprovar '{user}'?"):
            t = threading.Thread(target=self._thread_approve, args=(user,))
            t.daemon = True
            t.start()

    def _thread_approve(self, user):
        proxy = None
        try:
            proxy = Pyro5.api.Proxy(self.server_uri_str)
            proxy.approve_client(self.nickname, user)
            # após aprovar, requisita listas
            self.request_pending_list()
            self.request_user_list()
        except Exception as e:
            print("[approve] Erro:", e)
            self.append_message(f"[Sistema] Erro ao aprovar {user}: {e}")
        finally:
            if proxy:
                proxy._pyroRelease()

    def ban_selected_from_admin(self):
        sel = self.admin_online_listbox.curselection()
        pending_sel = self.pending_listbox.curselection()
        target = None
        if sel:
            target = self.admin_online_listbox.get(sel[0])
        elif pending_sel:
            target = self.pending_listbox.get(pending_sel[0])
        if not target:
            messagebox.showinfo("Banir", "Selecione um usuário online ou pendente para banir.")
            return
        if target == self.nickname:
            messagebox.showwarning("Banir", "Você não pode banir a si mesmo.")
            return
        if messagebox.askyesno("Banir", f"Deseja banir '{target}'? Ele será desconectado."):
            t = threading.Thread(target=self._thread_ban, args=(target,))
            t.daemon = True
            t.start()

    def _thread_ban(self, target):
        proxy = None
        try:
            proxy = Pyro5.api.Proxy(self.server_uri_str)
            proxy.ban_client(self.nickname, target)
            # refresh
            self.request_pending_list()
            self.request_user_list()
        except Exception as e:
            print("[ban] Erro:", e)
            self.append_message(f"[Sistema] Erro ao banir {target}: {e}")
        finally:
            if proxy:
                proxy._pyroRelease()

    def ban_selected_quick(self):
        # Banir a seleção na user_listbox (rápido, não exige admin tab)
        sel = self.user_listbox.curselection()
        if not sel:
            messagebox.showinfo("Banir", "Selecione um usuário online para banir (admin apenas).")
            return
        user = self.user_listbox.get(sel[0])
        if user == self.nickname:
            messagebox.showwarning("Banir", "Você não pode banir a si mesmo.")
            return
        if messagebox.askyesno("Banir", f"Deseja banir '{user}'?"):
            t = threading.Thread(target=self._thread_ban, args=(user,))
            t.daemon = True
            t.start()

    # --------------------------
    # Eventos UI
    # --------------------------
    def on_user_select(self, event):
        if not self.user_listbox.curselection():
            return
        idx = self.user_listbox.curselection()[0]
        user = self.user_listbox.get(idx)
        # Alterna seleção de destinatário (se já selecionado, desmarca)
        if self.selected_recipient.get() == user:
            self.selected_recipient.set("")  # desemparelha
        else:
            self.selected_recipient.set(user)

    # --------------------------
    # Periodic refresh
    # --------------------------
    def periodic_refresh(self):
        if not self.root.winfo_exists():
            return
        self.request_user_list()
        if self.is_admin:
            self.request_pending_list()
        # re-agenda
        self.root.after(self.USER_REFRESH_MS, self.periodic_refresh)

    # --------------------------
    # Fechamento / cleanup
    # --------------------------
    def shutdown(self):
        try:
            if self.server and self.nickname:
                # tentar desregistrar
                try:
                    self.server.unregister(self.nickname)
                except Exception:
                    pass
            if self.pyro_thread:
                self.pyro_thread.shutdown()
                # join para tentar aguardar a thread encerrar (curto timeout)
                self.pyro_thread.join(timeout=1.0)
        except Exception as e:
            print("[shutdown] Erro:", e)

    def on_close(self):
        if messagebox.askokcancel("Sair", "Deseja realmente sair?"):
            self.shutdown()
            self.root.destroy()

# --------------------------
# Execução principal
# --------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    # Bind close
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
