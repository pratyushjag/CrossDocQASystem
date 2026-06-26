from controller import ResearchController

controller = ResearchController()

print("\n=== Stateful Research Assistant ===\n")

awaiting_topic = False

while True:

    state = controller.get_state()
    print(f"\nMODE: {state['mode']} | Corpus Size: {state['corpus_size']}")

    user_input = input(">> ")

    # If we're waiting for topic input
    if awaiting_topic:
        result = controller.start_exploration(user_input)
        print(f"Exploration completed. Approved papers: {result['approved_count']}")
        awaiting_topic = False
        continue

    # Handle commands
    if user_input.startswith("/"):
        response = controller.handle_command(user_input)

        if response["status"] == "awaiting_topic":
            print(response["message"])
            awaiting_topic = True

        elif response["status"] == "confirm_overwrite":
            print(response["message"])
            print("Type CONFIRM to proceed or CANCEL to abort.")
            decision = input(">> ").strip().upper()

            if decision == "CONFIRM":
                controller.confirm_overwrite()
                print("Enter research topic:")
                awaiting_topic = True
            else:
                print("Cancelled. Staying in current mode.")

        else:
            print(response["message"])

    # Handle research question
    else:
        response = controller.process_question(user_input)

        if response["status"] == "success":
            print("\n--- ANSWER ---\n")
            print(response["answer"])

        elif response["status"] == "insufficient_evidence":
            print(response["message"])
            print("Options:")
            for opt in response["options"]:
                print(f"- {opt['label']}")

        else:
            print(response["message"])
