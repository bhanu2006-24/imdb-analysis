import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.figure_factory as ff

# ---------------------------
# App config
# ---------------------------
st.set_page_config(
    page_title="IMDb Comprehensive Analytics",
    page_icon="🎬",
    layout="wide"
)

# ---------------------------
# Data loading
# ---------------------------
@st.cache_data
def load_data(clean_path: str, cast_path: str, genre_path: str):
    df_clean = pd.read_csv(clean_path)
    df_cast = pd.read_csv(cast_path)
    df_genre = pd.read_csv(genre_path)
    return df_clean, df_cast, df_genre

df_clean, df_cast, df_genre = load_data(
    clean_path="imdb_clean.csv",
    cast_path="imdb_cast_exploded.csv",
    genre_path="imdb_genre_exploded.csv"
)

# ---------------------------
# Column normalization (keep 'metadata' name unchanged)
# ---------------------------
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Preserve 'metadata' if present
    cols = []
    for c in df.columns:
        if c == "metadata":
            cols.append(c)
        else:
            cols.append(
                c.lower().strip()
                 .replace(" ", "_")
                 .replace("\n", "_")
                 .replace("\t", "_")
            )
    df.columns = cols
    return df

df_clean = normalize_columns(df_clean)
df_cast = normalize_columns(df_cast)
df_genre = normalize_columns(df_genre)

# If a variant exists like 'meta_data', rename to 'metadata'
for df_ in [df_clean, df_cast, df_genre]:
    if "meta_data" in df_.columns and "metadata" not in df_.columns:
        df_.rename(columns={"meta_data": "metadata"}, inplace=True)

# Duration fix (rename duration_ -> duration)
for df_ in [df_clean, df_cast, df_genre]:
    if "duration_" in df_.columns and "duration" not in df_.columns:
        df_.rename(columns={"duration_": "duration"}, inplace=True)

# ---------------------------
# Type assurance for numeric fields
# ---------------------------
def coerce_numeric(df: pd.DataFrame, cols: list[str]):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def impute_and_cast(df: pd.DataFrame):
    # Metadata can remain float; duration/year -> int for consistency
    if "metadata" in df.columns:
        df["metadata"] = df["metadata"].fillna(df["metadata"].median())
    if "duration" in df.columns:
        df["duration"] = df["duration"].fillna(df["duration"].median()).astype(int)
    if "year" in df.columns:
        df["year"] = df["year"].fillna(df["year"].median()).astype(int)
    return df

for df_ in [df_clean, df_cast, df_genre]:
    df_ = coerce_numeric(df_, ["metadata", "duration", "year"])
    df_ = impute_and_cast(df_)

# ---------------------------
# Sidebar filters
# ---------------------------
st.sidebar.title("Filters")

# Genre filter uses df_genre for available values
genres_available = sorted([g for g in df_genre["genre"].dropna().unique()]) if "genre" in df_genre.columns else []
genre_filter = st.sidebar.multiselect("Genres", genres_available, default=[])

# Cast filter uses df_cast
cast_available = sorted([c for c in df_cast["cast"].dropna().unique()]) if "cast" in df_cast.columns else []
cast_filter = st.sidebar.multiselect("Cast members", cast_available, default=[])

# Year range (from df_clean)
if "year" in df_clean.columns:
    year_min = int(df_clean["year"].min())
    year_max = int(df_clean["year"].max())
else:
    year_min, year_max = 1900, 2025
year_range = st.sidebar.slider("Year range", year_min, year_max, (year_min, year_max))

# Metadata score range
if "metadata" in df_clean.columns:
    meta_min = int(np.nanmin(df_clean["metadata"]))
    meta_max = int(np.nanmax(df_clean["metadata"]))
else:
    meta_min, meta_max = 0, 100
meta_range = st.sidebar.slider("Metadata range", meta_min, meta_max, (meta_min, meta_max))

# Title linking between exploded and clean
title_col = "title" if "title" in df_clean.columns else None

# Apply filters to movie-level df_clean
df_filtered = df_clean.copy()
if "year" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["year"].between(year_range[0], year_range[1])]
if "metadata" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["metadata"].between(meta_range[0], meta_range[1])]

# Reduce by genre filter (via titles present in df_genre)
if genre_filter and title_col and "genre" in df_genre.columns:
    titles_with_genre = df_genre[df_genre["genre"].isin(genre_filter)][title_col].unique().tolist()
    df_filtered = df_filtered[df_filtered[title_col].isin(titles_with_genre)]

# Reduce by cast filter (via titles present in df_cast)
if cast_filter and title_col and "cast" in df_cast.columns:
    titles_with_cast = df_cast[df_cast["cast"].isin(cast_filter)][title_col].unique().tolist()
    df_filtered = df_filtered[df_filtered[title_col].isin(titles_with_cast)]

st.sidebar.markdown("---")
st.sidebar.write(f"Filtered movies: {len(df_filtered)}")

# Download filtered data
csv_bytes = df_filtered.to_csv(index=False).encode("utf-8")
st.sidebar.download_button("Download filtered CSV", data=csv_bytes, file_name="imdb_filtered.csv", mime="text/csv")

# ---------------------------
# Header
# ---------------------------
st.title("🎬 IMDb Comprehensive Analytics Dashboard")
st.caption("Three-perspective analysis: movie-level (clean), cast-exploded, genre-exploded. All visuals honor the 'metadata' column name.")

# ---------------------------
# Tabs for sections
# ---------------------------
tabs = st.tabs([
    "Overview",
    "Genre analysis",
    "Cast analysis",
    "Yearly trends",
    "Scatter plots",
    "Correlation",
    "Data table"
])

# ---------------------------
# Overview tab
# ---------------------------
with tabs[0]:
    st.subheader("Key metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total movies", len(df_filtered))
    col2.metric("Avg duration (min)", round(df_filtered["duration"].mean(), 1) if "duration" in df_filtered.columns else "-")
    col3.metric("Avg metadata", round(df_filtered["metadata"].mean(), 1) if "metadata" in df_filtered.columns else "-")
    if title_col and "genre" in df_genre.columns:
        unique_titles_in_genre = df_genre[df_genre[title_col].isin(df_filtered[title_col])] if title_col in df_genre.columns else df_genre
        col4.metric("Genres covered", len(unique_titles_in_genre["genre"].unique()))
    else:
        col4.metric("Genres covered", "-")

    st.markdown("### Top genres and actors")
    # Top genres (filtered by titles present)
    if "genre" in df_genre.columns and title_col in df_genre.columns and title_col in df_filtered.columns:
        g_counts = (
            df_genre[df_genre[title_col].isin(df_filtered[title_col])]
            ["genre"].value_counts().head(15)
        )
        fig_g_bar = px.bar(g_counts, x=g_counts.values, y=g_counts.index, orientation="h", title="Top genres (filtered)")
        st.plotly_chart(fig_g_bar, use_container_width=True)

# g_counts is a Series: genre -> count
        g_counts_df = g_counts.reset_index()
        g_counts_df.columns = ["genre", "count"]  # ensure unique names

        fig_g_pie = px.pie(
            g_counts_df,
            values="count",
            names="genre",
            title="Genre distribution"
        )
        st.plotly_chart(fig_g_pie, use_container_width=True)


    # Top cast (filtered by titles present)
    if "cast" in df_cast.columns and title_col in df_cast.columns and title_col in df_filtered.columns:
        c_counts = (
            df_cast[df_cast[title_col].isin(df_filtered[title_col])]
            ["cast"].value_counts().head(15)
        )
        fig_c_bar = px.bar(c_counts, x=c_counts.values, y=c_counts.index, orientation="h", title="Top actors (filtered)")
        st.plotly_chart(fig_c_bar, use_container_width=True)

        c_counts_df = c_counts.reset_index()
        c_counts_df.columns = ["cast", "count"]

        fig_c_pie = px.pie(
            c_counts_df,
            values="count",
            names="cast",
            title="Cast distribution"
        )
        st.plotly_chart(fig_c_pie, use_container_width=True)


# ---------------------------
# Genre analysis tab
# ---------------------------
with tabs[1]:
    st.subheader("Genre analysis")
    if "genre" in df_genre.columns and title_col in df_genre.columns and title_col in df_filtered.columns:
        dfg = df_genre[df_genre[title_col].isin(df_filtered[title_col])].copy()

        # Top genres by frequency
        g_counts = dfg["genre"].value_counts().head(20)
        fig_g_counts = px.bar(g_counts, x=g_counts.values, y=g_counts.index, orientation="h", title="Top genres by count")
        st.plotly_chart(fig_g_counts, use_container_width=True)

        # Average metadata per genre
        if "metadata" in dfg.columns:
            g_scores = dfg.groupby("genre")["metadata"].mean().sort_values(ascending=False).head(20)
            fig_g_scores = px.bar(g_scores, x=g_scores.values, y=g_scores.index, orientation="h", title="Average metadata by genre (top 20)")
            st.plotly_chart(fig_g_scores, use_container_width=True)

        # Boxplots for duration and metadata by genre
        top_genres = dfg["genre"].value_counts().head(12).index
        dfg_top = dfg[dfg["genre"].isin(top_genres)]
        if "duration" in dfg_top.columns:
            fig_box_dur = px.box(dfg_top, x="genre", y="duration", title="Duration distribution by genre (top 12)")
            st.plotly_chart(fig_box_dur, use_container_width=True)
        if "metadata" in dfg_top.columns:
            fig_box_meta = px.box(dfg_top, x="genre", y="metadata", title="Metadata distribution by genre (top 12)")
            st.plotly_chart(fig_box_meta, use_container_width=True)
    

        # Genre trend over years
        if "year" in df_clean.columns:

            # Map movie-level year to each genre row via title
            df_year_genre = dfg_top.merge(
                df_clean[[title_col, "year"]],
                on=title_col,
                how="left"
            ) if title_col and title_col in df_clean.columns else dfg_top
            df_year_genre = df_genre.merge(
                df_clean[[title_col, "year"]],
                on=title_col,
                how="left"
            )

            # Fix duplicate year columns
            if "year_x" in df_year_genre.columns and "year_y" in df_year_genre.columns:
                # Prefer the one from df_clean (year_y), or coalesce
                df_year_genre["year"] = df_year_genre["year_y"].fillna(df_year_genre["year_x"])
                df_year_genre = df_year_genre.drop(columns=["year_x", "year_y"])
            elif "year_x" in df_year_genre.columns:
                df_year_genre = df_year_genre.rename(columns={"year_x": "year"})
            elif "year_y" in df_year_genre.columns:
                df_year_genre = df_year_genre.rename(columns={"year_y": "year"})

            # Now safe to dropna
            df_year_genre = df_year_genre.dropna(subset=["year"])

            pivot = df_year_genre.pivot_table(index="year", columns="genre", values=title_col, aggfunc="count").fillna(0)
            fig_heat = px.imshow(pivot.T, aspect="auto", color_continuous_scale="Viridis", title="Genre popularity over years (count)")
            st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Genre or title columns missing for genre analysis.")

# ---------------------------
# Cast analysis tab
# ---------------------------
# ---------------------------
# Cast analysis tab
# ---------------------------
with tabs[2]:
    st.subheader("Cast analysis")
    if "cast" in df_cast.columns and title_col in df_cast.columns and title_col in df_filtered.columns:
        dfc = df_cast[df_cast[title_col].isin(df_filtered[title_col])].copy()

        # Top actors by frequency
        c_counts = dfc["cast"].value_counts().head(20)
        fig_c_counts = px.bar(c_counts, x=c_counts.values, y=c_counts.index,
                              orientation="h", title="Top actors by count")
        st.plotly_chart(fig_c_counts, use_container_width=True)

        # Average metadata by actor
        if "metadata" in dfc.columns:
            c_scores = dfc.groupby("cast")["metadata"].mean().sort_values(ascending=False).head(20)
            fig_c_scores = px.bar(c_scores, x=c_scores.values, y=c_scores.index,
                                  orientation="h", title="Average metadata by actor (top 20)")
            st.plotly_chart(fig_c_scores, use_container_width=True)

        # Boxplot metadata by actor (top 15 frequent)
        top_actors = dfc["cast"].value_counts().head(15).index
        dfc_top = dfc[dfc["cast"].isin(top_actors)]
        if "metadata" in dfc_top.columns:
            fig_box_meta_actor = px.box(dfc_top, x="cast", y="metadata",
                                        title="Metadata distribution by actor (top 15)")
            st.plotly_chart(fig_box_meta_actor, use_container_width=True)

        # Actor trend over years (count of appearances)
        if title_col and "year" in df_clean.columns:
            df_year_cast = dfc_top.merge(df_clean[[title_col, "year"]], on=title_col, how="left")

            # unify year_x/year_y
            if "year_x" in df_year_cast.columns and "year_y" in df_year_cast.columns:
                df_year_cast["year"] = df_year_cast["year_y"].fillna(df_year_cast["year_x"])
                df_year_cast = df_year_cast.drop(columns=["year_x", "year_y"])
            elif "year_x" in df_year_cast.columns:
                df_year_cast = df_year_cast.rename(columns={"year_x": "year"})
            elif "year_y" in df_year_cast.columns:
                df_year_cast = df_year_cast.rename(columns={"year_y": "year"})

            if "year" in df_year_cast.columns:
                df_year_cast = df_year_cast.dropna(subset=["year"])
                count_by_year = df_year_cast.groupby(["year", "cast"]).size().reset_index(name="appearances")
                fig_line_cast = px.line(count_by_year, x="year", y="appearances", color="cast",
                                        title="Actor appearances over years (top 15)", markers=True)
                st.plotly_chart(fig_line_cast, use_container_width=True)
    else:
        st.info("Cast or title columns missing for cast analysis.")


# ---------------------------
# Yearly trends tab
# ---------------------------

# ---------------------------
# Yearly trends tab
# ---------------------------
with tabs[3]:
    st.subheader("Yearly trends (movie-level)")
    if "year" in df_filtered.columns:
        # Count per year
        yearly_count = df_filtered.groupby("year").size().reset_index(name="count")
        fig_count = px.line(yearly_count, x="year", y="count",
                            title="Movies per year", markers=True)
        st.plotly_chart(fig_count, use_container_width=True)

        # Avg duration per year
        if "duration" in df_filtered.columns:
            yearly_dur = df_filtered.groupby("year")["duration"].mean().reset_index()
            fig_dur = px.line(yearly_dur, x="year", y="duration",
                              title="Average duration per year", markers=True)
            st.plotly_chart(fig_dur, use_container_width=True)

        # Avg metadata per year
        if "metadata" in df_filtered.columns:
            yearly_meta = df_filtered.groupby("year")["metadata"].mean().reset_index()
            fig_meta = px.line(yearly_meta, x="year", y="metadata",
                               title="Average metadata per year", markers=True)
            st.plotly_chart(fig_meta, use_container_width=True)

        # Genre popularity heatmap over years (count)
        if "genre" in df_genre.columns and title_col in df_genre.columns and title_col in df_clean.columns:
            df_year_genre = df_genre.merge(df_clean[[title_col, "year"]],
                                           on=title_col, how="left")

            # unify year_x/year_y
            if "year_x" in df_year_genre.columns and "year_y" in df_year_genre.columns:
                df_year_genre["year"] = df_year_genre["year_y"].fillna(df_year_genre["year_x"])
                df_year_genre = df_year_genre.drop(columns=["year_x", "year_y"])
            elif "year_x" in df_year_genre.columns:
                df_year_genre = df_year_genre.rename(columns={"year_x": "year"})
            elif "year_y" in df_year_genre.columns:
                df_year_genre = df_year_genre.rename(columns={"year_y": "year"})

            if "year" in df_year_genre.columns:
                df_year_genre = df_year_genre.dropna(subset=["year"])
                pivot = df_year_genre.pivot_table(index="year", columns="genre",
                                                  values=title_col, aggfunc="count").fillna(0)
                fig_heatmap_yearly = px.imshow(
                    pivot.T,
                    aspect="auto",
                    color_continuous_scale="Viridis",
                    title="Genre popularity over years (count)"
                )
                st.plotly_chart(fig_heatmap_yearly, use_container_width=True, key="heatmap_yearly")
    else:
        st.info("Year column missing in movie-level dataset.")

# ---------------------------
# Scatter plots tab
# ---------------------------
with tabs[4]:
    st.subheader("Scatter plots (movie-level)")
    if {"metadata", "duration"}.issubset(df_filtered.columns):
        fig_scatter1 = px.scatter(df_filtered, x="duration", y="metadata",
                                  color="year" if "year" in df_filtered.columns else None,
                                  title="Metadata vs Duration", hover_data=[title_col] if title_col else None)
        st.plotly_chart(fig_scatter1, use_container_width=True)

    if {"metadata", "year"}.issubset(df_filtered.columns):
        fig_scatter2 = px.scatter(df_filtered, x="year", y="metadata",
                                  color="duration" if "duration" in df_filtered.columns else None,
                                  title="Metadata vs Year", hover_data=[title_col] if title_col else None)
        st.plotly_chart(fig_scatter2, use_container_width=True)

    if {"duration", "year"}.issubset(df_filtered.columns):
        fig_scatter3 = px.scatter(df_filtered, x="year", y="duration",
                                  color="metadata" if "metadata" in df_filtered.columns else None,
                                  title="Duration vs Year", hover_data=[title_col] if title_col else None)
        st.plotly_chart(fig_scatter3, use_container_width=True)

# ---------------------------
# Correlation tab
# ---------------------------
with tabs[5]:
    st.subheader("Correlation analysis (movie-level)")
    num_cols = [c for c in ["metadata", "duration", "year"] if c in df_filtered.columns]
    if len(num_cols) >= 2:
        corr = df_filtered[num_cols].corr()
        fig_corr_heatmap = ff.create_annotated_heatmap(
            z=corr.values,
            x=num_cols,
            y=num_cols,
            colorscale="Viridis",
            showscale=True
        )
        fig_corr_heatmap.update_layout(title="Correlation heatmap")
        st.plotly_chart(fig_corr_heatmap, use_container_width=True)
    else:
        st.info("Insufficient numeric columns for correlation.")

# ---------------------------
# Data table tab
# ---------------------------
with tabs[6]:
    st.subheader("Filtered data")
    st.dataframe(df_filtered, use_container_width=True, height=600)

    st.markdown("#### Export")
    st.download_button(
        label="Download filtered CSV",
        data=df_filtered.to_csv(index=False).encode("utf-8"),
        file_name="imdb_filtered.csv",
        mime="text/csv"
    )
