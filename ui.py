import streamlit as st
import requests

# ── CONFIG (MUST BE FIRST) ─────────────────────────────
st.set_page_config(
    page_title="CrossDoc QA",
    layout="wide"
)
if "corpus_built" not in st.session_state:
    st.session_state.corpus_built = False

if "history" not in st.session_state:
    st.session_state.history = []
st.markdown("""
<style>

/* Hide entire top header */
[data-testid="stHeader"] {
    display: none;
}

/* Adjust top spacing after removing header */
.block-container {
    padding-top: 0.5rem;
}

</style>
""", unsafe_allow_html=True)

# ── TITLE ──────────────────────────────────────────────
st.title("CrossDoc Research Assistant")

col1, col2, col3 = st.columns(3)

col1.metric("LLM", "Mistral 7B")
col2.metric("Retriever", "BM25+FAISS")
col3.metric("Embeddings", "MiniLM")
st.caption(
    "Domain-Specific Research QA System | "
    "Local LLM + Retrieval + Citations"
)
with st.sidebar:

    st.title("⚙ System Panel")

    st.info("""
    **Research Pipeline**

    • Semantic Retrieval

    • Local LLM (Mistral 7B)

    • Citation Validation

    • Corpus Governance

    • Evidence Grounding
    """)

    with st.expander("Instructions"):

        st.markdown("""
        1. Use precise research topics.

        2. Build corpus before querying.

        3. Use American English.

        4. Answers are grounded in approved corpus.
        """)

tab1, tab2 = st.tabs(
    ["Research Assistant",
     "System Overview"]
)

# ── BUILD CORPUS ───────────────────────────────────────
with tab1:
    with st.container(border=True):

        st.subheader("Build Research Corpus")

        topic = st.text_input(
            "Research Topic",
        )

        if st.button("Build Corpus"):
            if not topic.strip():
                st.warning("Enter a topic first")
            else:
                with st.spinner("Fetching and building corpus..."):
                    try:
                        res = requests.post(
                            "http://localhost:8001/explore",
                            json={"topic": topic}
                        ).json()

                        if res["status"] == "completed":
                            st.success(f"Corpus built with {res['approved_count']} papers")
                            st.session_state.corpus_built = True
                        else:
                            st.error("Exploration failed")

                    except Exception as e:
                        st.error(f"Error: {e}")

    # ── QUERY SYSTEM ───────────────────────────────────────

    with st.container(border=True):

        st.subheader("Ask Questions")

        query = st.text_area("Enter your question")

        if st.button("Run Query"):

            if not st.session_state.corpus_built:
                st.warning("Build corpus first")

            elif not query.strip():
                st.warning("Enter a question")

            else:
                with st.status(
                        "Executing Research Pipeline...",
                        expanded=True) as status:

                    st.write("Searching approved corpus")
                    st.write("Retrieving semantic evidence")
                    st.write("Building evidence context")
                    st.write("Running Mistral inference")
                    st.write("Validating citations")

                    try:
                        res = requests.post(
                            "http://localhost:8001/query",
                            json={"query": query}
                        ).json()

                        if res["status"] == "success":

                            st.markdown("### 📄 Research Report")

                            with st.container(border=True):
                                st.write(res["answer"])

                            st.download_button(
                                label="📥 Download Research Report",
                                data=res["answer"],
                                file_name="research_report.txt",
                                mime="text/plain"
                            )

                        else:
                            st.error(res.get("message", "Query failed"))

                    except Exception as e:
                        st.error(f"Error: {e}")


with tab2:

    st.subheader("System Overview")

    st.markdown("""
    ## System Architecture

    CrossDoc is a domain-specific research assistant that
    combines semantic retrieval with local Large Language
    Model inference to generate citation-grounded answers.
    """)
    st.image(
         "architecture.png",
         caption="CrossDoc Architecture",
     )

    st.markdown("""
    ### Research Pipeline

    1. User submits a research query.

    2. Relevant research papers are collected from arXiv.

    3. Papers are converted into sentence-level chunks.

    4. FAISS performs semantic retrieval.

    5. Relevant evidence chunks are selected.

    6. Local Mistral LLM generates the response.

    7. Citation validation ensures grounded output.
    """)

    st.markdown("""
    ### Core Technologies

    - Streamlit UI
    - FastAPI Backend
    - FAISS Vector Store
    - Sentence Transformers
    - Ollama
    - Mistral 7B
    """)

    st.markdown("""
    ### Key Features

    - Domain-Specific Corpus Governance
    - Retrieval-Augmented Generation (RAG)
    - Evidence Grounding
    - Citation Validation
    - Hallucination Reduction
    - Local LLM Inference
    """)
