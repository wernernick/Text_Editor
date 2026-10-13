# Lauffähige Backups

Jede Zeile ist ein geprüfter, startbarer Stand von `main` (Tests grün, `python main.py` startet, Windows-Build grün).
Zurück zu einem Stand: `git checkout <Commit>`. Die .exe liegt im verlinkten Build-Lauf unter **Artifacts → TextEditor**.

| Version | Commit | Datum (UTC) | Inhalt | Windows-Build |
|---|---|---|---|---|
| v0.5 | `2ebfa03` | 2026-10-13 15:13 | Tabellen im Dokumentmodell und .docx laden/speichern (Core #13; in der Oberfläche noch nicht sichtbar) | [Lauf](https://github.com/wernernick/Text_Editor/actions/runs/38419983663) |
| v0.4 | `7059798` | 2026-10-13 12:36 | Autosave mit Wiederherstellung, Backup vor dem Überschreiben, sicheres Speichern, zuletzt geöffnete Dateien, Seitenfarbe Neon/Papier, Datei per „Öffnen mit“ (#8, #10, #11) | [Lauf](https://github.com/wernernick/Text_Editor/actions/runs/38398512934) |
| v0.3 | `4658499` | 2026-10-13 12:14 | Aufzählungen/Nummerierung (Core #4 + UI), Suchen & Ersetzen mit Strg+F/Strg+H (#5, #6), stabilere Windows-Tests (#7) | [Lauf](https://github.com/wernernick/Text_Editor/actions/runs/38395537776) |
| v0.2 | `fbdd99b` | 2026-10-13 11:57 | Cyber-Oberfläche NEON//WRITE: Ribbon, Formatierung, Ausrichtung, Überschriften, Zoom, Statusleiste, .docx öffnen/speichern (#2) | [Lauf #2](https://github.com/wernernick/Text_Editor/actions/runs/38393828872) |
| v0.1 | `d6422af` | 2026-10-13 11:53 | Grundgerüst + Core-Engine: Dokumentmodell, .docx-Import/Export, Dateimanager, build_exe.py (#1) | [Lauf #1](https://github.com/wernernick/Text_Editor/actions/runs/38393319357) |
