import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(
    page_title="Dashboard Ventes Pharmacie",
    layout="wide",
)

st.title("💊 Dashboard Ventes Pharmacie")
st.markdown("Analyse des ventes par opérateur, produit, période, mois et années multiples.")


# -----------------------------
# FONCTION DE CHARGEMENT
# -----------------------------
@st.cache_data
def load_data(files) -> pd.DataFrame:
    """
    Prend un ou plusieurs fichiers Excel et renvoie un seul DataFrame fusionné.
    """
    if not isinstance(files, list):
        files = [files]

    df_list = []

    for f in files:
        tmp = pd.read_excel(f)

        # garder le nom du fichier comme info
        tmp["source_file"] = getattr(f, "name", "inconnu")

        # Supprimer les colonnes "Unnamed"
        tmp = tmp.loc[:, ~tmp.columns.str.contains("^Unnamed")]

        # Normaliser les noms de colonnes
        col_map = {}
        for col in tmp.columns:
            col_norm = col.lower().strip()

            if "produit" in col_norm and "nom" in col_norm:
                col_map[col] = "produit"
            elif "prix ttc" in col_norm:
                col_map[col] = "prix_ttc"
            elif "montant ttc" in col_norm:
                col_map[col] = "montant_ttc"
            elif col_norm.startswith("qt"):
                col_map[col] = "quantite"
            elif "client" in col_norm:
                col_map[col] = "client"
            elif "opérateur" in col_norm or "operateur" in col_norm:
                col_map[col] = "operateur"
            elif "date" == col_norm:
                col_map[col] = "date"
            elif "code13" in col_norm or "réf" in col_norm or "ref" in col_norm:
                col_map[col] = "code"

        tmp = tmp.rename(columns=col_map)

        # Conversion des types
        if "date" in tmp.columns:
            tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
            tmp["jour"] = tmp["date"].dt.date
            tmp["mois"] = tmp["date"].dt.to_period("M").astype(str)
            tmp["annee"] = tmp["date"].dt.year
            tmp["jour_semaine"] = tmp["date"].dt.day_name()
        else:
            tmp["jour"] = np.nan
            tmp["mois"] = np.nan
            tmp["annee"] = np.nan
            tmp["jour_semaine"] = np.nan

        if "quantite" in tmp.columns:
            tmp["quantite"] = pd.to_numeric(tmp["quantite"], errors="coerce").fillna(0)
        else:
            tmp["quantite"] = 1

        if "montant_ttc" in tmp.columns:
            tmp["montant_ttc"] = pd.to_numeric(tmp["montant_ttc"], errors="coerce").fillna(0)
        elif "prix_ttc" in tmp.columns:
            # fallback : Montant = Prix * Quantité
            tmp["prix_ttc"] = pd.to_numeric(tmp["prix_ttc"], errors="coerce").fillna(0)
            tmp["montant_ttc"] = tmp["prix_ttc"] * tmp["quantite"]
        else:
            tmp["montant_ttc"] = 0

        # Nettoyer le nom de produit / opérateur
        if "produit" in tmp.columns:
            tmp["produit"] = tmp["produit"].astype(str).str.strip()
        if "operateur" in tmp.columns:
            tmp["operateur"] = tmp["operateur"].astype(str).str.strip()

        df_list.append(tmp)

    # Fusionner tous les mois / fichiers
    if df_list:
        df = pd.concat(df_list, ignore_index=True)
    else:
        df = pd.DataFrame()

    return df


# -----------------------------
# UPLOAD MULTI-FICHIERS
# -----------------------------
st.sidebar.header("📂 Données")

uploaded_files = st.sidebar.file_uploader(
    "Choisis un ou plusieurs fichiers Excel de ventes (mois différents, années différentes)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    help="Tu peux sélectionner tous les fichiers (ex : août à novembre 2025, puis ajouter d'autres années).",
)

if not uploaded_files:
    st.info(
        "Charge un ou plusieurs fichiers de ventes au format Excel (.xlsx / .xls) via le panneau de gauche."
    )
    st.stop()

df = load_data(uploaded_files)

# Aperçu
with st.expander("Voir un aperçu des données brutes fusionnées"):
    st.dataframe(df.head())
    st.write(f"Nombre total de lignes : {len(df)}")
    if "source_file" in df.columns:
        st.write("Fichiers chargés :", df["source_file"].unique())


# -----------------------------
# FILTRES
# -----------------------------
st.sidebar.header("🎚️ Filtres")

# Filtre opérateur
if "operateur" in df.columns:
    all_ops = sorted([op for op in df["operateur"].dropna().unique()])
    selected_ops = st.sidebar.multiselect(
        "Opérateur(s)",
        options=all_ops,
        default=all_ops,
    )
else:
    selected_ops = []
    st.sidebar.warning("Colonne 'Opérateur' non trouvée. Filtre désactivé.")

# Filtre années
if "annee" in df.columns and df["annee"].notna().any():
    all_years = sorted(df["annee"].dropna().unique())
    selected_years = st.sidebar.multiselect(
        "Année(s)",
        options=all_years,
        default=all_years,
    )
else:
    selected_years = None

# Filtre mois (au format AAAA-MM)
if "mois" in df.columns and df["mois"].notna().any():
    all_months = sorted(df["mois"].dropna().unique())
    selected_months = st.sidebar.multiselect(
        "Mois (AAAA-MM)",
        options=all_months,
        default=all_months,
    )
else:
    selected_months = None

# Filtre dates précis (range)
if "date" in df.columns and df["date"].notna().any():
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    date_range = st.sidebar.date_input(
        "Période (dates précises)",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date
else:
    start_date = end_date = None
    st.sidebar.warning("Colonne 'Date' non trouvée. Filtre période désactivé.")

# Filtre texte produit
text_filter = st.sidebar.text_input(
    "Filtre produit (contient...)",
    value="",
    placeholder="ex : PARACETAMOL",
)

# -----------------------------
# APPLICATION DES FILTRES
# -----------------------------
df_filtre = df.copy()

if "operateur" in df_filtre.columns and selected_ops:
    df_filtre = df_filtre[df_filtre["operateur"].isin(selected_ops)]

if selected_years is not None and len(selected_years) > 0 and "annee" in df_filtre.columns:
    df_filtre = df_filtre[df_filtre["annee"].isin(selected_years)]

if selected_months is not None and len(selected_months) > 0 and "mois" in df_filtre.columns:
    df_filtre = df_filtre[df_filtre["mois"].isin(selected_months)]

if start_date is not None and end_date is not None and "date" in df_filtre.columns:
    mask_dates = (df_filtre["date"].dt.date >= start_date) & (
        df_filtre["date"].dt.date <= end_date
    )
    df_filtre = df_filtre[mask_dates]

if text_filter:
    if "produit" in df_filtre.columns:
        df_filtre = df_filtre[
            df_filtre["produit"].str.contains(text_filter, case=False, na=False)
        ]

# Sécurité : si vide
if df_filtre.empty:
    st.warning("Aucune donnée ne correspond aux filtres sélectionnés.")
    st.stop()

# -----------------------------
# KPIs
# -----------------------------
ca_total = df_filtre["montant_ttc"].sum()
quantite_totale = df_filtre["quantite"].sum()
nb_lignes = len(df_filtre)

nb_jours_actifs = df_filtre["jour"].nunique() if "jour" in df_filtre.columns else 0
ca_moy_jour = ca_total / nb_jours_actifs if nb_jours_actifs > 0 else 0
montant_moy_ligne = df_filtre["montant_ttc"].mean()

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("CA total (TTC)", f"{ca_total:,.0f}")
col2.metric("Quantité totale vendue", f"{quantite_totale:,.0f}")
col3.metric("Nombre de lignes de vente", f"{nb_lignes}")
col4.metric("CA moyen par jour", f"{ca_moy_jour:,.0f}")
col5.metric("Montant moyen par ligne", f"{montant_moy_ligne:,.0f}")

st.markdown("---")

# -----------------------------
# TABS : VUE GLOBALE / PRODUITS / OPÉRATEURS / TABLEAU
# -----------------------------
tab_global, tab_produits, tab_ops, tab_table = st.tabs(
    ["📈 Vue globale", "📦 Produits", "🧑‍💼 Opérateurs", "📋 Données détaillées"]
)

# --- TAB GLOBAL ---
with tab_global:
    st.subheader("Évolution du CA par jour")

    if "jour" in df_filtre.columns:
        ca_par_jour = (
            df_filtre.groupby("jour", as_index=False)["montant_ttc"].sum()
        )
        ca_par_jour = ca_par_jour.sort_values("jour")
        ca_par_jour = ca_par_jour.set_index("jour")

        st.line_chart(ca_par_jour["montant_ttc"])
    else:
        st.info("Aucune information de date disponible pour tracer l'évolution.")

# --- TAB PRODUITS ---
with tab_produits:
    st.subheader("Top produits par CA")

    if "produit" in df_filtre.columns:
        top_n = st.slider("Nombre de produits à afficher", 5, 30, 10)
        top_produits = (
            df_filtre.groupby("produit", as_index=False)
            .agg(
                CA=("montant_ttc", "sum"),
                Qté=("quantite", "sum"),
                Lignes=("montant_ttc", "count"),
            )
            .sort_values("CA", ascending=False)
            .head(top_n)
        )

        st.bar_chart(
            top_produits.set_index("produit")["CA"],
        )

        st.markdown("### Détail Top produits")
        st.dataframe(top_produits)
    else:
        st.info("Colonne 'produit' introuvable.")

# --- TAB OPÉRATEURS ---
with tab_ops:
    st.subheader("CA par opérateur")

    if "operateur" in df_filtre.columns:
        ca_par_op = (
            df_filtre.groupby("operateur", as_index=False)["montant_ttc"].sum()
            .rename(columns={"montant_ttc": "CA"})
            .sort_values("CA", ascending=False)
        )

        st.bar_chart(
            ca_par_op.set_index("operateur")["CA"],
        )

        st.markdown("### Détail CA par opérateur")
        st.dataframe(ca_par_op)
    else:
        st.info("Colonne 'Opérateur' introuvable.")

# --- TAB TABLEAU DÉTAILLÉ ---
with tab_table:
    st.subheader("Données détaillées (après filtres)")
    st.dataframe(df_filtre)

    # ✅ Correction du TypeError : on passe par un buffer BytesIO
    buffer = BytesIO()
    df_filtre.to_excel(buffer, index=False)
    buffer.seek(0)

    st.download_button(
        label="📥 Télécharger les données filtrées (Excel)",
        data=buffer,
        file_name="ventes_filtrees.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
