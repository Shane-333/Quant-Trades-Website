document.addEventListener('DOMContentLoaded', function () {
    const chatbotHeader = document.getElementById('chatbot-header');
    const chatbotBody = document.getElementById('chatbot-body');
    const chatbotToggle = document.getElementById('chatbot-toggle');
    const chatbotSend = document.getElementById('chatbot-send');
    const chatbotMessages = document.getElementById('chatbot-messages');
    const chatbotInput = document.getElementById('chatbot-input');

    chatbotHeader.addEventListener('click', function () {
        if (chatbotBody.style.display === 'none' || chatbotBody.style.display === '') {
            chatbotBody.style.display = 'flex';
            chatbotToggle.textContent = '-';
        } else {
            chatbotBody.style.display = 'none';
            chatbotToggle.textContent = '+';
        }
    });

    chatbotSend.addEventListener('click', function () {
        const userMessage = chatbotInput.value;
        if (userMessage.trim() !== '') {
            appendMessage('User', userMessage);
            chatbotInput.value = '';
            getChatbotResponse(userMessage);
        }
    });

    function appendMessage(sender, message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chatbot-message');
        messageElement.innerHTML = `<strong>${sender}:</strong> ${message}`;
        chatbotMessages.appendChild(messageElement);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    async function getChatbotResponse(userMessage) {
        appendMessage('Chatbot', 'Thinking...');

        try {
            const response = await fetch('http://localhost:8000/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: userMessage })
            });

            if (response.ok) {
                const data = await response.json();
                appendMessage('Chatbot', data.message || 'Sorry, I could not understand your question.');
            } else {
                appendMessage('Chatbot', 'Error: Failed to get response from the server.');
            }
        } catch (error) {
            appendMessage('Chatbot', 'Error: Failed to fetch response. Please check your network connection.');
        }
    }
});
