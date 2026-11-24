package mr.supnum.bib.impl;

import jakarta.jws.WebService;
import mr.supnum.bib.contrat.*;
import javax.xml.datatype.DatatypeFactory;
import javax.xml.datatype.XMLGregorianCalendar;
import java.time.LocalDate;

@WebService(
    serviceName = "EmpruntService",
    portName = "EmpruntPort",
    targetNamespace = "http://supnum.mr/bib",
    endpointInterface = "mr.supnum.bib.contrat.EmpruntPortType",
    wsdlLocation = "wsdl/EmpruntService.wsdl"
)
@com.sun.xml.ws.developer.SchemaValidation
public class EmpruntServiceImpl implements EmpruntPortType {

    @Override
    public EmpruntType emprunterLivre(String idAdherent, String isbn)
        throws LivreIndisponibleFault {

        if ("978-2-10-074444-4".equals(isbn)) {
            LivreIndisponible info = new LivreIndisponible();
            info.setIsbn(isbn);
            info.setRetourPrevu(date(LocalDate.of(2026, 12, 2)));
            throw new LivreIndisponibleFault("Livre indisponible", info);
        }

        EmpruntType emprunt = new EmpruntType();
        emprunt.setNumero("E-2026-0812");
        emprunt.setDateRetour(date(LocalDate.now().plusDays(14)));
        return emprunt;
    }

    private static XMLGregorianCalendar date(LocalDate date) {
        try {
            return DatatypeFactory.newInstance().newXMLGregorianCalendar(date.toString());
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }
}
