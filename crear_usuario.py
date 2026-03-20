import sqlite3
from werkzeug.security import generate_password_hash

def actualizar_seguridad():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()

    # 1. Aseguramos que la tabla exista
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')

    # 2. Borramos TODAS las credenciales antiguas por seguridad (adiós admin123)
    cursor.execute("DELETE FROM usuarios")

    # 3. DEFINE TUS NUEVAS CREDENCIALES AQUÍ
    # Te sugiero no usar "admin", usa algo como "alfredo.ti" o "strd_admin"
    user = "Soporte"
    password_plana = "@dm1nistr4d0rSTRD25*!"

    # 4. Encriptación (Hashing)
    password_encriptada = generate_password_hash(password_plana)

    try:
        # Insertamos el nuevo superusuario
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user, password_encriptada))
        conn.commit()
        print(f"✅ Seguridad actualizada. Nuevo acceso configurado para: '{user}'")
    except Exception as e:
        print(f"⚠️ Ocurrió un error: {e}")

    conn.close()

if __name__ == "__main__":
    actualizar_seguridad()