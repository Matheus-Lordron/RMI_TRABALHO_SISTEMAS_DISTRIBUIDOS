import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import Pyro5.api
import Pyro5.server
import base64
import os
import threading
from client_main_constants import *

SERVER_NAME = "PYRONAME:whatsut.server"

class LoginGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("WhatsUT - Login")
        self.master.geometry("350x300")
        self.master.resizable(False, False)
        self.master.configure(bg=COLOR_BG_APP)
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
        self.entry_pass.bind("<Return>", lambda e: self.try_login())
        
        tk.Button(frame, text="ENTRAR", bg=COLOR_BTN, fg=COLOR_BTN_TEXT, font=FONT_BOLD, relief="flat", command=self.try_login).pack(fill="x", pady=5)
        tk.Button(frame, text="Registrar", bg="#ffffff", fg=COLOR_BTN, font=FONT_MAIN, relief="groove", command=self.register).pack(fill="x")

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

class MainChatGUI:
    def __init__(self, master, server, username):
        self.master = master
        self.server = server
        self.username = username
        
        # Controle de qual chat está aberto
        self.active_chat_target = None  
        self.active_chat_is_group = False
        
        # Dicionário para guardar quem é o admin de cada grupo
        # Chave: Nome do Grupo -> Valor: Username do Admin
        self.group_admins = {} 

        self.master.title("WhatsUT")
        self.master.geometry("1000x700")
        self.master.configure(bg=COLOR_BG_APP)
        
        self.create_layout()
        
        self.load_users()
        self.load_groups()
        
        self.master.after(500, self._presence_loop)
        self.master.after(500, self._start_callback)
        self.master.after(1000, self._auto_refresh_active_chat)
        self.master.protocol("WM_DELETE_WINDOW", self._safe_logout)

    def create_layout(self):
        # HEADER
        header = tk.Frame(self.master, bg=COLOR_BTN, height=50)
        header.pack(fill="x")
        tk.Label(header, text=f"WhatsUT | {self.username}", bg=COLOR_BTN, fg="white", font=("Segoe UI", 12, "bold")).pack(side="left", padx=15, pady=10)
        tk.Button(header, text="Sair", bg="#d32f2f", fg="white", relief="flat", font=("Segoe UI", 9), command=self._safe_logout).pack(side="right", padx=15)

        # CONTAINER PRINCIPAL
        main_container = tk.Frame(self.master, bg=COLOR_BG_APP)
        main_container.pack(fill="both", expand=True)

        # ESQUERDA
        self.left_frame = tk.Frame(main_container, bg="white", width=300)
        self.left_frame.pack(side="left", fill="y", expand=False)
        self.left_frame.pack_propagate(False)

        canvas = tk.Canvas(self.left_frame, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.left_frame, orient="vertical", command=canvas.yview)
        self.scrollable_left = tk.Frame(canvas, bg="white")
        
        self.scrollable_left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_left, anchor="nw", width=280)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_left_sidebar()

        # DIREITA
        self.right_frame = tk.Frame(main_container, bg=COLOR_BG_APP)
        self.right_frame.pack(side="right", fill="both", expand=True)
        self._render_empty_state()

    def _build_left_sidebar(self):
        # Contatos
        tk.Label(self.scrollable_left, text="Contatos", bg="white", fg="#555", font=("Segoe UI", 11, "bold")).pack(pady=(15, 5), padx=10, anchor="w")
        self.user_list = tk.Listbox(self.scrollable_left, font=("Segoe UI", 10), bg="white", bd=0, highlightthickness=0, selectbackground=COLOR_BG_APP, selectforeground="black", height=8)
        self.user_list.pack(fill="x", padx=10)
        self.user_list.bind("<Double-Button-1>", lambda e: self.on_contact_select())
        
        tk.Button(self.scrollable_left, text="⟳ Atualizar Lista", bg="#eee", relief="flat", font=("Segoe UI", 8), command=self.load_users).pack(fill="x", padx=10, pady=2)

        tk.Frame(self.scrollable_left, bg="#ddd", height=1).pack(fill="x", padx=10, pady=15)

        # Grupos
        tk.Label(self.scrollable_left, text="Grupos", bg="white", fg="#555", font=("Segoe UI", 11, "bold")).pack(pady=(5, 5), padx=10, anchor="w")
        self.group_list = tk.Listbox(self.scrollable_left, font=("Segoe UI", 10), bg="white", bd=0, relief="flat", highlightthickness=0, selectbackground=COLOR_BG_APP, selectforeground="black", height=6)
        self.group_list.pack(fill="x", padx=10)
        self.group_list.bind("<Double-Button-1>", lambda e: self.on_group_select())

        # Botões de Grupo
        btn_frame = tk.Frame(self.scrollable_left, bg="white")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        style_btn = {"bg": COLOR_BTN, "fg": "white", "relief": "flat", "font": ("Segoe UI", 8)}
        style_sub = {"bg": "#eee", "fg": "black", "relief": "flat", "font": ("Segoe UI", 8)}

        tk.Button(btn_frame, text="Abrir Chat", command=self.on_open_chat_btn, **style_btn).pack(fill="x", pady=2)
        tk.Button(btn_frame, text="Criar Grupo", command=self.create_group, **style_sub).pack(fill="x", pady=2)
        tk.Button(btn_frame, text="Entrar", command=self.request_join_group, **style_sub).pack(fill="x", pady=2)
        tk.Button(btn_frame, text="Adicionar Membro", command=self.add_user_to_group, **style_sub).pack(fill="x", pady=2)
        tk.Button(btn_frame, text="Solicitações", command=self.open_group_requests, **style_sub).pack(fill="x", pady=2)
        tk.Button(btn_frame, text="Excluir", command=self.delete_group, bg="#d32f2f", fg="white", relief="flat", font=("Segoe UI", 8)).pack(fill="x", pady=(10, 2))
        
        tk.Frame(self.scrollable_left, bg="#ddd", height=1).pack(fill="x", padx=10, pady=15)
        tk.Button(self.scrollable_left, text="⚠️ Banir Usuário", command=self.request_ban_user, bg="#d32f2f", fg="white", relief="flat").pack(fill="x", padx=10, pady=5)


    def _render_empty_state(self):
        for widget in self.right_frame.winfo_children():
            widget.destroy()
        
        lbl = tk.Label(self.right_frame, text="Selecione um contato ou grupo\npara iniciar uma conversa", bg=COLOR_BG_APP, fg="#aaa", font=("Segoe UI", 16))
        lbl.place(relx=0.5, rely=0.5, anchor="center")

    def load_chat_interface(self, target_name, is_group):
        self.active_chat_target = target_name
        self.active_chat_is_group = is_group
        
        for widget in self.right_frame.winfo_children():
            widget.destroy()
            
        top_bar = tk.Frame(self.right_frame, bg="#fff", height=50)
        top_bar.pack(side="top", fill="x")
        
        icon = "👥" if is_group else "👤"
        tk.Label(top_bar, text=f"{icon} {target_name}", font=("Segoe UI", 14), bg="#fff", fg="#333").pack(side="left", padx=20, pady=10)
        
        if not is_group:
            tk.Button(top_bar, text="📂 Arquivos", command=self.show_files_current, bg="#eee", relief="flat").pack(side="right", padx=10)

        chat_frame = tk.Frame(self.right_frame, bg=COLOR_BG_CHAT)
        chat_frame.pack(side="top", fill="both", expand=True)
        
        self.txt_chat = tk.Text(chat_frame, state="disabled", wrap="word", bg=COLOR_BG_CHAT, relief="flat", font=("Segoe UI", 10), padx=10, pady=10)
        scrollbar_chat = ttk.Scrollbar(chat_frame, command=self.txt_chat.yview)
        self.txt_chat.configure(yscrollcommand=scrollbar_chat.set)
        
        scrollbar_chat.pack(side="right", fill="y")
        self.txt_chat.pack(side="left", fill="both", expand=True)
        
        # Tags de formatação
        self.txt_chat.tag_config("me", justify="right", rmargin=10, lmargin1=100, lmargin2=100, background=COLOR_MY_MSG, foreground="black", spacing1=5, spacing3=5)
        self.txt_chat.tag_config("other", justify="left", lmargin1=10, lmargin2=10, rmargin=100, background=COLOR_OTHER_MSG, foreground="black", spacing1=5, spacing3=5)
        self.txt_chat.tag_config("info", justify="center", foreground="#777", spacing1=5, spacing3=5, font=("Segoe UI", 8))
        
        # Tag especial para admin
        self.txt_chat.tag_config("admin_tag", font=("Segoe UI", 9, "bold"), foreground="#d32f2f") # Vermelho escuro para destacar

        bottom_bar = tk.Frame(self.right_frame, bg="#f0f2f5", height=60)
        bottom_bar.pack(side="bottom", fill="x", pady=0)
        
        if not is_group:
            tk.Button(bottom_bar, text="📎", font=("Segoe UI", 14), bg="#f0f2f5", relief="flat", command=self.send_file_current).pack(side="left", padx=10)

        self.entry_msg = tk.Entry(bottom_bar, font=("Segoe UI", 11), relief="flat", bg="white")
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=10, pady=10, ipady=8)
        self.entry_msg.bind("<Return>", lambda e: self.send_message_current())
        
        tk.Button(bottom_bar, text="Enviar ➤", bg=COLOR_BTN, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", command=self.send_message_current).pack(side="right", padx=10)
        
        self._load_conversation_data()

    def _load_conversation_data(self):
        if not self.active_chat_target:
            return
            
        try:
            self.txt_chat.config(state="normal")
            self.txt_chat.delete(1.0, tk.END)
            
            msgs = []
            if self.active_chat_is_group:
                msgs = self.server.get_group_conversation(self.active_chat_target)
                
                # Pega quem é o admin deste grupo (carregado previamente em load_groups)
                admin_name = self.group_admins.get(self.active_chat_target)

                for sender, content, ts in msgs:
                    tag = "me" if sender == self.username else "other"
                    
                    # Lógica de visualização do remetente
                    display_sender = sender
                    
                    if sender == admin_name:
                        # Se o remetente é o admin
                        if sender == self.username:
                            display_sender = "eu/admin"
                        else:
                            display_sender = f"admin/{sender}"
                    elif sender == self.username:
                        display_sender = "eu"

                    # Monta a mensagem
                    if tag == "other":
                        # Mensagem de outros
                        self.txt_chat.insert(tk.END, f"[{display_sender}] {content}\n", tag)
                    else:
                        # Mensagem minha (já alinhada à direita, mostramos o texto)
                        # Opcional: mostrar [eu/admin] antes do texto ou não. 
                        # Geralmente apps de chat não mostram nome na própria msg, 
                        # mas para atender seu requisito vou colocar:
                        self.txt_chat.insert(tk.END, f"[{display_sender}] {content}\n", tag)
                        
                    self.txt_chat.insert(tk.END, f"{ts}\n", "info")
            else:
                msgs = self.server.get_conversation(self.username, self.active_chat_target)
                for sender, receiver, content, ts in msgs:
                    tag = "me" if sender == self.username else "other"
                    self.txt_chat.insert(tk.END, f" {content}\n", tag)
                    self.txt_chat.insert(tk.END, f"{ts}\n", "info")
                    
            self.txt_chat.config(state="disabled")
            self.txt_chat.see(tk.END)
        except Exception as e:
            print(f"Erro ao carregar chat: {e}")

    def _auto_refresh_active_chat(self):
        if self.active_chat_target:
            try:
                self._load_conversation_data()
            except Exception:
                pass
        self.master.after(2000, self._auto_refresh_active_chat)

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
                messagebox.showwarning("Erro", "Falha ao enviar. Verifique se você está no grupo ou conectado.")
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
                self.server.send_message(self.username, self.active_chat_target, f"📎 Arquivo enviado: {filename}")
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
            
            lb = tk.Listbox(win, width=60)
            lb.pack(padx=10, pady=10)
            file_map = {}
            for idx, (fid, s, r, fname, fsize, ts) in enumerate(files):
                direction = "Enviado" if s == self.username else "Recebido"
                lb.insert(tk.END, f"[{direction}] {fname} ({fsize}b) - {ts}")
                file_map[idx] = (fid, fname)
                
            def _down():
                sel = lb.curselection()
                if not sel: return
                fid, fname = file_map[sel[0]]
                path = filedialog.asksaveasfilename(initialfile=fname)
                if path:
                    sfname, b64 = self.server.download_file(fid)
                    if b64:
                        with open(path, "wb") as f:
                            f.write(base64.b64decode(b64))
                        messagebox.showinfo("Sucesso", "Download concluído.")
            
            tk.Button(win, text="Baixar", command=_down).pack(pady=5)
        except Exception:
            pass

    def on_contact_select(self):
        sel = self.user_list.get(tk.ACTIVE)
        if not sel: return
        uname = sel.split(" ")[0]
        self.load_chat_interface(uname, is_group=False)

    def on_group_select(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        # Agora o nome vem limpo ou com (pendente), precisamos pegar só o nome
        gname = sel.split(" ")[0]
        self.load_chat_interface(gname, is_group=True)

    def on_open_chat_btn(self):
        if self.user_list.curselection():
            self.on_contact_select()
        elif self.group_list.curselection():
            self.on_group_select()
        else:
            messagebox.showinfo("Info", "Selecione um contato ou grupo na lista.")

    def load_users(self):
        try:
            users = self.server.list_users()
            try:
                status_map = dict(self.server.get_status_map())
            except Exception:
                status_map = {}
            
            self.user_list.delete(0, tk.END)
            for uid, uname, banned in users:
                if uname == self.username: continue
                display = uname + (" (banido)" if banned else "")
                self.user_list.insert(tk.END, display)
                idx = self.user_list.size() - 1
                color = COLOR_ONLINE if status_map.get(uname, False) else COLOR_OFFLINE
                self.user_list.itemconfig(idx, fg=color)
        except Exception as e:
            print(f"Erro users: {e}")

    def load_groups(self):
        try:
            data = self.server.list_groups_with_status(self.username)
            self.group_list.delete(0, tk.END)
            
            # Limpa e repopula o dicionário de admins
            self.group_admins = {}

            for name, admin_uname, status in data:
                # Guarda quem é o admin
                self.group_admins[name] = admin_uname

                # Ajuste visual: Se aprovado, não mostra nada. Se pendente, mostra (pendente).
                tag = "" if status == "aprovado" else f"({status})"
                
                # Monta a string para a lista
                display_str = f"{name} {tag}".strip()
                self.group_list.insert(tk.END, display_str)
        except Exception as e:
            print(f"Erro groups: {e}")

    def create_group(self):
        win = tk.Toplevel(self.master)
        win.title("Novo Grupo")
        win.geometry("300x200")
        tk.Label(win, text="Nome:").pack(pady=5)
        entry = tk.Entry(win)
        entry.pack(pady=5)
        var = tk.StringVar(value="transfer")
        tk.Label(win, text="Se admin sair:").pack(pady=5)
        tk.Radiobutton(win, text="Transferir Admin", variable=var, value="transfer").pack()
        tk.Radiobutton(win, text="Apagar Grupo", variable=var, value="delete").pack()
        def _save():
            name = entry.get().strip()
            if name:
                if self.server.create_group(self.username, name, var.get()):
                    self.load_groups()
                    win.destroy()
                else:
                    messagebox.showerror("Erro", "Falha ao criar.")
        tk.Button(win, text="Criar", command=_save, bg=COLOR_BTN, fg="white").pack(pady=10)

    def request_join_group(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        gname = sel.split(" ")[0]
        if self.server.request_join_group(self.username, gname):
            messagebox.showinfo("Sucesso", "Solicitação enviada.")
            self.load_groups()
        else:
            messagebox.showerror("Erro", "Falha.")

    def add_user_to_group(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        gname = sel.split(" ")[0]
        win = tk.Toplevel(self.master)
        win.title(f"Add em {gname}")
        tk.Label(win, text="Username:").pack()
        e = tk.Entry(win); e.pack()
        def _add():
            if self.server.add_member_direct(self.username, gname, e.get()):
                messagebox.showinfo("Sucesso", "Adicionado.")
                win.destroy()
            else:
                messagebox.showerror("Erro", "Falha (você é admin?)")
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
        lb = tk.Listbox(win)
        lb.pack()
        for r in reqs: lb.insert(tk.END, r)
        def _app():
            u = lb.get(tk.ACTIVE)
            if u and self.server.approve_member(self.username, gname, u):
                lb.delete(tk.ACTIVE)
                self.load_groups()
        tk.Button(win, text="Aprovar", command=_app).pack()

    def delete_group(self):
        sel = self.group_list.get(tk.ACTIVE)
        if not sel: return
        gname = sel.split(" ")[0]
        if messagebox.askyesno("Confirmar", f"Excluir {gname}?"):
            if self.server.delete_group(self.username, gname):
                self.load_groups()
                if self.active_chat_target == gname:
                    self._render_empty_state()
                    self.active_chat_target = None
            else:
                messagebox.showerror("Erro", "Falha (você é admin?)")

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
        try:
            self.server.heartbeat(self.username)
        except: pass
        self.master.after(20000, self._presence_loop)

    def _start_callback(self):
        class ClientCallback:
            def __init__(self, gui): self.gui = gui
            @Pyro5.server.expose
            def notify_private(self, sender, receiver):
                if self.gui.active_chat_target in [sender, receiver]:
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