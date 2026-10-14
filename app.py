import streamlit as st

st.set_page_config(page_title="Gestion Crèche", page_icon="👶", layout="wide")

st.title("👶 Mon Application de Crèche")
st.write(
    "Bienvenue sur l'interface de gestion connectée à Google Sheets et GitHub."
)

# Exemple de saisie simple
nom_enfant = st.text_input("Nom de l'enfant")
if st.button("Enregistrer"):
    if nom_enfant:
        st.success(f"Enfant {nom_enfant} pris en compte !")
    else:
        st.error("Veuillez entrer un nom.")
