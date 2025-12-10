import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
import Pyro5.api
import Pyro5.server
import base64
import os
import threading
from datetime import datetime, timedelta  # <--- ADICIONADO timedelta

# =============================================================================
# DEFINIÇÃO DO SERVIDOR
# =============================================================================
SERVER_NAME = "PYRONAME:whatsut.server"

# Se você tiver o arquivo de constantes, tenta importar
try:
    from client_main_constants import *
except ImportError:
    print("Aviso: client_main_constants não encontrado. Usando padrão.")

# =============================================================================
# CONSTANTES VISUAIS (TEMA WHATSAPP)
# =============================================================================
THEME = {
    "primary": "#075E54",       # Verde Escuro (Header)
    "secondary": "#128C7E",     # Verde Botões/Acentos
    "bg_app": "#dcdcdc",        # Fundo atrás do app
    "bg_chat": "#e5ddd5",       # Fundo da conversa (Bege clássico)
    "bg_sidebar": "#ffffff",    # Fundo da lista de contatos
    "bubble_out": "#dcf8c6",    # Balão enviado (Verde claro)
    "bubble_in": "#ffffff",     # Balão recebido (Branco)
    "danger": "#d32f2f",        # Botões de perigo
    "text": "#000000",
    "gray_btn": "#f0f0f0"
}

FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")

class LoginGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("WhatsUT - Login")
        self.master.geometry("400x450")
        self.master.resizable(False, False)
        self.master.configure(bg=THEME["primary"])

        self.server = None
        self.create_widgets()
        self.connect_server()

    def connect_server(self):
        try:
            self.server = Pyro5.api.Proxy(SERVER_NAME)
            self.server._pyroBind()
        except Exception as e:
            messagebox.showerror("Erro Crítico", f"Servidor indisponível: {e}")
            self.master.destroy()

    def create_widgets(self):
        card = tk.Frame(self.master, bg="white", padx=30, pady=30)
        card.place(relx=0.5, rely=0.5, anchor="center", width=340, height=380)

        tk.Label(card, text="WHATSUT", font=("Segoe UI", 24, "bold"), fg=THEME["primary"], bg="white").pack(pady=(0, 30))

        tk.Label(card, text="Nome de usuário", font=FONT_BOLD, bg="white", fg="#555").pack(anchor="w")
        self.entry_user = ttk.Entry(card, font=("Segoe UI", 12))
        self.entry_user.pack(fill="x", pady=(5, 15))

        tk.Label(card, text="Senha", font=FONT_BOLD, bg="white", fg="#555").pack(anchor="w")
        self.entry_pass = ttk.Entry(card, font=("Segoe UI", 12), show="•")
        self.entry_pass.pack(fill="x", pady=(5, 20))
        self.entry_pass.bind("<Return>", lambda e: self.try_login())

        btn_entrar = tk.Button(card, text="ACESSAR", bg=THEME["secondary"], fg="white", font=("Segoe UI", 11, "bold"), relief="flat", command=self.try_login)
        btn_entrar.pack(fill="x", pady=5, ipady=5)

        btn_reg = tk.Button(card, text="Criar conta", bg="white", fg=THEME["secondary"], font=("Segoe UI", 10), relief="flat", command=self.register)
        btn_reg.pack(fill="x", pady=5)

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
            messagebox.showerror("Erro", f"Falha na comunicação: {e}")

    def register(self):
        user = self.entry_user.get().strip()
        passwd = self.entry_pass.get().strip()
        if not user or not passwd:
            messagebox.showwarning("Aviso", "Preencha usuário e senha.")
            return
        try:
            success = self.server.register(user, passwd)
            if success:
                messagebox.showinfo("Registro", "Usuário criado! Faça login.")
            else:
                messagebox.showerror("Erro", "Nome de usuário indisponível.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao registrar: {e}")


class MainChatGUI:
    def __init__(self, master, server, username):
        self.master = master
        self.server = server
        self.username = username
        
        self.active_chat_target = None  
        self.active_chat_is_group = False
        self.group_admins = {} 

        self.master.title(f"WhatsUT | {self.username}")
        self.master.geometry("1100x720")
        self.master.configure(bg=THEME["bg_app"])

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._config_styles()

        self.create_layout()
        
        self.load_users()
        self.load_groups()
        
        self.master.after(500, self._presence_loop)
        self.master.after(500, self._start_callback)
        self.master.after(2000, self._auto_refresh_data)
        self.master.protocol("WM_DELETE_WINDOW", self._safe_logout)

    def _config_styles(self):
        self.style.configure("Green.TButton", background=THEME["secondary"], foreground="white", borderwidth=0, font=("Segoe UI", 9, "bold"))
        self.style.map("Green.TButton", background=[('active', THEME["primary"])])
        self.style.configure("Red.TButton", background=THEME["danger"], foreground="white", borderwidth=0, font=("Segoe UI", 9, "bold"))
        self.style.map("Red.TButton", background=[('active', '#b71c1c')])
        self.style.configure("Gray.TButton", background=THEME["gray_btn"], foreground="black", borderwidth=0, font=("Segoe UI", 9))
        self.style.map("Gray.TButton", background=[('active', '#e0e0e0')])

    def create_layout(self):
        # Header
        header = tk.Frame(self.master, bg=THEME["primary"], height=60)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=f"WhatsUT | {self.username}", bg=THEME["primary"], fg="white", font=("Segoe UI", 14, "bold")).pack(side="left", padx=20)
        tk.Button(header, text="Sair", bg=THEME["danger"], fg="white", relief="flat", padx=15, command=self._safe_logout).pack(side="right", padx=20, pady=12)

        # Container Principal
        container = tk.Frame(self.master, bg="white")
        container.pack(fill="both", expand=True)

        # Sidebar
        sidebar = tk.Frame(container, bg=THEME["bg_sidebar"], width=300)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="Contatos", bg="white", font=("Segoe UI", 11, "bold"), anchor="w", fg=THEME["primary"]).pack(fill="x", padx=10, pady=(15, 5))
        self.user_list = tk.Listbox(sidebar, height=6, relief="flat", bg="#f4f4f4", font=("Segoe UI", 10), selectbackground="#d0d0d0", selectforeground="black")
        self.user_list.pack(fill="x", padx=10)
        self.user_list.bind("<Double-Button-1>", lambda e: self.on_contact_select())

        ttk.Button(sidebar, text="↻ Atualizar Lista", style="Gray.TButton", command=self.load_users).pack(fill="x", padx=10, pady=5)

        tk.Label(sidebar, text="Grupos", bg="white", font=("Segoe UI", 11, "bold"), anchor="w", fg=THEME["primary"]).pack(fill="x", padx=10, pady=(15, 5))
        self.group_list = tk.Listbox(sidebar, height=4, relief="flat", bg="#f4f4f4", font=("Segoe UI", 10), selectbackground="#d0d0d0", selectforeground="black")
        self.group_list.pack(fill="x", padx=10)
        self.group_list.bind("<Double-Button-1>", lambda e: self.on_group_select())

        action_frame = tk.Frame(sidebar, bg="white")
        action_frame.pack(fill="x", padx=10, pady=20, side="bottom")

        ttk.Button(action_frame, text="Abrir Chat", style="Green.TButton", command=self.on_open_chat_btn).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Criar Grupo", style="Gray.TButton", command=self.create_group).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Entrar em Grupo", style="Gray.TButton", command=self.request_join_group).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Adicionar Membro", style="Gray.TButton", command=self.add_user_to_group).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Solicitações", style="Gray.TButton", command=self.open_group_requests).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Excluir Grupo", style="Red.TButton", command=self.delete_group).pack(fill="x", pady=(10, 2))
        ttk.Button(action_frame, text="Banir Usuário", style="Red.TButton", command=self.request_ban_user).pack(fill="x", pady=2)

        # Chat Area
        self.right_frame = tk.Frame(container, bg=THEME["bg_chat"])
        self.right_frame.pack(side="right", fill="both", expand=True)
        self._render_empty_state()

    def _render_empty_state(self):
        for widget in self.right_frame.winfo_children():
            widget.destroy()
        frame = tk.Frame(self.right_frame, bg=THEME["bg_chat"])
        frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(frame, text="WhatsUT Web", font=("Segoe UI", 20, "bold"), bg=THEME["bg_chat"], fg="#888").pack()
        tk.Label(frame, text="Selecione um contato ou grupo para começar.", font=("Segoe UI", 12), bg=THEME["bg_chat"], fg="#999").pack(pady=10)

    def load_chat_interface(self, target_name, is_group):
        self.active_chat_target = target_name
        self.active_chat_is_group = is_group

        for widget in self.right_frame.winfo_children():
            widget.destroy()

        chat_header = tk.Frame(self.right_frame, bg="#f0f0f0", height=60)
        chat_header.pack(side="top", fill="x")
        chat_header.pack_propagate(False)

        icon = "👥" if is_group else "👤"
        tk.Label(chat_header, text=icon, font=("Segoe UI", 18), bg="#f0f0f0").pack(side="left", padx=(20, 10))
        tk.Label(chat_header, text=target_name, font=("Segoe UI", 14, "bold"), bg="#f0f0f0").pack(side="left")

        if not is_group:
             ttk.Button(chat_header, text="Arquivos", style="Gray.TButton", command=self.show_files_current).pack(side="right", padx=20)

        self.canvas_chat = tk.Canvas(self.right_frame, bg=THEME["bg_chat"], highlightthickness=0)
        self.scrollbar_chat = ttk.Scrollbar(self.right_frame, orient="vertical", command=self.canvas_chat.yview)
        
        self.msg_frame = tk.Frame(self.canvas_chat, bg=THEME["bg_chat"])
        self.msg_frame.bind("<Configure>", lambda e: self.canvas_chat.configure(scrollregion=self.canvas_chat.bbox("all")))

        self.canvas_window = self.canvas_chat.create_window((0, 0), window=self.msg_frame, anchor="nw", width=self.right_frame.winfo_width())
        self.right_frame.bind("<Configure>", self._resize_canvas_frame)

        self.canvas_chat.configure(yscrollcommand=self.scrollbar_chat.set)
        self.canvas_chat.pack(side="top", fill="both", expand=True)
        self.scrollbar_chat.pack(side="right", fill="y", in_=self.canvas_chat)

        input_area = tk.Frame(self.right_frame, bg="#f0f0f0", height=70)
        input_area.pack(side="bottom", fill="x")

        if not is_group:
            tk.Button(input_area, text="📎", font=("Segoe UI", 16), bg="#f0f0f0", bd=0, command=self.send_file_current).pack(side="left", padx=15)

        self.entry_msg = tk.Entry(input_area, font=("Segoe UI", 12), bd=0, bg="white")
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=10, pady=15, ipady=5)
        self.entry_msg.bind("<Return>", lambda e: self.send_message_current())

        tk.Button(input_area, text="➤", font=("Segoe UI", 14, "bold"), bg=THEME["secondary"], fg="white", bd=0, padx=15, command=self.send_message_current).pack(side="right", padx=15, pady=10)

        self._load_conversation_data()

    def _resize_canvas_frame(self, event):
        canvas_width = event.width
        self.canvas_chat.itemconfig(self.canvas_window, width=canvas_width)

    # =========================================================================
    # LÓGICA DE FUSO HORÁRIO (CORREÇÃO BRASÍLIA)
    # =========================================================================
    def converter_hora_brasilia(self, timestamp_str):
        """
        Converte timestamp UTC do banco para Horário de Brasília (UTC-3).
        Retorna no formato HH:MM (ex: 20:29).
        """
        try:
            # Pega a string até os segundos (descarta milissegundos se houver)
            dt_utc = datetime.strptime(str(timestamp_str).split(".")[0], "%Y-%m-%d %H:%M:%S")
            # Subtrai 3 horas
            dt_br = dt_utc - timedelta(hours=3)
            # Retorna formatado
            return dt_br.strftime("%H:%M")
        except Exception:
            # Se der erro no parse, retorna como string mesmo
            return str(timestamp_str)

    # =========================================================================
    # RENDERIZAÇÃO DE BALÕES (BUBBLES)
    # =========================================================================
    def add_message_bubble(self, sender, text, timestamp, is_me, is_admin=False):
        # Cores e alinhamento
        bg_color = THEME["bubble_out"] if is_me else THEME["bubble_in"]
        align = "e" if is_me else "w"
        justify_txt = "right" if is_me else "left"
        
        row_container = tk.Frame(self.msg_frame, bg=THEME["bg_chat"])
        row_container.pack(fill="x", pady=2, padx=15)
        
        bubble = tk.LabelFrame(row_container, bg=bg_color, bd=0, padx=8, pady=5)
        bubble.pack(side=("right" if is_me else "left"), anchor=align)

        if not is_me and self.active_chat_is_group:
            color_name = "orange" if is_admin else "gray"
            name_txt = sender + (" (Admin)" if is_admin else "")
            tk.Label(bubble, text=name_txt, font=("Segoe UI", 8, "bold"), bg=bg_color, fg=color_name).pack(anchor="w")

        tk.Label(bubble, text=text, font=("Segoe UI", 10), bg=bg_color, fg="black", wraplength=450, justify=justify_txt).pack(anchor="w")
        
        # AQUI USAMOS A NOVA FUNÇÃO DE CONVERSÃO
        hora_formatada = self.converter_hora_brasilia(timestamp)
        tk.Label(bubble, text=hora_formatada, font=("Segoe UI", 7), bg=bg_color, fg="#777").pack(anchor="e")

    def _load_conversation_data(self):
        if not self.active_chat_target: return
        
        for w in self.msg_frame.winfo_children():
            w.destroy()

        try:
            msgs = []
            admin_name = ""
            
            if self.active_chat_is_group:
                msgs = self.server.get_group_conversation(self.active_chat_target)
                admin_name = self.group_admins.get(self.active_chat_target, "")
            else:
                msgs = self.server.get_conversation(self.username, self.active_chat_target)

            for data in msgs:
                if self.active_chat_is_group:
                    sender, content, ts = data
                    receiver = None
                else:
                    sender, receiver, content, ts = data
                
                is_me = (sender == self.username)
                is_admin_msg = (sender == admin_name) if self.active_chat_is_group else False

                self.add_message_bubble(sender, content, ts, is_me, is_admin_msg)

            self.msg_frame.update_idletasks()
            self.canvas_chat.yview_moveto(1.0)

        except Exception as e:
            print(f"Erro ao carregar chat: {e}")

    # =========================================================================
    # LÓGICA DO SERVIDOR
    # =========================================================================

    def _auto_refresh_data(self):
        # Lógica de refresh
        self.master.after(2000, self._auto_refresh_data)

    def send_message_current(self):
        if not self.active_chat_target: return
        text = self.entry_msg.get().strip()
        if not text: return
        try:
            ok = False
            if self.active_chat_is_group:
                ok = self.server.send_group_message(self.username, self.active_chat_target, text)
            else:
                ok = self.server.send_message(self.username, self.active_chat_target, text)
            if ok:
                self.entry_msg.delete(0, tk.END)
                self._load_conversation_data()
            else:
                messagebox.showwarning("Erro", "Falha ao enviar.")
        except Exception as e:
            print(e)

    def send_file_current(self):
        if self.active_chat_is_group:
            messagebox.showinfo("Info", "Envio de arquivos apenas em chat privado.")
            return
        filepath = filedialog.askopenfilename()
        if not filepath: return
        filename = os.path.basename(filepath)
        try:
            if os.path.getsize(filepath) > 5 * 1024 * 1024:
                messagebox.showwarning("Arquivo", "Muito grande (max 5MB).")
                return
            with open(filepath, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode('utf-8')
            ok, msg = self.server.send_file(self.username, self.active_chat_target, filename, b64_data)
            if ok:
                self.server.send_message(self.username, self.active_chat_target, f"📎 Enviou arquivo: {filename}")
                self._load_conversation_data()
                messagebox.showinfo("Sucesso", f"Arquivo '{filename}' enviado!")
            else:
                messagebox.showerror("Erro", msg)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha no envio: {e}")

    def show_files_current(self):
        if self.active_chat_is_group: return
        try:
            files = self.server.get_files_list(self.username, self.active_chat_target)
            win = tk.Toplevel(self.master)
            win.title(f"Arquivos - {self.active_chat_target}")
            win.geometry("400x300")
            lb = tk.Listbox(win, width=60, font=("Segoe UI", 9))
            lb.pack(padx=10, pady=10, fill="both", expand=True)
            file_map = {}
            for idx, (fid, s, r, fname, fsize, ts) in enumerate(files):
                direction = "Enviado" if s == self.username else "Recebido"
                lb.insert(tk.END, f"{direction} | {fname} | {ts}")
                file_map[idx] = (fid, fname)
            def _down():
                sel = lb.curselection()
                if not sel: return
                fid, fname = file_map[sel[0]]
                path = filedialog.asksaveasfilename(initialfile=fname)
                if path:
                    sfname, b64 = self.server.download_file(fid)
                    if b64:
                        with open(path, "wb") as f: f.write(base64.b64decode(b64))
                        messagebox.showinfo("Sucesso", "Download concluído.")
            tk.Button(win, text="Baixar Selecionado", command=_down, bg=THEME["secondary"], fg="white").pack(pady=10)
        except Exception: pass

    def load_users(self):
        try:
            users = self.server.list_users()
            try: status_map = dict(self.server.get_status_map())
            except: status_map = {}
            self.user_list.delete(0, tk.END)
            for uid, uname, banned in users:
                if uname == self.username: continue
                display = uname + (" (banido)" if banned else "")
                self.user_list.insert(tk.END, display)
                idx = self.user_list.size() - 1
                color = "#00c853" if status_map.get(uname, False) else "#757575"
                self.user_list.itemconfig(idx, fg=color)
        except Exception as e: print(f"Erro users: {e}")

    def load_groups(self):
        try:
            data = self.server.list_groups_with_status(self.username)
            self.group_list.delete(0, tk.END)
            self.group_admins = {}
            for name, admin_uname, status in data:
                self.group_admins[name] = admin_uname
                tag = "" if status == "aprovado" else f"({status})"
                self.group_list.insert(tk.END, f"{name} {tag}".strip())
        except Exception as e: print(f"Erro groups: {e}")

    def on_contact_select(self):
        sel = self.user_list.get(tk.ACTIVE)
        if not sel: return
        uname = sel.split(" ")[0]
        self.load_chat_interface(uname, is_group=False)

    def on_group_select(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        gname = sel.split(" ")[0]
        self.load_chat_interface(gname, is_group=True)

    def on_open_chat_btn(self):
        if self.user_list.curselection(): self.on_contact_select()
        elif self.group_list.curselection(): self.on_group_select()
        else: messagebox.showinfo("Info", "Selecione um item na lista.")

    def create_group(self):
        win = tk.Toplevel(self.master)
        win.title("Novo Grupo")
        win.geometry("300x200")
        tk.Label(win, text="Nome:").pack(pady=5)
        entry = tk.Entry(win); entry.pack(pady=5)
        var = tk.StringVar(value="transfer")
        tk.Label(win, text="Se admin sair:").pack(pady=5)
        tk.Radiobutton(win, text="Transferir Admin", variable=var, value="transfer").pack()
        tk.Radiobutton(win, text="Apagar Grupo", variable=var, value="delete").pack()
        def _save():
            name = entry.get().strip()
            if name and self.server.create_group(self.username, name, var.get()):
                self.load_groups()
                win.destroy()
            else: messagebox.showerror("Erro", "Falha ao criar.")
        tk.Button(win, text="Criar", command=_save, bg=THEME["secondary"], fg="white").pack(pady=10)

    def request_join_group(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        gname = sel.split(" ")[0]
        if self.server.request_join_group(self.username, gname):
            messagebox.showinfo("Sucesso", "Solicitação enviada.")
            self.load_groups()
        else: messagebox.showerror("Erro", "Falha.")

    def add_user_to_group(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        gname = sel.split(" ")[0]
        win = tk.Toplevel(self.master)
        tk.Label(win, text="Username:").pack(); e = tk.Entry(win); e.pack()
        def _add():
            if self.server.add_member_direct(self.username, gname, e.get()):
                messagebox.showinfo("Sucesso", "Adicionado.")
                win.destroy()
            else: messagebox.showerror("Erro", "Falha.")
        tk.Button(win, text="Add", command=_add).pack()

    def open_group_requests(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        gname = sel.split(" ")[0]
        reqs = self.server.list_pending_requests(self.username, gname)
        if not reqs:
            messagebox.showinfo("Info", "Nenhuma solicitação.")
            return
        win = tk.Toplevel(self.master)
        lb = tk.Listbox(win); lb.pack()
        for r in reqs: lb.insert(tk.END, r)
        def _app():
            u = lb.get(tk.ACTIVE)
            if u and self.server.approve_member(self.username, gname, u):
                lb.delete(tk.ACTIVE); self.load_groups()
        tk.Button(win, text="Aprovar", command=_app).pack()

    def delete_group(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        gname = sel.split(" ")[0]
        if messagebox.askyesno("Confirmar", f"Excluir {gname}?"):
            if self.server.delete_group(self.username, gname):
                self.load_groups()
                if self.active_chat_target == gname: self._render_empty_state()
            else: messagebox.showerror("Erro", "Falha.")

    def request_ban_user(self):
        win = tk.Toplevel(self.master)
        tk.Label(win, text="Alvo:").pack(); t=tk.Entry(win); t.pack()
        tk.Label(win, text="Motivo:").pack(); r=tk.Entry(win); r.pack()
        def _b():
            ok, msg = self.server.request_ban_user(self.username, t.get(), r.get())
            messagebox.showinfo("Info", msg)
            if ok: win.destroy()
        tk.Button(win, text="Banir", command=_b, bg="red", fg="white").pack()

    def _presence_loop(self):
        try: self.server.heartbeat(self.username)
        except: pass
        self.master.after(20000, self._presence_loop)

    def _start_callback(self):
        class ClientCallback:
            def __init__(self, gui): self.gui = gui
            @Pyro5.server.expose
            def notify_private(self, sender, receiver):
                if self.gui.active_chat_target in [sender, receiver]:
                    self.gui.master.after(0, self.gui._load_conversation_data)
                elif self.gui.active_chat_is_group and receiver == self.gui.active_chat_target:
                    self.gui.master.after(0, self.gui._load_conversation_data)
            @Pyro5.server.expose
            def notify_file(self, s, r, f):
                self.notify_private(s, r)
        self._daemon = Pyro5.server.Daemon()
        self._cb = ClientCallback(self)
        self._uri = self._daemon.register(self._cb)
        threading.Thread(target=self._daemon.requestLoop, daemon=True).start()
        try: self.server.register_callback(self.username, self._uri)
        except: pass

    def _safe_logout(self):
        try: self.server.unregister_callback(self.username)
        except: pass
        self.master.destroy()

def start_app():
    root = tk.Tk()
    LoginGUI(root)
    root.mainloop()

if __name__ == "__main__":
    start_app()