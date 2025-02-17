import os
import time
import json

from flask import Flask, jsonify, request
from openai import OpenAI

from tools.functions.add_lead_to_spreadsheet import add_lead_to_spreadsheet

app = Flask(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


def call_function(name, arguments):
    """Calls a function by name with given arguments."""
    if name == "add_lead_to_spreadsheet":
        return add_lead_to_spreadsheet(arguments["email"], arguments["phone"])
    else:
        return {"error": f"Function '{name}' not found."}


@app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({"message": "Hello, world!"}), 200


@app.route('/chat', methods=['POST'])
def chat():
    print('Entering chat.!.!.')

    print(request)

    print('HERE!!!')
    print(request.json)

    data = request.json

    print()
    print(f"Received data: {data}")
    print()

    if (not data) or ('assistant_id' not in data) or ('prompt' not in data):
        error_message = "Missing required parameters: assistant_id, prompt, & thread_id"
        print(f"Error: {error_message}")
        return jsonify({"error": error_message}), 400

    assistant_id = data['assistant_id']
    prompt = data['prompt']
    thread_id = data['thread_id']

    try:
        # Create a new thread
        if (thread_id == 'N/A'):
            thread = client.beta.threads.create()
            thread_id = thread.id
        else:
            pass

        while True:
            user_message = client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=prompt)

            run = client.beta.threads.runs.create(  # Run the assistant to get a response
                thread_id=thread_id,
                assistant_id=assistant_id)

            i = 0  # Polling for the run status
            while run.status not in ["completed", "failed", "requires_action"]:
                if i > 0:
                    time.sleep(5)
                run = client.beta.threads.runs.retrieve(thread_id=thread_id,
                                                        run_id=run.id)
                i += 1
                print(run.status)

            if run.status == "requires_action":  # Handle required actions
                tools_to_call = run.required_action.submit_tool_outputs.tool_calls
                print(len(tools_to_call))
                print(tools_to_call)

                tool_output_array = []

                for each_tool in tools_to_call:
                    tool_call_id = each_tool.id  # Correct attribute for tool_call_id
                    function_name = each_tool.function.name
                    function_args = json.loads(
                        each_tool.function.arguments)  # Parse the JSON string

                    print(f"Tool ID: {tool_call_id}")
                    print(f"Function to call: {function_name}")
                    print(f"Parameters to use: {function_args}")

                    # Handle the function calls
                    if function_name == "add_lead_to_spreadsheet":
                        output = add_lead_to_spreadsheet(
                            function_args["email"],
                            function_args["phone_number"])
                    else:
                        output = "Invalid function name"

                    tool_output_array.append({
                        "tool_call_id": tool_call_id,
                        "output": output
                    })

                print(tool_output_array)

                # Submit the tool outputs
                run = client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_output_array)

                i = 0  # Check the run operation status again
                while run.status not in [
                        "completed", "failed", "requires_action"
                ]:
                    if i > 0:
                        time.sleep(10)
                    run = client.beta.threads.runs.retrieve(
                        thread_id=thread_id, run_id=run.id)
                    i += 1
                    print(run.status)

            response_message = None  # Retrieve the assistant's response message
            messages = client.beta.threads.messages.list(
                thread_id=thread_id).data
            for message in messages:
                if message.role == "assistant":
                    response_message = message
                    break

            if response_message:
                print(f"Assistant response: {response_message.content}\n")

                if isinstance(response_message.content, list):
                    response_text = response_message.content[0].text.value
                else:
                    response_text = response_message.content.text.value

                print("<-*-*-*-> response_text <-*-*-*->", response_text)

                return jsonify({
                    "response": response_text,
                    "thread_id": thread_id,
                }), 200
            else:
                print("No assistant response found.\n")
                return jsonify({"error": "No assistant response found"}), 500

    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(f"Error: {error_message}")
        return jsonify({"response": "Oops! An error occurred."}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
