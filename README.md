# Visible Obstacles Count

Plugin Python per QGIS 3.40 che calcola, per ogni pixel valido di un DTM, il numero di ostacoli puntuali visibili entro una distanza massima, producendo un raster GeoTIFF Int32 allineato al DTM.

## File inclusi

- `__init__.py`: entry point del plugin.
- `metadata.txt`: metadati standard QGIS.
- `visible_obstacles_count.py`: bootstrap del plugin e integrazione con la GUI di QGIS.
- `visible_obstacles_count_dialog.py`: dialog PyQt, raccolta parametri, feedback all'utente.
- `validation.py`: validazioni sugli input.
- `raster_utils.py`: lettura del raster in NumPy e scrittura GeoTIFF.
- `visibility_engine.py`: motore di calcolo della visibilità.

## Installazione in QGIS 3.40

1. Copiare l'intera cartella del plugin in una directory dei plugin Python di QGIS, ad esempio:
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/visible_obstacles_count`
   - Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\visible_obstacles_count`
2. Riavviare QGIS oppure usare **Plugins > Manage and Install Plugins > Installed**.
3. Attivare il plugin **Visible Obstacles Count**.

## Note prestazionali

- Il DTM viene pre-caricato interamente in memoria con NumPy.
- Gli ostacoli vengono pre-filtrati per altezza valida e posizione campionabile sul DTM.
- Per ogni riga del raster si applica un filtro preliminare sulla distanza in Y, seguito da un filtro euclideo completo per i pixel della riga.
- Il test di linea di vista si interrompe appena il DTM supera la quota interpolata.

## Possibili ottimizzazioni future

- Spatial index sugli ostacoli.
- Parallelizzazione per blocchi/righe.
- Task asincrono QGIS per evitare il blocco dell'interfaccia su dataset molto grandi.
- Strategie di caching dei profili di visibilità e campionamento raster più avanzato.
