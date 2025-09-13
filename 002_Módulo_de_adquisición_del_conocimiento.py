# experto_chat.py
# Sistema experto sencillo con adquisición de conocimiento (sin web)
# - Consola interactiva
# - Persistencia en SQLite
# - Coincidencia por similitud del coseno sobre bolsa de palabras
# - Todo en español, listo para copiar, pegar y ejecutar

import sqlite3
import re
import unicodedata
import math
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

# =========================
# 1) Utilidades de texto
# =========================

def normalizar(texto: str) -> str:
    """
    Minúsculas, quitar acentos y limpiar caracteres no alfanuméricos (básico).
    """
    t = texto.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")  # quitar acentos
    t = re.sub(r"[^a-z0-9ñ\s\?\!\.,]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def tokenizar(texto: str) -> List[str]:
    """
    Tokenización muy simple en base a caracteres no alfanuméricos.
    """
    return [tok for tok in re.split(r"[^a-z0-9ñ]+", normalizar(texto)) if tok]

def vectorizar(tokens: List[str]) -> Dict[str, int]:
    """
    Convierte lista de tokens en vector de frecuencias (bolsa de palabras).
    """
    vec: Dict[str, int] = {}
    for tok in tokens:
        vec[tok] = vec.get(tok, 0) + 1
    return vec

def similitud_coseno(a: Dict[str, int], b: Dict[str, int]) -> float:
    """
    Similitud del coseno entre dos vectores dispersos representados como dict.
    """
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in set(a) | set(b))
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return 0.0 if na * nb == 0 else dot / (na * nb)

# =========================
# 2) Almacenamiento (SQLite)
# =========================

DB_PATH = Path("data.db")

def iniciar_db() -> None:
    """
    Crea la tabla kb si no existe y siembra 3 pares (pregunta, respuesta) básicos.
    """
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS kb (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              pregunta TEXT NOT NULL,
              respuesta TEXT NOT NULL,
              creado_en TEXT DEFAULT (datetime('now'))
            )
            """
        )
        cur = con.execute("SELECT COUNT(*) FROM kb")
        (count,) = cur.fetchone()
        if count == 0:
            semillas = [
                ("hola", "Hola, ¿en qué te ayudo?"),
                ("como estas", "Bien. ¿Qué necesitas?"),
                ("de que te gustaria hablar", "Podemos hablar de ingeniería, programación o del tema que traes."),
            ]
            con.executemany("INSERT INTO kb(pregunta, respuesta) VALUES(?, ?)", semillas)

def guardar_entrada(pregunta: str, respuesta: str) -> None:
    """
    Inserta una nueva (pregunta, respuesta) normalizando la pregunta.
    """
    norm = normalizar(pregunta)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO kb(pregunta, respuesta) VALUES(?, ?)", (norm, respuesta))

def cargar_todas() -> List[Tuple[int, str, str]]:
    """
    Devuelve todas las filas de la KB: (id, pregunta, respuesta).
    """
    with sqlite3.connect(DB_PATH) as con:
        cur = con.execute("SELECT id, pregunta, respuesta FROM kb")
        return list(cur.fetchall())

# =========================
# 3) Núcleo de coincidencia
# =========================

def mejor_coincidencia(texto_usuario: str) -> Tuple[Dict, str]:
    """
    Retorna (mejor, pregunta_normalizada) donde mejor = {id, score, pregunta, respuesta}
    correspondiente a la mejor coincidencia por similitud del coseno.
    """
    norm = normalizar(texto_usuario)
    vec_q = vectorizar(tokenizar(norm))

    filas = cargar_todas()
    mejor = {"id": -1, "score": 0.0, "pregunta": "", "respuesta": ""}

    for fid, preg, resp in filas:
        vec = vectorizar(tokenizar(preg))
        s = similitud_coseno(vec_q, vec)
        if s > mejor["score"]:
            mejor = {"id": fid, "score": float(s), "pregunta": preg, "respuesta": resp}

    return mejor, norm

# =========================
# 4) API de alto nivel
# =========================

@dataclass
class Resultado:
    coincidencia: bool
    respuesta: str
    puntaje: float
    pregunta_coincidente: Optional[str] = None

UMBRAL = 0.72  # ajustable

def responder(mensaje: str) -> Resultado:
    mejor, _ = mejor_coincidencia(mensaje)
    if mejor["score"] >= UMBRAL:
        return Resultado(
            coincidencia=True,
            respuesta=mejor["respuesta"],
            puntaje=round(mejor["score"], 3),
            pregunta_coincidente=mejor["pregunta"],
        )
    else:
        return Resultado(
            coincidencia=False,
            respuesta="No tengo una respuesta para eso todavía.",
            puntaje=round(mejor["score"], 3),
        )

# =========================
# 5) REPL de consola
# =========================

def repl() -> None:
    """
    Bucle de conversación por consola:
    - Usuario escribe una pregunta.
    - Si hay match (>= UMBRAL), se responde desde la KB.
    - Si NO hay match, se pide al usuario enseñar la respuesta y se guarda.
    """
    print("Sistema experto (sin web). Ctrl+C para salir.")
    while True:
        try:
            user = input("Tú: ").strip()
            if not user:
                continue
            r = responder(user)
            if r.coincidencia:
                print(f"Bot: {r.respuesta}  [match='{r.pregunta_coincidente}', score={r.puntaje}]")
            else:
                print(f"Bot: {r.respuesta}  [score≈{r.puntaje}]")
                print("Bot: ¿Qué te gustaría que respondiera la próxima vez?")
                nuevo = input("Enséñame la respuesta: ").strip()
                if nuevo:
                    guardar_entrada(user, nuevo)
                    print("Bot: Listo. Ya lo aprendí.")
        except KeyboardInterrupt:
            print("\nSaliendo…")
            break

# =========================
# 6) Punto de entrada
# =========================

if __name__ == "__main__":
    iniciar_db()
    repl()
