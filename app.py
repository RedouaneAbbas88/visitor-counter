import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import uuid

st.set_page_config(page_title="Creche Manager", page_icon="🏫", layout="wide")

# ------------------------------------------------------------
# Configuration and Google Sheets connection
# ------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

@st.cache_resource
def get_gspread_client():
    info = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(credentials)

@st.cache_resource
def get_spreadsheet():
    client = get_gspread_client()
    return client.open_by_key(st.secrets["google_sheets"]["spreadsheet_id"])

def get_worksheet(sheet_name):
    return get_spreadsheet().worksheet(sheet_name)

def read_sheet(sheet_name):
    """Return the sheet as a DataFrame, or an empty DataFrame if it has no rows."""
    ws = get_worksheet(sheet_name)
    records = ws.get_all_records()
    return pd.DataFrame(records)

def append_record(sheet_name, record):
    """Append a row using the exact column order already present in the worksheet."""
    ws = get_worksheet(sheet_name)
    headers = ws.row_values(1)
    row = [record.get(header, "") for header in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")

def tenant_id():
    # The signed-in account's tenant is determined by secrets, not by a form.
    return st.session_state["user"]["id_creche"]

def tenant_rows(df):
    if df.empty or "ID_Creche" not in df.columns:
        return df
    return df[df["ID_Creche"].astype(str) == str(tenant_id())].copy()

def audit(action, module, object_type="", object_id="", result="OK", details=""):
    try:
        append_record("Journal_Audit", {
            "ID_Audit": make_id("AUD"),
            "ID_Creche": tenant_id(),
            "ID_Utilisateur": st.session_state["user"]["id_utilisateur"],
            "Action": action,
            "Module": module,
            "Type_Objet": object_type,
            "ID_Objet": object_id,
            "Date_Heure": datetime.now().isoformat(timespec="seconds"),
            "Resultat": result,
            "Details_Sans_Donnees_Sensibles": details,
        })
    except Exception:
        # Audit failures should not reveal credentials or sensitive records to users.
        pass

# ------------------------------------------------------------
# Simple login backed by Streamlit secrets.
# Passwords must be bcrypt hashes; never put plaintext passwords in GitHub.
# ------------------------------------------------------------
def login_screen():
    st.title("🏫 Creche Manager")
    st.caption("Plateforme de gestion des crèches")
    st.info("Connecte-toi avec un compte configuré par l'administrateur.")
    with st.form("login_form"):
        username = st.text_input("Identifiant")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter", type="primary")
    if submitted:
        try:
            import bcrypt
            users = st.secrets["users"]
            user_cfg = users.get(username)
            if user_cfg and bcrypt.checkpw(password.encode("utf-8"), user_cfg["password_hash"].encode("utf-8")):
                st.session_state["user"] = {
                    "username": username,
                    "id_utilisateur": user_cfg["id_utilisateur"],
                    "id_creche": user_cfg["id_creche"],
                    "nom": user_cfg.get("nom", username),
                    "role": user_cfg.get("role", "Administrateur"),
                    "langue": user_cfg.get("langue", "fr"),
                }
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")
        except Exception:
            st.error("Configuration de connexion incomplète. Vérifie les secrets Streamlit et la bibliothèque bcrypt.")

def show_table(sheet_name, title, search_columns=None):
    st.subheader(title)
    try:
        df = tenant_rows(read_sheet(sheet_name))
        if df.empty:
            st.info("Aucune donnée enregistrée pour le moment.")
            return
        if search_columns:
            search = st.text_input(f"Rechercher dans {title}", key=f"search_{sheet_name}")
            if search:
                mask = pd.Series(False, index=df.index)
                for col in search_columns:
                    if col in df.columns:
                        mask = mask | df[col].astype(str).str.contains(search, case=False, na=False)
                df = df[mask]
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} ligne(s)")
    except Exception as exc:
        st.error(f"Impossible de lire la feuille « {sheet_name} ». Vérifie son nom et ses en-têtes dans Google Sheets.")
        st.caption(str(exc))

def add_parent():
    st.subheader("Ajouter un parent")
    with st.form("add_parent_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom *")
            prenom = st.text_input("Prénom *")
            tel = st.text_input("Téléphone principal *")
            email = st.text_input("E-mail")
        with c2:
            tel2 = st.text_input("Téléphone secondaire")
            adresse = st.text_input("Adresse")
            profession = st.text_input("Profession")
            statut = st.selectbox("Statut", ["Actif", "Inactif"])
        urgence_nom = st.text_input("Nom du contact d'urgence")
        urgence_tel = st.text_input("Téléphone du contact d'urgence")
        submitted = st.form_submit_button("Enregistrer le parent", type="primary")
    if submitted:
        if not nom.strip() or not prenom.strip() or not tel.strip():
            st.warning("Les champs Nom, Prénom et Téléphone principal sont obligatoires.")
            return
        try:
            record = {
                "ID_Parent": make_id("PAR"),
                "ID_Creche": tenant_id(),
                "Nom": nom.strip(),
                "Prenom": prenom.strip(),
                "Telephone_Principal": tel.strip(),
                "Telephone_Secondaire": tel2.strip(),
                "Email": email.strip(),
                "Adresse": adresse.strip(),
                "Profession": profession.strip(),
                "Contact_Urgence_Nom": urgence_nom.strip(),
                "Contact_Urgence_Telephone": urgence_tel.strip(),
                "Notes_Non_Sensibles": "",
                "Statut": statut,
                "Date_Ajout": datetime.now().isoformat(timespec="seconds"),
                "Date_Modification": datetime.now().isoformat(timespec="seconds"),
            }
            append_record("Parents", record)
            audit("CREATE", "Parents", "Parent", record["ID_Parent"])
            st.success("Parent enregistré.")
            st.rerun()
        except Exception as exc:
            st.error("Enregistrement impossible. Vérifie la connexion Google Sheets et les colonnes de la feuille Parents.")
            st.caption(str(exc))

def add_child():
    st.subheader("Ajouter un enfant")
    try:
        groups = tenant_rows(read_sheet("Groupes"))
        group_options = {}
        if not groups.empty and {"ID_Groupe", "Nom_Groupe"}.issubset(groups.columns):
            group_options = {
                str(row["Nom_Groupe"]): str(row["ID_Groupe"])
                for _, row in groups.iterrows()
                if str(row.get("Statut", "Actif")).lower() not in ("inactif", "désactivé", "desactive")
            }
    except Exception:
        group_options = {}
    with st.form("add_child_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom *")
            prenom = st.text_input("Prénom *")
            naissance = st.date_input("Date de naissance", value=date(2023, 1, 1), min_value=date(2000, 1, 1), max_value=date.today())
            sexe = st.selectbox("Sexe", ["Non renseigné", "F", "M"])
        with c2:
            adresse = st.text_input("Adresse")
            groupe_nom = st.selectbox("Groupe", ["Non affecté"] + list(group_options.keys()))
            statut = st.selectbox("Statut", ["Actif", "En attente", "Inactif"])
            premiere = st.date_input("Date de première inscription", value=date.today())
        st.warning("N'enregistre pas de détails médicaux dans cette première version. Nous ajouterons un module protégé adapté.")
        submitted = st.form_submit_button("Enregistrer l'enfant", type="primary")
    if submitted:
        if not nom.strip() or not prenom.strip():
            st.warning("Les champs Nom et Prénom sont obligatoires.")
            return
        try:
            now = datetime.now().isoformat(timespec="seconds")
            record = {
                "ID_Enfant": make_id("ENF"),
                "ID_Creche": tenant_id(),
                "Nom": nom.strip(),
                "Prenom": prenom.strip(),
                "Date_Naissance": naissance.isoformat(),
                "Sexe": "" if sexe == "Non renseigné" else sexe,
                "Adresse": adresse.strip(),
                "Date_Premiere_Inscription": premiere.isoformat(),
                "ID_Groupe": group_options.get(groupe_nom, ""),
                "Allergies_Informations_Protegees": "",
                "Informations_Medicales_Protegees": "",
                "Photo_Fichier_ID": "",
                "Statut": statut,
                "Date_Ajout": now,
                "Date_Modification": now,
            }
            append_record("Enfants", record)
            audit("CREATE", "Enfants", "Enfant", record["ID_Enfant"])
            st.success("Enfant enregistré.")
            st.rerun()
        except Exception as exc:
            st.error("Enregistrement impossible. Vérifie la connexion Google Sheets et les colonnes de la feuille Enfants.")
            st.caption(str(exc))

def add_expense():
    st.subheader("Ajouter une dépense")
    try:
        cats = tenant_rows(read_sheet("Categories_Depenses"))
        category_options = {}
        if not cats.empty and {"ID_Categorie_Depense", "Nom_Categorie"}.issubset(cats.columns):
            category_options = {
                str(row["Nom_Categorie"]): str(row["ID_Categorie_Depense"])
                for _, row in cats.iterrows()
            }
    except Exception:
        category_options = {}
    with st.form("add_expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            date_depense = st.date_input("Date de dépense", value=date.today())
            libelle = st.text_input("Libellé *")
            fournisseur = st.text_input("Fournisseur")
            montant = st.number_input("Montant (DA) *", min_value=0.0, step=100.0)
        with c2:
            categorie = st.selectbox("Catégorie", ["Non classée"] + list(category_options.keys()))
            mode = st.selectbox("Mode de paiement", ["Espèces", "Virement", "Chèque", "Carte", "Autre"])
            justificatif = st.text_input("Numéro du justificatif")
            statut = st.selectbox("Statut", ["Validée", "En attente", "Annulée"])
        submitted = st.form_submit_button("Enregistrer la dépense", type="primary")
    if submitted:
        if not libelle.strip() or montant <= 0:
            st.warning("Le libellé et un montant supérieur à zéro sont obligatoires.")
            return
        try:
            record = {
                "ID_Depense": make_id("DEP"),
                "ID_Creche": tenant_id(),
                "Date_Depense": date_depense.isoformat(),
                "ID_Categorie_Depense": category_options.get(categorie, ""),
                "Libelle": libelle.strip(),
                "Fournisseur": fournisseur.strip(),
                "Numero_Justificatif": justificatif.strip(),
                "Montant": montant,
                "Devise": "DZD",
                "Mode_Paiement": mode,
                "Reference_Paiement": "",
                "Justificatif_Fichier_ID": "",
                "Enregistre_Par": st.session_state["user"]["id_utilisateur"],
                "Statut": statut,
                "Date_Ajout": datetime.now().isoformat(timespec="seconds"),
            }
            append_record("Depenses", record)
            audit("CREATE", "Depenses", "Depense", record["ID_Depense"])
            st.success("Dépense enregistrée.")
            st.rerun()
        except Exception as exc:
            st.error("Enregistrement impossible. Vérifie la connexion Google Sheets et les colonnes de la feuille Depenses.")
            st.caption(str(exc))

def dashboard():
    st.title("Tableau de bord")
    try:
        enfants = tenant_rows(read_sheet("Enfants"))
        presences = tenant_rows(read_sheet("Presences_Enfants"))
        factures = tenant_rows(read_sheet("Factures"))
        depenses = tenant_rows(read_sheet("Depenses"))
        personnel = tenant_rows(read_sheet("Personnel"))
        today_str = date.today().isoformat()
        present_count = 0
        if not presences.empty and {"Date", "Statut_Presence"}.issubset(presences.columns):
            todays = presences[presences["Date"].astype(str).str[:10] == today_str]
            present_count = int(todays["Statut_Presence"].astype(str).str.lower().isin(["présent", "present", "présente", "presente"]).sum())
        outstanding = 0.0
        if not factures.empty and "Solde_Calcule" in factures.columns:
            outstanding = pd.to_numeric(factures["Solde_Calcule"], errors="coerce").fillna(0).sum()
        monthly_expenses = 0.0
        if not depenses.empty and {"Date_Depense", "Montant"}.issubset(depenses.columns):
            month_prefix = date.today().strftime("%Y-%m")
            month_rows = depenses[
                depenses["Date_Depense"].astype(str).str.startswith(month_prefix)
                & ~depenses.get("Statut", pd.Series("", index=depenses.index)).astype(str).str.lower().eq("annulée")
            ]
            monthly_expenses = pd.to_numeric(month_rows["Montant"], errors="coerce").fillna(0).sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Enfants actifs", int(enfants.get("Statut", pd.Series(dtype=str)).astype(str).str.lower().eq("actif").sum()) if not enfants.empty else 0)
        c2.metric("Présents aujourd'hui", present_count)
        c3.metric("Personnel actif", int(personnel.get("Statut", pd.Series(dtype=str)).astype(str).str.lower().eq("actif").sum()) if not personnel.empty else 0)
        c4.metric("Impayés (DA)", f"{outstanding:,.0f}".replace(",", " "))
        st.divider()
        st.metric("Dépenses du mois (DA)", f"{monthly_expenses:,.0f}".replace(",", " "))
        st.caption("Les indicateurs dépendent des données renseignées dans Google Sheets.")
    except Exception as exc:
        st.error("La connexion à Google Sheets a échoué ou la structure des feuilles n'est pas encore prête.")
        st.caption(str(exc))

# ------------------------------------------------------------
# Main app
# ------------------------------------------------------------
if "user" not in st.session_state:
    login_screen()
    st.stop()

user = st.session_state["user"]
with st.sidebar:
    st.title("🏫 Creche Manager")
    st.write(f"Connecté : **{user['nom']}**")
    st.caption(f"Rôle : {user['role']}")
    lang = st.selectbox("Langue / اللغة", ["Français", "العربية"], index=0 if user.get("langue", "fr") == "fr" else 1)
    menu = st.radio("Navigation", [
        "Tableau de bord",
        "Enfants",
        "Ajouter un enfant",
        "Parents",
        "Ajouter un parent",
        "Personnel",
        "Présences enfants",
        "Factures",
        "Paiements",
        "Dépenses",
        "Ajouter une dépense",
        "Groupes",
    ])
    if st.button("Se déconnecter"):
        del st.session_state["user"]
        st.rerun()

try:
    # Verify the configured tenant exists and avoid trusting any tenant ID from the browser.
    tenant_records = read_sheet("Creches")
    tenant_records = tenant_records[tenant_records.get("ID_Creche", pd.Series(dtype=str)).astype(str) == str(tenant_id())]
    if tenant_records.empty:
        st.error("L'établissement associé à ce compte n'existe pas dans la feuille Creches. Vérifie les secrets Streamlit.")
        st.stop()
except Exception as exc:
    st.error("Impossible de vérifier l'établissement dans Google Sheets.")
    st.caption("Vérifie l'ID du classeur, les autorisations du compte de service et la présence de la feuille Creches.")
    st.stop()

if menu == "Tableau de bord":
    dashboard()
elif menu == "Enfants":
    show_table("Enfants", "Liste des enfants", ["Nom", "Prenom", "ID_Enfant"])
elif menu == "Ajouter un enfant":
    add_child()
elif menu == "Parents":
    show_table("Parents", "Liste des parents", ["Nom", "Prenom", "Telephone_Principal", "Email"])
elif menu == "Ajouter un parent":
    add_parent()
elif menu == "Personnel":
    show_table("Personnel", "Liste du personnel", ["Nom", "Prenom", "Poste", "Telephone"])
elif menu == "Présences enfants":
    show_table("Presences_Enfants", "Présences des enfants", ["ID_Enfant", "Date", "Statut_Presence"])
elif menu == "Factures":
    show_table("Factures", "Factures", ["Numero_Facture", "ID_Parent", "Statut"])
elif menu == "Paiements":
    show_table("Paiements", "Paiements", ["Numero_Recu", "ID_Parent", "Mode_Paiement"])
elif menu == "Dépenses":
    show_table("Depenses", "Dépenses", ["Libelle", "Fournisseur", "Date_Depense"])
elif menu == "Ajouter une dépense":
    add_expense()
elif menu == "Groupes":
    show_table("Groupes", "Groupes", ["Nom_Groupe", "Nom_Responsable"])
