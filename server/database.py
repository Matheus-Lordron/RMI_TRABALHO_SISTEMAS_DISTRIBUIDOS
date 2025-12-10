import sqlite3
from pathlib import Path

DB_NAME = "whatsut.db"

class Database:
    def __init__(self):
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

        # Tabela de grupos com configuração de admin
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            admin INTEGER NOT NULL,
            admin_on_leave TEXT DEFAULT 'transfer',
            FOREIGN KEY(admin) REFERENCES users(id)
        )
        """)

        # Relação usuário X grupo
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            user_id INTEGER,
            group_id INTEGER,
            approved INTEGER DEFAULT 0,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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

        # Tabela de mensagens de grupo
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            sender INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(group_id) REFERENCES groups(id),
            FOREIGN KEY(sender) REFERENCES users(id)
        )
        """)

        # Tabela de arquivos enviados
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender INTEGER NOT NULL,
            receiver INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_data BLOB NOT NULL,
            file_size INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender) REFERENCES users(id),
            FOREIGN KEY(receiver) REFERENCES users(id)
        )
        """)

        # Tabela de solicitações de banimento
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ban_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester INTEGER NOT NULL,
            target_user INTEGER NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(requester) REFERENCES users(id),
            FOREIGN KEY(target_user) REFERENCES users(id)
        )
        """)

        self.conn.commit()
        
        # --- MIGRAÇÕES (CORREÇÃO: Agora dentro de create_tables) ---
        # Isso garante que bancos antigos recebam as novas colunas
        try:
            cursor.execute("ALTER TABLE groups ADD COLUMN admin_on_leave TEXT DEFAULT 'transfer'")
        except Exception:
            pass # Coluna já existe
            
        try:
            cursor.execute("ALTER TABLE group_members ADD COLUMN joined_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        except Exception:
            pass # Coluna já existe
            
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

    def unban_user(self, username):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET banned = 0 WHERE username = ?", (username,))
        self.conn.commit()

    def list_users(self):
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

    # --------- ENVIO DE ARQUIVOS ---------
    def save_file(self, sender_id, receiver_id, filename, file_data):
        cursor = self.conn.cursor()
        file_size = len(file_data)
        cursor.execute(
            """INSERT INTO file_transfers 
            (sender, receiver, filename, file_data, file_size) 
            VALUES (?, ?, ?, ?, ?)""",
            (sender_id, receiver_id, filename, file_data, file_size)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_files_between(self, user_a_id, user_b_id):
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT f.id, su.username, ru.username, f.filename, 
               f.file_size, f.timestamp
        FROM file_transfers f
        JOIN users su ON f.sender = su.id
        JOIN users ru ON f.receiver = ru.id
        WHERE (f.sender = ? AND f.receiver = ?)
           OR (f.sender = ? AND f.receiver = ?)
        ORDER BY f.timestamp ASC
        """, (user_a_id, user_b_id, user_b_id, user_a_id))
        return cursor.fetchall()

    def get_file_data(self, file_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT filename, file_data FROM file_transfers WHERE id = ?",
            (file_id,)
        )
        return cursor.fetchone()

    # --------- GRUPOS ---------
    def create_group(self, name, admin_id, admin_on_leave='transfer'):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO groups (name, admin, admin_on_leave) VALUES (?, ?, ?)",
                (name, admin_id, admin_on_leave)
            )
            gid = cursor.lastrowid
            cursor.execute(
                "INSERT INTO group_members (user_id, group_id, approved) VALUES (?, ?, 1)",
                (admin_id, gid)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_group(self, name):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, name, admin, admin_on_leave FROM groups WHERE name = ?",
            (name,)
        )
        return cursor.fetchone()

    def list_groups(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT g.id, g.name, u.username AS admin_username, g.admin_on_leave
            FROM groups g
            JOIN users u ON g.admin = u.id
        """)
        return cursor.fetchall()

    def update_group_admin(self, group_id, new_admin_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE groups SET admin = ? WHERE id = ?",
            (new_admin_id, group_id)
        )
        self.conn.commit()

    def delete_group(self, group_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
            cursor.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
            cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
            self.conn.commit()
            return True
        except Exception:
            return False

    # --------- MEMBROS DE GRUPO ---------
    def request_join_group(self, user_id, group_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO group_members (user_id, group_id, approved) VALUES (?, ?, 0)",
                (user_id, group_id)
            )
            self.conn.commit()
            return True
        except Exception:
            return False

    def approve_member(self, user_id, group_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE group_members SET approved = 1 WHERE user_id = ? AND group_id = ?",
            (user_id, group_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def add_member_approved(self, user_id, group_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO group_members (user_id, group_id, approved) VALUES (?, ?, 1)",
            (user_id, group_id)
        )
        self.conn.commit()
        return True

    def remove_member(self, user_id, group_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM group_members WHERE user_id = ? AND group_id = ?",
            (user_id, group_id)
        )
        self.conn.commit()

    def membership_status(self, user_id, group_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT approved FROM group_members WHERE user_id = ? AND group_id = ?",
            (user_id, group_id)
        )
        row = cursor.fetchone()
        return None if not row else row[0]

    def list_group_members(self, group_id, approved_only=False):
        cursor = self.conn.cursor()
        if approved_only:
            cursor.execute("""
                SELECT u.id, u.username
                FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = ? AND gm.approved = 1
                ORDER BY gm.joined_at ASC
            """, (group_id,))
        else:
            cursor.execute("""
                SELECT u.id, u.username, gm.approved
                FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = ?
            """, (group_id,))
        return cursor.fetchall()

    def list_pending_requests(self, group_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.username
            FROM group_members gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.group_id = ? AND gm.approved = 0
        """, (group_id,))
        return cursor.fetchall()

    # --------- MENSAGENS DE GRUPO ---------
    def save_group_message(self, group_id, sender_id, content):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO group_messages (group_id, sender, content) VALUES (?, ?, ?)",
            (group_id, sender_id, content)
        )
        self.conn.commit()

    def get_group_messages(self, group_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.username AS sender_name, gm.content, gm.timestamp
            FROM group_messages gm
            JOIN users u ON gm.sender = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.timestamp ASC
        """, (group_id,))
        return cursor.fetchall()

    # --------- SOLICITAÇÕES DE BANIMENTO ---------
    def create_ban_request(self, requester_id, target_id, reason):
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO ban_requests (requester, target_user, reason) 
            VALUES (?, ?, ?)""",
            (requester_id, target_id, reason)
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_ban_requests(self, status='pending'):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT br.id, ru.username AS requester, tu.username AS target,
                   br.reason, br.timestamp
            FROM ban_requests br
            JOIN users ru ON br.requester = ru.id
            JOIN users tu ON br.target_user = tu.id
            WHERE br.status = ?
            ORDER BY br.timestamp DESC
        """, (status,))
        return cursor.fetchall()

    def approve_ban_request(self, request_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE ban_requests SET status = 'approved' WHERE id = ?",
            (request_id,)
        )
        self.conn.commit()

    def reject_ban_request(self, request_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE ban_requests SET status = 'rejected' WHERE id = ?",
            (request_id,)
        )
        self.conn.commit()