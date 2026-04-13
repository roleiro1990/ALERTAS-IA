import requests
import time

import os

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID_FREE")
API_KEY = os.getenv("API_KEY")
API_BASE = "https://v3.football.api-sports.io"

alertas_enviadas = set()
alertas_remates_totales_altos = set()
alertas_1t_enviadas = set()

primera_vuelta = True


def bandera_pais(pais):
    pais_a_iso = {
        "Argentina": "AR",
        "Spain": "ES",
        "Mexico": "MX",
        "USA": "US",
        "Brazil": "BR",
        "England": "GB",
        "Italy": "IT",
        "Germany": "DE",
        "France": "FR",
        "Portugal": "PT",
        "Netherlands": "NL",
        "Turkey": "TR",
        "Chile": "CL",
        "Colombia": "CO",
        "Uruguay": "UY",
        "Paraguay": "PY",
        "Peru": "PE",
        "Nicaragua": "NI",
        "El Salvador": "SV",
        "Costa Rica": "CR",
        "Honduras": "HN",
        "Guatemala": "GT",
        "Panama": "PA",
        "Dominican Republic": "DO",
        "Belgium": "BE",
        "Denmark": "DK",
        "Croatia": "HR",
        "Slovenia": "SI",
        "Czech Republic": "CZ",
        "Czech-Republic": "CZ",
        "Ghana": "GH",
        "Iceland": "IS",
        "World": "🌍",
        "Jamaica": "JM",
        "Venezuela": "VE",
    }

    codigo = pais_a_iso.get(pais)

    if codigo == "🌍":
        return "🌍"

    if not codigo:
        return "🌍"

    return "".join(chr(127397 + ord(c)) for c in codigo)


def tipo_expulsion(minuto):
    try:
        minuto = int(minuto)
    except (TypeError, ValueError):
        return "EXPULSIÓN", ""

    if minuto <= 30:
        return "EXPULSIÓN TEMPRANA", "1–30 min"
    elif minuto <= 69:
        return "EXPULSIÓN MEDIA", "31–69 min"
    else:
        return "EXPULSIÓN TARDÍA", "70+ min"


def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
    }
    requests.post(url, data=data, timeout=20)


def obtener_partidos_en_vivo():
    url = f"{API_BASE}/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json().get("response", [])


def obtener_eventos(fixture_id):
    url = f"{API_BASE}/fixtures/events?fixture={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json().get("response", [])


def obtener_estadisticas(fixture_id):
    url = f"{API_BASE}/fixtures/statistics?fixture={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json().get("response", [])


def get_stat(stats, nombre):
    for s in stats:
        if s.get("type") == nombre:
            valor = s.get("value")

            if valor is None:
                return 0

            if isinstance(valor, int):
                return valor

            if isinstance(valor, str):
                valor = valor.replace("%", "").strip()
                return int(valor) if valor.isdigit() else 0

    return 0


def obtener_remates(stats):
    candidatos = [
        get_stat(stats, "Total Shots"),
        get_stat(stats, "Shots Total"),
        get_stat(stats, "Shots"),
    ]
    return max(candidatos)


def es_roja(evento):
    tipo = str(evento.get("type", "")).lower()
    detalle = str(evento.get("detail", "")).lower()
    comentario = str(evento.get("comments", "")).lower()

    palabras_roja = [
        "red card",
        "yellow red card",
        "second yellow",
        "2nd yellow",
        "red",
    ]

    return (
        any(p in tipo for p in palabras_roja)
        or any(p in detalle for p in palabras_roja)
        or any(p in comentario for p in palabras_roja)
    )


def revisar_partidos():
    global primera_vuelta

    partidos = obtener_partidos_en_vivo()

    for partido in partidos:
        fixture_id = partido["fixture"]["id"]
        home = partido["teams"]["home"]["name"]
        away = partido["teams"]["away"]["name"]
        goles_local = partido["goals"]["home"]
        goles_visitante = partido["goals"]["away"]
        liga = partido["league"]["name"]
        pais = partido["league"]["country"]
        bandera = bandera_pais(pais)

        estado_corto = partido.get("fixture", {}).get("status", {}).get("short", "")

        eventos = obtener_eventos(fixture_id)

        # EVENTOS EN VIVO -> SOLO EXPULSIONES
        for evento in eventos:
            minuto_evento = evento.get("time", {}).get("elapsed", 0)
            equipo_evento = evento.get("team", {}).get("name", "Equipo")
            tipo = str(evento.get("type", ""))
            detalle = str(evento.get("detail", ""))

            clave = f"{fixture_id}-{minuto_evento}-{equipo_evento}-{tipo}-{detalle}"

            if clave in alertas_enviadas:
                continue

            if primera_vuelta:
                alertas_enviadas.add(clave)
                continue

            if es_roja(evento):
                titulo_expulsion, rango_expulsion = tipo_expulsion(minuto_evento)

                mensaje = (
                    f"<b>🟥 {titulo_expulsion} ({rango_expulsion})</b>\n\n"
                    f"🔴 {equipo_evento}\n\n"
                    f"{liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⏱ Min {minuto_evento}\n"
                    f"⚽ {goles_local}-{goles_visitante}"
                )
                enviar_mensaje(mensaje)
                alertas_enviadas.add(clave)

            else:
                alertas_enviadas.add(clave)

        # ALERTAS DEL 1T -> SOLO REMATES TOTALES ALTOS, AHORA EN HT
        if estado_corto == "HT" and fixture_id not in alertas_1t_enviadas and not primera_vuelta:
            estadisticas = obtener_estadisticas(fixture_id)

            remates_home = 0
            remates_away = 0
            total_remates = 0

            if len(estadisticas) >= 2:
                home_stats = estadisticas[0]["statistics"]
                away_stats = estadisticas[1]["statistics"]

                remates_home = obtener_remates(home_stats)
                remates_away = obtener_remates(away_stats)
                total_remates = remates_home + remates_away

            if total_remates >= 15:
                clave = f"{fixture_id}-remates-totales-altos"
                if clave not in alertas_remates_totales_altos:
                    mensaje = (
                        f"<b>🥅 VOLUMEN ALTO DE REMATES 🥅</b>\n\n"
                        f"⏱ Remate cada 3 minutos o menos\n\n"
                        f"{liga} ({pais}) {bandera}\n"
                        f"{home} vs {away}\n\n"
                        f"⏱ 1T Finalizado | ⚽ {goles_local}-{goles_visitante}\n"
                        f"🔴 {home}: {remates_home}\n"
                        f"🔵 {away}: {remates_away}\n"
                        f"📊 Total: {total_remates}"
                    )
                    enviar_mensaje(mensaje)
                    alertas_remates_totales_altos.add(clave)

            # Marcar que ya se revisó el 1T de este partido
            alertas_1t_enviadas.add(fixture_id)

    primera_vuelta = False


def main():
    while True:
        try:
            revisar_partidos()
        except Exception as e:
            print("ERROR FREE:", e)

        print("FREE ESPERANDO 30 SEGUNDOS...\n")
        time.sleep(90)


if __name__ == "__main__":
    main()
