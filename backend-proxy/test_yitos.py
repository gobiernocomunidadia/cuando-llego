import urllib.request
import ssl
import json
import xml.etree.ElementTree as ET

AUTOBUSES_URL = "https://clswsantafe.smartmovepro.net/ModuloParadas/SWParadas.asmx"
YITOS_USUARIO = "YITOS"
YITOS_CLAVE = "WEBYITOS1045"
YITOS_COD_ENTIDAD = "628"

payload_xml = f"""
  <usuario>{YITOS_USUARIO}</usuario>
  <clave>{YITOS_CLAVE}</clave>
  <codigoEntidad>{YITOS_COD_ENTIDAD}</codigoEntidad>
"""

method_name = "RecuperarBanderasEnFuncionamiento"
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

ssl_context = ssl._create_unverified_context()

try:
    req = urllib.request.Request(AUTOBUSES_URL, data=soap_payload.encode('utf-8'), headers=headers, method="POST")
    with urllib.request.urlopen(req, context=ssl_context, timeout=15) as response:
        body = response.read().decode('utf-8')
        root = ET.fromstring(body)
        namespaces = {'ns': 'http://clsw.smartmovepro.net/'}
        result_node = root.find(f'.//ns:{method_name}Result', namespaces)
        print(result_node.text)
except Exception as e:
    print(f"Error: {e}")
