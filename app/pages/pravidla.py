import streamlit as st

st.title("📖 Pravidla")

st.markdown("""
### Účastníci
Chajda, Saša, Vojta, Poli.

### Před každým kolem
Každý účastník tipuje výsledky všech 10 zápasů daného kola Premier League
a nominuje 0–3 fotbalisty, u kterých věří, že v tomto kole skórují nebo nahrají.

### Bodování — tipy na výsledky
| Výsledek | Body |
|---|---|
| Přesný výsledek | 10 |
| Správná tendence (výhra/remíza/prohra) | 2 |
| Jinak | 0 |

### Bodování — nominovaní fotbalisté
| Událost | Body |
|---|---|
| Gól | 5 |
| Každý další gól | +2 |
| Asistence | 2 |
| Každá další asistence | +1 |
| Nominovaný hráč nastoupil, ale nedal gól ani asistenci | −2 |

Hráč, kterého nikdo nenominoval, body ani penalizaci nikomu nezakládá.
""")
