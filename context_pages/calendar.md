+++
id = "calendar"
title = "Calendario"
priority = 90
triggers = ["calendario", "agenda", "appuntamento", "appuntamenti", "evento", "eventi", "impegni", "domani", "oggi"]
tools = ["calendar_list_events", "calendar_get_event", "calendar_create_event", "calendar_update_event", "calendar_delete_event"]
+++
Il calendario PostgreSQL è la fonte autorevole degli impegni.
Consulta gli eventi prima di rispondere su appuntamenti reali.
Usa date ISO 8601 con offset e fuso Europe/Rome.
Le scritture degli agenti sono proposte: non dichiararle applicate finché l'utente non le approva.
Per modificare o eliminare, leggi prima ID e versione dell'evento.
