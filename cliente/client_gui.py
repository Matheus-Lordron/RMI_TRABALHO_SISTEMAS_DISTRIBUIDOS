# ==================================================
# client/client_gui.py  (ESTILIZADO)
# ==================================================

import tkinter as tk
from tkinter import ttk, messagebox, font
import Pyro5.api
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
        self.lbl_header = tk.Label(header, text=f"⚪ {other}", bg=COLOR_BTN, fg="white", font=("Segoe UI", 14, "bold"))
        self.lbl_header.pack(pady=10, padx=10, anchor="w")

        self.create_widgets()
        self.load_conversation()
        self.update_status()

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
        icon = "🟢" if online else "⚪"
        self.lbl_header.config(text=f"{icon} {self.other}")
        self.master.after(5000, self.update_status)

# =================== MAIN CHAT GUI ===================

class MainChatGUI:
    def __init__(self, master, server, username):
        self.master = master
        self.server = server
        self.username = username

        self.master.title(f"WhatsUT")
        self.master.geometry("800x600")
        self.master.configure(bg=COLOR_BG_APP)

        self.create_widgets()
        self.load_users()
        self._presence_loop()

    def create_widgets(self):
        # Header
        header = tk.Frame(self.master, bg=COLOR_BTN, height=60)
        header.pack(fill="x")
        
        tk.Label(header, text=f"Bem-vindo, {self.username}", bg=COLOR_BTN, fg="white", 
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=20, pady=10)
        
        tk.Button(header, text="Sair", bg="#d32f2f", fg="white", relief="flat", 
                  command=self.logout).pack(side="right", padx=20)

        # Container Principal
        container = tk.Frame(self.master, bg=COLOR_BG_APP)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Coluna da Esquerda (Lista de Usuários)
        left_frame = tk.Frame(container, bg="white", width=250)
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False) # Força o tamanho

        tk.Label(left_frame, text="Contatos", bg="white", fg="#555", 
                 font=("Segoe UI", 12, "bold")).pack(pady=10, anchor="w", padx=10)

        self.user_list = tk.Listbox(left_frame, font=("Segoe UI", 11), bg="white", bd=0, 
                                    highlightthickness=0, selectbackground=COLOR_BG_APP, selectforeground="black")
        self.user_list.pack(fill="both", expand=True, padx=5, pady=5)
        self.user_list.bind("<Double-Button-1>", self.open_chat_on_double_click)

        # Botão atualizar lista
        tk.Button(left_frame, text="Atualizar Lista", bg="#eee", relief="flat", 
                  command=self.load_users).pack(fill="x", padx=5, pady=5)

        # Coluna da Direita (Placeholder ou área de ação)
        right_frame = tk.Frame(container, bg="#f8f9fa")
        right_frame.pack(side="right", fill="both", expand=True, padx=(20, 0))

        # Mensagem de "Selecione um chat"
        self.placeholder_lbl = tk.Label(right_frame, text="Selecione um contato ao lado\npara iniciar uma conversa", 
                                        bg="#f8f9fa", fg="#aaa", font=("Segoe UI", 16))
        self.placeholder_lbl.place(relx=0.5, rely=0.5, anchor="center")

        btn_open = tk.Button(right_frame, text="Abrir Chat Selecionado", bg=COLOR_BTN, fg="white", 
                             font=("Segoe UI", 11), relief="flat", command=self.open_selected_chat)
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
                icon = "🟢" if status_map.get(uname, False) else "⚪"
                display = f"{icon} {uname}"
                if banned:
                    display += " (banido)"
                
                self.user_list.insert(tk.END, display)

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar usuários: {e}")

    def get_selected_username(self):
        sel = self.user_list.get(tk.ACTIVE)
        if not sel:
            return None
        if sel.startswith("👤 "):
            sel = sel.replace("👤 ", "")
        if sel.startswith("🟢 "):
            sel = sel.replace("🟢 ", "")
        if sel.startswith("⚪ "):
            sel = sel.replace("⚪ ", "")
        return sel.split(" ")[0]

    def open_selected_chat(self):
        other = self.get_selected_username()
        if not other:
            messagebox.showwarning("Aviso", "Selecione um usuário.")
            return
        self.open_chat_window(other)

    def open_chat_on_double_click(self, event):
        self.open_selected_chat()

    def open_chat_window(self, other_username):
        chat_root = tk.Toplevel(self.master)
        ChatWindow(chat_root, self.server, self.username, other_username)

    def logout(self):
        try:
            self.server.set_offline(self.username)
        except Exception:
            pass
        self.master.destroy()

    def _presence_loop(self):
        try:
            self.server.heartbeat(self.username)
        except Exception:
            pass
        self.master.after(20000, self._presence_loop)

# =================== START APP ===================

def start_app():
    root = tk.Tk()
    LoginGUI(root)
    root.mainloop()

if __name__ == "__main__":
    start_app()
