import os
from exploration import run_exploration

from research import (
    load_corpus,
    chunk_corpus,
    retrieve_chunks,
    has_sufficient_evidence,
    generate_answer,
    update_conversation_summary
)


class ResearchController:

    def __init__(self, corpus_path="approved_corpus.json", min_threshold=3):
        self.corpus_path = corpus_path
        self.min_threshold = min_threshold

        self.mode = "exploration"
        self.corpus_size = 0

        # Conversation memory
        self.conversation_summary = ""

        self._initialize()

    # -----------------------------
    def _initialize(self):
        if os.path.exists(self.corpus_path):
            corpus = load_corpus(self.corpus_path)
            self.corpus_size = len(corpus)

            if self.corpus_size >= self.min_threshold:
                self.mode = "research"
            else:
                self.mode = "exploration"
        else:
            self.mode = "exploration"
            self.corpus_size = 0

    # -----------------------------
    def start_exploration(self, topic):

        result = run_exploration(topic)

        if result["status"] == "completed":
            self.update_corpus_state()

        return {
            "status": result["status"],
            "approved_count": self.corpus_size,
            "mode": self.mode
        }

    # -----------------------------
    def get_state(self):
        return {
            "mode": self.mode,
            "corpus_size": self.corpus_size
        }

    # -----------------------------
    def handle_command(self, command):
        command = command.strip().lower()

        if command == "/explore":

            if os.path.exists(self.corpus_path) and self.corpus_size > 0:
                return {
                    "status": "confirm_overwrite",
                    "message": "Existing corpus detected. Starting new exploration will overwrite it.",
                    "options": [
                        {"code": "CONFIRM_OVERWRITE", "label": "Yes, start new exploration"},
                        {"code": "CANCEL", "label": "No, stay in current mode"}
                    ]
                }

            return {
                "status": "awaiting_topic",
                "message": "Exploration mode activated. Provide research topic."
            }

        return {
            "status": "unknown_command",
            "message": "Unknown command."
        }

    # -----------------------------
    def confirm_overwrite(self):
        if os.path.exists(self.corpus_path):
            os.remove(self.corpus_path)

        self.mode = "exploration"
        self.corpus_size = 0

        return {
            "status": "reset",
            "message": "Corpus cleared. Switched to Exploration Mode."
        }

    # -----------------------------
    def update_corpus_state(self):
        if os.path.exists(self.corpus_path):
            corpus = load_corpus(self.corpus_path)
            self.corpus_size = len(corpus)

            if self.corpus_size >= self.min_threshold:
                self.mode = "research"
            else:
                self.mode = "exploration"

        return self.get_state()

    # -----------------------------
    def process_question(self, question):

        if self.mode == "exploration":
            return {
                "status": "exploration_required",
                "message": "System is in Exploration Mode. Use /explore to build corpus."
            }

        corpus = load_corpus(self.corpus_path)
        chunks = chunk_corpus(corpus)

        query = f"{self.conversation_summary} {question}".strip()
        retrieved = retrieve_chunks(query, chunks)

        if not has_sufficient_evidence(retrieved, self.min_threshold):
            return {
                "status": "insufficient_evidence",
                "message": "Insufficient evidence in approved corpus.",
                "options": [
                    {"code": "REFINE", "label": "Refine question"},
                    {"code": "EXPLORE", "label": "Expand corpus via Exploration Mode"}
                ]
            }

        # Generate answer with conversation context
        answer = generate_answer(
            question,
            retrieved,
            self.conversation_summary
        )

        # Update conversation memory
        self.conversation_summary = update_conversation_summary(
            self.conversation_summary,
            question,
            answer
        )

        return {
            "status": "success",
            "answer": answer
        }


# -----------------------------
# CLI Interface
# -----------------------------

if __name__ == "__main__":

    controller = ResearchController()

    print("=== Stateful Research Assistant ===\n")

    state = controller.get_state()
    print(f"MODE: {state['mode']} | Corpus Size: {state['corpus_size']}")

    while True:

        question = input(">> ")

        result = controller.process_question(question)

        if result["status"] == "success":
            print("\n--- ANSWER ---\n")
            print(result["answer"])

        else:
            print(result["message"])