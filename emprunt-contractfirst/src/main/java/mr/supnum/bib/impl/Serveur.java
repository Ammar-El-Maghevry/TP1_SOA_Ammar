package mr.supnum.bib.impl;

import jakarta.xml.ws.Endpoint;

public class Serveur {

    public static void main(String[] args) {
        String url = args.length == 0
            ? "http://localhost:8080/bib/EmpruntService"
            : args[0];

        Endpoint.publish(url, new EmpruntServiceImpl());
        System.out.println("WSDL : " + url + "?wsdl");
    }
}
