import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px

st.set_page_config(page_title="Digital Decay Dashboard", layout="wide")

st.title("Digital Decay and Web Link Status Dashboard")
st.write("---")

def load_dashboard_data():
    conn = duckdb.connect('web_decay_dw.db', read_only=True)
    fact_links = conn.execute("SELECT * FROM fact_link_status").fetchdf()
    dim_domains = conn.execute("SELECT * FROM dim_domain").fetchdf()
    conn.close()
    return fact_links, dim_domains

try:
    fact_links, dim_domains = load_dashboard_data()

    total_checks = len(fact_links)
    dead_links = fact_links['is_dead'].sum()
    decay_rate = (dead_links / total_checks * 100) if total_checks > 0 else 0
    avg_latency = fact_links['response_time_ms'].mean() if total_checks > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Total Links Scanned", value=total_checks)
    col2.metric(label="Dead Links Identified", value=int(dead_links), delta=f"{decay_rate:.1f}% Decay Rate", delta_color="inverse")
    col3.metric(label="Average Server Latency", value=f"{int(avg_latency)} ms")
    col4.metric(label="Unique Domains Monitored", value=len(dim_domains))

    st.write("---")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("HTTP Response Code Distribution")
        status_counts = fact_links['http_status_code'].value_counts().reset_index()
        status_counts.columns = ['Status Code', 'Count']
        status_counts['Status Code'] = status_counts['Status Code'].astype(str).replace('0', 'Timeout/Error')
        fig_pie = px.pie(status_counts, values='Count', names='Status Code', color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig_pie, width='stretch')

    with chart_col2:
        st.subheader("Latency Profile by Extension")
        merged_df = fact_links.merge(dim_domains, on='domain_hash', how='inner')
        tld_latency = merged_df.groupby('top_level_domain')['response_time_ms'].mean().reset_index()
        tld_latency.columns = ['Extension', 'Avg Latency (ms)']
        fig_bar = px.bar(tld_latency, x='Extension', y='Avg Latency (ms)', text_auto='.0f')
        st.plotly_chart(fig_bar, width='stretch')

    st.write("---")
    st.subheader("High-Risk / Broken Domains Tracker")

    merged_df = fact_links.merge(dim_domains, on='domain_hash', how='inner')
    domain_summary = merged_df.groupby('domain_name').agg(
        total_pings=('check_id', 'count'),
        failures=('is_dead', 'sum'),
        avg_speed_ms=('response_time_ms', 'mean')
    ).reset_index()

    domain_summary['failure_rate'] = (domain_summary['failures'] / domain_summary['total_pings'] * 100).round(1)
    rotten_domains = domain_summary.sort_values(by='failure_rate', ascending=False)

    st.dataframe(
        rotten_domains[['domain_name', 'total_pings', 'failures', 'failure_rate', 'avg_speed_ms']],
        column_config={
            "domain_name": "Domain Website",
            "total_pings": "Scans Conducted",
            "failures": "Dead Events",
            "failure_rate": st.column_config.ProgressColumn("Failure Rate", format="%f%%", min_value=0, max_value=100),
            "avg_speed_ms": "Avg Latency (ms)"
        },
        width='stretch',
        hide_index=True
    )

except Exception as e:
    st.info("Please run the ingestion pipeline script first to generate the local database file.")
    st.caption(f"Error context: {e}")
