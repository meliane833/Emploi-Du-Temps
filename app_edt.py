import streamlit as st
import pandas as pd
import random
from datetime import datetime
import io
from io import BytesIO
import base64
import zipfile
import json
import streamlit as st

# PROTECTION PAR MOT DE PASSE
def check_password():
    """Retourne True si l'utilisateur a le bon mot de passe."""
    def password_entered():
        """Vérifie si le mot de passe est correct."""
        if st.session_state["password"] == "0035":  # ← Changez ce mot de passe !
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Ne pas stocker le mot de passe
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Premier affichage, afficher le champ de mot de passe.
        st.text_input(
            "🔒 Mot de passe", type="password", on_change=password_entered, key="password"
        )
        st.write("*Veuillez contacter l'administrateur pour obtenir l'accès*")
        return False
    elif not st.session_state["password_correct"]:
        # Mot de passe incorrect, afficher à nouveau le champ + erreur.
        st.text_input(
            "🔒 Mot de passe", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Mot de passe incorrect")
        return False
    else:
        # Mot de passe correct.
        return True

if not check_password():
    st.stop()  # Arrête l'exécution si mauvais mot de passe

# Configuration des heures de cours par matière et par niveau selon vos spécifications
MATIERES_HEURES = {
    "6ème": {
        "FRANÇAIS": 5,
        "MATHÉMATIQUES": 4,
        "ANGLAIS": 3,
        "EPS": 2,
        "HISTOIRE-GÉOGRAPHIE": 2,
        "SVT": 1.5,
        "PHYSIQUE-CHIMIE": 1.5,
        "INFORMATIQUE": 1,
        "EDHC": 1,
        "MUSIQUE": 1,  # Classes paires
        "ART_PLASTIQUE": 1  # Classes impaires
    },
    "5ème": {
        "FRANÇAIS": 5,
        "MATHÉMATIQUES": 4,
        "ANGLAIS": 3,
        "EPS": 2,
        "HISTOIRE-GÉOGRAPHIE": 3,
        "SVT": 2,
        "PHYSIQUE-CHIMIE": 2,
        "INFORMATIQUE": 1,
        "EDHC": 1,
        "MUSIQUE": 1,  # Classes paires
        "ART_PLASTIQUE": 1  # Classes impaires
    },
    "4ème": {
        "FRANÇAIS": 6,
        "MATHÉMATIQUES": 4,
        "ANGLAIS": 3,
        "EPS": 2,
        "HISTOIRE-GÉOGRAPHIE": 4,
        "SVT": 2,
        "PHYSIQUE-CHIMIE": 2,
        "INFORMATIQUE": 1,
        "EDHC": 1,
        "ALLEMAND": 3,  # Classes paires
        "ESPAGNOL": 3,  # Classes impaires
        "MUSIQUE": 1,   # Classes paires
        "ART_PLASTIQUE": 1  # Classes impaires
    },
    "3ème": {
        "FRANÇAIS": 6,
        "MATHÉMATIQUES": 4,
        "ANGLAIS": 3,
        "EPS": 2,
        "HISTOIRE-GÉOGRAPHIE": 4,
        "SVT": 2,
        "PHYSIQUE-CHIMIE": 2,
        "INFORMATIQUE": 1,
        "EDHC": 1,
        "ALLEMAND": 3,  # Classes paires
        "ESPAGNOL": 3,  # Classes impaires
        "MUSIQUE": 1,   # Classes paires
        "ART_PLASTIQUE": 1  # Classes impaires
    }
}

# Créneaux horaires disponibles (en heures de 55 minutes)
HORAIRES = [
    ("07:30", "08:25"),
    ("08:25", "09:20"),
    ("09:20", "10:15"),
    ("10:15", "10:30"),  # Récréation (bloqué)
    ("10:30", "11:25"),
    ("11:25", "12:20"),
    ("12:20", "13:30"),  # Pause déjeuner (bloqué)
    ("13:30", "14:25"),
    ("14:25", "15:20"),
    ("15:20", "15:35"),  # Récréation (bloqué)
    ("15:35", "16:30"),
    ("16:30", "17:25")
]

JOURS = ["LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI"]

MAX_HEURES_PAR_PROF = 21  # limite 21h par semaine
MAX_MATIERES_PAR_JOUR = 3  # Maximum 3 matières différentes par jour
BLOQUE_INDICES = (3, 6, 9)  # indices à ne pas utiliser (récréations / pause)

class GenerateurEmploiDuTemps:
    def __init__(self):
        # Initialise correctement les attributs
        self.professeurs = []
        self.classes = []
        self.emplois_du_temps_profs = {}
        self.emplois_du_temps_classes = {}
        self.affectations_matieres = {}  # {classe: {matiere: prof}}
        self.prof_load = {}  # {prof_nom: heures_assignees}
        self.matieres_par_jour = {}  # {classe: {jour: set(matières)}}

    def est_classe_paire(self, classe):
        """Détermine si une classe est paire ou impaire."""
        try:
            numero = int(classe.rsplit(" ", 1)[1])
            return numero % 2 == 0
        except Exception:
            return False

    def get_matieres_par_classe(self, classe):
        """Retourne les matières spécifiques à une classe (langues/arts)"""
        try:
            niveau = classe.rsplit(" ", 1)[0]
            matieres = MATIERES_HEURES[niveau].copy()
        except Exception:
            return {}

        if self.est_classe_paire(classe):
            matieres.pop("ART_PLASTIQUE", None)
            matieres.pop("ESPAGNOL", None)
        else:
            matieres.pop("MUSIQUE", None)
            matieres.pop("ALLEMAND", None)

        return matieres

    def ajouter_professeur(self, nom, matieres):
        """Ajoute un professeur avec ses matières"""
        professeur = {
            "nom": nom,
            "matieres": matieres,
            "classes_assignees": {}  # {classe: [matières]}
        }
        self.professeurs.append(professeur)
        self.emplois_du_temps_profs[nom] = self.creer_edt_vide()
        self.prof_load[nom] = 0
        return professeur

    def creer_classes(self, classes_par_niveau):
        """Crée les classes selon la configuration"""
        self.classes = []
        for niveau, nombre in classes_par_niveau.items():
            for i in range(1, nombre + 1):
                classe = f"{niveau} {i}"
                self.classes.append(classe)
                self.emplois_du_temps_classes[classe] = self.creer_edt_vide()
                # Initialiser le suivi des matières par jour
                self.matieres_par_jour[classe] = {jour: set() for jour in JOURS}
        return self.classes

    def creer_edt_vide(self):
        """Crée un emploi du temps vide"""
        edt = {}
        for jour in JOURS:
            edt[jour] = ["" for _ in HORAIRES]
        return edt

    def assigner_matieres_aux_professeurs(self):
        """Assigner les matières aux professeurs en équilibrant la charge"""
        self.affectations_matieres = {}
        for prof in self.professeurs:
            prof["classes_assignees"] = {}
            self.prof_load[prof["nom"]] = 0

        for classe in self.classes:
            matieres_classe = self.get_matieres_par_classe(classe)
            self.affectations_matieres[classe] = {}

            for matiere, heures in sorted(matieres_classe.items(), key=lambda x: -x[1]):
                heures_entieres = int(round(heures))
                profs_candidates = [p for p in self.professeurs if matiere in p["matieres"] and self.prof_load[p["nom"]] + heures_entieres <= MAX_HEURES_PAR_PROF]

                if not profs_candidates:
                    profs_candidates = [p for p in self.professeurs if matiere in p["matieres"]]

                if not profs_candidates:
                    st.warning(f"⚠ Aucun professeur trouvé pour {matiere} en {classe}")
                    continue

                profs_candidates.sort(key=lambda p: self.prof_load[p["nom"]])
                professeur = profs_candidates[0]

                if classe not in professeur["classes_assignees"]:
                    professeur["classes_assignees"][classe] = []
                professeur["classes_assignees"][classe].append(matiere)
                self.affectations_matieres[classe][matiere] = professeur["nom"]
                self.prof_load[professeur["nom"]] += heures_entieres

    def peut_ajouter_matiere(self, classe, jour, matiere):
        """Vérifie si on peut ajouter une matière ce jour sans dépasser la limite"""
        matieres_ce_jour = self.matieres_par_jour[classe][jour]
        if matiere in matieres_ce_jour:
            return True  # La matière est déjà présente ce jour
        return len(matieres_ce_jour) < MAX_MATIERES_PAR_JOUR

    def ajouter_matiere_jour(self, classe, jour, matiere):
        """Ajoute une matière au compteur du jour"""
        self.matieres_par_jour[classe][jour].add(matiere)

    def trouver_meilleur_placement(self, classe, matiere, prof, heures_necessaires):
        """Trouve le meilleur placement pour éviter les trous"""
        meilleur_score = -1
        meilleur_placement = None
        
        for jour in JOURS:
            # Vérifier si on peut ajouter cette matière ce jour
            if not self.peut_ajouter_matiere(classe, jour, matiere):
                continue
                
            # Vérifier si le prof a déjà cette matière ce jour
            if self.prof_a_matiere_ce_jour(prof, matiere, classe, jour):
                continue
                
            # Essayer tous les créneaux possibles
            for start in range(0, len(HORAIRES) - heures_necessaires + 1):
                indices = list(range(start, start + heures_necessaires))
                
                # Vérifier la validité du créneau
                if any(idx in BLOQUE_INDICES for idx in indices):
                    continue
                if not all(self.creneau_libre_prof(prof, jour, idx) for idx in indices):
                    continue
                if not all(self.creneau_libre_classe(classe, jour, idx) for idx in indices):
                    continue
                
                # Calculer le score de ce placement (plus c'est compact, mieux c'est)
                score = self.calculer_score_placement(classe, jour, indices)
                
                if score > meilleur_score:
                    meilleur_score = score
                    meilleur_placement = (jour, start, indices)
        
        return meilleur_placement

    def prof_a_matiere_ce_jour(self, prof, matiere, classe, jour):
        """Vérifie si le prof a déjà cette matière avec cette classe ce jour"""
        edt_prof = self.emplois_du_temps_profs[prof]
        for creneau in edt_prof[jour]:
            if creneau != "" and classe in creneau and matiere in creneau:
                return True
        return False

    def calculer_score_placement(self, classe, jour, indices_proposes):
        """Calcule un score pour évaluer la qualité du placement"""
        score = 0
        edt_classe = self.emplois_du_temps_classes[classe][jour]
        
        # Compter les créneaux déjà occupés ce jour
        creneaux_occupes = [i for i, cell in enumerate(edt_classe) if cell != ""]
        
        if not creneaux_occupes:
            # Si pas de cours ce jour, favoriser le matin
            score += 10 - min(indices_proposes)
        else:
            # Vérifier la contiguïté
            tous_indices = sorted(set(creneaux_occupes + indices_proposes))
            est_contigu = (max(tous_indices) - min(tous_indices) + 1 == len(tous_indices))
            
            if est_contigu:
                score += 50  # Bonus important pour la contiguïté
            else:
                # Pénalité pour les trous
                trous = self.compter_trous(tous_indices)
                score -= trous * 10
        
        # Bonus pour les blocs du matin
        if max(indices_proposes) < 6:  # Avant la pause déjeuner
            score += 20
        
        return score

    def compter_trous(self, indices):
        """Compte le nombre de trous dans une séquence d'indices"""
        if len(indices) <= 1:
            return 0
        trous = 0
        for i in range(1, len(indices)):
            if indices[i] - indices[i-1] > 1:
                trous += 1
        return trous

    def placer_cours_compact(self, classe, matiere, prof, heures_totales):
        """Place les cours de manière compacte sans trous"""
        heures_restantes = int(round(heures_totales))
        
        while heures_restantes > 0:
            # Essayer d'abord un bloc de 2h si possible
            bloc_size = 2 if heures_restantes >= 2 else 1
            
            placement = self.trouver_meilleur_placement(classe, matiere, prof, bloc_size)
            
            if placement:
                jour, start, indices = placement
                # Placer le bloc
                for idx in indices:
                    self.emplois_du_temps_profs[prof][jour][idx] = f"{classe} {matiere}"
                    self.emplois_du_temps_classes[classe][jour][idx] = f"{matiere} - {prof}"
                # Mettre à jour le compteur de matières
                self.ajouter_matiere_jour(classe, jour, matiere)
                self.prof_load[prof] += bloc_size
                heures_restantes -= bloc_size
            else:
                # Si pas de placement optimal, essayer avec relaxation des contraintes
                if not self.placer_cours_force(classe, matiere, prof, bloc_size):
                    st.warning(f"⚠ Impossible de placer {bloc_size}h de {matiere} pour {classe} avec {prof}")
                    heures_restantes -= bloc_size

    def placer_cours_force(self, classe, matiere, prof, bloc_size):
        """Force le placement d'un cours quand aucun placement optimal n'est trouvé"""
        for jour in JOURS:
            # Vérifier la limite de matières même en placement forcé
            if not self.peut_ajouter_matiere(classe, jour, matiere):
                continue
                
            if self.prof_a_matiere_ce_jour(prof, matiere, classe, jour):
                continue
                
            for start in range(0, len(HORAIRES) - bloc_size + 1):
                indices = list(range(start, start + bloc_size))
                
                if any(idx in BLOQUE_INDICES for idx in indices):
                    continue
                if not all(self.creneau_libre_prof(prof, jour, idx) for idx in indices):
                    continue
                if not all(self.creneau_libre_classe(classe, jour, idx) for idx in indices):
                    continue
                
                # Placement forcé
                for idx in indices:
                    self.emplois_du_temps_profs[prof][jour][idx] = f"{classe} {matiere}"
                    self.emplois_du_temps_classes[classe][jour][idx] = f"{matiere} - {prof}"
                # Mettre à jour le compteur de matières
                self.ajouter_matiere_jour(classe, jour, matiere)
                self.prof_load[prof] += bloc_size
                return True
        return False

    def generer_emplois_du_temps(self):
        """Génère automatiquement tous les emplois du temps"""
        # Réinitialiser tous les EDT
        for nom in list(self.emplois_du_temps_profs.keys()):
            self.emplois_du_temps_profs[nom] = self.creer_edt_vide()
        for classe in list(self.emplois_du_temps_classes.keys()):
            self.emplois_du_temps_classes[classe] = self.creer_edt_vide()
        # Réinitialiser le compteur de matières par jour
        for classe in self.matieres_par_jour:
            for jour in JOURS:
                self.matieres_par_jour[classe][jour] = set()

        for nom in self.prof_load:
            self.prof_load[nom] = 0

        # Trier les matières par heures pour placer d'abord les plus lourdes
        toutes_affectations = []
        for prof in self.professeurs:
            for classe, matieres in prof["classes_assignees"].items():
                for matiere in matieres:
                    heures = self.get_matieres_par_classe(classe).get(matiere, 0)
                    if heures > 0:
                        toutes_affectations.append((prof["nom"], classe, matiere, heures))
        
        # Trier par heures décroissantes
        toutes_affectations.sort(key=lambda x: -x[3])
        
        # Placer les cours
        for prof_nom, classe, matiere, heures in toutes_affectations:
            self.placer_cours_compact(classe, matiere, prof_nom, heures)

    def creneau_libre_prof(self, nom_prof, jour, creneau):
        """Vérifie si un créneau est libre pour un professeur"""
        return self.emplois_du_temps_profs.get(nom_prof, {}).get(jour, [""]*len(HORAIRES))[creneau] == ""

    def creneau_libre_classe(self, classe, jour, creneau):
        """Vérifie si un créneau est libre pour une classe"""
        return self.emplois_du_temps_classes.get(classe, {}).get(jour, [""]*len(HORAIRES))[creneau] == ""

    def to_dict(self):
        """Convertit l'état du générateur en dictionnaire pour la sauvegarde"""
        return {
            'professeurs': self.professeurs,
            'classes': self.classes,
            'emplois_du_temps_profs': self.emplois_du_temps_profs,
            'emplois_du_temps_classes': self.emplois_du_temps_classes,
            'affectations_matieres': self.affectations_matieres,
            'prof_load': self.prof_load,
            'matieres_par_jour': {classe: {jour: list(matieres) for jour, matieres in jours.items()} 
                                 for classe, jours in self.matieres_par_jour.items()}
        }

    def from_dict(self, data):
        """Charge l'état du générateur depuis un dictionnaire"""
        self.professeurs = data.get('professeurs', [])
        self.classes = data.get('classes', [])
        self.emplois_du_temps_profs = data.get('emplois_du_temps_profs', {})
        self.emplois_du_temps_classes = data.get('emplois_du_temps_classes', {})
        self.affectations_matieres = data.get('affectations_matieres', {})
        self.prof_load = data.get('prof_load', {})
        
        # Reconstruire les sets pour matieres_par_jour
        self.matieres_par_jour = {}
        matieres_data = data.get('matieres_par_jour', {})
        for classe, jours in matieres_data.items():
            self.matieres_par_jour[classe] = {}
            for jour, matieres_list in jours.items():
                self.matieres_par_jour[classe][jour] = set(matieres_list)

# Fonctions d'export Excel
def exporter_edt_professeur_excel(edt, nom_prof):
    """Exporte l'emploi du temps d'un professeur en format Excel"""
    data = []
    for i, (debut, fin) in enumerate(HORAIRES):
        row = {"HORAIRES": f"{debut} - {fin}"}
        for jour in JOURS:
            row[jour] = edt[jour][i]
        data.append(row)
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Emploi du Temps', index=False)
        worksheet = writer.sheets['Emploi du Temps']
        worksheet.column_dimensions['A'].width = 15
        for col in ['B', 'C', 'D', 'E', 'F']:
            worksheet.column_dimensions[col].width = 25
    
    output.seek(0)
    return output

def exporter_edt_classe_excel(edt, classe):
    """Exporte l'emploi du temps d'une classe en format Excel"""
    data = []
    for i, (debut, fin) in enumerate(HORAIRES):
        row = {"HORAIRES": f"{debut} - {fin}"}
        for jour in JOURS:
            row[jour] = edt[jour][i]
        data.append(row)
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Emploi du Temps', index=False)
        worksheet = writer.sheets['Emploi du Temps']
        worksheet.column_dimensions['A'].width = 15
        for col in ['B', 'C', 'D', 'E', 'F']:
            worksheet.column_dimensions[col].width = 25
    
    output.seek(0)
    return output

def exporter_tous_edt_zip(generateur):
    """Exporte tous les emplois du temps dans un fichier ZIP"""
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        # Exporter tous les professeurs
        for prof in generateur.professeurs:
            nom_prof = prof["nom"]
            edt = generateur.emplois_du_temps_profs[nom_prof]
            fichier_excel = exporter_edt_professeur_excel(edt, nom_prof)
            zip_file.writestr(f"EDT de {nom_prof}.xlsx", fichier_excel.getvalue())
        
        # Exporter toutes les classes
        for classe in generateur.classes:
            edt = generateur.emplois_du_temps_classes[classe]
            fichier_excel = exporter_edt_classe_excel(edt, classe)
            zip_file.writestr(f"EDT de {classe}.xlsx", fichier_excel.getvalue())
    
    zip_buffer.seek(0)
    return zip_buffer

def afficher_edt_professeur(edt, nom_prof):
    """Affiche l'emploi du temps d'un professeur avec option d'export Excel"""
    st.subheader(f"📅 Emploi du Temps - {nom_prof}")

    data = []
    for i, (debut, fin) in enumerate(HORAIRES):
        row = {"HORAIRES": f"{debut} - {fin}"}
        for jour in JOURS:
            row[jour] = edt[jour][i]
        data.append(row)

    df = pd.DataFrame(data)
    st.dataframe(df, width='stretch', height=400)
    
    # Bouton d'export Excel individuel
    fichier_excel = exporter_edt_professeur_excel(edt, nom_prof)
    nom_fichier = f"EDT de {nom_prof}.xlsx"
    
    st.download_button(
        label="📥 Télécharger CET EDT en Excel",
        data=fichier_excel,
        file_name=nom_fichier,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

def afficher_edt_classe(edt, classe):
    """Affiche l'emploi du temps d'une classe avec option d'export Excel"""
    st.subheader(f"📅 Emploi du Temps - {classe}")

    data = []
    for i, (debut, fin) in enumerate(HORAIRES):
        row = {"HORAIRES": f"{debut} - {fin}"}
        for jour in JOURS:
            row[jour] = edt[jour][i]
        data.append(row)

    df = pd.DataFrame(data)
    st.dataframe(df, width='stretch', height=400)
    
    # Bouton d'export Excel individuel
    fichier_excel = exporter_edt_classe_excel(edt, classe)
    nom_fichier = f"EDT de {classe}.xlsx"
    
    st.download_button(
        label="📥 Télécharger CET EDT en Excel",
        data=fichier_excel,
        file_name=nom_fichier,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

def main():
    st.set_page_config(page_title="Générateur Automatique d'EDT", layout="wide")
    st.title("🎯 Générateur Automatique d'Emplois du Temps")
    
    # Initialisation avec sauvegarde automatique
    if 'generateur' not in st.session_state:
        st.session_state.generateur = GenerateurEmploiDuTemps()
        st.session_state.professeurs_ajoutes = []
        st.session_state.classes_creees = False
        st.session_state.edt_generes = False
        st.session_state.active_tab = "Gestion"
        
        # Charger les données sauvegardées si elles existent
        if 'sauvegarde_edt' in st.session_state:
            try:
                st.session_state.generateur.from_dict(st.session_state.sauvegarde_edt)
                st.session_state.professeurs_ajoutes = st.session_state.generateur.professeurs
                st.session_state.classes_creees = len(st.session_state.generateur.classes) > 0
                st.session_state.edt_generes = len(st.session_state.generateur.emplois_du_temps_profs) > 0
            except:
                pass

    generateur = st.session_state.generateur
    
    # Fonction pour sauvegarder l'état
    def sauvegarder_etat():
        st.session_state.sauvegarde_edt = generateur.to_dict()

    with st.sidebar:
        st.header("📋 Navigation")
        
        onglets = {
            "⚙ Gestion": "Gestion",
            "👨‍🏫 EDT Professeurs": "Professeurs", 
            "🏫 EDT Classes": "Classes"
        }
        
        onglet_selectionne = st.radio(
            "Sélectionnez une section:",
            options=list(onglets.keys()),
            index=list(onglets.keys()).index("⚙ Gestion") if st.session_state.active_tab == "Gestion" else 
                   list(onglets.keys()).index("👨‍🏫 EDT Professeurs") if st.session_state.active_tab == "Professeurs" else 
                   list(onglets.keys()).index("🏫 EDT Classes")
        )
        
        st.session_state.active_tab = onglets[onglet_selectionne]
        
        # --- IMPORT EXCEL DANS LA SIDEBAR ---
        st.divider()
        st.header("📥 Import Excel")
        
        fichier_excel = st.file_uploader(
            "Importer des professeurs",
            type=["xlsx"],
            key="file_uploader_sidebar",
            help="Fichier Excel avec colonnes 'Nom' et 'Matières'"
        )
        
        if fichier_excel is not None:
            if st.button("🚀 Importer les Professeurs", use_container_width=True, type="primary"):
                try:
                    with st.spinner("📖 Lecture du fichier Excel..."):
                        df = pd.read_excel(fichier_excel)
                    
                    if 'Nom' not in df.columns or 'Matières' not in df.columns:
                        st.error("❌ Le fichier doit contenir les colonnes 'Nom' et 'Matières'")
                    else:
                        nouveaux_profs = 0
                        with st.spinner("👨‍🏫 Ajout des professeurs..."):
                            for _, row in df.iterrows():
                                nom = str(row['Nom']).strip()
                                if nom:
                                    matieres = [m.strip() for m in str(row['Matières']).split(",") if m.strip()]
                                    if matieres:
                                        if not any(p["nom"] == nom for p in st.session_state.professeurs_ajoutes):
                                            prof = generateur.ajouter_professeur(nom, matieres)
                                            st.session_state.professeurs_ajoutes.append(prof)
                                            nouveaux_profs += 1
                        
                        if nouveaux_profs > 0:
                            st.success(f"✅ {nouveaux_profs} nouveaux professeurs importés!")
                            sauvegarder_etat()
                            st.rerun()
                        else:
                            st.info("ℹ️ Aucun nouveau professeur à importer")
                except Exception as e:
                    st.error(f"❌ Erreur lors de la lecture du fichier: {str(e)}")
        
        # --- BOUTON EXPORT GLOBAL ---
        st.divider()
        st.header("📤 Export Global")
        
        if st.session_state.edt_generes:
            if st.button("📦 Télécharger TOUS les EDT", 
                        use_container_width=True, 
                        type="primary",
                        help="Télécharge tous les emplois du temps en un seul fichier ZIP"):
                
                with st.spinner("🔄 Préparation de l'archive..."):
                    zip_file = exporter_tous_edt_zip(generateur)
                    
                st.download_button(
                    label="💾 Télécharger l'archive ZIP",
                    data=zip_file,
                    file_name="Tous_les_emplois_du_temps.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        else:
            st.info("👆 Générer d'abord les EDT pour exporter")
        
        # --- STATUT ---
        st.divider()
        st.metric("👨‍🏫 Professeurs", len(st.session_state.professeurs_ajoutes))
        st.metric("🏫 Classes créées", "Oui" if st.session_state.classes_creees else "Non")
        st.metric("📅 EDT Générés", "Oui" if st.session_state.edt_generes else "Non")

    # --- CONTENU PRINCIPAL ---
    if st.session_state.active_tab == "Gestion":
        st.header("⚙ Gestion de l'Établissement")

        st.subheader("Classes par Niveau")
        classes_par_niveau = {}
        col1, col2 = st.columns(2)
        with col1:
            classes_par_niveau["6ème"] = st.number_input("6ème", min_value=1, max_value=10, value=4, key="nb_6eme")
            classes_par_niveau["5ème"] = st.number_input("5ème", min_value=1, max_value=10, value=4, key="nb_5eme")
        with col2:
            classes_par_niveau["4ème"] = st.number_input("4ème", min_value=1, max_value=10, value=4, key="nb_4eme")
            classes_par_niveau["3ème"] = st.number_input("3ème", min_value=1, max_value=10, value=4, key="nb_3eme")

        if st.button("🏫 Créer les Classes", key="creer_classes"):
            classes = generateur.creer_classes(classes_par_niveau)
            st.session_state.classes_creees = True
            st.success(f"✅ {len(classes)} classes créées!")
            sauvegarder_etat()

        if st.session_state.classes_creees:
            st.subheader("👨‍🏫 Gestion des Professeurs")
            
            with st.form("ajout_professeur"):
                st.write("### Ajouter un Professeur Manuellement")
                col1, col2 = st.columns(2)
                with col1:
                    nom_prof = st.text_input("Nom du Professeur", "KOUASSI JEAN", key="nom_prof")
                with col2:
                    toutes_matieres = list({matiere for niveau in MATIERES_HEURES.values() for matiere in niveau.keys()})
                    matieres = st.multiselect(
                        "Matière(s) enseignée(s)",
                        toutes_matieres,
                        default=["MATHÉMATIQUES"],
                        key="matieres_prof"
                    )
                if st.form_submit_button("➕ Ajouter le Professeur", use_container_width=True):
                    if nom_prof and matieres:
                        if any(p["nom"] == nom_prof for p in st.session_state.professeurs_ajoutes):
                            st.error("❌ Ce professeur existe déjà!")
                        else:
                            prof = generateur.ajouter_professeur(nom_prof, matieres)
                            st.session_state.professeurs_ajoutes.append(prof)
                            st.success(f"✅ Professeur {nom_prof} ajouté!")
                            sauvegarder_etat()
                    else:
                        st.error("❌ Veuillez remplir tous les champs!")

            if st.session_state.professeurs_ajoutes:
                st.subheader("📋 Liste des Professeurs")
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Total : {len(st.session_state.professeurs_ajoutes)} professeurs**")
                with col2:
                    if st.button("🗑️ Vider la liste", type="secondary", use_container_width=True):
                        st.session_state.professeurs_ajoutes = []
                        generateur.professeurs = []
                        generateur.emplois_du_temps_profs = {}
                        generateur.prof_load = {}
                        st.success("✅ Liste des professeurs vidée!")
                        sauvegarder_etat()
                        st.rerun()
                
                for i, prof in enumerate(st.session_state.professeurs_ajoutes):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"**{prof['nom']}** - Matières: {', '.join(prof['matieres'])}")
                    with col2:
                        if st.button("❌", key=f"del_{i}", help="Supprimer ce professeur"):
                            st.session_state.professeurs_ajoutes.pop(i)
                            generateur.professeurs = [p for p in generateur.professeurs if p["nom"] != prof["nom"]]
                            if prof["nom"] in generateur.emplois_du_temps_profs:
                                del generateur.emplois_du_temps_profs[prof["nom"]]
                            if prof["nom"] in generateur.prof_load:
                                del generateur.prof_load[prof["nom"]]
                            st.success(f"✅ Professeur {prof['nom']} supprimé!")
                            sauvegarder_etat()
                            st.rerun()

            st.divider()
            if st.button("🎯 Générer les Emplois du Temps", 
                        type="primary", 
                        use_container_width=True,
                        disabled=not st.session_state.professeurs_ajoutes):
                
                if not st.session_state.professeurs_ajoutes:
                    st.warning("⚠ Veuillez d'abord ajouter des professeurs.")
                else:
                    with st.spinner("🔄 Attribution des matières aux professeurs..."):
                        generateur.assigner_matieres_aux_professeurs()
                    
                    with st.spinner("🔄 Génération des emplois du temps..."):
                        generateur.generer_emplois_du_temps()
                    
                    st.session_state.edt_generes = True
                    st.session_state.active_tab = "Professeurs"
                    st.success("✅ Emplois du temps générés!")
                    sauvegarder_etat()
                    st.rerun()

    elif st.session_state.active_tab == "Professeurs":
        if st.session_state.edt_generes:
            st.header("📅 Emplois du Temps - Professeurs")
            professeur_selectionne = st.selectbox(
                "Choisir un professeur:",
                [p["nom"] for p in st.session_state.professeurs_ajoutes],
                key="select_prof"
            )
            if professeur_selectionne:
                afficher_edt_professeur(
                    generateur.emplois_du_temps_profs[professeur_selectionne],
                    professeur_selectionne
                )
        else:
            st.info("👈 Générer d'abord les emplois du temps dans l'onglet Gestion")

    elif st.session_state.active_tab == "Classes":
        if st.session_state.edt_generes:
            st.header("📅 Emplois du Temps - Classes")
            classe_selectionnee = st.selectbox(
                "Choisir une classe :",
                generateur.classes,
                key="select_classe"
            )
            if classe_selectionnee:
                afficher_edt_classe(
                    generateur.emplois_du_temps_classes[classe_selectionnee],
                    classe_selectionnee
                )
        else:
            st.info("👈 Générer d'abord les emplois du temps dans l'onglet Gestion")

if __name__ == "__main__":

    main()
