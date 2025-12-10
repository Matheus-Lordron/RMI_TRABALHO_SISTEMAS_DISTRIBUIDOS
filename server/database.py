# server/database.py
import sqlite3
from pathlib import Path

DB_NAME = "whatsut.db"

class Database:
    def __init__(self):
        # criar o arquivo do DB na pasta atual se não existir
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Tabela de usuários
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            banned INTEGER DEFAULT 0
        )
        """)

        # Tabela de grupos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            admin INTEGER NOT NULL,
            FOREIGN KEY(admin) REFERENCES users(id)
        )
        """)

        # Relação usuário X grupo
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            user_id INTEGER,
            group_id INTEGER,
            approved INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, group_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(group_id) REFERENCES groups(id)
        )
        """)

        # Tabela de mensagens privadas
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender INTEGER NOT NULL,
            receiver INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender) REFERENCES users(id),
            FOREIGN KEY(receiver) REFERENCES users(id)
        )
        """)

        self.conn.commit()

    # --------- CRUD Usuário ---------
    def add_user(self, username, password_hash):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user(self, username):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, banned FROM users WHERE username = ?",
            (username,)
        )
        return cursor.fetchone()

    def ban_user(self, username):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET banned = 1 WHERE username = ?", (username,))
        self.conn.commit()

    # ---- Listar usuários (verificação / admin) ----
    def list_users(self):
        """
        Retorna lista de tuplas (id, username, banned).
        Usado para debug e para exibir na interface administrativa.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, username, banned FROM users")
        return cursor.fetchall()

    # --------- MENSAGENS PRIVADAS ---------
    def save_message(self, sender_id, receiver_id, content):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO messages (sender, receiver, content) VALUES (?, ?, ?)",
            (sender_id, receiver_id, content)
        )
        self.conn.commit()

    def get_messages_between(self, user_a_id, user_b_id):
        """
        Retorna todas as mensagens trocadas entre user_a e user_b,
        ordenadas por timestamp asc. Cada linha: (sender_username, receiver_username, content, timestamp)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT su.username AS sender_name,
               ru.username AS receiver_name,
               m.content,
               m.timestamp
        FROM messages m
        JOIN users su ON m.sender = su.id
        JOIN users ru ON m.receiver = ru.id
        WHERE (m.sender = ? AND m.receiver = ?)
           OR (m.sender = ? AND m.receiver = ?)
        ORDER BY m.timestamp ASC
        """, (user_a_id, user_b_id, user_b_id, user_a_id))
        return cursor.fetchall()
