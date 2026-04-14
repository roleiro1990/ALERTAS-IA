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

primera_vuelta_eventos = True
primera_vuelta_1t = True

ULTIMA_REVISION_EVENTOS = 0
ULTIMA_REVISION_1T = 0

INTERVALO_EVENTOS = 60
INTERVALO_1T = 120


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


def revisar_eventos_vivo():
    global primera_vuelta_eventos

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

        eventos = obtener_eventos(fixture_id)

        for evento in eventos:
            minuto_evento = evento.get("time", {}).get("elapsed", 0)
            equipo_evento = evento.get("team", {}).get("name", "Equipo")
            tipo = str(evento.get("type", ""))
            detalle = str(evento.get("detail", ""))

            clave = f"{fixture_id}-{minuto_evento}-{equipo_evento}-{tipo}-{detalle}"

            if clave in alertas_enviadas:
                continue

            if primera_vuelta_eventos:
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

    primera_vuelta_eventos = False


def revisar_mercado_1t():
    global primera_vuelta_1t

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
        minuto_actual = partido.get("fixture", {}).get("status", {}).get("elapsed", 0) or 0

        if fixture_id in alertas_1t_enviadas:
            continue

        if primera_vuelta_1t:
            continue

        if estado_corto not in ["HT", "2H"]:
            continue

        if estado_corto == "2H" and minuto_actual > 55:
            continue

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

        alertas_1t_enviadas.add(fixture_id)

    primera_vuelta_1t = False


def revisar_partidos():
    global ULTIMA_REVISION_EVENTOS, ULTIMA_REVISION_1T

    while True:
        try:
            ahora = time.time()

            if ahora - ULTIMA_REVISION_EVENTOS >= INTERVALO_EVENTOS:
                revisar_eventos_vivo()
                ULTIMA_REVISION_EVENTOS = ahora

            if ahora - ULTIMA_REVISION_1T >= INTERVALO_1T:
                revisar_mercado_1t()
                ULTIMA_REVISION_1T = ahora

        except Exception as e:
            print("ERROR BOT_FREE:", e)
            time.sleep(10)
            continue

        print("BOT FREE ACTIVO | EXPULSIONES: 60s | REMATES 1T: 120s\n")
        time.sleep(5)
