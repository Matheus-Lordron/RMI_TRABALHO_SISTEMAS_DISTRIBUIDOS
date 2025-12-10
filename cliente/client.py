# client/client.py
import Pyro5.api

def test_connection():
    try:
        server = Pyro5.api.Proxy("PYRONAME:whatsut.server")
        response = server.ping()
        print("🟢 Resposta do servidor:", response)
    except:
        print("🔴 Não foi possível conectar ao servidor!")

if __name__ == "__main__":
    test_connection()
