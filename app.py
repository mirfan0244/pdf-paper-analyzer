import os
import pandas as pd
import streamlit as st
import altair as alt

from pdf_to_md import (
    extract_pdf_text,
    build_extraction_prompt,
    parse_llm_response,
    save_markdown,
    load_all_metadata,
)
from llm_client import get_client, extract_metadata, chat_with_data
from chart_generator import (
    year_distribution,
    count_by_field,
    generate_mermaid_author_network,
    author_cooccurrence,
    generate_mermaid_ontology,
    build_keyword_cooccurrence,
)

PDF_DIR = "pdfs"
MD_DIR = "md_output"

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(MD_DIR, exist_ok=True)

st.set_page_config(page_title="PDF Paper Analyzer", layout="wide")
st.title("PDF Paper Analyzer")

with st.sidebar:
    provider = st.selectbox("LLM Provider", ["Gemini", "Ollama", "OpenAI"])
    user_schema = st.text_area(
        "Metadata Schema",
        value="""{
  "title": "",
  "authors": [],
  "year": "",
  "research_field": "",
  "methodology": "",
  "keywords": [],
  "summary": ""
}""",
        height=180,
    )

client, model = get_client(provider)

if "history" not in st.session_state:
    st.session_state.history = []

tab1, tab2, tab3, tab4 = st.tabs([
    "Extract",
    "Metadata Table",
    "Charts & Ontology",
    "Q&A"
])

with tab1:
    st.header("PDF → Markdown Extraction")

    pdf_files = sorted(
        [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    )
    md_files = sorted(
        [f for f in os.listdir(MD_DIR) if f.lower().endswith(".md")]
    )

    pending_pdfs = [
        f for f in pdf_files
        if f.replace(".pdf", ".md") not in md_files
    ]

    st.subheader("Files")
    if not pdf_files:
        st.info("No PDFs found in pdfs/ folder.")
    else:
        for pdf_name in pdf_files:
            md_name = pdf_name.replace(".pdf", ".md")
            status = "✅ Extracted" if md_name in md_files else "⏳ Pending"
            st.markdown(f"- `{pdf_name}` — {status}")

    st.write(f"Total PDFs: {len(pdf_files)}")
    st.write(f"Pending extraction: {len(pending_pdfs)}")

    if st.button("🚀 Extract All Pending"):
        if not pending_pdfs:
            st.success("No pending PDFs to extract.")
        else:
            progress = st.progress(0)
            status_box = st.empty()

            for i, pdf_name in enumerate(pending_pdfs):
                status_box.write(f"Extracting: {pdf_name}")

                raw_text = extract_pdf_text(os.path.join(PDF_DIR, pdf_name))
                prompt = build_extraction_prompt(raw_text, user_schema)
                response = extract_metadata(client, model, raw_text, prompt)

                metadata, body = parse_llm_response(response)

                if "_parse_error" in metadata:
                    st.warning(f"Skipping {pdf_name} due to JSON parse error.")
                    st.code(response[:3000])
                else:
                    save_markdown(MD_DIR, pdf_name, metadata, body)

                progress.progress((i + 1) / len(pending_pdfs))

            st.success("Extraction completed.")
            st.rerun()

all_meta = load_all_metadata(MD_DIR)

with tab2:
    st.header("Metadata Table")

    if not all_meta:
        st.info("No metadata found yet. Extract PDFs first.")
    else:
        df = pd.DataFrame(all_meta)
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "📥 Download CSV",
            df.to_csv(index=False),
            file_name="metadata.csv",
            mime="text/csv",
        )

with tab3:
    st.header("Charts & Ontology")

    if not all_meta:
        st.info("No metadata available yet.")
    else:
        year_data = year_distribution(all_meta)
        if year_data:
            df_year = pd.DataFrame(year_data.items(), columns=["Year", "Count"])
            df_year["Year"] = df_year["Year"].astype(str)
            chart = alt.Chart(df_year).mark_bar().encode(
                y=alt.Y("Year:N", sort="-x"),
                x="Count:Q"
            )
            st.subheader("Year Distribution")
            st.altair_chart(chart, use_container_width=True)

        st.subheader("Author Collaboration Network")
        author_mermaid = generate_mermaid_author_network(all_meta)
        st.code(author_mermaid, language="mermaid")

        author_data = author_cooccurrence(all_meta)
        if author_data["counts"]:
            st.dataframe(
                pd.DataFrame(
                    author_data["counts"].items(),
                    columns=["Author", "Papers"]
                ),
                use_container_width=True,
            )

        for field, label in [
            ("research_field", "Field"),
            ("methodology", "Method")
        ]:
            data = count_by_field(all_meta, field)
            if data:
                df_field = pd.DataFrame(data.items(), columns=[label, "Count"])
                chart = alt.Chart(df_field).mark_bar().encode(
                    y=alt.Y(f"{label}:N", sort="-x"),
                    x="Count:Q"
                )
                st.subheader(f"{label} Distribution")
                st.altair_chart(chart, use_container_width=True)

        st.subheader("Knowledge Ontology")
        st.code(generate_mermaid_ontology(all_meta), language="mermaid")

        st.subheader("Keyword Co-occurrence")
        keyword_pairs = build_keyword_cooccurrence(all_meta)
        if keyword_pairs:
            st.dataframe(pd.DataFrame(keyword_pairs), use_container_width=True)
        else:
            st.info("No keyword co-occurrence data found.")

with tab4:
    st.header("Q&A")

    if not all_meta:
        st.info("Extract some papers first.")
    else:
        context = "\n\n".join(
            f"### {m.get('title', 'Untitled')}\n" +
            "\n".join(f"- **{k}**: {v}" for k, v in m.items())
            for m in all_meta
        )

        quick_prompts = {
            "📊 Trend Analysis": "Analyze the temporal trends across these papers and mention specific paper titles.",
            "🔍 Common Themes": "What common themes appear across these papers? Mention specific paper titles.",
            "⚡ Research Gaps": "Identify 3 to 5 research gaps based on these papers and cite specific titles.",
            "🔀 Cross-Pollination": "Find unexpected connections between papers from different methods or fields."
        }

        cols = st.columns(2)
        quick_clicked = None
        labels = list(quick_prompts.keys())

        for i, label in enumerate(labels):
            if cols[i % 2].button(label):
                quick_clicked = quick_prompts[label]

        for msg in st.session_state.history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if quick_clicked:
            st.session_state.history.append({
                "role": "user",
                "content": quick_clicked
            })

            with st.chat_message("user"):
                st.markdown(quick_clicked)

            with st.chat_message("assistant"):
                placeholder = st.empty()
                full_response = ""

                stream = chat_with_data(
                    client,
                    model,
                    context,
                    quick_clicked,
                    st.session_state.history[:-1]
                )

                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        full_response += delta.content
                        placeholder.markdown(full_response)

            st.session_state.history.append({
                "role": "assistant",
                "content": full_response
            })

        if prompt := st.chat_input("Ask about your papers..."):
            st.session_state.history.append({
                "role": "user",
                "content": prompt
            })

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                placeholder = st.empty()
                full_response = ""

                stream = chat_with_data(
                    client,
                    model,
                    context,
                    prompt,
                    st.session_state.history[:-1]
                )

                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        full_response += delta.content
                        placeholder.markdown(full_response)

            st.session_state.history.append({
                "role": "assistant",
                "content": full_response
            })