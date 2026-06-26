from controller import ResearchController

# Single shared controller instance
controller = ResearchController()


def handle_query(query: str):
    response = controller.process_question(query)

    if response["status"] == "success":
        return {
            "status": "success",
            "answer": response["answer"]
        }

    elif response["status"] == "insufficient_evidence":
        return {
            "status": "insufficient_evidence",
            "message": response["message"],
        }

    else:
        return {
            "status": "error",
            "message": response.get("message", "Unknown error")
        }


def handle_explore(topic: str):
    result = controller.start_exploration(topic)

    return {
        "status": result["status"],
        "approved_count": result.get("approved_count", 0),
        "mode": result.get("mode", "exploration")
    }