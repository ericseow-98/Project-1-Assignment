
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

# --- Page Config ---
st.set_page_config(layout="wide")

# --- 1. Backend Logic ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('sme_salary_benchmarks.csv')
        return df
    except FileNotFoundError:
        st.error("Could not find 'sme_salary_benchmarks.csv'.")
        return pd.DataFrame()

# --- 2. Frontend UI ---
st.title("SME Salary Dashboard")
st.markdown("Use this tool to benchmark salaries against standard market rates in Singapore.")

df = load_data()

#stremlit stops if the dataframe is empty
if df.empty:
    st.stop()

# Search Bar
search_query = st.text_input(
    "Search by Keyword:", 
    placeholder="Type any part of a job title (e.g., 'data', 'software', 'executive')..."
)

st.divider()

# --- 3. Dynamic Results & Filtering ---
if search_query:
    results_df = df[df['title'].str.contains(search_query, case=False, na=False)].copy()
    
    st.sidebar.header("Refine Your Search")
    
    # -- Industry Filter --
    available_industries = ["All"] + sorted(results_df['categories'].unique().tolist())
    selected_industry = st.sidebar.selectbox("Filter by Industry", available_industries)
    
    if selected_industry != "All":
        results_df = results_df[results_df['categories'] == selected_industry]
        
    # -- Expanded Logically Sorted Seniority Filter --
    logical_hierarchy = [
        "Fresh/entry level",
        "Non-executive",
        "Junior Executive",
        "Executive",
        "Senior Executive",
        "Professional",
        "Manager",
        "Middle Management",
        "Senior Management"
    ]
            
    raw_seniorities = results_df['positionLevels'].unique().tolist()
    sorted_seniorities = sorted(
        raw_seniorities, 
        key=lambda x: logical_hierarchy.index(x) if x in logical_hierarchy else 999
    )
    
    available_seniorities = ["All"] + sorted_seniorities
    selected_seniority = st.sidebar.selectbox("Filter by Seniority", available_seniorities)
    
    if selected_seniority != "All":
        results_df = results_df[results_df['positionLevels'] == selected_seniority]

    # -- Expanded Logically Sorted Minimum Year of Experiences --
    # Setup the bins
    bins = [-1, 0, 3, 6, 9, np.inf]
    logical_yoe = ["0", "1 - 3", "4 - 6", "7 - 9", "10 and above"]

    # Create the new column safely
    results_df["grouped_yoe"] = pd.cut(
        results_df["minimumYearsExperience"], bins=bins, labels=logical_yoe
    )
    
    # Dynamically extract categories that are ACTUALLY present in the data
    # .dropna().unique() on a Categorical column returns only the present categories
    present_categories = results_df["grouped_yoe"].dropna().unique()

    # Build the Streamlit Sidebar Selectbox
    available_yoe = ["All"] + logical_yoe
    selected_yoe = st.sidebar.selectbox("Filter by Year of Experiences", available_yoe)

    # Filter the DataFrame cleanly
    if selected_yoe != "All":
        # Explicitly casting to string prevents Categorical/Object type conflicts
        results_df = results_df[results_df["grouped_yoe"].astype(str) == selected_yoe]

    # --- Display Results ---
    if len(results_df) > 0:
        st.subheader(f"Found {len(results_df)} roles matching your criteria")
        
        # --- C. TOP-LEVEL METRICS ---
        abs_min = results_df['Entry_Salary_25th'].min()
        avg_entry = results_df['Entry_Salary_25th'].mean()
        avg_median = results_df['Median_Salary'].mean()
        total_postings = results_df['Total_Postings'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Absolute Lowest (25th)", f"${abs_min:,.0f}")
        with col2:
            st.metric("Avg. Target Entry (25th)", f"${avg_entry:,.0f}")
        with col3:
            st.metric("Avg. Median Market", f"${avg_median:,.0f}")
        with col4:
            st.metric("Total Postings", f"{total_postings:,}")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- A. Formatted Data Table ---
        # Overwrite all column names by assigning a new list of the exact same length directly to display_df.columns
        display_df = results_df[['categories', 'title', 'positionLevels', 'Entry_Salary_25th', 'Median_Salary', 'minimumYearsExperience', 'Total_Postings', 'postedCompany_name']]
        display_df.columns = ['Industry', 'Job Title', 'Seniority', 'Target Entry (25th)', 'Median Market', 'Year of Experiences', 'Total Postings', 'Company Name']
        
        st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Target Entry (25th)": st.column_config.NumberColumn(format="$%d"),
                "Median Market": st.column_config.NumberColumn(format="$%d")
            }
        )
        
        # --- B. PLOTLY VISUALIZATIONS SECTION ---
        st.divider()
        st.subheader("Market Insights")
        
        # MAIN CHART: Salary Comparison
        chart_data_raw = results_df.sort_values(by='Median_Salary', ascending=False).head(15).copy()
        chart_data_raw['Full_Label'] = (
            "[" + chart_data_raw['categories'] + "] " + 
            chart_data_raw['title'] + " (" + chart_data_raw['positionLevels'] + ")"
        )
        melted_df = chart_data_raw.melt(
            id_vars=['Full_Label'],
            value_vars=['Entry_Salary_25th', 'Median_Salary'],
            var_name='Salary Type', value_name='Salary'
        )
        melted_df['Salary Type'] = melted_df['Salary Type'].map({
            'Entry_Salary_25th': 'Target Entry (25th)',
            'Median_Salary': 'Median Market'
        })
        
        fig_main = px.bar(
            melted_df, x='Salary', y='Full_Label', color='Salary Type',
            barmode='group', orientation='h',
            title="Top 15 Salary Ranges for Search (Highest to Lowest)",
            color_discrete_map={'Target Entry (25th)': '#1f77b4', 'Median Market': '#ff7f0e'}
        )
        fig_main.update_layout(yaxis_title=None, xaxis_title="Salary (SGD)", yaxis={'categoryorder': 'total ascending'}, hovermode="y unified", margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_main, use_container_width=True)

        # SUB-CHARTS: Demand and Progression Side-by-Side
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            demand_df = results_df.groupby('categories')['Total_Postings'].sum().reset_index()
            demand_df = demand_df.sort_values(by='Total_Postings', ascending=False).head(7)
            
            fig_donut = px.pie(
                demand_df, 
                values='Total_Postings', 
                names='categories', 
                hole=0.4,
                title="Hiring Demand by Industry (Searched Roles)"
            )
            fig_donut.update_traces(textposition='inside', textinfo='percent+label')
            fig_donut.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig_donut, use_container_width=True)
            
        with chart_col2:
            # CHANGED: We now group on 'df' (the full database) instead of 'results_df'
            progression_df = df.groupby('positionLevels')['Median_Salary'].mean().reset_index()
            
            progression_df['sort_index'] = progression_df['positionLevels'].apply(
                lambda x: logical_hierarchy.index(x) if x in logical_hierarchy else 999
            )
            progression_df = progression_df.sort_values('sort_index')
            
            fig_progression = px.bar(
                progression_df, 
                x='positionLevels', 
                y='Median_Salary', 
                # CHANGED: Updated the title to clarify this is the overall market
                title="Overall Market: Avg Median Salary by Seniority",
                color_discrete_sequence=['#2ca02c'] 
            )
            fig_progression.update_layout(xaxis_title=None, yaxis_title="Avg Median Salary (SGD)",  title_font=dict(size=15), margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig_progression, use_container_width=True)

    else:
        st.warning("No roles match these specific filters. Try setting them back to 'All'.")
        
else:
    st.info("👆 Start typing a keyword in the search bar above to generate market data and visualizations.")
    st.sidebar.info("Search for a job title first to see filter options.")
    st.markdown("#### Database Stats")
    st.metric("Total Roles Benchmarked", len(df['title']))