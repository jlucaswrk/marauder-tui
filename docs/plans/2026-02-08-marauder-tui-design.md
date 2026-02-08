# Marauder TUI — Design Document

**Data:** 2026-02-08
**Stack:** Python 3.9+ / Textual / pyserial

## Objetivo

GUI estilo terminal hacker para controlar ESP32 Marauder via serial.
Dashboard live, ataques one-click, wardriving log, serial raw.

## Arquitetura

3 camadas:
1. **SerialBridge** — thread serial + parser de respostas do Marauder
2. **MarauderEngine** — estado (APs, stations, BLE devices), fila de comandos
3. **TUI App (Textual)** — interface visual, zero logica de negocio

## Telas

1. **Dashboard** — paineis live (WiFi APs, BLE devices, activity feed), hotkeys F1-F5
2. **Attacks** — menu de ataques WiFi (deauth, beacon, probe, rickroll) e BLE (spam)
3. **Log** — sessoes salvas em JSON lines, export CSV, historico
4. **Serial Raw** — terminal direto com a serial, input manual

## Estrutura

```
marauder-tui/
├── marauder/
│   ├── __init__.py
│   ├── app.py
│   ├── serial_bridge.py
│   ├── engine.py
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── dashboard.py
│   │   ├── attacks.py
│   │   ├── logs.py
│   │   └── serial_raw.py
│   └── widgets/
│       ├── __init__.py
│       ├── rssi_bar.py
│       ├── device_table.py
│       └── activity_feed.py
├── pyproject.toml
└── README.md
```

## Detalhes

- Sessoes salvas em `~/.marauder-tui/sessions/`
- Formato: JSON lines (um device por linha + timestamp)
- Auto-detect porta serial (procura cu.usbserial-*)
- RSSI bars visuais com cores (verde/amarelo/vermelho)
- Confirmar antes de qualquer ataque
