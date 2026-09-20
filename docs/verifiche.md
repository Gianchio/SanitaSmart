# Verifiche della versione di consegna

## Esito

Suite automatica: 26 test superati. Il resoconto integrale è in `test_results.txt`; il comando ripetibile è `python -m unittest discover -s tests -v` dalla cartella del progetto.

Sono presenti 19 prove API/pagina, una prova dell'importazione senza creazione del database, quattro prove isolate del logout e due controlli del contratto OpenAPI. I casi parametrizzati nei singoli test non sono conteggiati come prove autonome.

## Matrice delle evidenze

| Requisito | Prova | Risultato |
| --- | --- | --- |
| Accesso riservato | Letture senza token e credenziali errate | 401; profilo valido privo di password hash |
| Ruoli | Medico tenta pazienti/annullamento; segreteria tenta referto; admin esegue scritture | Operazioni vietate rifiutate; autorizzate completate |
| Persistenza | Inserimento paziente e riapertura del database | Record conservato |
| Prenotazione | Due richieste sequenziali e due concorrenti per lo stesso slot | Una sola visita confermata; conflitto rifiutato |
| Normalizzazione | Stessa data/ora con rappresentazioni testuali diverse | Nessuna seconda prenotazione sullo stesso slot |
| Agenda | Orario durante pausa o fuori intervallo di 30 minuti | 400 |
| Annullamento | Modifica stato e nuova prenotazione | Record annullato conservato; slot liberato |
| Input | JSON malformato/non oggetto, tipi errati e campi vuoti | 400 |
| Integrità | Paziente inesistente e testi contenenti sintassi SQL | 404 per paziente assente; testo memorizzato senza esecuzione SQL |
| Logout | Corpo vuoto, JSON vuoto, ripetizione e altre sessioni | 204 senza corpo; sola sessione corrente revocata |
| Sessioni | Nuovo server sullo stesso database | Dati presenti, sessioni non ereditate |
| Contratto | Riferimenti e risposte reali delle 12 operazioni | Tipi, proprietà richieste e valori enumerati controllati |

Il controllo del contratto non è una validazione esaustiva di ogni vincolo OpenAPI o condizione di errore. I test non sono una certificazione di sicurezza né una prova di carico.

## Prove nel browser

Svolte sulla stessa versione del codice, con archivio di prova separato e server locale sulla porta 8765. Percorso osservato:

1. Accesso con account segreteria e caricamento degli indicatori.
2. Registrazione di Elena Verdi, nominativo fittizio; modulo ripulito e paziente disponibile nella selezione.
3. Prenotazione di una visita per il 12 ottobre alle 10:00 e comparsa del record.
4. Annullamento: record conservato, stato modificato e contatore delle visite confermate aggiornato.
5. Nuova prenotazione sullo slot liberato; il record annullato resta distinto dal nuovo record confermato.
6. Pulsante Esci: ritorno alla schermata di accesso.
7. Accesso medico: dati consultabili e moduli amministrativi assenti.

Le immagini sono acquisizioni reali del browser, non ricostruzioni. Rappresentano porzioni della pagina nella finestra disponibile; i contatori cambiano durante la sequenza. `03_prenotazione.png` documenta la nuova conferma dopo l'annullamento, quindi mostra entrambi i record. `04_annullamento.png` mostra lo stato precedente alla nuova prenotazione. La numerazione identifica il tema, non l'ordine finale di tutte le acquisizioni.

- `screenshots/01_accesso.png`: schermata di accesso.
- `screenshots/02_dashboard.png`: account segreteria e contatori.
- `screenshots/03_prenotazione.png`: slot nuovamente prenotato e record annullato conservato.
- `screenshots/04_annullamento.png`: visita annullata.
- `screenshots/05_uscita.png`: schermata dopo Esci.
- `screenshots/06_medico.png`: account medico e indicatori; l'assenza dei moduli è stata verificata nella pagina.

## Conservazione dei dati

L'impronta SHA-256 del database dimostrativo prima e dopo le prove è identica:

`BC7D645E0FD8795F4DDEAB389236490FE383F6B6F22D1F298D6FE267326B1D38`

Le scritture delle prove HTTP e del browser riguardano archivi separati. I dati fittizi già presenti nella copia principale sono conservati.

## Verifiche successive

Restano da progettare prove di carico, ripristino da backup, interruzione durante una scrittura, compatibilità estesa fra browser e accessibilità. La doppia richiesta concorrente verifica un conflitto specifico, non la capacità massima del sistema.
