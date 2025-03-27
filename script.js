// Monaco Editor Configuration
require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.34.0/min/vs' } });
require(['vs/editor/editor.main'], function () {
    window.editor = monaco.editor.create(document.getElementById('editor'), {
        value: "// Select a problem to load the code template",
        language: "java", // Updated language to Java
        theme: "vs-dark",
        automaticLayout: true,
        tabSize: 4
    });
});

// Function to load the code template for the selected problem
function loadProblemTemplate() {
    const select = document.getElementById("problem-select");
    const selectedOption = select.options[select.selectedIndex];
    const template = selectedOption.getAttribute("data-template");
    window.editor.setValue(template);
}

// Function to run code and check against test cases
function runCode() {
    const code = window.editor.getValue();
    const problemId = parseInt(document.getElementById("problem-select").value);

    fetch('/run_code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, problem_id: problemId })
    })
        .then(response => response.json())
        .then(data => {
            const resultMessageElement = document.getElementById("result-message");

            // Check if result is an array before calling forEach
            if (Array.isArray(data.result)) {
                let output = "";
                data.result.forEach(test => {
                    output += `Test case (args: ${JSON.stringify(test.args)})\n`;
                    output += `Expected Output: ${test.expected_output}\n`;
                    output += `Your Output: ${test.user_output}\n`;
                    output += `Result: ${test.is_correct ? "Correct" : "Incorrect"}\n\n`;
                });
                document.getElementById("output").textContent = output;
                resultMessageElement.textContent = data.message;
            } else {
                // Handle case where result is not an array (error case)
                document.getElementById("output").textContent = data.message;
                resultMessageElement.textContent = data.message;
            }

            // Apply success or error styling based on correctness
            if (data.correct) {
                resultMessageElement.classList.add("success-message");
                resultMessageElement.classList.remove("error-message");
            } else {
                resultMessageElement.classList.add("error-message");
                resultMessageElement.classList.remove("success-message");
            }
        })
        .catch(error => {
            document.getElementById("output").textContent = `Error: ${error.message}`;
        });
}

// Function to send a message to ChatGPT
function sendMessage() {
    const message = document.getElementById("chat-input").value;
    const editorContent = window.editor.getValue(); // Get editor content
    const problemId = document.getElementById("problem-select").value;

    if (message.trim() === "") return;

    const chatLog = document.getElementById("chat-log");
    chatLog.innerHTML += `<div class="message user"><strong>User:</strong> ${message}</div>`;
    document.getElementById("chat-input").value = "";

    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message,
            context: editorContent,
            question_id: problemId
        })
    })
        .then(response => response.json())
        .then(data => {
            const formattedResponse = formatCodeBlocks(data.response); // Format code blocks
            chatLog.innerHTML += `<div class="message assistant"><strong>Assistant:</strong> ${formattedResponse}</div>`;
            chatLog.scrollTop = chatLog.scrollHeight;
        })
        .catch(error => {
            chatLog.innerHTML += `<div class="message assistant"><strong>Error:</strong> ${error.message}</div>`;
            chatLog.scrollTop = chatLog.scrollHeight;
        });
}

// Function to format code blocks in ChatGPT's response
function formatCodeBlocks(text) {
    // Replace triple backticks with <pre><code> for multiline code blocks
    text = text.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

    // Replace single backticks with <code> for inline code, only if content is non-empty and non-whitespace
    text = text.replace(/`([^`\n]+)`/g, '<code>$1</code>');

    return text;
}

// Handle copy events from the ChatGPT response area
function handleCopy(event) {
    const selectedText = window.getSelection().toString(); // Get the copied text
    if (selectedText.trim()) {
        console.log("Copied text:", selectedText);
        recordClipboardEvent("copy", selectedText);
    }
}

// Handle paste events in the editor
document.getElementById("editor").addEventListener("paste", (event) => {
    const pastedText = (event.clipboardData || window.clipboardData).getData("text");
    console.log("Pasted text:", pastedText);
    recordClipboardEvent("paste", pastedText);
});

// Record clipboard events for copy and paste
function recordClipboardEvent(action, content) {
    const problemId = document.getElementById("problem-select").value;

    fetch('/record_clipboard_event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action, // "copy" or "paste"
            content,
            question_id: problemId, // Send the question ID
            timestamp: new Date().toISOString() // Add a timestamp
        })
    })
        .then(response => response.json())
        .then(data => console.log("Clipboard event recorded:", data))
        .catch(error => console.error("Error recording clipboard event:", error));
}





