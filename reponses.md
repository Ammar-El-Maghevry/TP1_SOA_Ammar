# TP1 — SOAP et WSDL

**Binôme (identifiants GitHub) : Ammar-El-Maghevry et mohamedsalem66.**

Les observations ci-dessous ont été vérifiées avec JDK 17, Maven et Metro 4.0.2,
par des échanges HTTP/SOAP automatisés dans `verifier.py`. Les deux services
utilisent par défaut la même adresse et doivent donc être lancés séparément.
Les dates de retour des nouveaux emprunts sont calculées à J+14.

## Lancer et vérifier les projets

Depuis la racine du dépôt, lancer la partie A :

```bash
mvn -f emprunt-codefirst/pom.xml compile exec:java
```

Ouvrir `http://localhost:8080/bib/EmpruntService?wsdl`, puis le schéma
`http://localhost:8080/bib/EmpruntService?xsd=1`. Dans SoapUI, créer un
« New SOAP Project » avec l'URL du WSDL et ouvrir la requête `emprunterLivre`.

Envoyer un message depuis un autre terminal :

```bash
curl -i -X POST http://localhost:8080/bib/EmpruntService \
  -H 'Content-Type: text/xml; charset=utf-8' \
  -H 'SOAPAction: ""' \
  --data-binary @xml/01-emprunter.xml
```

Arrêter la partie A avec `Ctrl+C`, puis générer les classes et lancer la partie B :

```bash
mvn -f emprunt-contractfirst/pom.xml generate-sources
mvn -f emprunt-contractfirst/pom.xml compile exec:java
```

Pour la partie B, utiliser les paramètres qualifiés et l'action du contrat :

```bash
curl -i -X POST http://localhost:8080/bib/EmpruntService \
  -H 'Content-Type: text/xml; charset=utf-8' \
  -H 'SOAPAction: "http://supnum.mr/bib/emprunterLivre"' \
  --data-binary @xml/09-emprunter-contractfirst.xml
```

Remplacer le fichier après `@` pour essayer les autres messages :

| Fichier | Partie | Résultat attendu |
| --- | --- | --- |
| `01-emprunter.xml` | A | HTTP 200 au premier emprunt de cet ISBN |
| `02-emprunter-12.xml` | A | HTTP 500, `VersionMismatch`, avec `text/xml` |
| `03-fault-sender-12.xml` | Exemple de réponse | Fault SOAP 1.2 écrite à la main, pas une requête |
| `04-rendre-corrige.xml` | A | HTTP 200, pénalité égale à zéro |
| `05-isbn-invalide.xml` | A | HTTP 500, `Client` |
| `06-livre-indisponible.xml` | A | HTTP 500, `Server`, avec détail métier |
| `07-must-understand.xml` | A | HTTP 500, `MustUnderstand` |
| `08-retour-invalide.xml` | A | HTTP 500, `Client` |
| `09-emprunter-contractfirst.xml` | B | HTTP 200 |
| `10-indisponible-contractfirst.xml` | B | HTTP 500, `Server`, avec détail métier |
| `11-isbn-invalide-contractfirst.xml` | B | HTTP 500, `Client`, validation XSD |

En partie A, renvoyer un ISBN déjà emprunté provoque une Fault métier : redémarrer
le serveur ou choisir un autre ISBN valide pour refaire un test de succès.
`rendreLivre` reste le squelette du TP : il vérifie le préfixe du numéro et renvoie
zéro, sans remettre le livre en disponibilité. La partie B reprend l'implémentation
pédagogique du sujet : numéro fixe et ISBN indisponible prédéfini.

Vérifications reproductibles :

```bash
mvn -f emprunt-codefirst/pom.xml clean verify
mvn -f emprunt-contractfirst/pom.xml clean verify
xmllint --noout xml/*.xml
python3 verifier.py
```

Le script nécessite Python 3, JDK 17 et Maven, sans bibliothèque Python externe.
Il démarre et arrête ses propres serveurs sur des ports temporaires. Il vérifie
également, dans des copies temporaires de la partie B, les variantes sans
`@SchemaValidation` et sans `wsdlLocation`. Les sources originales restent dans
leur état final : validation activée et WSDL fourni explicitement. Les classes
de `target/generated-sources/wsimport/` sont générées par Maven et ne sont pas
versionnées. Les lanceurs acceptent aussi une URL en argument, par exemple
`-Dexec.args=http://localhost:8081/bib/EmpruntService` après `exec:java`.

## Étape 2 — Lire le WSDL généré

### 1. URL, opérations et messages

L'adresse d'appel est `http://localhost:8080/bib/EmpruntService`.
Le WSDL est obtenu en ajoutant `?wsdl` ; ce n'est pas l'adresse à laquelle
envoyer les requêtes métier.

| Opération du `portType` | Message d'entrée | Message de sortie |
| --- | --- | --- |
| `emprunterLivre` | `tns:emprunterLivre` | `tns:emprunterLivreResponse` |
| `rendreLivre` | `tns:rendreLivre` | `tns:rendreLivreResponse` |

Ici, `tns` désigne `http://supnum.mr/bib` ; son préfixe peut changer sans modifier
le contrat. L'emprunt déclare également le message de fault
`tns:LivreIndisponibleException`.

Lecture de bas en haut : `wsdl:service` contient le port et son adresse ;
`wsdl:binding` précise le protocole et le format ; `wsdl:portType` décrit les
opérations ; `wsdl:message` référence les éléments décrits par le schéma XSD
importé dans `wsdl:types`.

### 2. Style, use et version SOAP

Le binding est **document/literal** : `soap:binding style="document"` et
`soap:body use="literal"`. Les données du Body sont des documents XML conformes
aux éléments du schéma, sans encodage SOAP RPC.

C'est **SOAP 1.1** : le WSDL emploie l'extension de binding
`http://schemas.xmlsoap.org/wsdl/soap/` et les enveloppes utilisent
`http://schemas.xmlsoap.org/soap/envelope/`. Le numéro « 1.1 » du WSDL ne suffit
pas à déterminer la version SOAP : c'est le binding qui la fixe.

### 3. Types de `isbn` et `dateRetour`

Les deux sont générés en **`xs:string`**, puisque les champs Java sont des
`String`. Le motif ISBN n'apparaît pas dans le XSD : la vérification Java par
`Pattern` est une règle d'exécution, pas une contrainte de schéma déduite par JAX-WS.
Une date formatée comme `2026-12-08` reste ici une chaîne dans le contrat.

### 4. Préfixes des paramètres

L'élément d'opération est qualifié : `<bib:emprunterLivre>`. Ses paramètres sont
non qualifiés : `<idAdherent>` et `<isbn>`, sans préfixe et sans espace de noms
par défaut. C'est ce qui est utilisé dans `xml/01-emprunter.xml`.

### 5. Rôles de HTTP, XML, SOAP et WSDL

Dans une vue Raw, la ligne `POST /bib/EmpruntService HTTP/1.1`, les en-têtes
`Content-Type`, `SOAPAction` et le statut `HTTP/1.1 200` ou `500` appartiennent à
**HTTP**, le transport. **XML** fournit la syntaxe structurée, les éléments et
leurs espaces de noms. **SOAP** définit l'enveloppe, le Header, le Body et les
Faults. **WSDL** décrit à l'avance l'adresse, les opérations, les messages, les
types et le binding ; il permet notamment à SoapUI de préparer les requêtes.

## Étape 3 — Envoyer des messages SOAP

### 1. Pourquoi POST ?

Le binding SOAP/HTTP utilisé transmet la requête SOAP dans le corps d'un POST.
Le nom ou le caractère « lecture seule » de l'opération ne transforme pas cet
appel en GET REST. GET sert ici à consulter les métadonnées `?wsdl` et `?xsd=1`.

### 2. Le Header `jeton` empêche-t-il le traitement ?

Non : `01-emprunter.xml` reçoit HTTP 200 sur un serveur neuf, avec un numéro
d'emprunt et une date de retour. Aucun handler ne comprend ni ne vérifie ce jeton.
Sans `mustUnderstand="1"`, ce bloc inconnu peut être ignoré ; sa présence ne
constitue donc pas une authentification.

### 3. Réponse au message SOAP 1.2

En conservant les en-têtes de la commande du sujet (`Content-Type: text/xml`),
`02-emprunter-12.xml` reçoit **HTTP 500**, une Fault **SOAP 1.1** de code
`VersionMismatch`. Le texte observé est :

```text
Couldn't create SOAP message. Expecting Envelope in namespace http://schemas.xmlsoap.org/soap/envelope/, but got http://www.w3.org/2003/05/soap-envelope
```

Le binding n'accepte que SOAP 1.1. Utiliser le type de contenu propre à SOAP 1.2,
`application/soap+xml`, donne ici **HTTP 415 Unsupported Media Type** : changer
l'enveloppe et le type HTTP ne change pas le binding du serveur.

### 4. Les cinq erreurs du message fourni

| Erreur | Correction |
| --- | --- |
| Ouverture `<soap:envelope>` avec une minuscule et fermeture `</soap:Envelope>` | Utiliser `Envelope` avec la même casse ; XML est sensible à la casse. |
| Espace de noms métier `http://supnum.mr/bibliotheque` | Employer `http://supnum.mr/bib`. |
| Paramètre `<bib:numero>` non conforme au contrat | Employer `<numeroEmprunt>`, avec le bon nom et sans qualification en partie A. |
| Fermeture `</rendreLivre>` différente de l'ouverture `<bib:rendreLivre>` | Fermer avec `</bib:rendreLivre>`. |
| `soap:Header` placé après `soap:Body` | Placer le Header avant le Body. |

Le message complet n'est pas bien formé : les erreurs de balises doivent être
corrigées avant de pouvoir observer les autres. Une fois isolées, certaines
erreurs sont tolérées par Metro sans validation XSD : le Header après le Body
est ignoré dans notre essai et le retour reçoit HTTP 200. Un paramètre mal nommé
peut aussi être ignoré et devenir `null` en Java. Avant l'étape 4, `rendreLivre`
renvoyait zéro même dans ce cas ; après l'ajout du contrôle, il renvoie une Fault
`Client` avec `Numéro d'emprunt inconnu : null`. Cette tolérance ne rend pas le
message conforme. Le fichier entièrement corrigé est `04-rendre-corrige.xml`.

## Étape 4 — Provoquer et construire des Faults

### 1. Codes reçus pour les deux ISBN

| Cas | HTTP | `faultcode` (nom local) | `faultstring` |
| --- | --- | --- | --- |
| ISBN `978-2-10` | 500 | `Client` | `ISBN mal formé : 978-2-10` |
| ISBN `978-2-10-074444-4` | 500 | `Server` | `Livre indisponible` |

Les valeurs complètes de `faultcode` sont des QName dans l'espace de noms SOAP
1.1, par exemple `S:Client` ; le choix du préfixe `S` n'a pas d'importance.
Le contrôle ajouté à `rendreLivre` produit également HTTP 500 / `Client` pour un
numéro nul ou ne commençant pas par `E-2026-`.

### 2. Détail métier et description dans le contrat

Pour le livre indisponible, le détail de la partie A contient :

```xml
<detail xmlns:bib="http://supnum.mr/bib">
    <bib:LivreIndisponible>
        <isbn>978-2-10-074444-4</isbn>
        <retourPrevu>2026-12-02</retourPrevu>
    </bib:LivreIndisponible>
</detail>
```

Le `wsdl:fault` de l'opération référence le message
`LivreIndisponibleException`. Sa part référence l'élément XSD
`bib:LivreIndisponible`, dont le type `livreIndisponibleInfo`, décrit dans le
schéma importé par `wsdl:types`, contient `isbn` et `retourPrevu`.
Le binding comporte aussi un `soap:fault use="literal"`.

### 3. Choix de JAX-WS pour le livre indisponible

Metro choisit **`Server`** pour cette exception métier déclarée. L'annotation
`@WebFault` fournit un détail typé et une déclaration dans le contrat ; elle ne
demande pas automatiquement un code `Client`.

Le serveur est en état de fonctionner ; c'est une indisponibilité métier, pas
une panne interne. Un code `Client` en SOAP 1.1, ou `Sender` en SOAP 1.2, serait
plus utile ici pour signaler que le client doit changer son choix ou attendre,
plutôt que répéter immédiatement la même requête. Le détail métier permet au
client de distinguer cette situation indépendamment du code générique.

### 4. `mustUnderstand="1"` et `"0"`

Avec `soap:mustUnderstand="1"`, le destinataire doit comprendre le bloc `jeton`.
Comme aucun traitement n'est prévu, Metro renvoie HTTP 500 et une Fault
`MustUnderstand`, avant l'appel métier :

```text
MustUnderstand headers:[{http://supnum.mr/bib}jeton] are not understood
```

Avec `"0"`, le bloc peut être ignoré et l'opération s'exécute normalement.
Sur un ISBN encore disponible, le test reçoit HTTP 200. Si l'ISBN a déjà été
emprunté, une Fault métier peut naturellement apparaître à la place.

### 5. Comparaison des Faults 1.1 et 1.2

En SOAP 1.1, les enfants non qualifiés du `soap:Fault` sont `faultcode`,
`faultstring` et éventuellement `detail`. En SOAP 1.2, la structure emploie les
éléments qualifiés `soap:Code/soap:Value`, `soap:Reason/soap:Text` et
`soap:Detail`. `soap:Text` porte `xml:lang="fr"` dans notre exemple et le code
est `soap:Sender`, au lieu de `Client`. L'espace de noms de l'enveloppe change
également. Le détail `bib:IsbnInvalide` est ici un exemple construit à la main,
pas un élément déclaré dans les contrats SOAP 1.1 des deux projets.

```bash
xmllint --noout xml/03-fault-sender-12.xml
```

Cette commande réussit ; elle vérifie que le XML est bien formé, pas à elle
seule toute sa conformité à la spécification SOAP 1.2.

## Étape 5 — Générer le code depuis le WSDL

Le projet `emprunt-contractfirst` contient le WSDL fourni et le plugin
`com.sun.xml.ws:jaxws-maven-plugin:4.0.2`. `mvn generate-sources` crée les classes
du paquet `mr.supnum.bib.contrat` dans `target/generated-sources/wsimport/`.

### 1. Opération, fault et action SOAP

L'opération est `emprunterLivre`, dans le `portType` `EmpruntPortType`.
Elle reçoit `bib:emprunterLivreRequest`, renvoie
`bib:emprunterLivreResponse` et déclare une fault nommée `LivreIndisponible`
référençant le message **`bib:LivreIndisponibleFault`**.

L'action du binding est **`http://supnum.mr/bib/emprunterLivre`**, à envoyer dans
l'en-tête HTTP `SOAPAction`, entre guillemets. Ce contrat ne déclare pas
`rendreLivre` : cette opération appartient uniquement à la partie A du sujet.

### 2. Signature Java générée

```java
public EmpruntType emprunterLivre(String idAdherent, String isbn)
    throws LivreIndisponibleFault;
```

L'interface générée contient les annotations `@WebMethod`, `@WebParam`,
`@WebResult`, `@RequestWrapper` et `@ResponseWrapper` qui relient cette signature
aux noms et aux espaces de noms du contrat.

### 3. Type Java de `dateRetour`

Il s'agit de **`javax.xml.datatype.XMLGregorianCalendar`**, avec une annotation
JAXB `@XmlSchemaType(name = "date")`, puisque le contrat impose `xs:date`.
Dans la partie A, le champ Java était `String` et le schéma indiquait
`xs:string`. En partie B, l'implémentation convertit `LocalDate` vers
`XMLGregorianCalendar` sans ajouter de composante horaire.

### 4. Exception générée et origine du nom

La classe est **`mr.supnum.bib.contrat.LivreIndisponibleFault`**, qui étend
`Exception`. Son nom est issu du message WSDL `LivreIndisponibleFault` référencé
par le `wsdl:fault` de l'opération. Son annotation
`@WebFault(name = "LivreIndisponible", targetNamespace = "http://supnum.mr/bib")`
identifie l'élément XML de détail ; la classe JAXB `LivreIndisponible` porte les
données `isbn` et `retourPrevu`.

## Étape 6 — Implémenter et comparer

`EmpruntServiceImpl` implémente l'interface générée ; son lanceur publie
l'endpoint avec `Endpoint.publish`. La version finale conserve `wsdlLocation`
et active `@com.sun.xml.ws.developer.SchemaValidation`.

### 1. WSDL publié

Oui : avec `wsdlLocation = "wsdl/EmpruntService.wsdl"`, le service publie le
contrat fourni. Le motif ISBN est toujours dans `IsbnType` et `dateRetour`
est toujours `xs:date`. Metro peut ajuster l'adresse publiée et ajouter des
métadonnées : cela ne signifie pas que le fichier est identique octet par octet.

### 2. Adaptation de `01-emprunter.xml`

Oui. Le schéma de la partie B impose `elementFormDefault="qualified"`. Il faut
qualifier les paramètres, et pas seulement l'élément d'opération :

```xml
<bib:emprunterLivre xmlns:bib="http://supnum.mr/bib">
    <bib:idAdherent>A-117</bib:idAdherent>
    <bib:isbn>978-2-07-036822-8</bib:isbn>
</bib:emprunterLivre>
```

Il faut également changer l'en-tête HTTP `SOAPAction`. Le fichier adapté est
`09-emprunter-contractfirst.xml`. Avec validation, l'ancien fichier non adapté
reçoit HTTP 500 / `Client` : le serveur attend
`{http://supnum.mr/bib}idAdherent`, pas un `idAdherent` sans espace de noms.
Sans validation, ignorer des éléments et obtenir des paramètres nuls n'est pas
une preuve de conformité au contrat.

### 3. ISBN invalide, sans puis avec validation

**Sans `@SchemaValidation`**, l'ISBN `978-2-10`, envoyé avec les bons espaces de
noms, n'est pas refusé par le seul fait que le WSDL possède un motif. La
signature générée reçoit un `String` et l'implémentation du sujet ne teste pas
ce format : on observe HTTP 200.

**Avec `@SchemaValidation`**, Metro valide le message contre le XSD avant
d'exécuter la méthode. On observe HTTP 500 et une Fault SOAP 1.1 `Client`, sans
détail métier `LivreIndisponible`. Le `faultstring` contient :

```text
org.xml.sax.SAXParseException; cvc-pattern-valid: Value '978-2-10' is not facet-valid with respect to pattern '97[89]-\d-\d{2,5}-\d{2,6}-\d' for type 'IsbnType'.
```

Le cas métier `978-2-10-074444-4` reste distinct : HTTP 500 / `Server`, texte
`Livre indisponible` et détail structuré avec la date `2026-12-02`.

### 4. Suppression de `wsdlLocation`

Dans l'essai où seule cette propriété de l'annotation de l'implémentation est
retirée, Metro reconstruit le contrat à partir de l'interface et des classes
générées. Le schéma est publié séparément via `?xsd=1`. Le type simple
`IsbnType` et son motif **disparaissent**, car la propriété Java est un `String`
et les annotations générées ne conservent pas cette restriction de motif.

En revanche, **`xs:date` est conservé** grâce à
`@XmlSchemaType(name = "date")`, et la qualification des éléments est conservée
par les annotations JAXB. Même avec `@SchemaValidation`, l'ISBN invalide est
alors accepté dans notre essai : la validation porte sur le schéma reconstruit,
qui n'a plus la restriction. Il faut donc garder la référence au WSDL pour
préserver entièrement le contrat d'origine.

## Conclusion — Choisir l'approche

### 1. Différences observées entre les contrats

- Partie A : `isbn` et `dateRetour` sont des `xs:string`, sans motif ISBN ;
  partie B : `isbn` utilise `IsbnType` avec un motif et `dateRetour` est `xs:date`.
- Partie A : les paramètres sont non qualifiés ; partie B : ils sont qualifiés.
- La partie A déclare deux opérations ; le WSDL de la partie B n'en déclare
  qu'une et fixe explicitement son action SOAP.

### 2. Renommer `dateRetour` dans le code

En code-first, renommer la propriété exposée sans conserver son nom XML change
le WSDL généré. Les clients qui attendent `dateRetour` peuvent alors ne plus
désérialiser la réponse correctement.

En contract-first, changer le code métier ne change pas automatiquement le
WSDL source. L'implémentation doit continuer à respecter les classes générées.
On ne renomme pas à la main un champ dans `target/` : il serait recréé à la
génération suivante. Modifier le contrat partagé exige une évolution coordonnée
ou une nouvelle version pour ne pas casser les clients.

### 3. Paiement multi-clients et prototype

Pour **Paiement**, appelé par Scolarité (.NET), Bibliothèque (PHP) et le portail
(Node.js), je choisirais **contract-first** : chaque équipe génère son client
à partir d'un contrat commun, stable et indépendant du langage.

Pour un **prototype interne de deux jours**, je choisirais **code-first** pour
aller plus vite, puis je figerais et vérifierais le WSDL avant une utilisation
durable par d'autres consommateurs.
