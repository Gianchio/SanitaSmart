# SanitaSmart

Prototipo full stack API based per una clinica polispecialistica di esempio. Gestisce pazienti, prenotazioni, consultazione dei referti e ruoli del personale. La dashboard presenta indicatori operativi; non contiene contabilità o dati economico-finanziari.

## Avvio locale

Occorre Python 3.11 o successivo. L'applicazione e i test usano la sola libreria standard.

Dalla cartella del progetto:

```powershell
python app.py
```

Aprire http://127.0.0.1:8000 nel browser. Al primo avvio viene creato `sanitasmart.db` con dati fittizi. Gli avvii successivi conservano l'archivio. Per fermare il server premere Ctrl+C nel terminale. Dopo una modifica al codice, riavviare il server e ricaricare la pagina.

| Ruolo | Email | Password dimostrativa |
| --- | --- | --- |
| Segreteria | segreteria@sanitasmart.test | Segreteria123! |
| Medico | medico@sanitasmart.test | Medico123! |
| Amministratore | admin@sanitasmart.test | Admin123! |

## Prove ripetibili

```powershell
python -m unittest discover -s tests -v
```

La suite comprende 26 test. Ogni prova HTTP prepara un database temporaneo nella cartella `tests/.tmp`, usa una porta libera e chiude le risorse prima della pulizia. Il database della dimostrazione non viene usato dai test. Importare `app.py` non crea né apre il database.

I risultati della verifica sono in `docs/verifiche.md` e `docs/test_results.txt`. Le schermate della versione corrente sono in `docs/screenshots/`.

## Funzioni

- Accesso con tre ruoli, profilo e logout con revoca del token.
- Registrazione e consultazione pazienti.
- Consultazione disponibilità, prenotazione e annullamento senza eliminare il record.
- Controllo degli slot sul server, normalizzazione di data e ora e vincolo contro prenotazioni concorrenti.
- Consultazione referti nella pagina; pubblicazione tramite API per medico o amministratore.
- Persistenza SQLite, query parametrizzate e chiavi esterne.

Il medico non dispone dei moduli amministrativi. Il server verifica comunque i permessi sulle richieste. Gli utenti autenticati leggono tutte le risorse del prototipo.

## Materiali

- `app.py`: repository, gestore HTTP e costruzione del server.
- `static/`: interfaccia HTML, CSS e JavaScript.
- `openapi.yaml`: contratto delle 12 operazioni, richieste, risposte, errori e token Bearer. Il file usa sintassi JSON valida anche come YAML 1.2 ed è importabile in strumenti OpenAPI 3.0.3.
- `docs/design.md`: architettura, schema ER, classi e motivazioni delle scelte.
- `docs/verifiche.md`: requisiti, prove, risultati e limiti.
- `tests/`: suite ripetibile e controlli del contratto API.

## Scaricare e provare il progetto

Dalla pagina del repository selezionare **Code > Download ZIP**, estrarre l'archivio e aprire un terminale nella cartella che contiene `app.py`. Eseguire il comando di avvio riportato sopra.

Il repository contiene i sorgenti e i materiali per la valutazione. L'applicazione viene eseguita sul computer del lettore; la pagina GitHub non esegue il backend Python. Non occorrono pacchetti Python aggiuntivi. I dati dimostrativi vengono creati al primo avvio e sono interamente fittizi.

## Limiti del prototipo

Il server è destinato alla dimostrazione locale su 127.0.0.1. Non sono implementati anagrafica medici, durata variabile delle visite, portale pazienti, scadenza dei token, permessi sul singolo paziente, audit o ripristino da backup. I referti non sono collegati a una visita specifica. Il codice 401 viene usato anche per il ruolo insufficiente. Le credenziali pubblicate sono soltanto dimostrative.
