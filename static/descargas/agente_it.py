import requests, psutil, socket, os, subprocess, sys, ctypes, winreg
from datetime import datetime

SERVER_IP = "192.168.128.107" 
URL_DESTINO = f"https://AlfredoV.pythonanywhere.com/reporte_agente"

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def get_hw_info(tipo):
    targets = ["csproduct", "bios", "systemenclosure"]
    for t in targets:
        try:
            if tipo == "serial": cmd = f"wmic {t} get identifyingnumber" if t == "csproduct" else f"wmic {t} get serialnumber"
            elif tipo == "modelo": cmd = f"wmic {t} get name"
            else: cmd = f"wmic {t} get vendor" if t == "csproduct" else "wmic computersystem get manufacturer"
            res = subprocess.check_output(cmd, shell=True).decode(errors='ignore').split('\n')
            val = res[1].strip()
            if val and not any(x in val.lower() for x in ["identifying", "serial", "name"]): return val
        except: continue
    return "N/A"

def get_mac_address():
    try:
        import uuid
        return ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8*6, 8)][::-1]).upper()
    except: return "N/A"

def get_installed_software():
    software_list = []
    # Rutas del registro de Windows para programas instalados (32 y 64 bits)
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
                    # Filtrar actualizaciones de Windows o entradas vacías
                    if name and "Update" not in name:
                        software_list.append({"nombre": name, "version": version})
                except: continue
        except: continue
    return software_list

def enviar_reporte():
    try:
        hostname = socket.gethostname()
        payload = {
            "equipo": hostname, "usuario": os.getlogin(),
            "ip_v4": socket.gethostbyname(hostname),
            "ram_total": f"{round(psutil.virtual_memory().total / (1024**3))}GB",
            "disco_total": f"{round(psutil.disk_usage('C:').total / (1024**3))}GB",
            "ram_uso": f"{psutil.virtual_memory().percent}%",
            "disco_libre": f"{psutil.disk_usage('C:').free // (1024**3)}GB Libres",
            "n_serie": get_hw_info("serial"), "marca": get_hw_info("brand"), "modelo": get_hw_info("modelo"),
            "mac": get_mac_address(),
            "software": get_installed_software() # Nueva data
        }
        requests.post(URL_DESTINO, json=payload, timeout=20)
        ctypes.windll.user32.MessageBoxW(0, f"✅ Reporte de Auditoría enviado para {hostname}", "IT Toolbox", 0x40)
    except: pass

if __name__ == "__main__":
    if is_admin(): enviar_reporte()
    else: ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)