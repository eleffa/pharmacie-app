import streamlit as st
import pandas as pd
import numpy as np

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(
    page_title="Dashboard Ventes Pharmacie",
    layout="wide",
)

st.title("💊 Dashboard Ventes Pharmacie")
st.markdown("Analyse des ventes par opérateur, produit et période.")


# -----------------------------
# FONCTION DE CHARGEMENT
# -----------------------------
@st.cache_data
def load_data(file) -> pd.DataFrame:
    df = pd.read_excel(file)

    # Supprimer les colonnes "Unnamed"
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # Normaliser les noms de colonnes
    col_map = {}
    for col in df.columns:
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

    df = df.rename(columns=col_map)

    # Conversion des types
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["jour"] = df["date"].dt.date
        df["mois"] = df["date"].dt.to_period("M").astype(str)
        df["jour_semaine"] = df["date"].dt.day_name()
    else:
        df["jour"] = np.nan
        df["mois"] = np.nan
        df["jour_semaine"] = np.nan

    if "quantite" in df.columns:
        df["quantite"] = pd.to_numeric(df["quantite"], errors="coerce").fillna(0)
    else:
        df["quantite"] = 1

    if "montant_ttc" in df.columns:
        df["montant_ttc"] = pd.to_numeric(df["montant_ttc"], errors="coerce").fillna(0)
    elif "prix_ttc" in df.columns:
        # fallback : Montant = Prix * Quantité
        df["prix_ttc"] = pd.to_numeric(df["prix_ttc"], errors="coerce").fillna(0)
        df["montant_ttc"] = df["prix_ttc"] * df["quantite"]
    else:
        df["montant_ttc"] = 0

    # Nettoyer le nom de produit / opérateur
    if "produit" in df.columns:
        df["produit"] = df["produit"].astype(str).str.strip()
    if "operateur" in df.columns:
        df["operateur"] = df["operateur"].astype(str).str.strip()

    return df


# -----------------------------
# UPLOAD OU FICHIER LOCAL
# -----------------------------
st.sidebar.header("📂 Données")

uploaded_file = st.sidebar.file_uploader(
    "Choisis un fichier Excel de ventes",
    type=["xlsx", "xls"],
    help="Par exemple : Ventes Août2 2025.xlsx",
)

if uploaded_file is None:
    st.info(
        "Charge ton fichier de ventes au format Excel (.xlsx) via le panneau de gauche."
    )
    st.stop()

df = load_data(uploaded_file)

# Affichage rapide des colonnes détectées
with st.expander("Voir un aperçu des données brutes"):
    st.dataframe(df.head())

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
        default=all_ops,  # tu peux mettre ici un nom précis si tu te focalises sur une personne
    )
else:
    selected_ops = []
    st.sidebar.warning("Colonne 'Opérateur' non trouvée. Filtre désactivé.")

# Filtre dates
if "date" in df.columns and df["date"].notna().any():
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    date_range = st.sidebar.date_input(
        "Période",
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

nb_jours_actifs = df_filtre["jour"].nunique()
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
    st.download_button(
        label="📥 Télécharger les données filtrées (Excel)",
        data=df_filtre.to_excel(index=False, engine="openpyxl"),
        file_name="ventes_filtrees.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
