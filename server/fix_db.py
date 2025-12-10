import sqlite3

# Conecta no seu banco de dados atual
print("🔧 Iniciando reparo no banco de dados...")
try:
    conn = sqlite3.connect("whatsut.db")
    cursor = conn.cursor()

    # 1. Tenta adicionar a coluna que falta na tabela de grupos
    try:
        print(" -> Adicionando coluna 'admin_on_leave' na tabela groups...")
        cursor.execute("ALTER TABLE groups ADD COLUMN admin_on_leave TEXT DEFAULT 'transfer'")
        print("    ✅ Sucesso!")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("    ⚠️ A coluna já existia (tudo certo).")
        else:
            print(f"    ❌ Erro: {e}")

    # 2. Tenta adicionar a coluna de data nos membros (importante para ordem de admin)
    try:
        print(" -> Adicionando coluna 'joined_at' na tabela group_members...")
        cursor.execute("ALTER TABLE group_members ADD COLUMN joined_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        print("    ✅ Sucesso!")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("    ⚠️ A coluna já existia (tudo certo).")
        else:
            print(f"    ❌ Erro: {e}")

    conn.commit()
    conn.close()
    print("\n🚀 Banco de dados atualizado! Agora você pode rodar o servidor.")

except Exception as e:
    print(f"\n❌ Erro crítico ao abrir o banco: {e}")