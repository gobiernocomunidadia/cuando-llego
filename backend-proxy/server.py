import http.server
import urllib.request
import urllib.parse
import hmac
import hashlib
import time
import json
import os
import sys
import ssl
import xml.etree.ElementTree as ET

# Helper to load environment variables from .env file manually
def load_env(env_path):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

# Load env file in the same directory
base_dir = os.path.dirname(os.path.abspath(__file__))
load_env(os.path.join(base_dir, ".env"))

PORT = int(os.environ.get("PORT", 3000))
API_KEY = os.environ.get("BONDICOM_API_KEY", "5f81c3a7d9be4f126ab8e47cd2f63a0e91b7c4d2")
SECRET_KEY = os.environ.get("BONDICOM_SECRET_KEY", "c1e47ab92d5f83a6b74e2190fa6d3bc58e2a7f41")
BASE_URL = os.environ.get("BONDICOM_BASE_URL", "http://www.ojosauron.com.ar:5000/api/bondicom")

# Autobuses Santa Fe (Smartmove) API Config
AUTOBUSES_URL = os.environ.get("AUTOBUSES_URL", "https://clswsantafe.smartmovepro.net/ModuloParadas/SWParadas.asmx")
AUTOBUSES_USUARIO = os.environ.get("AUTOBUSES_USUARIO", "WEB.BSASAUT")
AUTOBUSES_CLAVE = os.environ.get("AUTOBUSES_CLAVE", "PAR.SW.BSASAU")
AUTOBUSES_COD_EMPRESA = os.environ.get("AUTOBUSES_COD_EMPRESA", "924")

# Yitos API Config
YITOS_USUARIO = os.environ.get("YITOS_USUARIO", "YITOS")
YITOS_CLAVE = os.environ.get("YITOS_CLAVE", "WEBYITOS1045")
YITOS_COD_EMPRESA = os.environ.get("YITOS_COD_EMPRESA", "1045")
YITOS_COD_ENTIDAD = os.environ.get("YITOS_COD_ENTIDAD", "628")
YITOS_OFFSET = 10000

def call_bondicom(remote_url):
    """Encapsulates the signature generation and request for the Bondicom API."""
    timestamp = str(int(time.time()))
    body = ""
    data_to_sign = API_KEY + timestamp + body
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        data_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        'X-Api-Key': API_KEY,
        'X-TIMESTAMP': timestamp,
        'X-SIGNATURE': signature,
        'Accept': 'application/json',
        'User-Agent': 'Python-Proxy-Server'
    }

    req = urllib.request.Request(remote_url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, response.read()

def call_autobuses_soap(method_name, payload_xml):
    """Executes a SOAP 1.1 request to the Autobuses ASMX web service and parses the result."""
    soap_action = f"http://clsw.smartmovepro.net/{method_name}"
    
    soap_payload = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <{method_name} xmlns="http://clsw.smartmovepro.net/">
      {payload_xml}
    </{method_name}>
  </soap:Body>
</soap:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{soap_action}"',
        "Content-Length": str(len(soap_payload))
    }

    # Bypass SSL verification since the Autobuses server certificate is expired
    ssl_context = ssl._create_unverified_context()
    
    req = urllib.request.Request(AUTOBUSES_URL, data=soap_payload.encode('utf-8'), headers=headers, method="POST")
    with urllib.request.urlopen(req, context=ssl_context, timeout=15) as response:
        body = response.read().decode('utf-8')
        root = ET.fromstring(body)
        namespaces = {'ns': 'http://clsw.smartmovepro.net/'}
        result_node = root.find(f'.//ns:{method_name}Result', namespaces)
        if result_node is not None:
            return result_node.text
        else:
            raise Exception("SOAP response missing result node")

class ProxyHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        sys_log = f"[{self.log_date_time_string()}] {format % args}"
        print(sys_log, flush=True)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)

        if path == "/api/lineas":
            try:
                # 1. Fetch Bondicom lines
                bondicom_lines = []
                try:
                    _, body = call_bondicom(f"{BASE_URL}/lineas")
                    bondicom_lines = json.loads(body.decode('utf-8'))
                except Exception as e:
                    print(f"Error fetching Bondicom lines: {e}", flush=True)

                # 2. Fetch Autobuses lines
                autobuses_lines = []
                try:
                    payload = f"""
                      <usuario>{AUTOBUSES_USUARIO}</usuario>
                      <clave>{AUTOBUSES_CLAVE}</clave>
                      <codigoEmpresa>{AUTOBUSES_COD_EMPRESA}</codigoEmpresa>
                      <isSublinea>false</isSublinea>
                    """
                    res = call_autobuses_soap("RecuperarLineasPorCodigoEmpresa", payload)
                    data = json.loads(res)
                    if data.get("CodigoEstado") == 0:
                        for l in data.get("lineas", []):
                            line_num = l.get("Descripcion", "")
                            line_id = int(l.get("CodigoLineaParada"))
                            autobuses_lines.append({
                                "id": line_id,
                                "ds": f"Linea {line_num}" if not line_num.lower().startswith("linea") else line_num
                            })
                except Exception as e:
                    print(f"Error fetching Autobuses lines: {e}", flush=True)

                # 3. Fetch Yitos lines
                yitos_lines = []
                try:
                    payload = f"""
                      <usuario>{YITOS_USUARIO}</usuario>
                      <clave>{YITOS_CLAVE}</clave>
                      <codigoEmpresa>{YITOS_COD_EMPRESA}</codigoEmpresa>
                      <isSublinea>false</isSublinea>
                    """
                    res = call_autobuses_soap("RecuperarLineasPorCodigoEmpresa", payload)
                    data = json.loads(res)
                    if data.get("CodigoEstado") == 0:
                        for l in data.get("lineas", []):
                            line_num = l.get("Descripcion", "")
                            line_id = int(l.get("CodigoLineaParada"))
                            yitos_lines.append({
                                "id": line_id + YITOS_OFFSET,
                                "ds": f"Linea {line_num}" if not line_num.lower().startswith("linea") else line_num
                            })
                    else:
                        # Fallback to RecuperarBanderasEnFuncionamiento
                        payload2 = f"""
                          <usuario>{YITOS_USUARIO}</usuario>
                          <clave>{YITOS_CLAVE}</clave>
                          <codigoEntidad>{YITOS_COD_ENTIDAD}</codigoEntidad>
                        """
                        res2 = call_autobuses_soap("RecuperarBanderasEnFuncionamiento", payload2)
                        data2 = json.loads(res2)
                        if data2.get("CodigoEstado") == 0:
                            seen_lines = set()
                            for b in data2.get("banderas", []):
                                line_id = int(b.get("CodigoParada"))
                                line_desc = b.get("DescripcionCorta", "YITOS")
                                if line_id not in seen_lines:
                                    seen_lines.add(line_id)
                                    yitos_lines.append({
                                        "id": line_id + YITOS_OFFSET,
                                        "ds": f"Linea {line_desc}"
                                    })
                except Exception as e:
                    print(f"Error fetching Yitos lines: {e}", flush=True)

                merged_lines = bondicom_lines + autobuses_lines + yitos_lines
                self.send_json_response(200, merged_lines)
            except Exception as e:
                self.send_error_response(500, f"Error listing lines: {str(e)}")
            return

        elif path == "/api/recorridos":
            linea_id_str = query_params.get("linea", [None])[0]
            if not linea_id_str:
                self.send_error_response(400, 'Missing parameter "linea"')
                return
            
            try:
                linea_id = int(linea_id_str)
                if linea_id >= 10000:
                    real_linea_id = linea_id - YITOS_OFFSET
                    payload = f"""
                      <usuario>{YITOS_USUARIO}</usuario>
                      <clave>{YITOS_CLAVE}</clave>
                      <codigoLineaParada>{real_linea_id}</codigoLineaParada>
                      <isSublinea>false</isSublinea>
                      <isInteligente>false</isInteligente>
                    """
                    res = call_autobuses_soap("RecuperarParadasCompletoPorLinea", payload)
                    data = json.loads(res)
                    
                    recorridos = []
                    if data.get("CodigoEstado") == 0:
                        paradas_dict = data.get("paradas", {})
                        for bandera_key, paradas_list in paradas_dict.items():
                            desc = bandera_key
                            if paradas_list:
                                desc = paradas_list[0].get("AbreviaturaAmpliadaBandera") or bandera_key
                            recorridos.append({
                                "id": f"{linea_id}_{bandera_key}",
                                "ds": f"{bandera_key} - {desc}"
                            })
                    self.send_json_response(200, recorridos)
                elif linea_id >= 1000:
                    payload = f"""
                      <usuario>{AUTOBUSES_USUARIO}</usuario>
                      <clave>{AUTOBUSES_CLAVE}</clave>
                      <codigoLineaParada>{linea_id}</codigoLineaParada>
                      <isSublinea>false</isSublinea>
                      <isInteligente>false</isInteligente>
                    """
                    res = call_autobuses_soap("RecuperarParadasCompletoPorLinea", payload)
                    data = json.loads(res)
                    
                    recorridos = []
                    if data.get("CodigoEstado") == 0:
                        paradas_dict = data.get("paradas", {})
                        for bandera_key, paradas_list in paradas_dict.items():
                            # Find description from the first parada
                            desc = bandera_key
                            if paradas_list:
                                desc = paradas_list[0].get("AbreviaturaAmpliadaBandera") or bandera_key
                            recorridos.append({
                                "id": f"{linea_id}_{bandera_key}",
                                "ds": f"{bandera_key} - {desc}"
                            })
                    self.send_json_response(200, recorridos)
                else:
                    # Forward to Bondicom
                    status, body = call_bondicom(f"{BASE_URL}/recorridos?linea={linea_id}")
                    self.send_response_body(status, body)
            except Exception as e:
                self.send_error_response(500, f"Error listing recorridos: {str(e)}")
            return

        elif path == "/api/paradas":
            recorrido = query_params.get("recorrido", [None])[0]
            
            if not recorrido:
                self.send_error_response(400, 'Missing parameter "recorrido"')
                return

            try:
                if "_" in recorrido:
                    # Autobuses recorrido format: lineaId_bandera
                    linea_id_str, bandera = recorrido.split("_", 1)
                    linea_id = int(linea_id_str)
                    
                    if linea_id >= 10000:
                        real_linea_id = linea_id - YITOS_OFFSET
                        usuario = YITOS_USUARIO
                        clave = YITOS_CLAVE
                    else:
                        real_linea_id = linea_id
                        usuario = AUTOBUSES_USUARIO
                        clave = AUTOBUSES_CLAVE
                        
                    payload = f"""
                      <usuario>{usuario}</usuario>
                      <clave>{clave}</clave>
                      <codigoLineaParada>{real_linea_id}</codigoLineaParada>
                      <isSublinea>false</isSublinea>
                      <isInteligente>false</isInteligente>
                    """
                    res = call_autobuses_soap("RecuperarParadasCompletoPorLinea", payload)
                    data = json.loads(res)
                    
                    mapped_paradas = []
                    if data.get("CodigoEstado") == 0:
                        paradas_dict = data.get("paradas", {})
                        paradas_list = paradas_dict.get(bandera, [])
                        for p in paradas_list:
                            # Skip placeholder/terminal items
                            if p.get("Identificador") == "9999999999":
                                continue
                            
                            lat_str = p.get("LatitudParada")
                            lng_str = p.get("LongitudParada")
                            
                            mapped_paradas.append({
                                "id": p.get("Identificador"),
                                "ds": p.get("Descripcion"),
                                "latitud": float(lat_str) if lat_str else 0.0,
                                "longitud": float(lng_str) if lng_str else 0.0
                            })
                    self.send_json_response(200, mapped_paradas)
                else:
                    # Forward to Bondicom
                    status, body = call_bondicom(f"{BASE_URL}/paradas-por-recorrido?recorrido={recorrido}")
                    self.send_response_body(status, body)
            except Exception as e:
                self.send_error_response(500, f"Error listing paradas: {str(e)}")
            return

        elif path == "/api/prediccion":
            parada = query_params.get("parada", [None])[0]
            linea_id_str = query_params.get("linea", [None])[0]
            
            if not parada or not linea_id_str:
                self.send_error_response(400, 'Missing parameters "parada" and/or "linea"')
                return

            try:
                linea_id = int(linea_id_str)
                if linea_id >= 1000:
                    if linea_id >= 10000:
                        real_linea_id = linea_id - YITOS_OFFSET
                        usuario = YITOS_USUARIO
                        clave = YITOS_CLAVE
                    else:
                        real_linea_id = linea_id
                        usuario = AUTOBUSES_USUARIO
                        clave = AUTOBUSES_CLAVE

                    payload = f"""
                      <usuario>{usuario}</usuario>
                      <clave>{clave}</clave>
                      <identificadorParada>{parada}</identificadorParada>
                      <codigoLineaParada>{real_linea_id}</codigoLineaParada>
                      <codigoAplicacion>1</codigoAplicacion>
                      <localidad>Lomas de Zamora</localidad>
                      <isSublinea>false</isSublinea>
                      <isSoloAdaptados>false</isSoloAdaptados>
                    """
                    res = call_autobuses_soap("RecuperarProximosArribos", payload)
                    data = json.loads(res)
                    
                    mapped_predictions = []
                    if data.get("CodigoEstado") == 0:
                        arribos_list = data.get("arribos", [])
                        for a in arribos_list:
                            lat_val = a.get("Latitud")
                            lng_val = a.get("Longitud")
                            
                            mapped_predictions.append({
                                "interno": a.get("IdentificadorCoche"),
                                "lat": float(lat_val) if lat_val else 0.0,
                                "lon": float(lng_val) if lng_val else 0.0,
                                "latitud": float(lat_val) if lat_val else 0.0,
                                "longitud": float(lng_val) if lng_val else 0.0,
                                "tiempo": a.get("Arribo"),
                                "tiempoEstimado": a.get("Arribo"),
                                "cartel": a.get("DescripcionBandera"),
                                "ramal": a.get("DescripcionBandera")
                            })
                    self.send_json_response(200, mapped_predictions)
                else:
                    # Forward to Bondicom
                    status, body = call_bondicom(f"{BASE_URL}/Prediccion?fkParada={parada}&fkLineaForzada={linea_id}")
                    self.send_response_body(status, body)
            except Exception as e:
                self.send_error_response(500, f"Error fetching predictions: {str(e)}")
            return

        else:
            self.send_error_response(404, "Not Found")
            return

    def send_json_response(self, code, obj):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode('utf-8'))

    def send_response_body(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))

def run():
    server_address = ('', PORT)
    httpd = http.server.HTTPServer(server_address, ProxyHTTPRequestHandler)
    print(f"Secure Python API Proxy Server running at http://localhost:{PORT}...", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping proxy server...", flush=True)

if __name__ == '__main__':
    run()

