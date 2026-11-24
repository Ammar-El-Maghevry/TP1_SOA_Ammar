#!/usr/bin/env python3
"""Vérifications HTTP/SOAP du TP (Python 3, JDK 17 et Maven requis)."""

from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
BIB = "http://supnum.mr/bib"
SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS = {
    "wsdl": "http://schemas.xmlsoap.org/wsdl/",
    "soap": "http://schemas.xmlsoap.org/wsdl/soap/",
    "xs": "http://www.w3.org/2001/XMLSchema",
}
ACTION = BIB + "/emprunterLivre"
CHECKS = 0


def check(condition, description):
    global CHECKS
    if not condition:
        raise AssertionError(description)
    CHECKS += 1
    print("OK : " + description, flush=True)


def get(url):
    with urlopen(url, timeout=5) as response:
        return response.read()


def xml_file(name):
    return (ROOT / "xml" / name).read_text(encoding="utf-8")


def post(url, xml, action="", content_type="text/xml; charset=utf-8"):
    request = Request(url, data=xml.encode("utf-8"), headers={
        "Content-Type": content_type,
        "SOAPAction": '"' + action + '"',
    })
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.read()


def expect_response(url, name, status, code=None, reason=None, action="", xml=None,
                    content_type="text/xml; charset=utf-8"):
    actual_status, body = post(url, xml if xml is not None else xml_file(name),
                               action, content_type)
    check(actual_status == status,
          f"{name} : HTTP {actual_status} (attendu {status})")
    root = ET.fromstring(body) if body else None
    if code is not None:
        fault = root.find(f"{{{SOAP}}}Body/{{{SOAP}}}Fault")
        check(fault is not None, name + " : Fault SOAP 1.1")
        actual_code = fault.findtext("faultcode", "").split(":")[-1]
        actual_reason = fault.findtext("faultstring", "")
        check(actual_code == code, f"{name} : faultcode={actual_code}")
        if reason is not None:
            check(reason in actual_reason, f"{name} : {actual_reason}")
        else:
            print("  faultstring : " + actual_reason, flush=True)
    return root


@contextmanager
def server(project):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}/bib/EmpruntService"
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
        process = subprocess.Popen(
            ["mvn", "-q", "compile", "exec:java", "-Dexec.args=" + url],
            cwd=project, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 120
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Le serveur Maven s'est arrêté.")
                try:
                    get(url + "?wsdl")
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Le serveur n'est pas prêt après 120 secondes.")
                    time.sleep(0.25)
            yield url
        except BaseException:
            log.seek(0)
            print(log.read(), flush=True)
            raise
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def codefirst():
    with server(ROOT / "emprunt-codefirst") as url:
        wsdl = ET.fromstring(get(url + "?wsdl"))
        schema = ET.fromstring(get(url + "?xsd=1"))
        operations = wsdl.findall("wsdl:portType/wsdl:operation", NS)
        check({op.get("name") for op in operations} == {"emprunterLivre", "rendreLivre"},
              "code-first : deux opérations dans le portType")
        for op in operations:
            print("  opération : " + ET.tostring(op, encoding="unicode"), flush=True)
        binding = wsdl.find("wsdl:binding/soap:binding", NS)
        check(binding.get("style") == "document", "code-first : SOAP 1.1 document/literal")
        check(all(body.get("use") == "literal"
                  for body in wsdl.findall(".//soap:body", NS)), "code-first : use=literal")
        for name in ("isbn", "dateRetour"):
            elements = schema.findall(f".//xs:element[@name='{name}']", NS)
            check(bool(elements) and all(e.get("type").split(":")[-1] == "string"
                                        for e in elements), name + " : xs:string en code-first")
        check(schema.find(".//xs:pattern", NS) is None, "code-first : aucun motif ISBN dans le XSD")

        soapui = xml_file("01-emprunter.xml").replace("978-2-07-036822-8", "978-1-234-5678-9")
        expect_response(url, "requête étape 2", 200, xml=soapui)
        response = expect_response(url, "01-emprunter.xml", 200)
        check(response.findtext(".//numero") == "E-2026-0813", "code-first : numéro d'emprunt incrémenté")
        check(response.findtext(".//dateRetour") == str(date.today() + timedelta(days=14)),
              "code-first : date de retour à J+14")
        expect_response(url, "emprunt répété", 500, "Server", "Livre indisponible",
                        xml=xml_file("01-emprunter.xml"))
        expect_response(url, "02-emprunter-12.xml", 500, "VersionMismatch")
        status, _ = post(url, xml_file("02-emprunter-12.xml"),
                         content_type="application/soap+xml; charset=utf-8")
        check(status == 415, "SOAP 1.2 avec application/soap+xml : HTTP 415")
        expect_response(url, "04-rendre-corrige.xml", 200)
        expect_response(url, "05-isbn-invalide.xml", 500, "Client", "ISBN mal formé : 978-2-10")
        response = expect_response(url, "06-livre-indisponible.xml", 500, "Server", "Livre indisponible")
        detail = response.find(f".//detail/{{{BIB}}}LivreIndisponible")
        check(detail is not None and detail.findtext("isbn") == "978-2-10-074444-4"
              and detail.findtext("retourPrevu") == "2026-12-02", "Fault déclarée : détail ISBN et retourPrevu")
        expect_response(url, "07-must-understand.xml", 500, "MustUnderstand")
        optional = xml_file("07-must-understand.xml").replace('mustUnderstand="1"', 'mustUnderstand="0"')
        optional = optional.replace("978-2-07-036822-8", "978-1-111-1111-1")
        expect_response(url, "mustUnderstand=0", 200, xml=optional)
        expect_response(url, "08-retour-invalide.xml", 500, "Client", "Numéro d'emprunt inconnu : INVALIDE")
        missing = xml_file("04-rendre-corrige.xml").replace(
            "<numeroEmprunt>E-2026-0812</numeroEmprunt>", "<bib:numero>E-2026-0812</bib:numero>")
        expect_response(url, "paramètre mal nommé", 500, "Client", "Numéro d'emprunt inconnu : null", xml=missing)
        header = "    <soap:Header>\n        <bib:jeton>abc123</bib:jeton>\n    </soap:Header>\n"
        misplaced = xml_file("04-rendre-corrige.xml").replace(header, "")
        misplaced = misplaced.replace("</soap:Envelope>", header + "</soap:Envelope>")
        expect_response(url, "Header après Body (tolérance Metro)", 200, xml=misplaced)


def contractfirst(project, validation=True, supplied_wsdl=True):
    with server(project) as url:
        wsdl = ET.fromstring(get(url + "?wsdl"))
        if supplied_wsdl:
            check(wsdl.find(".//xs:pattern", NS) is not None, "contract-first : motif ISBN publié")
            date_element = wsdl.find(".//xs:element[@name='dateRetour']", NS)
            check(date_element.get("type").split(":")[-1] == "date", "contract-first : dateRetour est xs:date")
        else:
            schema = ET.fromstring(get(url + "?xsd=1"))
            check(schema.find(".//xs:pattern", NS) is None, "sans wsdlLocation : motif ISBN perdu")
            check(schema.find(".//xs:simpleType[@name='IsbnType']", NS) is None,
                  "sans wsdlLocation : IsbnType perdu")
            date_element = schema.find(".//xs:element[@name='dateRetour']", NS)
            check(date_element.get("type").split(":")[-1] == "date", "sans wsdlLocation : xs:date conservé")

        response = expect_response(url, "09-emprunter-contractfirst.xml", 200, action=ACTION)
        check(response.findtext(f".//{{{BIB}}}numero") == "E-2026-0812", "contract-first : numéro retourné")
        check(response.findtext(f".//{{{BIB}}}dateRetour") == str(date.today() + timedelta(days=14)),
              "contract-first : date de retour à J+14")
        response = expect_response(url, "10-indisponible-contractfirst.xml", 500, "Server",
                                   "Livre indisponible", action=ACTION)
        detail = response.find(f".//detail/{{{BIB}}}LivreIndisponible")
        check(detail is not None and detail.findtext(f"{{{BIB}}}isbn") == "978-2-10-074444-4"
              and detail.findtext(f"{{{BIB}}}retourPrevu") == "2026-12-02", "contract-first : détail qualifié")
        if validation:
            expect_response(url, "11-isbn-invalide-contractfirst.xml", 500, "Client",
                            "cvc-pattern-valid", action=ACTION)
            expect_response(url, "01-emprunter.xml non adapté", 500, "Client", "idAdherent", action=ACTION,
                            xml=xml_file("01-emprunter.xml"))
        else:
            expect_response(url, "ISBN invalide sans validation effective", 200, action=ACTION,
                            xml=xml_file("11-isbn-invalide-contractfirst.xml"))


def main():
    for file in sorted((ROOT / "xml").glob("*.xml")):
        ET.parse(file)
    check(True, "tous les fichiers XML sont bien formés")
    fault = ET.parse(ROOT / "xml/03-fault-sender-12.xml")
    soap12 = "{http://www.w3.org/2003/05/soap-envelope}"
    check(fault.findtext(f"{soap12}Body/{soap12}Fault/{soap12}Code/{soap12}Value") == "soap:Sender",
          "Fault manuelle : SOAP 1.2 Sender")
    codefirst()
    contractfirst(ROOT / "emprunt-contractfirst")
    # Les deux expériences de l'étape 6 utilisent des copies temporaires du projet.
    with tempfile.TemporaryDirectory(prefix="tp1-soap-") as temporary:
        project = Path(temporary) / "emprunt-contractfirst"
        shutil.copytree(ROOT / "emprunt-contractfirst", project, ignore=shutil.ignore_patterns("target"))
        source = project / "src/main/java/mr/supnum/bib/impl/EmpruntServiceImpl.java"
        original = source.read_text(encoding="utf-8")
        source.write_text(original.replace("@com.sun.xml.ws.developer.SchemaValidation\n", ""), encoding="utf-8")
        contractfirst(project, validation=False)
        source.write_text(original.replace(',\n    wsdlLocation = "wsdl/EmpruntService.wsdl"', ""), encoding="utf-8")
        contractfirst(project, validation=False, supplied_wsdl=False)
    print(f"\n{CHECKS} vérifications réussies.", flush=True)


if __name__ == "__main__":
    main()
