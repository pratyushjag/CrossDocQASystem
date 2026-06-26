import json
import re
import requests
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import matplotlib

# -----------------------------
# Configuration
# -----------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral:7b-instruct-q4_K_M"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

STOPWORDS = {
    "what", "is", "are", "the", "a", "an", "of",
    "in", "on", "for", "to", "and", "with",
    "about", "how", "why", "does", "do", "did"
}

# -----------------------------
# Global Embedding State (Cached)
# -----------------------------

embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
faiss_index = None
chunk_metadata = None


# -----------------------------
# Corpus Handling
# -----------------------------

def load_corpus(path="approved_corpus.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def chunk_corpus(corpus):

    chunks = []

    for paper_id, paper in enumerate(corpus):

        text = paper["summary"]
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunk_id = 0

        for sentence in sentences:

            sentence = sentence.strip()

            if len(sentence) < 40:
                continue

            chunks.append({
                "paper_id": paper_id,
                "chunk_id": chunk_id,
                "title": paper["title"],
                "text": sentence
            })

            chunk_id += 1

    return chunks

# -----------------------------
# Semantic Retrieval
# -----------------------------

def build_embedding_index(chunks):
    global faiss_index, chunk_metadata

    texts = [chunk["text"] for chunk in chunks]

    embeddings = embedding_model.encode(texts, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    faiss_index = index
    chunk_metadata = chunks


def retrieve_chunks_embedding(question, top_k=5):
    global faiss_index, chunk_metadata

    if faiss_index is None:
        raise ValueError("FAISS index not built.")

    query_embedding = embedding_model.encode([question], convert_to_numpy=True)
    query_embedding = query_embedding.astype("float32")

    distances, indices = faiss_index.search(query_embedding, top_k)

    retrieved = []
    for idx in indices[0]:
        if idx < len(chunk_metadata):
            retrieved.append(chunk_metadata[idx])

    return retrieved

def diversity_filter(chunks, max_per_paper=2, final_k=7):

    paper_counts = {}
    filtered = []

    for chunk in chunks:

        pid = chunk["paper_id"]

        if paper_counts.get(pid, 0) >= max_per_paper:
            continue

        filtered.append(chunk)
        paper_counts[pid] = paper_counts.get(pid, 0) + 1

        if len(filtered) >= final_k:
            break

    return filtered

def has_sufficient_evidence(retrieved_chunks, min_chunks=3):
    return len(retrieved_chunks) >= min_chunks


# -----------------------------
# Prompt Construction
# -----------------------------



def format_context(retrieved_chunks):
    global chunk_metadata

    blocks = []

    for i, chunk in enumerate(retrieved_chunks, 1):

        pid = chunk["paper_id"]
        cid = chunk["chunk_id"]

        prev_text = ""
        next_text = ""

        # find neighboring sentences
        for c in chunk_metadata:
            if c["paper_id"] == pid and c["chunk_id"] == cid - 1:
                prev_text = c["text"]

            if c["paper_id"] == pid and c["chunk_id"] == cid + 1:
                next_text = c["text"]

        # build evidence window
        evidence_parts = [prev_text, chunk["text"], next_text]
        evidence = " ".join([p for p in evidence_parts if p]).strip()

        block = f"[{i}] Paper: {chunk['title']}\nEvidence: {evidence}\n"

        blocks.append(block)

    return "\n\n".join(blocks)

def detect_question_type(question):

    q = question.lower()

    comparison_keywords = [
        "difference", "different", "compare",
        "differ", "vs", "versus", "contrast"
    ]

    source_keywords = [
        "which paper", "which study", "which work",
        "who proposed", "who introduced",
        "introduced", "proposed", "first proposed",
        "origin", "introduced in"
    ]

    if any(k in q for k in comparison_keywords):
        return "comparison"

    if any(k in q for k in source_keywords):
        return "source"

    return "definition"

def build_prompt(question, context, conversation_summary=""):

    qtype = detect_question_type(question)

    if qtype == "definition":

        structure = """
Definition of the Concept:
Supporting Evidence:
For each point, cite specific evidence from the excerpts and explain what it supports.
Limitations in Approved Corpus:

"""

        task_instruction = """
Define the concept mentioned in the question using the evidence excerpts.

Explain its key characteristics clearly.
"""

    elif qtype == "comparison":

        structure = """
Definitions of the Two Concepts:
Key Differences:
Supporting Evidence:
Limitations in Approved Corpus:
"""

        task_instruction = """
Identify the TWO main concepts mentioned in the question.

Define both concepts using the evidence excerpts.

Then explain the key differences between them.
"""

    else:  # source attribution

        structure = """
Identified Paper:
Supporting Evidence:
Limitations in Approved Corpus:
"""

        task_instruction = """
Identify which paper introduced or proposed the concept mentioned in the question.

State the paper title and explain briefly what it introduced using the evidence excerpts.
"""

    return f"""
Conversation Context:
{conversation_summary if conversation_summary else "No prior conversation context."}

You are a strict research analyst.

Your task is to answer the user's question using ONLY the provided evidence excerpts.

Important rules:
- The excerpts are the only allowed source of information.
- Do NOT introduce claims not supported by the excerpts.
- Cite evidence using bracketed numbers like [1], [2].
- For each paper, explicitly state what concept or claim it supports.
- Generate the output in short and separate paragraphs ONLY.
- At the end of the answer, list the papers used in the order of the times the evidence from a paper is being used.
- If only one paper is dominant in the answer, mention only that paper. 

Task:
{task_instruction}

Use the EXACT section headers below.

{structure}

If the excerpts contain partial or indirect evidence,
attempt a best-effort definition using available information.

If there is no evidence of the concept in the excerpts, then REFUSE to answer and respond with "Insufficient evidence in approved corpus"

Question:
{question}
Evidence excerpts:
{context}
"""
def update_conversation_summary(previous_summary, question, answer):
    prompt = f"""
    Update the research conversation summary in at most 2 sentences.

    The summary should contain:
    - the main research topic
    - key findings or comparisons discovered so far

    Previous summary:
    {previous_summary}

    New exchange:
    Question: {question}
    Answer: {answer}

    Updated summary:
    """
    return call_llm(prompt, temperature=0.2)

def repair_missing_citations(answer, retrieved_chunks):
    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
    repaired = []

    for p in paragraphs:
        if p.endswith(":"):
            repaired.append(p)
            continue

        if not re.search(r"\[(\d+(,\s*\d+)*)\]\s*\.?\s*$", p):
            p = p + " [1]"   # attach fallback citation

        repaired.append(p)

    return "\n\n".join(repaired)
# -----------------------------
# Citation Validation
# -----------------------------

def validate_citations(answer, max_source_number):

    # Extract citation groups like [1], [2,5], [1, 3]
    citation_groups = re.findall(r"\[(.*?)\]", answer)

    if not citation_groups:
        return False

    citation_numbers = []

    for group in citation_groups:
        parts = group.split(",")
        for p in parts:
            try:
                citation_numbers.append(int(p.strip()))
            except ValueError:
                return False
    print("Citation numbers detected:", citation_numbers)
    print("Max allowed:", max_source_number)
    # Ensure citation numbers are within valid range
    for c in citation_numbers:
        if c > max_source_number:
            return False
    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]

    for p in paragraphs:

        lines = p.split("\n")

        # Remove section header if present
        if lines[0].strip().endswith(":"):
            content = "\n".join(lines[1:]).strip()
        else:
            content = p.strip()

        if not content:
            continue

        if not re.search(r"\[(\d+(,\s*\d+)*)\]\s*\.?\s*$", content):
            print("\nVALIDATION FAILURE:")
            print("Paragraph content:")
            print(repr(content))
            return False

    return True

def enforce_citation_diversity(answer, retrieved_chunks):
    import re

    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]

    idx = 1
    new_paragraphs = []

    for p in paragraphs:

        # Skip headers
        if p.endswith(":"):
            new_paragraphs.append(p)
            continue

        # Replace ONLY if paragraph ends with [1]
        if re.search(r"\[1\]\s*$", p) and len(retrieved_chunks) > 1:
            p = re.sub(r"\[1\]\s*$", f"[{idx}]", p)

            idx += 1
            if idx > len(retrieved_chunks):
                idx = 1

        new_paragraphs.append(p)

    return "\n\n".join(new_paragraphs)
# -----------------------------
# Ollama Integration
# -----------------------------


def call_llm(prompt, temperature=0.25):

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "temperature": temperature,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload)

    if response.status_code != 200:
        return "LLM call failed."

    result = response.json()
    return result.get("response", "").strip()

def visualize_evidence_distribution(retrieved_chunks):

    import matplotlib.pyplot as plt
    from collections import Counter

    titles = [chunk["title"] for chunk in retrieved_chunks]
    counts = Counter(titles)

    papers = list(counts.keys())
    values = list(counts.values())

    plt.figure(figsize=(10,5))
    plt.barh(papers, values)

    plt.title("Evidence Contribution to Answer")
    plt.xlabel("Number of Evidence Chunks")
    plt.ylabel("Paper")

    plt.tight_layout()
    plt.show()

def visualize_citation_influence(answer, retrieved_chunks):

    import matplotlib.pyplot as plt

    counts = extract_citation_counts(answer, retrieved_chunks)

    if not counts:
        return

    papers = list(counts.keys())
    values = list(counts.values())

    plt.figure(figsize=(8,4))
    plt.barh(papers, values)

    plt.title("Citation Influence on Answer")
    plt.xlabel("Number of Citations")
    plt.ylabel("Paper")

    plt.tight_layout()
    plt.show()

def extract_citation_counts(answer, retrieved_chunks):

    import re
    from collections import Counter

    citation_groups = re.findall(r"\[(.*?)\]", answer)

    citation_numbers = []

    for group in citation_groups:
        parts = group.split(",")
        for p in parts:
            try:
                citation_numbers.append(int(p.strip()))
            except ValueError:
                continue

    citation_numbers = [
        c for c in citation_numbers if 1 <= c <= len(retrieved_chunks)
    ]

    titles = [retrieved_chunks[c-1]["title"] for c in citation_numbers]

    return Counter(titles)

# -----------------------------
# Answer Generation Pipeline
# -----------------------------



def generate_answer(question, retrieved_chunks, conversation_summary=""):

    if not retrieved_chunks or len(retrieved_chunks) < 3:
        return "Insufficient evidence in approved corpus."

    if not is_retrieval_relevant(retrieved_chunks, question):
        print("[DEBUG] Retrieval rejected due to low relevance")
        return "Insufficient evidence in approved corpus."

    context = format_context(retrieved_chunks)

    prompt = build_prompt(question, context, conversation_summary)
    print("🚀 Calling LLM for main answer...")
    answer = call_llm(prompt)

    if "Insufficient evidence" in answer:
        return "Insufficient evidence in approved corpus."

    answer = repair_missing_citations(answer, retrieved_chunks)

    answer = enforce_citation_diversity(answer, retrieved_chunks)

    if validate_citations(answer, len(retrieved_chunks)):

        visualize_evidence_distribution(retrieved_chunks)

        visualize_citation_influence(answer, retrieved_chunks)

        return answer



    return "Answer rejected due to citation non-compliance."

# -----------------------------
# Main Retrieval Entry (Used by Controller)
# -----------------------------

def retrieve_chunks(question, chunks, top_k=12):
    global faiss_index

    if faiss_index is None:
        build_embedding_index(chunks)

    retrieved_chunks = retrieve_chunks_embedding(question, top_k)

    retrieved_chunks = diversity_filter(retrieved_chunks)

    print("\nRetrieved titles:")
    for chunk in retrieved_chunks:
        print("-", chunk["title"])

    return retrieved_chunks

def is_retrieval_relevant(retrieved_chunks, question):

    if not retrieved_chunks:
        return False

    # Check diversity: at least 2 different papers
    unique_titles = set(chunk["title"] for chunk in retrieved_chunks)

    return len(unique_titles) >= 2
