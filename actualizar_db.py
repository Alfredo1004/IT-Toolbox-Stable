import sqlite3
import os

# Localizamos la ruta de la base de datos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'soporte.db')

def actualizar():
    try:
        # Conectamos a la base de datos
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Ejecutamos el comando para agregar la columna
        print("Intentando agregar la columna 'ubicacion' a la tabla 'celulares'...")
        cursor.execute("ALTER TABLE celulares ADD COLUMN ubicacion TEXT;")
        
        # Guardamos los cambios
        conn.commit()
        print("✅ Columna 'ubicacion' agregada con éxito.")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️ La columna 'ubicacion' ya existe en la tabla.")
        else:
            print(f"❌ Error operativo: {e}")
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    actualizar()