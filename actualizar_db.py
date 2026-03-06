import sqlite3
conn = sqlite3.connect('soporte.db')
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE gastos ADD COLUMN factura_pdf TEXT DEFAULT ''")
    print("✅ Columna añadida en local.")
except:
    print("⚠️ La columna ya existía.")
conn.commit()
conn.close()