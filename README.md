# Portfolio Tracker

Lokalna aplikacja do monitorowania portfela inwestycyjnego (akcje, ETF, obligacje, krypto).

## Wymagania

- Python 3.11+

## Instalacja

```bash
# Sklonuj lub pobierz projekt, wejdź do katalogu
cd "APP INV"

# Utwórz środowisko wirtualne (zalecane)
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

# Zainstaluj zależności
pip install -r requirements.txt

# Skopiuj plik z kluczem API (wypełnisz go w Kroku 2)
cp .env.example .env
```

## Uruchomienie

```bash
streamlit run app.py
```

Aplikacja otworzy się w przeglądarce pod adresem `http://localhost:8501`.

## Struktura

```
APP INV/
├── app.py           # główna aplikacja Streamlit
├── database.py      # obsługa SQLite
├── portfolio.db     # baza danych (tworzona automatycznie)
├── requirements.txt
├── .env             # klucz API (NIE commituj do gita)
└── .env.example
```
