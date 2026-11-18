import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import uuid

st.set_page_config(page_title="Creche Manager Pro", page_icon="🏫", layout="wide")

# ============================================================
# CONFIGURATION - Google Sheets multi-établissements
# ============================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Feuilles créées automatiquement si elles n'existent pas.
# Les colonnes existantes ne sont jamais supprimées : les nouvelles sont ajoutées à droite.
SCHEMAS = {
    # Schéma conservé à partir du classeur source de l'utilisateur.
    "Creches": ["ID_Creche", "Nom_Creche", "Nom_Legal", "NIF", "NIS", "RC", "Adresse", "Wilaya", "Commune", "Telephone", "Email", "Nom_Directeur", "Capacite_Max", "Devise", "Langue_Defaut", "Date_Creation", "Statut", "Date_Ajout", "Date_Modification"],
    "Journal_Audit": ["ID_Audit", "ID_Creche", "ID_Utilisateur", "Action", "Module", "Type_Objet", "ID_Objet", "Date_Heure", "Resultat", "Details_Sans_Donnees_Sensibles"],
    "Parents": ["ID_Parent", "ID_Creche", "Nom", "Prenom", "Telephone_Principal", "Telephone_Secondaire", "Email", "Adresse", "Profession", "Contact_Urgence_Nom", "Contact_Urgence_Telephone", "Notes_Non_Sensibles", "Statut", "Date_Ajout", "Date_Modification"],
    "Enfants": ["ID_Enfant", "ID_Creche", "Nom", "Prenom", "Date_Naissance", "Sexe", "Adresse", "Date_Premiere_Inscription", "ID_Groupe", "Allergies_Informations_Protegees", "Informations_Medicales_Protegees", "Photo_Fichier_ID", "Statut", "Date_Ajout", "Date_Modification", "Regime_Alimentaire", "Personnes_Autorisees", "Informations_Accueil"],
    "Enfants_Parents": ["ID_Lien", "ID_Creche", "ID_Enfant", "ID_Parent", "Lien_Parente", "Responsable_Financier", "Contact_Prioritaire", "Autorise_Informations", "Date_Debut", "Date_Fin"],
    "Documents": ["ID_Document", "ID_Creche", "Type_Objet", "ID_Objet", "Type_Document", "Nom_Fichier", "Google_Drive_File_ID", "Date_Document", "Date_Expiration", "Ajoute_Par", "Date_Ajout", "Categorie", "Obligatoire", "Statut", "Commentaire"],
    "Groupes": ["ID_Groupe", "ID_Creche", "Nom_Groupe", "Age_Min_Mois", "Age_Max_Mois", "Capacite", "Nom_Responsable", "Statut", "Date_Ajout"],
    "Personnel": ["ID_Personnel", "ID_Creche", "Nom", "Prenom", "Date_Naissance", "Telephone", "Email", "Adresse", "Poste", "Date_Embauche", "Type_Contrat", "Salaire_Base", "Devise", "Numero_Compte_Paie_Reference", "Contact_Urgence", "Statut", "Date_Ajout", "Date_Modification"],
    "Presences_Enfants": ["ID_Presence", "ID_Creche", "ID_Enfant", "Date", "Heure_Arrivee", "Heure_Depart", "Statut_Presence", "Motif_Absence", "Depose_Par", "Recupere_Par", "Enregistre_Par", "Commentaire", "Date_Ajout"],
    "Presences_Personnel": ["ID_Presence_Personnel", "ID_Creche", "ID_Personnel", "Date", "Heure_Arrivee", "Heure_Depart", "Statut_Presence", "Motif_Absence", "Valide_Par", "Date_Ajout"],
    "Salaires": ["ID_Salaire", "ID_Creche", "ID_Personnel", "Mois_Paie", "Annee_Paie", "Salaire_Base", "Primes", "Retenues", "Net_A_Payer", "Date_Paiement", "Mode_Paiement", "Reference_Paiement", "Statut", "Valide_Par", "Date_Ajout"],
    "Restaurants": ["ID_Restaurant", "ID_Creche", "Nom", "Type", "Capacite", "Statut"],
    "Repas": ["ID_Repas", "ID_Creche", "Date", "Service", "Nom_Repas", "Description", "ID_Restaurant", "Age_Concerne", "Allergenes", "Statut"],
    "Transport": ["ID_Transport", "ID_Creche", "Nom_Ligne", "Vehicule", "Chauffeur", "Capacite", "Zone", "Statut"],
    "Affectations_Transport": ["ID_Affectation", "ID_Creche", "ID_Enfant", "ID_Transport", "Date_Debut", "Date_Fin", "Arret", "Personne_Autorisee", "Statut"],
}


def make_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@st.cache_resource
def get_gspread_client():
    credentials = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(credentials)


@st.cache_resource
def get_spreadsheet():
    return get_gspread_client().open_by_key(st.secrets["google_sheets"]["spreadsheet_id"])


def get_worksheet(name):
    return get_spreadsheet().worksheet(name)


def ensure_sheets():
    book = get_spreadsheet()
    for name, required in SCHEMAS.items():
        try:
            ws = book.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = book.add_worksheet(title=name, rows=1000, cols=max(20, len(required)))
            ws.append_row(required)
            continue
        headers = ws.row_values(1)
        if not headers:
            ws.append_row(required)
        else:
            missing = [col for col in required if col not in headers]
            if missing:
                ws.update(values=[headers + missing], range_name="A1")


def read_sheet(name):
    ws = get_worksheet(name)
    records = ws.get_all_records()
    return pd.DataFrame(records)


def append_record(name, record):
    ws = get_worksheet(name)
    headers = ws.row_values(1)
    ws.append_row([record.get(h, "") for h in headers], value_input_option="USER_ENTERED")


def tenant_id():
    return str(st.session_state["user"]["id_creche"])


def tenant_rows(df):
    if df.empty or "ID_Creche" not in df.columns:
        return df.copy()
    return df[df["ID_Creche"].astype(str) == tenant_id()].copy()


def save_record(sheet, record, module, obj_type, obj_id):
    append_record(sheet, record)
    try:
        append_record("Journal_Audit", {
            "ID_Audit": make_id("AUD"), "ID_Creche": tenant_id(),
            "ID_Utilisateur": st.session_state["user"]["id_utilisateur"],
            "Action": "CREATE", "Module": module, "Type_Objet": obj_type,
            "ID_Objet": obj_id, "Date_Heure": datetime.now().isoformat(timespec="seconds"),
            "Resultat": "OK", "Details_Sans_Donnees_Sensibles": "Enregistrement créé"
        })
    except Exception:
        pass


def options_from_sheet(sheet, id_col, label_cols, active_only=True):
    df = tenant_rows(read_sheet(sheet))
    result = {}
    if df.empty or id_col not in df.columns:
        return result
    for _, r in df.iterrows():
        if active_only and "Statut" in df.columns and str(r.get("Statut", "Actif")).lower() not in ("actif", "active", "en attente", ""):
            continue
        label = " ".join(str(r.get(c, "")).strip() for c in label_cols if str(r.get(c, "")).strip())
        result[label or str(r[id_col])] = str(r[id_col])
    return result


def login_screen():
    st.title("🏫 Creche Manager Pro")
    st.caption("Gestion complète des établissements de petite enfance")
    with st.form("login_form"):
        username = st.text_input("Identifiant")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter", type="primary")
    if submitted:
        try:
            import bcrypt
            cfg = st.secrets["users"].get(username)
            if cfg and bcrypt.checkpw(password.encode(), cfg["password_hash"].encode()):
                st.session_state["user"] = {
                    "username": username, "id_utilisateur": cfg["id_utilisateur"],
                    "id_creche": cfg["id_creche"], "nom": cfg.get("nom", username),
                    "role": cfg.get("role", "Administrateur")
                }
                st.rerun()
            st.error("Identifiant ou mot de passe incorrect.")
        except Exception:
            st.error("Configuration de connexion invalide. Vérifie les secrets et bcrypt.")


def table_page(sheet, title, search_cols=None):
    st.subheader(title)
    df = tenant_rows(read_sheet(sheet))
    if df.empty:
        st.info("Aucun enregistrement pour le moment.")
        return
    if search_cols:
        q = st.text_input("Rechercher", key=f"search_{sheet}")
        if q:
            mask = pd.Series(False, index=df.index)
            for col in search_cols:
                if col in df.columns:
                    mask |= df[col].astype(str).str.contains(q, case=False, na=False)
            df = df[mask]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} enregistrement(s)")


def parent_form():
    st.subheader("👨‍👩‍👧 Fiche parent / responsable")
    with st.form("parent_form", clear_on_submit=True):
        a, b = st.columns(2)
        with a:
            nom = st.text_input("Nom *"); prenom = st.text_input("Prénom *")
            tel = st.text_input("Téléphone principal *"); tel2 = st.text_input("Téléphone secondaire")
            email = st.text_input("E-mail"); profession = st.text_input("Profession")
        with b:
            adresse = st.text_input("Adresse"); lien = st.selectbox("Lien avec l'enfant", ["Père", "Mère", "Tuteur légal", "Autre"])
            urgence = st.text_input("Contact d'urgence"); urgence_tel = st.text_input("Téléphone d'urgence")
            autorise = st.selectbox("Autorisé à récupérer l'enfant ?", ["Oui", "Non"])
            statut = st.selectbox("Statut", ["Actif", "Inactif"])
        ok = st.form_submit_button("Enregistrer le parent", type="primary")
    if ok:
        if not nom.strip() or not prenom.strip() or not tel.strip():
            st.warning("Nom, prénom et téléphone sont obligatoires."); return
        pid = make_id("PAR"); now = datetime.now().isoformat(timespec="seconds")
        save_record("Parents", {"ID_Parent": pid, "ID_Creche": tenant_id(), "Nom": nom.strip(), "Prenom": prenom.strip(),
            "Telephone_Principal": tel.strip(), "Telephone_Secondaire": tel2.strip(), "Email": email.strip(), "Adresse": adresse.strip(),
            "Profession": profession.strip(), "Contact_Urgence_Nom": urgence.strip(), "Contact_Urgence_Telephone": urgence_tel.strip(),
            "Notes_Non_Sensibles": f"Lien: {lien}; Récupération autorisée: {autorise}", "Statut": statut,
            "Date_Ajout": now, "Date_Modification": now}, "Parents", "Parent", pid)
        st.success("Fiche parent créée."); st.rerun()


def child_form():
    st.subheader("🧒 Inscription d'un nouvel enfant")
    parents = tenant_rows(read_sheet("Parents"))
    if parents.empty:
        st.warning("Ajoute d'abord au moins un parent dans le module Parents."); return
    parent_opts = {}
    for _, p in parents.iterrows():
        if str(p.get("Statut", "Actif")).lower() == "inactif": continue
        label = f"{p.get('Nom','')} {p.get('Prenom','')} — {p.get('Telephone_Principal','')}"
        parent_opts[label] = str(p.get("ID_Parent", ""))
    groups = options_from_sheet("Groupes", "ID_Groupe", ["Nom_Groupe"])
    with st.form("child_form", clear_on_submit=True):
        st.markdown("**1. Identité de l'enfant**")
        a, b = st.columns(2)
        with a:
            nom = st.text_input("Nom de l'enfant *"); prenom = st.text_input("Prénom *")
            naissance = st.date_input("Date de naissance", value=date(2023, 1, 1), min_value=date(2000, 1, 1), max_value=date.today())
            sexe = st.selectbox("Sexe", ["Non renseigné", "F", "M"])
        with b:
            adresse = st.text_input("Adresse de l'enfant")
            groupe_label = st.selectbox("Classe / Groupe", ["Non affecté"] + list(groups.keys()))
            inscription = st.date_input("Date d'inscription", value=date.today())
            statut = st.selectbox("Statut", ["Actif", "En attente", "Inactif"])
        st.markdown("**2. Rattachement familial**")
        p1 = st.selectbox("Parent principal / responsable légal *", list(parent_opts.keys()))
        p2_choices = ["Aucun"] + [x for x in parent_opts if x != p1]
        p2 = st.selectbox("Deuxième parent (facultatif)", p2_choices)
        st.markdown("**3. Informations utiles à l'accueil**")
        regime = st.text_input("Régime alimentaire / consignes de repas")
        allergies = st.text_area("Allergies ou alertes médicales importantes", help="Données sensibles : accès à limiter aux personnes habilitées.")
        medical = st.text_area("Informations médicales / consignes particulières", help="Ne remplace pas un dossier médical officiel.")
        personnes = st.text_area("Personnes autorisées à récupérer l'enfant")
        ok = st.form_submit_button("Créer la fiche enfant", type="primary")
    if ok:
        if not nom.strip() or not prenom.strip(): st.warning("Nom et prénom obligatoires."); return
        eid = make_id("ENF"); now = datetime.now().isoformat(timespec="seconds")
        save_record("Enfants", {"ID_Enfant": eid, "ID_Creche": tenant_id(), "Nom": nom.strip(), "Prenom": prenom.strip(),
            "Date_Naissance": naissance.isoformat(), "Sexe": "" if sexe == "Non renseigné" else sexe, "Adresse": adresse.strip(),
            "Date_Premiere_Inscription": inscription.isoformat(), "ID_Groupe": groups.get(groupe_label, ""),
            "Regime_Alimentaire": regime.strip(), "Allergies_Informations_Protegees": allergies.strip(),
            "Informations_Medicales_Protegees": medical.strip(), "Personnes_Autorisees": personnes.strip(),
            "Photo_Fichier_ID": "", "Statut": statut, "Date_Ajout": now, "Date_Modification": now}, "Enfants", "Enfant", eid)
        # Relation normalisée : un enfant peut avoir plusieurs parents via Enfants_Parents.
        for parent_id, lien, prioritaire, financier in [
            (parent_opts[p1], "Parent principal", "Oui", "Oui"),
            (parent_opts[p2], "Deuxième parent", "Non", "Non") if p2 != "Aucun" else ("", "", "", "")
        ]:
            if parent_id:
                append_record("Enfants_Parents", {"ID_Lien": make_id("LNK"), "ID_Creche": tenant_id(), "ID_Enfant": eid,
                    "ID_Parent": parent_id, "Lien_Parente": lien, "Responsable_Financier": financier,
                    "Contact_Prioritaire": prioritaire, "Autorise_Informations": "Oui", "Date_Debut": inscription.isoformat(), "Date_Fin": ""})
        st.success("Fiche enfant créée et parent(s) rattaché(s). Tu peux maintenant compléter son dossier administratif et médical."); st.rerun()


def document_center():
    st.subheader("📁 Dossier administratif et médical")
    children = tenant_rows(read_sheet("Enfants"))
    if children.empty: st.info("Aucun enfant enregistré."); return
    child_opts = {f"{r.get('Nom','')} {r.get('Prenom','')} ({r.get('ID_Enfant','')})": str(r.get("ID_Enfant")) for _, r in children.iterrows()}
    selected = st.selectbox("Choisir l'enfant", list(child_opts.keys()))
    child_id = child_opts[selected]
    docs = tenant_rows(read_sheet("Documents"))
    docs = docs[(docs.get("Type_Objet", pd.Series(dtype=str)).astype(str) == "Enfant") & (docs.get("ID_Objet", pd.Series(dtype=str)).astype(str) == child_id)] if not docs.empty else docs
    with st.expander("➕ Ajouter / mettre à jour une pièce du dossier", expanded=True):
        with st.form("doc_form", clear_on_submit=True):
            categorie = st.selectbox("Catégorie", ["Administratif", "Médical"])
            document = st.selectbox("Document", ["Acte de naissance", "Photos d'identité", "Copie pièce d'identité parent", "Fiche de renseignements", "Contrat / règlement signé", "Carnet de santé", "Certificat médical", "Vaccinations", "Fiche allergies / protocole", "Autorisation parentale", "Autre"])
            obligatoire = st.selectbox("Pièce obligatoire ?", ["Oui", "Non"])
            statut = st.selectbox("État", ["Reçu", "Manquant", "À renouveler", "Non applicable"])
            depot = st.date_input("Date de dépôt", value=date.today())
            expiration = st.date_input("Date d'expiration (si applicable)", value=None)
            fichier = st.text_input("Lien ou identifiant du fichier (Drive)")
            commentaire = st.text_input("Commentaire")
            ok = st.form_submit_button("Enregistrer la pièce")
        if ok:
            did = make_id("DOC")
            # La feuille Documents source utilise une structure générique Type_Objet / ID_Objet.
            save_record("Documents", {"ID_Document": did, "ID_Creche": tenant_id(), "Type_Objet": "Enfant", "ID_Objet": child_id,
                "Type_Document": document, "Nom_Fichier": fichier.strip(),
                "Google_Drive_File_ID": fichier.strip(), "Date_Document": depot.isoformat(),
                "Date_Expiration": "" if expiration is None else expiration.isoformat(),
                "Ajoute_Par": st.session_state["user"]["id_utilisateur"], "Date_Ajout": datetime.now().isoformat(timespec="seconds"),
                "Categorie": categorie, "Obligatoire": obligatoire, "Statut": statut, "Commentaire": commentaire.strip()}, "Dossiers enfants", "Document", did)
            st.success("Pièce enregistrée."); st.rerun()
    st.markdown("**État du dossier de l'enfant**")
    required = ["Acte de naissance", "Fiche de renseignements", "Contrat / règlement signé", "Carnet de santé", "Certificat médical", "Vaccinations"]
    status_map = {}
    if not docs.empty:
        for _, r in docs.iterrows():
            status_map[str(r.get("Type_Document", ""))] = str(r.get("Statut", "Manquant"))
    missing = [d for d in required if status_map.get(d, "Manquant") not in ("Reçu", "Non applicable")]
    c1, c2, c3 = st.columns(3)
    c1.metric("Pièces obligatoires", len(required)); c2.metric("Pièces à compléter", len(missing)); c3.metric("Pièces reçues", len(required)-len(missing))
    if missing: st.warning("Documents à fournir : " + " • ".join(missing))
    else: st.success("Dossier complet selon la liste de contrôle définie.")
    if not docs.empty: st.dataframe(docs, use_container_width=True, hide_index=True)


def attendance_children():
    st.subheader("🕘 Présence des enfants")
    children = tenant_rows(read_sheet("Enfants"))
    if children.empty: st.info("Aucun enfant actif."); return
    children = children[children.get("Statut", pd.Series("Actif", index=children.index)).astype(str).str.lower() == "actif"]
    opts = {f"{r.get('Nom','')} {r.get('Prenom','')} — {r.get('ID_Enfant','')}": str(r.get("ID_Enfant")) for _, r in children.iterrows()}
    with st.form("attendance_child_form"):
        d = st.date_input("Date", value=date.today())
        selected = st.multiselect("Enfants", list(opts.keys()))
        status = st.selectbox("Statut", ["Présent", "Absent", "Retard", "Absence justifiée", "Sortie anticipée"])
        arrival = st.text_input("Heure d'arrivée (ex. 08:15)")
        departure = st.text_input("Heure de départ (ex. 16:30)")
        comment = st.text_input("Observation")
        ok = st.form_submit_button("Enregistrer les présences", type="primary")
    if ok:
        if not selected: st.warning("Sélectionne au moins un enfant."); return
        for label in selected:
            pid = make_id("PEN")
            save_record("Presences_Enfants", {"ID_Presence": pid, "ID_Creche": tenant_id(), "ID_Enfant": opts[label], "Date": d.isoformat(),
                "Heure_Arrivee": arrival, "Heure_Depart": departure, "Statut_Presence": status,
                "Enregistre_Par": st.session_state["user"]["id_utilisateur"], "Commentaire": comment}, "Présences enfants", "Présence", pid)
        st.success("Présences enregistrées."); st.rerun()
    table_page("Presences_Enfants", "Historique des présences", ["ID_Enfant", "Date", "Statut_Presence"])


def group_form():
    st.subheader("🏷️ Gestion des classes et groupes")
    staff = options_from_sheet("Personnel", "ID_Personnel", ["Nom", "Prenom"])
    with st.form("group_form", clear_on_submit=True):
        name = st.text_input("Nom de la classe / groupe *")
        age_min = st.number_input("Âge minimum (mois)", min_value=0, max_value=120, value=24)
        age_max = st.number_input("Âge maximum (mois)", min_value=0, max_value=120, value=36)
        capacity = st.number_input("Capacité maximale", min_value=1, value=15)
        responsible = st.selectbox("Éducateur / responsable", ["Non affecté"] + list(staff.keys()))
        status = st.selectbox("Statut", ["Actif", "Inactif"])
        ok = st.form_submit_button("Créer le groupe")
    if ok:
        if not name.strip(): st.warning("Le nom du groupe est obligatoire."); return
        gid = make_id("GRP")
        save_record("Groupes", {"ID_Groupe": gid, "ID_Creche": tenant_id(), "Nom_Groupe": name.strip(), "Age_Min_Mois": age_min,
            "Age_Max_Mois": age_max, "Capacite": capacity, "Nom_Responsable": "" if responsible == "Non affecté" else responsible,
            "Statut": status, "Date_Ajout": datetime.now().isoformat(timespec="seconds")}, "Groupes", "Groupe", gid)
        st.success("Groupe créé."); st.rerun()


def staff_form():
    st.subheader("👩‍🏫 Fiche du personnel")
    with st.form("staff_form", clear_on_submit=True):
        a,b = st.columns(2)
        with a:
            nom=st.text_input("Nom *"); prenom=st.text_input("Prénom *"); poste=st.selectbox("Poste", ["Directeur(trice)", "Éducateur(trice)", "Auxiliaire", "Cuisinier(ère)", "Chauffeur", "Agent d'entretien", "Administratif", "Autre"])
            tel=st.text_input("Téléphone"); email=st.text_input("E-mail")
        with b:
            embauche=st.date_input("Date d'embauche", value=date.today()); salaire=st.number_input("Salaire de base mensuel (DA)", min_value=0.0, step=1000.0)
            contrat=st.selectbox("Type de contrat", ["CDI", "CDD", "Temps partiel", "Vacataire", "Autre"]); statut=st.selectbox("Statut", ["Actif", "Inactif"])
        ok=st.form_submit_button("Enregistrer le salarié", type="primary")
    if ok:
        if not nom.strip() or not prenom.strip(): st.warning("Nom et prénom obligatoires."); return
        sid=make_id("PER")
        save_record("Personnel", {"ID_Personnel":sid,"ID_Creche":tenant_id(),"Nom":nom.strip(),"Prenom":prenom.strip(),"Poste":poste,"Telephone":tel,"Email":email,"Date_Embauche":embauche.isoformat(),"Salaire_Base":salaire,"Type_Contrat":contrat,"Statut":statut}, "Personnel", "Personnel", sid)
        st.success("Salarié enregistré."); st.rerun()


def staff_attendance():
    st.subheader("⏱️ Pointage du personnel")
    staff=tenant_rows(read_sheet("Personnel"))
    if staff.empty: st.info("Ajoute d'abord les salariés."); return
    opts={f"{r.get('Nom','')} {r.get('Prenom','')} — {r.get('Poste','')}":str(r.get("ID_Personnel")) for _,r in staff.iterrows() if str(r.get("Statut","Actif")).lower()=="actif"}
    with st.form("staff_attendance_form"):
        d=st.date_input("Date", value=date.today()); selected=st.multiselect("Salariés", list(opts.keys()))
        status=st.selectbox("Statut", ["Présent", "Absent", "Retard", "Congé", "Maladie", "Repos"])
        entry=st.text_input("Heure d'entrée", value="08:00"); exit_=st.text_input("Heure de sortie", value="16:00"); comment=st.text_input("Observation")
        ok=st.form_submit_button("Enregistrer le pointage")
    if ok:
        if not selected: st.warning("Sélectionne au moins un salarié."); return
        for label in selected:
            hours=0.0
            try:
                t1=datetime.strptime(entry,"%H:%M"); t2=datetime.strptime(exit_,"%H:%M"); hours=max(0,(t2-t1).total_seconds()/3600)
            except ValueError: pass
            rid=make_id("PST")
            save_record("Presences_Personnel", {"ID_Presence_Personnel":rid,"ID_Creche":tenant_id(),"ID_Personnel":opts[label],"Date":d.isoformat(),"Heure_Arrivee":entry,"Heure_Depart":exit_,"Statut_Presence":status,"Motif_Absence":comment,"Valide_Par":st.session_state["user"]["id_utilisateur"],"Date_Ajout":datetime.now().isoformat(timespec="seconds")}, "Présences personnel", "Pointage", rid)
        st.success("Pointage enregistré."); st.rerun()
    table_page("Presences_Personnel", "Historique du pointage", ["ID_Personnel", "Date", "Statut_Presence"])


def payroll_page():
    st.subheader("💰 Préparation de la paie")
    staff = tenant_rows(read_sheet("Personnel"))
    pres = tenant_rows(read_sheet("Presences_Personnel"))
    if staff.empty:
        st.info("Aucun salarié."); return
    opts = {f"{r.get('Nom','')} {r.get('Prenom','')} — {r.get('Poste','')}": r for _, r in staff.iterrows()}
    with st.form("payroll_form"):
        person = st.selectbox("Salarié", list(opts.keys()))
        month = st.text_input("Mois de paie (AAAA-MM)", value=date.today().strftime("%Y-%m"))
        bonus = st.number_input("Primes (DA)", min_value=0.0, step=500.0)
        deductions = st.number_input("Retenues (DA)", min_value=0.0, step=500.0)
        days = st.number_input("Jours travaillés à payer", min_value=0.0, max_value=31.0, value=26.0)
        payment_date = st.date_input("Date de paiement", value=date.today())
        payment_mode = st.selectbox("Mode de paiement", ["Virement", "Espèces", "Chèque", "Autre"])
        ok = st.form_submit_button("Calculer et enregistrer la paie", type="primary")
    if ok:
        if len(month) != 7 or month[4:5] != "-":
            st.warning("Saisis le mois au format AAAA-MM."); return
        row = opts[person]
        base = float(row.get("Salaire_Base", 0) or 0)
        month_rows = pres[(pres.get("ID_Personnel", pd.Series(dtype=str)).astype(str) == str(row.get("ID_Personnel"))) & pres.get("Date", pd.Series(dtype=str)).astype(str).str.startswith(month)] if not pres.empty else pd.DataFrame()
        absences = int(month_rows.get("Statut_Presence", pd.Series(dtype=str)).astype(str).str.lower().isin(["absent", "maladie"]).sum()) if not month_rows.empty else 0
        prorata = base * min(float(days), 26.0) / 26.0
        net = max(0, prorata + bonus - deductions)
        sid = make_id("SAL")
        try:
            year, month_num = month.split("-")
            year_num = int(year); month_num = int(month_num)
        except ValueError:
            st.warning("Mois invalide."); return
        save_record("Salaires", {"ID_Salaire": sid, "ID_Creche": tenant_id(), "ID_Personnel": row.get("ID_Personnel"),
            "Mois_Paie": month_num, "Annee_Paie": year_num, "Salaire_Base": base, "Primes": bonus, "Retenues": deductions,
            "Net_A_Payer": net, "Date_Paiement": payment_date.isoformat(), "Mode_Paiement": payment_mode,
            "Reference_Paiement": "", "Statut": "À vérifier", "Valide_Par": "", "Date_Ajout": datetime.now().isoformat(timespec="seconds")}, "Salaires", "Bulletin", sid)
        st.success(f"Paie estimative enregistrée : {net:,.0f} DA. Estimation à valider selon le contrat et les règles applicables."); st.rerun()
    table_page("Salaires", "Historique des salaires", ["ID_Personnel", "Mois_Paie", "Annee_Paie", "Statut"])


def restaurant_meals():
    st.subheader("🍽️ Restaurants et planification des repas")
    tab1,tab2=st.tabs(["Paramétrage restaurant", "Menu / repas"])
    with tab1:
        with st.form("restaurant_form", clear_on_submit=True):
            name=st.text_input("Nom du restaurant / cuisine *"); kind=st.selectbox("Type",["Cuisine interne","Prestataire externe","Salle de restauration"]); capacity=st.number_input("Capacité",min_value=1,value=30); status=st.selectbox("Statut",["Actif","Inactif"])
            ok=st.form_submit_button("Enregistrer le restaurant")
        if ok:
            if not name.strip(): st.warning("Nom obligatoire.")
            else:
                rid=make_id("RST"); save_record("Restaurants",{"ID_Restaurant":rid,"ID_Creche":tenant_id(),"Nom":name,"Type":kind,"Capacite":capacity,"Statut":status},"Restaurants","Restaurant",rid); st.success("Restaurant enregistré."); st.rerun()
        table_page("Restaurants","Restaurants configurés",["Nom","Type"])
    with tab2:
        restaurants=options_from_sheet("Restaurants","ID_Restaurant",["Nom"])
        with st.form("meal_form",clear_on_submit=True):
            d=st.date_input("Date du repas",value=date.today()); service=st.selectbox("Service",["Petit-déjeuner","Déjeuner","Goûter"]); meal=st.text_input("Intitulé du repas *"); desc=st.text_area("Composition / détails"); restaurant=st.selectbox("Restaurant",["Non défini"]+list(restaurants.keys())); age=st.text_input("Groupe d'âge concerné"); allergens=st.text_input("Allergènes à signaler"); status=st.selectbox("Statut",["Prévu","Validé","Servi","Annulé"])
            ok=st.form_submit_button("Enregistrer le repas")
        if ok:
            if not meal.strip(): st.warning("Intitulé obligatoire.")
            else:
                mid=make_id("REP"); save_record("Repas",{"ID_Repas":mid,"ID_Creche":tenant_id(),"Date":d.isoformat(),"Service":service,"Nom_Repas":meal,"Description":desc,"ID_Restaurant":restaurants.get(restaurant,""),"Age_Concerne":age,"Allergenes":allergens,"Statut":status},"Repas","Repas",mid); st.success("Repas enregistré."); st.rerun()
        table_page("Repas","Planning des repas",["Date","Service","Nom_Repas"])


def transport_page():
    st.subheader("🚌 Transport scolaire")
    tab1,tab2=st.tabs(["Lignes et véhicules", "Affectation des enfants"])
    with tab1:
        with st.form("transport_form",clear_on_submit=True):
            name=st.text_input("Nom de la ligne / tournée *"); vehicle=st.text_input("Véhicule / immatriculation"); driver=st.text_input("Chauffeur"); cap=st.number_input("Capacité",min_value=1,value=15); zone=st.text_input("Zone desservie"); status=st.selectbox("Statut",["Actif","Inactif"])
            ok=st.form_submit_button("Enregistrer la ligne")
        if ok:
            if not name.strip(): st.warning("Nom obligatoire.")
            else:
                tid=make_id("TRN"); save_record("Transport",{"ID_Transport":tid,"ID_Creche":tenant_id(),"Nom_Ligne":name,"Vehicule":vehicle,"Chauffeur":driver,"Capacite":cap,"Zone":zone,"Statut":status},"Transport","Ligne",tid); st.success("Ligne enregistrée."); st.rerun()
        table_page("Transport","Lignes de transport",["Nom_Ligne","Chauffeur","Zone"])
    with tab2:
        children=options_from_sheet("Enfants","ID_Enfant",["Nom","Prenom"]); lines=options_from_sheet("Transport","ID_Transport",["Nom_Ligne"])
        with st.form("transport_assign_form",clear_on_submit=True):
            child=st.selectbox("Enfant",list(children.keys()) or ["Aucun"]); line=st.selectbox("Ligne",list(lines.keys()) or ["Aucune"]); start=st.date_input("Date de début",value=date.today()); end=st.date_input("Date de fin",value=None); stop=st.text_input("Arrêt / adresse de prise en charge"); guardian=st.text_input("Personne autorisée à remettre / récupérer l'enfant"); status=st.selectbox("Statut",["Actif","Suspendu","Terminé"])
            ok=st.form_submit_button("Affecter l'enfant")
        if ok:
            if child=="Aucun" or line=="Aucune": st.warning("Choisis un enfant et une ligne.")
            else:
                aid=make_id("AFF"); save_record("Affectations_Transport",{"ID_Affectation":aid,"ID_Creche":tenant_id(),"ID_Enfant":children[child],"ID_Transport":lines[line],"Date_Debut":start.isoformat(),"Date_Fin":"" if end is None else end.isoformat(),"Arret":stop,"Personne_Autorisee":guardian,"Statut":status},"Transport","Affectation",aid); st.success("Affectation enregistrée."); st.rerun()
        table_page("Affectations_Transport","Affectations transport",["ID_Enfant","ID_Transport","Statut"])


def dashboard():
    st.title("📊 Tableau de bord de la crèche")
    children=tenant_rows(read_sheet("Enfants")); parents=tenant_rows(read_sheet("Parents")); staff=tenant_rows(read_sheet("Personnel")); docs=tenant_rows(read_sheet("Documents")); pres=tenant_rows(read_sheet("Presences_Enfants")); invoices=tenant_rows(read_sheet("Factures")); meals=tenant_rows(read_sheet("Repas"))
    today=date.today().isoformat()
    active_children=int(children.get("Statut",pd.Series(dtype=str)).astype(str).str.lower().eq("actif").sum()) if not children.empty else 0
    active_staff=int(staff.get("Statut",pd.Series(dtype=str)).astype(str).str.lower().eq("actif").sum()) if not staff.empty else 0
    present=0
    if not pres.empty:
        todays=pres[pres.get("Date",pd.Series(dtype=str)).astype(str).str[:10]==today]
        present=int(todays.get("Statut_Presence",pd.Series(dtype=str)).astype(str).str.lower().isin(["présent","present","présente","presente"]).sum())
    outstanding=0
    if not invoices.empty and "Solde_Calcule" in invoices: outstanding=pd.to_numeric(invoices["Solde_Calcule"],errors="coerce").fillna(0).sum()
    c1,c2,c3,c4=st.columns(4); c1.metric("Enfants actifs",active_children); c2.metric("Présents aujourd'hui",present); c3.metric("Parents référencés",len(parents)); c4.metric("Personnel actif",active_staff)
    c5,c6=st.columns(2); c5.metric("Impayés (DA)",f"{outstanding:,.0f}".replace(","," "))
    todays_meals=meals[meals.get("Date",pd.Series(dtype=str)).astype(str).str[:10]==today] if not meals.empty else pd.DataFrame(); c6.metric("Repas prévus aujourd'hui",len(todays_meals))
    st.divider(); st.subheader("🚨 Dossiers enfants à compléter")
    required=["Acte de naissance","Fiche de renseignements","Contrat / règlement signé","Carnet de santé","Certificat médical","Vaccinations"]
    incomplete=[]
    for _,child in children.iterrows():
        if str(child.get("Statut","Actif")).lower()=="inactif": continue
        child_docs=docs[(docs.get("Type_Objet",pd.Series(dtype=str)).astype(str)=="Enfant") & (docs.get("ID_Objet",pd.Series(dtype=str)).astype(str)==str(child.get("ID_Enfant")))] if not docs.empty else pd.DataFrame()
        received=set()
        if not child_docs.empty:
            received=set(child_docs.loc[child_docs.get("Statut", pd.Series(dtype=str)).astype(str).isin(["Reçu", "Non applicable"]), "Type_Document"].astype(str))
        missing=[d for d in required if d not in received]
        if missing: incomplete.append({"Enfant":f"{child.get('Nom','')} {child.get('Prenom','')}","Documents manquants":", ".join(missing),"Nombre manquant":len(missing)})
    st.metric("Enfants avec dossier incomplet",len(incomplete))
    if incomplete: st.dataframe(pd.DataFrame(incomplete),use_container_width=True,hide_index=True)
    else: st.success("Tous les dossiers actifs sont complets selon la checklist.")
    st.caption("Les informations médicales sont sensibles : limite les accès aux seuls membres du personnel autorisés. Les calculs de paie sont des estimations à valider selon les contrats et la réglementation applicable.")


# ============================================================
# APPLICATION
# ============================================================
if "user" not in st.session_state:
    login_screen(); st.stop()

try:
    ensure_sheets()
    tenant = read_sheet("Creches")
    tenant = tenant[tenant.get("ID_Creche",pd.Series(dtype=str)).astype(str)==tenant_id()]
    if tenant.empty:
        st.error("Crèche non reconnue. Vérifie ID_Creche dans les secrets et dans la feuille Creches."); st.stop()
except Exception as exc:
    st.error("Impossible de préparer les feuilles Google Sheets. Vérifie les autorisations du compte de service.")
    st.caption(str(exc)); st.stop()

with st.sidebar:
    st.title("🏫 Creche Manager Pro")
    st.caption(f"{st.session_state['user']['nom']} • {st.session_state['user']['role']}")
    menu=st.radio("MENU PRINCIPAL",[
        "Tableau de bord",
        "Fiches enfants", "Inscrire un enfant", "Dossiers administratifs & médicaux",
        "Fiches parents", "Ajouter un parent",
        "Classes & groupes", "Présence des enfants",
        "Personnel", "Ajouter un salarié", "Pointage du personnel", "Paie & salaires",
        "Restaurants & repas", "Transport scolaire",
        "Factures", "Paiements", "Dépenses", "Journal d'activité"
    ])
    if st.button("🔄 Actualiser les données"):
        st.rerun()
    if st.button("Se déconnecter"):
        del st.session_state["user"]; st.rerun()

try:
    if menu=="Tableau de bord": dashboard()
    elif menu=="Fiches enfants": table_page("Enfants","Liste des enfants",["Nom","Prenom","ID_Enfant"])
    elif menu=="Inscrire un enfant": child_form()
    elif menu=="Dossiers administratifs & médicaux": document_center()
    elif menu=="Fiches parents": table_page("Parents","Liste des parents",["Nom","Prenom","Telephone_Principal"])
    elif menu=="Ajouter un parent": parent_form()
    elif menu=="Classes & groupes":
        group_form(); st.divider(); table_page("Groupes","Classes et groupes",["Nom_Groupe","Age_Min_Mois","Age_Max_Mois"])
    elif menu=="Présence des enfants": attendance_children()
    elif menu=="Personnel": table_page("Personnel","Liste du personnel",["Nom","Prenom","Poste"])
    elif menu=="Ajouter un salarié": staff_form()
    elif menu=="Pointage du personnel": staff_attendance()
    elif menu=="Paie & salaires": payroll_page()
    elif menu=="Restaurants & repas": restaurant_meals()
    elif menu=="Transport scolaire": transport_page()
    elif menu=="Factures": table_page("Factures","Factures",["Numero_Facture","ID_Parent","Statut"])
    elif menu=="Paiements": table_page("Paiements","Paiements",["Numero_Recu","ID_Parent","Mode_Paiement"])
    elif menu=="Dépenses": table_page("Depenses","Dépenses",["Libelle","Fournisseur","Date_Depense"])
    elif menu=="Journal d'activité": table_page("Journal_Audit","Journal d'activité",["Module","Action","ID_Objet"])
except Exception as exc:
    st.error("Une erreur est survenue dans ce module. Vérifie les en-têtes Google Sheets et les droits d'accès.")
    st.caption(str(exc))
