import requests, psutil, socket, os, subprocess, sys, ctypes

SERVER_IP = "192.168.128.107" 
URL_DESTINO = f"http://{SERVER_IP}:5000/reporte_agente"

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def get_hw_info(tipo):
    targets = ["bios", "csproduct", "computersystem"]
    for t in targets:
        try:
            if tipo == "serial": cmd = f"wmic {t} get serialnumber" if t != "csproduct" else "wmic csproduct get identifyingnumber"
            elif tipo == "modelo": cmd = f"wmic {t} get name"
            else: cmd = f"wmic {t} get manufacturer" if t != "csproduct" else "wmic csproduct get vendor"
            res = subprocess.check_output(cmd, shell=True).decode(errors='ignore').split('\n')
            val = res[1].strip()
            if val and not any(x in val.lower() for x in ["name", "identifying", "serial", "vendor"]):
                return val
        except: continue
    return "N/A"

def get_mac_address():
    try:
        import uuid
        return ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8*6, 8)][::-1]).upper()
    except: return "N/A"

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
            "n_serie": get_hw_info("serial"), "marca": get_hw_info("marca"), "modelo": get_hw_info("modelo"),
            "mac": get_mac_address()
        }
        requests.post(URL_DESTINO, json=payload, timeout=10)
        ctypes.windll.user32.MessageBoxW(0, f"✅ Reporte enviado para {hostname}", "IT Toolbox", 0x40)
    except: pass

if __name__ == "__main__":
    if is_admin(): enviar_reporte()
    else: ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)