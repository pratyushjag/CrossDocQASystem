import requests
import feedparser
import json




STOPWORDS = {"and", "or", "the", "of", "in", "on", "for", "with", "a", "an", "to"}

ALLOWED_CATEGORIES = ["cs.CL", "cs.AI", "cs.LG"]



def search_arxiv(query, max_results=20):
    base_url = "http://export.arxiv.org/api/query?"

    category_query = " OR ".join([f"cat:{cat}" for cat in ALLOWED_CATEGORIES])

    params = {
        "search_query": f"(all:{query}) AND ({category_query})",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }

    response = requests.get(base_url, params=params)

    if response.status_code != 200:
        print("Error fetching data from arXiv")
        return []

    feed = feedparser.parse(response.text)

    papers = []

    for entry in feed.entries:
        category = entry.tags[0]["term"] if entry.tags else None

        papers.append({
            "title": entry.title.strip(),
            "summary": entry.summary.strip(),
            "category": category
        })

    return papers


def extract_keywords(query):
    tokens = query.lower().split()
    return [t for t in tokens if t not in STOPWORDS]



def specificity_filter(papers, keywords, min_matches=2):

    filtered = []

    for paper in papers:
        text = (paper["title"] + " " + paper["summary"]).lower()

        match_count = sum(1 for kw in keywords if kw in text)

        if match_count >= min_matches:
            filtered.append((match_count, paper))

    filtered.sort(key=lambda x: x[0], reverse=True)

    return [paper for score, paper in filtered]



def display_papers(papers):
    print("\nRecommended Papers:\n")

    for i, paper in enumerate(papers, 1):
        print(f"{i}. {paper['title']} ({paper.get('category', 'N/A')})")
        print("-" * 80)



def run_exploration(topic):

    results = search_arxiv(topic, max_results=20)

    if not results:
        return {"status": "failed", "approved_count": 0}

    keywords = extract_keywords(topic)
    filtered = specificity_filter(results, keywords, min_matches=2)

    if not filtered:
        return {"status": "failed", "approved_count": 0}

    recommended = filtered[:5]

    # 🔥 AUTO APPROVE (NO INPUT)
    approved_papers = recommended

    with open("approved_corpus.json", "w", encoding="utf-8") as f:
        json.dump(approved_papers, f, indent=2, ensure_ascii=False)

    return {
        "status": "completed",
        "approved_count": len(approved_papers)
    }