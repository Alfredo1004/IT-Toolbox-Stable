import requests, psutil, socket, os, subprocess, sys, ctypes, winreg, platform
from datetime import datetime

# CONFIGURACIÓN: Ajusta la URL de tu servidor en la nube
URL_DESTINO = "https://AlfredoV.pythonanywhere.com/reporte_agente"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_hw_info(tipo):
    # Comandos WMIC optimizados para extraer solo el valor, omitiendo encabezados
    cmds = {
        "serial": "wmic bios get serialnumber",
        "modelo": "wmic csproduct get name",
        "marca": "wmic computersystem get manufacturer",
        "cpu": "wmic cpu get name"
    }
    try:
        # Ejecutamos el comando y limpiamos la salida
        res = subprocess.check_output(cmds[tipo], shell=True).decode(errors='ignore').split('\n')
        # Filtramos líneas vacías y el nombre de la columna (ej. "SerialNumber")
        datos = [line.strip() for line in res if line.strip() and tipo.upper() not in line.upper() and "NAME" not in line.upper() and "MANUFACTURER" not in line.upper()]
        return datos[0] if datos else "N/A"
    except:
        return "N/A"

def get_ip_address():
    try:
        # Método de conexión UDP: el más fiable para detectar la IP de la interfaz de red activa
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

def get_mac_address():
    try:
        import uuid
        return ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8*6, 8)][::-1]).upper()
    except:
        return "N/A"

def get_installed_software():
    software_list = []
    paths = [r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 
             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"]
    for path in paths:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    try: version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                    except: version = "N/A"
                    if name and "Update" not in name:
                        software_list.append({"nombre": name, "version": version})
                except: continue
        except: continue
    return software_list

def enviar_reporte():
    try:
        hostname = socket.gethostname()
        
        # Diccionario de datos (JSON) sincronizado exactamente con app.py
        payload = {
            "equipo": hostname,
            "usuario": os.getlogin(),
            "ip": get_ip_address(),
            "mac": get_mac_address(),
            "serie": get_hw_info("serial"),
            "modelo": get_hw_info("modelo"),
            "marca": get_hw_info("marca"),
            "procesador": get_hw_info("cpu"),
            "ram_total": f"{round(psutil.virtual_memory().total / (1024**3))}GB",
            "disco_total": f"{round(psutil.disk_usage('C:').total / (1024**3))}GB",
            "ram_uso": f"{psutil.virtual_memory().percent}%",
            "disco_libre": f"{psutil.disk_usage('C:').free // (1024**3)}GB Libres",
            "software": get_installed_software()
        }
        
        # Envío de datos al servidor
        requests.post(URL_DESTINO, json=payload, timeout=20)
        
        # Mensaje de confirmación al usuario
        ctypes.windll.user32.MessageBoxW(0, f"✅ Auditoría de Sistema completada para {hostname}.\n\nLos datos técnicos han sido enviados al servidor de TI.", "IT Toolbox Pro", 0x40)
    except Exception as e:
        # En caso de error (como falta de internet), no mostramos nada para no interrumpir al usuario
        pass

if __name__ == "__main__":
    if is_admin():
        enviar_reporte()
    else:
        # Si no tiene permisos, solicita elevación automáticamente
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)