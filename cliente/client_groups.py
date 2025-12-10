import tkinter as tk
from tkinter import ttk, messagebox
from client_main_constants import COLOR_BTN, COLOR_BG_CHAT, COLOR_BG_APP, COLOR_MY_MSG, COLOR_OTHER_MSG, FONT_MAIN

class GroupChatWindow:
    def __init__(self, master, server, me, group_name):
        self.master = master
        self.server = server
        self.me = me
        self.group_name = group_name
        self._alive = True
        self.master.title(f"Grupo: {group_name}")
        self.master.geometry("700x550")
        top = tk.Frame(self.master, bg=COLOR_BTN, height=60)
        top.pack(fill="x")
        tk.Label(top, text=group_name, bg=COLOR_BTN, fg="white", font=("Segoe UI", 14, "bold")).pack(side="left", padx=10, pady=10)
        bottom = tk.Frame(self.master, bg=COLOR_BG_APP, height=60)
        bottom.pack(side="bottom", fill="x")
        self.entry_msg = tk.Entry(bottom, font=("Segoe UI", 11), relief="flat", bg="white")
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=10, pady=10, ipady=5)
        self.entry_msg.bind("<Return>", lambda e: self.send_message())
        btn_send = tk.Button(bottom, text="➤", bg=COLOR_BTN, fg="white", font=("Segoe UI", 12), relief="flat", command=self.send_message)
        btn_send.pack(side="left", padx=(0, 10))
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
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_conversation(self):
        try:
            conv = self.server.get_group_conversation(self.group_name)
            self.chat_area.config(state="normal")
            self.chat_area.delete(1.0, tk.END)
            for sender, content, ts in conv:
                tag = "me" if sender == self.me else "other"
                display = f"[{sender}] {content}\n" if tag == "other" else f"{content}\n"
                self.chat_area.insert(tk.END, f" {display}", tag)
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

    def on_close(self):
        self._alive = False
        self.master.destroy()

    def _loop(self):
        if not self._alive:
            return
        try:
            self.load_conversation()
        except Exception:
            pass
        if self._alive:
            self.master.after(2000, self._loop)
