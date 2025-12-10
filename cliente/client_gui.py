# ==================================================
# client/client_gui.py  (ESTILIZADO)
# ==================================================

import tkinter as tk
from tkinter import ttk, messagebox, font
import Pyro5.api
import Pyro5.server
import threading
from datetime import datetime

SERVER_NAME = "PYRONAME:whatsut.server"

# --- Paleta de Cores (Estilo similar ao WhatsApp Web) ---
COLOR_BG_APP = "#f0f2f5"      # Fundo geral
COLOR_BG_CHAT = "#efeae2"     # Fundo da área de conversa
COLOR_MY_MSG = "#d9fdd3"      # Verde claro (minhas mensagens)
COLOR_OTHER_MSG = "#ffffff"   # Branco (mensagens do outro)
COLOR_BTN = "#008069"         # Verde botão
COLOR_BTN_TEXT = "#ffffff"    # Texto do botão
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
COLOR_ONLINE = "#21a365"
COLOR_OFFLINE = "#8e9ba3"

# =================== LOGIN GUI ===================

class LoginGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("WhatsUT - Login")
        self.master.geometry("350x300")
        self.master.resizable(False, False)
        self.master.configure(bg=COLOR_BG_APP)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Configurar estilos globais
        self.style.configure("TFrame", background=COLOR_BG_APP)
        self.style.configure("TLabel", background=COLOR_BG_APP, font=FONT_MAIN)
        self.style.configure("TButton", font=FONT_BOLD, padding=6)

        self.create_widgets()
        self.connect_server()

    def connect_server(self):
        try:
            self.server = Pyro5.api.Proxy(SERVER_NAME)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível conectar ao servidor: {e}")
            self.master.destroy()

    def create_widgets(self):
        frame = ttk.Frame(self.master, padding=20)
        frame.pack(expand=True)

        ttk.Label(frame, text="WhatsUT", font=("Segoe UI", 20, "bold"), foreground=COLOR_BTN).pack(pady=(0, 20))

        ttk.Label(frame, text="Usuário:").pack(anchor="w")
        self.entry_user = ttk.Entry(frame, width=35, font=FONT_MAIN)
        self.entry_user.pack(pady=(2, 10))

        ttk.Label(frame, text="Senha:").pack(anchor="w")
        self.entry_pass = ttk.Entry(frame, width=35, show="•", font=FONT_MAIN)
        self.entry_pass.pack(pady=(2, 20))

        # Botão personalizado
        btn_login = tk.Button(frame, text="ENTRAR", bg=COLOR_BTN, fg=COLOR_BTN_TEXT, 
                              font=FONT_BOLD, relief="flat", command=self.try_login)
        btn_login.pack(fill="x", pady=5)

        btn_reg = tk.Button(frame, text="Registrar", bg="#ffffff", fg=COLOR_BTN, 
                            font=FONT_MAIN, relief="groove", command=self.register)
        btn_reg.pack(fill="x")

    def try_login(self):
        user = self.entry_user.get().strip()
        passwd = self.entry_pass.get().strip()

        if not user or not passwd:
            messagebox.showwarning("Aviso", "Preencha todos os campos.")
            return

        try:
            auth, msg = self.server.login(user, passwd)
            if auth:
                self.master.destroy()
                root = tk.Tk()
                MainChatGUI(root, self.server, user)
                root.mainloop()
            else:
                messagebox.showerror("Erro", msg)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao conectar: {e}")

    def register(self):
        user = self.entry_user.get().strip()
        passwd = self.entry_pass.get().strip()
        if not user or not passwd:
            messagebox.showwarning("Aviso", "Preencha usuário e senha.")
            return
        try:
            success = self.server.register(user, passwd)
            if success:
                messagebox.showinfo("Registro", "Usuário registrado com sucesso!")
            else:
                messagebox.showerror("Erro", "Nome de usuário já existe.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao registrar: {e}")

# =================== CHAT WINDOW (ESTILIZADA) ===================

class ChatWindow:
    def __init__(self, master, server, me, other):
        self.master = master
        self.server = server
        self.me = me
        self.other = other

        self.master.title(f"Conversa com {other}")
        self.master.geometry("600x500")
        self.master.configure(bg=COLOR_BG_CHAT)
        
        # Ícone ou título estilizado
        header = tk.Frame(self.master, bg=COLOR_BTN, height=50)
        header.pack(fill="x")
        self.status_canvas = tk.Canvas(header, width=14, height=14, bg=COLOR_BTN, highlightthickness=0)
        self.status_canvas.pack(side="left", padx=(10, 0), pady=18)
        self.lbl_header = tk.Label(header, text=other, bg=COLOR_BTN, fg="white", font=("Segoe UI", 14, "bold"))
        self.lbl_header.pack(side="left", padx=10, pady=10, anchor="w")

        self.create_widgets()
        self.load_conversation()
        self.update_status()
        self._chat_refresh_loop()

    def create_widgets(self):
        # --- 1. BARRA INFERIOR (INPUT) ---
        # Criamos e empacotamos a barra inferior PRIMEIRO com side="bottom".
        # Isso garante que ela reserve o espaço dela no rodapé da janela.
        bottom = tk.Frame(self.master, bg=COLOR_BG_APP, height=60)
        bottom.pack(side="bottom", fill="x")

        self.entry_msg = tk.Entry(bottom, font=("Segoe UI", 11), relief="flat", bg="white")
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=10, pady=10, ipady=5)
        self.entry_msg.bind("<Return>", lambda e: self.send_message())

        btn_send = tk.Button(bottom, text="➤", bg=COLOR_BTN, fg="white", 
                             font=("Segoe UI", 12), relief="flat", command=self.send_message)
        btn_send.pack(side="left", padx=(0, 10))

        btn_refresh = tk.Button(bottom, text="↻", bg="#cccccc", fg="black", 
                                font=("Segoe UI", 10), relief="flat", command=self.load_conversation)
        btn_refresh.pack(side="left", padx=(0, 10))

        # --- 2. ÁREA DE CHAT (CENTRO) ---
        # Agora empacotamos o chat. Como a barra de baixo já pegou o espaço dela,
        # o chat vai ocupar apenas o "resto" disponível.
        frame_chat = tk.Frame(self.master, bg=COLOR_BG_CHAT)
        frame_chat.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        self.chat_area = tk.Text(frame_chat, state="disabled", wrap="word", 
                                 bg=COLOR_BG_CHAT, relief="flat", font=FONT_MAIN, padx=10, pady=10)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_chat, command=self.chat_area.yview)
        self.chat_area.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.chat_area.pack(side="left", fill="both", expand=True)

        # CONFIGURAÇÃO DAS TAGS
        self.chat_area.tag_config("me", justify="right", rmargin=10, lmargin1=100, lmargin2=100, 
                                  background=COLOR_MY_MSG, foreground="black", spacing1=5, spacing3=5)
        
        self.chat_area.tag_config("other", justify="left", lmargin1=10, lmargin2=10, rmargin=100,
                                  background=COLOR_OTHER_MSG, foreground="black", spacing1=5, spacing3=5)
        
        self.chat_area.tag_config("meta", justify="center", foreground="#888888", font=("Segoe UI", 8))

    def load_conversation(self):
        try:
            conv = self.server.get_conversation(self.me, self.other)
            self.chat_area.config(state="normal")
            self.chat_area.delete(1.0, tk.END)

            current_date = ""

            for sender, receiver, content, ts in conv:
                # Exibir data se mudou o dia (opcional, simplificado aqui mostra timestamp no bubble)
                tag = "me" if sender == self.me else "other"
                
                # Formatando visualmente: "Mensagem \n [Hora]"
                display_text = f"{content}\n"
                
                # Inserir o texto da mensagem com a tag de cor de fundo
                self.chat_area.insert(tk.END, " " + display_text + " ", tag)
                self.chat_area.insert(tk.END, f"{ts}\n\n", tag) # Timestamp dentro do bloco

            self.chat_area.config(state="disabled")
            self.chat_area.see(tk.END)
        except Exception as e:
            print(f"Erro load: {e}") # Print no console para não spamar popup

    def send_message(self):
        text = self.entry_msg.get().strip()
        if not text:
            return
        try:
            ok = self.server.send_message(self.me, self.other, text)
            if ok:
                self.entry_msg.delete(0, tk.END)
                self.load_conversation()
            else:
                messagebox.showerror("Erro", "Falha ao enviar.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao enviar: {e}")

    def update_status(self):
        try:
            online = self.server.is_online(self.other)
        except Exception:
            online = False
        self._draw_status(online)
        self.master.after(5000, self.update_status)

    def _draw_status(self, online):
        self.status_canvas.delete("all")
        color = COLOR_ONLINE if online else COLOR_OFFLINE
        self.status_canvas.create_oval(0, 0, 14, 14, fill=color, outline=color)

    def _chat_refresh_loop(self):
        try:
            self.load_conversation()
        except Exception:
            pass
        self.master.after(1000, self._chat_refresh_loop)

# =================== MAIN CHAT GUI ===================

class MainChatGUI:
    def __init__(self, master, server, username):
        self.master = master
        self.server = server
        self.username = username
        self.open_chats = {}

        self.master.title(f"WhatsUT")
        self.master.geometry("800x600")
        self.master.configure(bg=COLOR_BG_APP)

        self.create_widgets()
        self.load_users()
        self.master.after(500, lambda: self._presence_loop())
        self.master.after(500, lambda: self._start_callback())
        self.load_groups()

    def create_widgets(self):
        # Header
        header = tk.Frame(self.master, bg=COLOR_BTN, height=60)
        header.pack(fill="x")
        
        tk.Label(header, text=f"Bem-vindo, {self.username}", bg=COLOR_BTN, fg="white", 
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=20, pady=10)
        
        def _do_logout():
            self.logout()
        tk.Button(header, text="Sair", bg="#d32f2f", fg="white", relief="flat", 
                  command=_do_logout).pack(side="right", padx=20)

        # Container Principal
        container = tk.Frame(self.master, bg=COLOR_BG_APP)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Coluna da Esquerda (Lista de Usuários e Grupos) - COM SCROLL
        left_frame = tk.Frame(container, bg="white", width=280)
        left_frame.pack(side="left", fill="both", expand=False)
        left_frame.pack_propagate(False)

        # Canvas e Scrollbar para toda a coluna esquerda
        canvas = tk.Canvas(left_frame, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # ===== SEÇÃO DE CONTATOS =====
        contacts_section = tk.Frame(scrollable_frame, bg="white")
        contacts_section.pack(fill="x", pady=(10, 5))

        tk.Label(contacts_section, text="Contatos", bg="white", fg="#555", 
                 font=("Segoe UI", 12, "bold")).pack(pady=5, anchor="w", padx=10)

        self.user_list = tk.Listbox(contacts_section, font=("Segoe UI", 10), bg="white", bd=0, 
                                    highlightthickness=0, selectbackground=COLOR_BG_APP, 
                                    selectforeground="black", height=6)
        self.user_list.pack(fill="x", padx=10, pady=5)
        self.user_list.bind("<Double-Button-1>", lambda e: self.open_selected_chat())

        tk.Button(contacts_section, text="Atualizar Lista", bg="#eee", relief="flat", 
                  font=("Segoe UI", 9), command=self.load_users).pack(fill="x", padx=10, pady=5)

        # ===== SEPARADOR =====
        separator = tk.Frame(scrollable_frame, bg="#ddd", height=1)
        separator.pack(fill="x", padx=10, pady=10)

        # ===== SEÇÃO DE GRUPOS =====
        groups_section = tk.Frame(scrollable_frame, bg="white")
        groups_section.pack(fill="x", pady=(5, 10))

        tk.Label(groups_section, text="Grupos", bg="white", fg="#555", 
                 font=("Segoe UI", 12, "bold")).pack(pady=5, anchor="w", padx=10)

        # Lista de grupos
        self.group_list = tk.Listbox(groups_section, font=("Segoe UI", 10), bg="white", 
                                     bd=1, relief="solid", highlightthickness=0,
                                     selectbackground=COLOR_BG_APP, selectforeground="black", 
                                     height=5)
        self.group_list.pack(fill="x", padx=10, pady=5)

        # Botões de grupos
        btn_style = {"bg": "#eee", "relief": "flat", "font": ("Segoe UI", 9)}
        btn_primary_style = {"bg": COLOR_BTN, "fg": "white", "relief": "flat", "font": ("Segoe UI", 9, "bold")}

        tk.Button(groups_section, text="Atualizar Grupos", command=self.load_groups, 
                  **btn_style).pack(fill="x", padx=10, pady=3)
        
        tk.Button(groups_section, text="Criar Grupo", command=self.create_group, 
                  **btn_primary_style).pack(fill="x", padx=10, pady=3)
        
        tk.Button(groups_section, text="Entrar no Grupo", command=self.request_join_group, 
                  **btn_primary_style).pack(fill="x", padx=10, pady=3)
        
        tk.Button(groups_section, text="Adicionar Usuário", command=self.add_user_to_group, 
                  **btn_primary_style).pack(fill="x", padx=10, pady=3)
        
        tk.Button(groups_section, text="Excluir Grupo", command=self.delete_group, 
                  **btn_style).pack(fill="x", padx=10, pady=3)
        
        tk.Button(groups_section, text="Solicitações", command=self.open_group_requests, 
                  **btn_style).pack(fill="x", padx=10, pady=3)
        
        tk.Button(groups_section, text="Abrir Chat do Grupo", command=self.open_group_chat, 
                  **btn_primary_style).pack(fill="x", padx=10, pady=(3, 15))

        # Empacotar canvas e scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Habilitar scroll com mouse wheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ===== Coluna da Direita (Área de mensagens) =====
        right_frame = tk.Frame(container, bg="#f8f9fa")
        right_frame.pack(side="right", fill="both", expand=True, padx=(20, 0))

        # Mensagem de "Selecione um chat"
        self.placeholder_lbl = tk.Label(right_frame, 
                                        text="Selecione um contato ao lado\npara iniciar uma conversa", 
                                        bg="#f8f9fa", fg="#aaa", font=("Segoe UI", 16))
        self.placeholder_lbl.place(relx=0.5, rely=0.5, anchor="center")

        btn_open = tk.Button(right_frame, text="Abrir Chat Selecionado", bg=COLOR_BTN, 
                             fg="white", font=("Segoe UI", 11), relief="flat", 
                             command=self.open_selected_chat)
        btn_open.pack(side="bottom", pady=20)

    def load_users(self):
        try:
            users = self.server.list_users()
            try:
                status_map = dict(self.server.get_status_map())
            except Exception:
                status_map = {}
            self.user_list.delete(0, tk.END)

            for uid, uname, banned in users:
                if uname == self.username:
                    continue # Não mostra a si mesmo na lista de contatos para chat
                display = uname
                if banned:
                    display += " (banido)"
                self.user_list.insert(tk.END, display)
                idx = self.user_list.size() - 1
                color = COLOR_ONLINE if status_map.get(uname, False) else COLOR_OFFLINE
                try:
                    self.user_list.itemconfig(idx, fg=color)
                except Exception:
                    pass

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar usuários: {e}")

    def load_groups(self):
        try:
            data = self.server.list_groups_with_status(self.username)
            self.group_list.delete(0, tk.END)
            for name, admin_uname, status in data:
                tag = "(aprovado)" if status == "aprovado" else ("(pendente)" if status == "pendente" else "")
                disp = f"{name} {tag}".strip()
                self.group_list.insert(tk.END, disp)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar grupos: {e}")

    def get_selected_username(self):
        sel = self.user_list.get(tk.ACTIVE)
        if not sel:
            return None
        return sel.split(" ")[0]

    def open_selected_chat(self):
        other = self.get_selected_username()
        if not other:
            messagebox.showwarning("Aviso", "Selecione um usuário.")
            return
        self.open_chat_window(other)

    def get_selected_group(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel:
            return None
        return sel.split(" ")[0]

    def request_join_group(self):
        g = self.get_selected_group()
        if not g:
            messagebox.showwarning("Aviso", "Selecione um grupo.")
            return
        try:
            ok = self.server.request_join_group(self.username, g)
            if ok:
                messagebox.showinfo("Grupo", "Solicitação enviada.")
                self.load_groups()
            else:
                messagebox.showerror("Erro", "Falha ao solicitar entrada.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha: {e}")

    def create_group(self):
        win = tk.Toplevel(self.master)
        win.title("Criar Grupo")
        frm = tk.Frame(win)
        frm.pack(padx=10, pady=10)
        tk.Label(frm, text="Nome do grupo").pack(anchor="w")
        entry = tk.Entry(frm, width=28)
        entry.pack(pady=(2, 10))
        def _do_create():
            name = entry.get().strip()
            if not name:
                return
            try:
                ok = self.server.create_group(self.username, name)
                if ok:
                    self.load_groups()
                    win.destroy()
                else:
                    messagebox.showerror("Erro", "Falha ao criar grupo.")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha: {e}")
        tk.Button(frm, text="Criar", bg=COLOR_BTN, fg="white", relief="flat", command=_do_create).pack(fill="x")

    def open_group_requests(self):
        g = self.get_selected_group()
        if not g:
            messagebox.showwarning("Aviso", "Selecione um grupo.")
            return
        try:
            pend = self.server.list_pending_requests(self.username, g)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao buscar solicitações: {e}")
            return
        win = tk.Toplevel(self.master)
        win.title(f"Solicitações - {g}")
        lb = tk.Listbox(win, font=("Segoe UI", 11))
        lb.pack(fill="both", expand=True, padx=10, pady=10)
        for u in pend:
            lb.insert(tk.END, u)
        def approve():
            sel = lb.get(tk.ACTIVE)
            if not sel:
                return
            try:
                ok = self.server.approve_member(self.username, g, sel)
                if ok:
                    lb.delete(tk.ACTIVE)
                    self.load_groups()
                else:
                    messagebox.showerror("Erro", "Não foi possível aprovar.")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha: {e}")
        tk.Button(win, text="Aprovar", bg=COLOR_BTN, fg="white", relief="flat", command=approve).pack(pady=10)

    def add_user_to_group(self):
        g = self.get_selected_group()
        if not g:
            messagebox.showwarning("Aviso", "Selecione um grupo.")
            return
        win = tk.Toplevel(self.master)
        win.title(f"Adicionar Usuário - {g}")
        frm = tk.Frame(win)
        frm.pack(padx=10, pady=10)
        tk.Label(frm, text="Username do usuário").pack(anchor="w")
        entry = tk.Entry(frm, width=28)
        entry.pack(pady=(2, 10))
        def _do_add():
            uname = entry.get().strip()
            if not uname:
                return
            try:
                ok = self.server.add_member_direct(self.username, g, uname)
                if ok:
                    messagebox.showinfo("Grupo", "Usuário adicionado.")
                    self.load_groups()
                    win.destroy()
                else:
                    messagebox.showerror("Erro", "Falha ao adicionar. Verifique se você é admin.")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha: {e}")
        tk.Button(frm, text="Adicionar", bg=COLOR_BTN, fg="white", relief="flat", command=_do_add).pack(fill="x")

    def delete_group(self):
        g = self.get_selected_group()
        if not g:
            messagebox.showwarning("Aviso", "Selecione um grupo.")
            return
        if not messagebox.askyesno("Confirmar", f"Excluir o grupo '{g}'?"):
            return
        try:
            ok = self.server.delete_group(self.username, g)
            if ok:
                messagebox.showinfo("Grupo", "Grupo excluído.")
                self.load_groups()
            else:
                messagebox.showerror("Erro", "Falha ao excluir. Verifique se você é admin.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha: {e}")

    def open_group_chat(self):
        g = self.get_selected_group()
        if not g:
            messagebox.showwarning("Aviso", "Selecione um grupo.")
            return
        try:
            data = dict((name, status) for name, _, status in self.server.list_groups_with_status(self.username))
            st = data.get(g)
            if st != "aprovado":
                messagebox.showwarning("Aviso", "Você não é membro aprovado do grupo.")
                return
        except Exception:
            pass
        chat_root = tk.Toplevel(self.master)
        GroupChatWindow(chat_root, self.server, self.username, g)

    def open_chat_window(self, other_username):
        chat_root = tk.Toplevel(self.master)
        win = ChatWindow(chat_root, self.server, self.username, other_username)
        self.open_chats[other_username] = win

    def logout(self):
        try:
            self.server.set_offline(self.username)
            try:
                self.server.unregister_callback(self.username)
            except Exception:
                pass
        except Exception:
            pass
        self.master.destroy()

    def _safe_logout(self):
        try:
            self.logout()
        except Exception:
            try:
                self.master.destroy()
            except Exception:
                pass

    def _presence_loop(self):
        try:
            self.server.heartbeat(self.username)
        except Exception:
            pass
        self.master.after(20000, self._presence_loop)

    def _start_callback(self):
        class ClientCallback:
            def __init__(self, gui):
                self.gui = gui
            @Pyro5.server.expose
            def notify_private(self, sender, receiver):
                def _upd():
                    other = sender if sender != self.gui.username else receiver
                    w = self.gui.open_chats.get(other)
                    if w:
                        w.load_conversation()
                self.gui.master.after(0, _upd)
        self._daemon = Pyro5.server.Daemon()
        self._cb = ClientCallback(self)
        self._cb_uri = self._daemon.register(self._cb)
        threading.Thread(target=self._daemon.requestLoop, daemon=True).start()
        try:
            self.server.register_callback(self.username, self._cb_uri)
        except Exception:
            pass

class GroupChatWindow:
    def __init__(self, master, server, me, group_name):
        self.master = master
        self.server = server
        self.me = me
        self.group_name = group_name
        self._alive = True
        self.master.title(group_name)
        self.master.geometry("600x500")
        top = tk.Frame(self.master, bg=COLOR_BTN, height=50)
        top.pack(fill="x")
        tk.Label(top, text=group_name, bg=COLOR_BTN, fg="white", font=("Segoe UI", 14, "bold")).pack(side="left", padx=10, pady=10)
        bottom = tk.Frame(self.master, bg=COLOR_BG_APP, height=60)
        bottom.pack(side="bottom", fill="x")
        self.entry_msg = tk.Entry(bottom, font=("Segoe UI", 11), relief="flat", bg="white")
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=10, pady=10, ipady=5)
        self.entry_msg.bind("<Return>", lambda e: self.send_message())
        btn_send = tk.Button(bottom, text="➤", bg=COLOR_BTN, fg="white", font=("Segoe UI", 12), relief="flat", command=self.send_message)
        btn_send.pack(side="left", padx=(0, 10))
        btn_refresh = tk.Button(bottom, text="↻", bg="#cccccc", fg="black", font=("Segoe UI", 10), relief="flat", command=self.load_conversation)
        btn_refresh.pack(side="left", padx=(0, 10))
        frame_chat = tk.Frame(self.master, bg=COLOR_BG_CHAT)
        frame_chat.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        self.chat_area = tk.Text(frame_chat, state="disabled", wrap="word", bg=COLOR_BG_CHAT, relief="flat", font=FONT_MAIN, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(frame_chat, command=self.chat_area.yview)
        self.chat_area.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.chat_area.pack(side="left", fill="both", expand=True)
        self.chat_area.tag_config("me", justify="right", rmargin=10, lmargin1=100, lmargin2=100, background=COLOR_MY_MSG, foreground="black", spacing1=5, spacing3=5)
        self.chat_area.tag_config("other", justify="left", lmargin1=10, lmargin2=10, rmargin=100, background=COLOR_OTHER_MSG, foreground="black", spacing1=5, spacing3=5)
        self.load_conversation()
        self._loop()
        self.master.bind("<Destroy>", lambda e: setattr(self, "_alive", False))

    def load_conversation(self):
        try:
            conv = self.server.get_group_conversation(self.group_name)
            self.chat_area.config(state="normal")
            self.chat_area.delete(1.0, tk.END)
            for sender, content, ts in conv:
                tag = "me" if sender == self.me else "other"
                self.chat_area.insert(tk.END, " " + content + " ", tag)
                self.chat_area.insert(tk.END, f"{ts}\n\n", tag)
            self.chat_area.config(state="disabled")
            self.chat_area.see(tk.END)
        except Exception:
            pass

    def send_message(self):
        text = self.entry_msg.get().strip()
        if not text:
            return
        try:
            ok = self.server.send_group_message(self.me, self.group_name, text)
            if ok:
                self.entry_msg.delete(0, tk.END)
                self.load_conversation()
        except Exception:
            pass

    def _loop(self):
        if not getattr(self, "_alive", True):
            return
        try:
            self.load_conversation()
        except Exception:
            pass
        if getattr(self, "_alive", True):
            self.master.after(2000, self._loop)

# =================== START APP ===================

def start_app():
    root = tk.Tk()
    LoginGUI(root)
    root.mainloop()

if __name__ == "__main__":
    start_app()
