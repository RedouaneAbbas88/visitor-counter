import streamlit as st
import pandas as pd
from datetime import datetime

# Titre de l'application
st.title("📊 Visitor Counter - Stand Foire")

st.write("Application de comptage des visiteurs (version simple) 🚀")

# Initialisation du compteur dans Streamlit
if "count" not in st.session_state:
    st.session_state.count = 0

# Bouton pour simuler un visiteur
if st.button("➕ Ajouter un visiteur"):
    st.session_state.count += 1

# Affichage du compteur
st.metric(label="👥 Nombre de visiteurs", value=st.session_state.count)

# Sauvegarde des données
data = {
    "date": [datetime.now().strftime("%Y-%m-%d")],
    "heure": [datetime.now().strftime("%H:%M:%S")],
    "visiteurs": [st.session_state.count]
}

df = pd.DataFrame(data)

# Affichage tableau
st.subheader("📋 Historique")
st.dataframe(df)
