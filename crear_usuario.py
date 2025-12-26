import sqlite3
from werkzeug.security import generate_password_hash

def inicializar_seguridad():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
    
    # REEMPLAZA 'tu_usuario' y 'tu_password' con lo que desees usar
    user = "admin"
    password_encriptada = generate_password_hash("admin123")
    
    try:
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user, password_encriptada))
        conn.commit()
        print(f"✅ Usuario '{user}' creado.")
    except:
        print("⚠️ El usuario ya existe.")
    conn.close()

if __name__ == "__main__":
    inicializar_seguridad()